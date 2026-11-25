"""4.4 on paper: score, virtual trades and their endpoints (SQLite in memory, fake IQ service, a small score table)."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.upstream import Upstream, get_upstream
from api.routers import market as market_router
from core.config import get_settings
from db import models
from db.session import Base, get_session
from main import app
from services import market
from signals.data.candles import TIMEFRAMES, Candle
from signals.live import plan as planning
from signals.live import run
from signals.live.scan import Event
from signals.live.score import FRAME_WEIGHT, score, tables

T0 = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
EVIDENCE = {"proven": False, "last30": {"n": 5}, "shuffled": {"n": 9}}
TABLE = {"weights": {"Elliott": 60.0, "SFP": 40.0}, "quality": {"Elliott|12345 sonu|diyagonal": 0.5, "Elliott|12345 sonu": 0.2, "SFP": 0.3, "SFP|RSI uyumsuz": 1.0},
         "limits": {"SCALP": 40, "SWING": 70}, "evidence": {"SCALP": EVIDENCE, "SWING": EVIDENCE}, "base": {}}
ME = {"X-User-Id": "u1"}


# ---------- score

def test_frames_weigh_more_the_higher_they_are():
    w = [FRAME_WEIGHT[f] for f in TIMEFRAMES]
    assert w == sorted(w) and w[-1] == 1.0 and w[0] == 0.45


def test_a_category_counts_once_with_its_best_rule_and_frame():
    s = score({"15m": ["Elliott|12345 sonu|diyagonal", "SFP|RSI uyumsuz|"], "1M": ["Elliott|12345 sonu|uzamasız", "SFP|uyumsuzluk yok|"]}, TABLE)
    assert s.categories["Elliott"]["points"] == pytest.approx(60 * 0.45 * 0.5)          # better than 60 x 1.0 x 0.2 on 1M
    assert s.categories["SFP"] == {"points": 18.0, "frame": "15m", "rule": "SFP|RSI uyumsuz|"}
    assert s.total == pytest.approx(13.5 + 18)
    assert score({"1M": ["Harmonik|Bat|"]}, TABLE).total == 0          # nothing proven, nothing earned


def test_the_score_never_exceeds_100():
    tags = {f: ["Elliott|12345 sonu|diyagonal", "SFP|RSI uyumsuz|"] for f in TIMEFRAMES}
    assert score(tags, {**TABLE, "quality": {k: 1.0 for k in TABLE["quality"]}}).total <= 100


def test_the_stored_tables_follow_the_agreed_shape():
    for asset, t in tables().items():
        assert sum(t["weights"].values()) == pytest.approx(100, abs=0.5) and all(v >= 0 for v in t["weights"].values())
        assert t["weights"]["Elliott"] == max(t["weights"].values())
        assert all(0 <= q <= 1 for q in t["quality"].values())
        assert list(t["limits"].values()) == sorted(t["limits"].values())
        assert set(t["evidence"]) == set(t["limits"])


def event(side=-1, **tags):
    return Event(T0.timestamp(), side, "15m", ("Uyumsuzluk|RSI|tepede anlık",), 100.0, 101.0 if side == -1 else 99.0, 2.0, tags)


def test_a_plan_only_when_a_limit_is_reached():
    shown, plan = run.judge("BTCUSDT", event(**{"15m": ["SFP|RSI uyumsuz|"]}), TABLE)
    assert shown["kind"] is None and plan is None and shown["score"] == 18
    shown, plan = run.judge("BTCUSDT", event(**{"1M": ["SFP|RSI uyumsuz|"]}), TABLE)
    assert (plan.kind, plan.direction, plan.stop, plan.first_target) == ("SCALP", "SHORT", 101.5, 97.75)          # 101 + 0.25 x ATR
    assert plan.evidence["proven"] is False
    _, long = run.judge("BTCUSDT", event(1, **{"1M": ["SFP|RSI uyumsuz|"]}), TABLE)
    assert (long.direction, long.stop) == ("LONG", 98.5)


# ---------- virtual trades

@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


def plan(side=-1, kind="SCALP", entry=100.0, stop=102.0, asset="BTCUSDT"):
    return planning.make(asset, side, kind, T0.timestamp(), 50, entry, stop, "15m", {}, EVIDENCE)


def candle(i, high, low, close=None):
    return Candle(T0 + timedelta(minutes=15 * i), low, high, low, close if close is not None else low, 1.0, 0.5)


def test_one_open_trade_per_asset_and_direction(db):
    assert market.open_trade(db, plan()) is not None
    db.flush()
    assert market.open_trade(db, plan(kind="SWING")) is None
    assert market.open_trade(db, plan(1, stop=98.0)) is not None
    assert market.open_trade(db, plan(asset="XAU")) is not None


@pytest.mark.parametrize(("bars", "reason", "result"), [
    ([candle(0, 101, 99), candle(1, 101, 96.5)], "TARGET", 1.45),
    ([candle(0, 102.0, 99)], "STOP", -1.05),
    ([candle(0, 103, 90)], "STOP", -1.05),                                       # both in one candle: the stop counts
    ([candle(-1, 103, 90), candle(0, 101, 99)], None, None),                     # a candle before the trade opened is not looked at
])
def test_how_a_short_ends(db, bars, reason, result):
    t = market.open_trade(db, plan())
    db.flush()
    closed = market.follow(db, "BTCUSDT", bars)
    assert (closed == [t]) == (reason is not None)
    assert (t.exit_reason, t.result_r) == (reason, result)


def test_a_long_is_the_mirror_and_time_ends_a_trade(db):
    t = market.open_trade(db, plan(1, stop=98.0))
    db.flush()
    bars = [candle(i, 101, 99, 100.5) for i in range(planning.HORIZON + 3)]
    market.follow(db, "BTCUSDT", bars)
    assert t.exit_reason == "EXPIRED" and t.result_r == pytest.approx(0.25 - 0.05)
    assert market.utc(t.closed_at) == T0 + timedelta(minutes=15 * planning.HORIZON)
    assert market.open_trades(db, "BTCUSDT") == []


def test_performance_counts_only_closed_trades(db):
    for i, r in enumerate((1.45, -1.05, -1.05, None)):
        t = market.open_trade(db, plan(asset=f"A{i}"))
        t.result_r, t.closed_at = r, T0 + timedelta(hours=i) if r else None
    db.flush()
    from sqlalchemy import select
    p = market.performance(list(db.scalars(select(models.VirtualTrade))))
    assert (p["n"], p["winRate"], p["longestLosingStreak"], p["maxDrawdownR"]) == (3, 0.333, 2, 2.1)
    assert market.performance([])["averageR"] is None


# ---------- endpoints

@pytest.fixture
def web(client, db, monkeypatch):
    monkeypatch.setattr(market_router, "tables", lambda: {"BTCUSDT": TABLE})
    app.dependency_overrides[get_session] = lambda: db
    body = {"success": True, "message": "", "data": {"score": 50, "segment": "MEDIUM", "resultVersion": 1, "createdAt": "x", "updatedAt": "x", "factorBreakdown": {"version": "v2", "appliedRule": None}}}
    app.dependency_overrides[get_upstream] = lambda: Upstream(get_settings(), httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    return client


def test_view_without_and_with_a_trade(web, db):
    item = web.get("/api/portfolio/market/view", headers=ME).json()["data"]["items"][0]
    assert (item["asset"], item["status"], item["openTrades"], item["scan"]) == ("BTC", "NO_VIEW", [], None)
    market.save_scan(db, "BTCUSDT", T0, {"triggers": []})
    market.open_trade(db, plan())
    db.flush()
    d = web.get("/api/portfolio/market/view", headers=ME).json()["data"]
    assert d["items"][0]["status"] == "CONFIRMED" and d["items"][0]["openTrades"][0]["evidence"]["proven"] is False
    assert "Sanal işlem" in d["disclaimer"]


def test_the_size_depends_on_the_users_score(web, db):
    market.open_trade(db, plan())
    db.flush()
    d = web.get("/api/portfolio/u1/market-plan", headers=ME).json()["data"]
    assert d["iqScore"] == 50
    assert d["items"][0]["size"] == {"marginPercent": 5.5, "leverage": 9, "riskPercent": 0.99}          # 5.5 % x 9 x 2 % stop
    assert web.get("/api/portfolio/u1/market-plan", headers={"X-User-Id": "u2"}).status_code == 403


def test_trades_and_performance_need_the_gateway(web, db):
    market.open_trade(db, plan())
    db.flush()
    assert len(web.get("/api/portfolio/market/trades?asset=BTC", headers=ME).json()["data"]["items"]) == 1
    assert web.get("/api/portfolio/market/trades?asset=GOLD", headers=ME).json()["data"]["items"] == []
    assert web.get("/api/portfolio/market/performance", headers=ME).json()["data"]["n"] == 0
    assert web.get("/api/portfolio/market/view").status_code == 401
