"""4.4 on paper: score, virtual trades and their endpoints (SQLite in memory, fake IQ service, a small score table)."""

from dataclasses import replace
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
from signals.live.fibs import Fib
from signals.live.scan import Event
from signals.live.score import LTF_FRAMES, kind_of, score, side_of, tables
from signals.scoring.confirm_report import quality

T0 = datetime(2026, 11, 25, 9, 0, tzinfo=timezone.utc)
EVIDENCE = {"proven": False, "last30": {"n": 5}, "shuffled": {"n": 9}}
# points per timeframe and rule (Aykut, 26 Nov: each rule its own success; HTF 70, LTF 30)
TABLE = {"points": {"15m": {"Elliott|12345 sonu|diyagonal": 5.0, "SFP|RSI uyumsuz": 8.0}, "30m": {"SFP|RSI uyumsuz": 6.0}, "1h": {"SFP|RSI uyumsuz": 10.0},
                    "4h": {"SFP|RSI uyumsuz": 20.0, "Elliott|12345 sonu|diyagonal": 30.0}, "1M": {"Elliott|12345 sonu|diyagonal": 50.0, "SFP|RSI uyumsuz": 20.0}},
         "weights": {"Elliott": 55.0, "SFP": 30.0}, "limits": {"SCALP": 40, "SWING": 70}, "evidence": {"SCALP": EVIDENCE, "SWING": EVIDENCE}, "base": {}}
ME = {"X-User-Id": "u1"}


# ---------- score

def test_quality_is_the_rules_own_success_shrunk_by_its_sample():
    assert quality(5, 5) == pytest.approx(0.8)          # 5 of 5: at least 80 (Aykut)
    assert quality(4, 5) == pytest.approx(0.64)         # 80 % on 5 cases: 0.8 x 80
    assert quality(75, 75) > quality(75, 100)           # 100 % on 75 beats 75 % on 100
    assert quality(4, 4) == 0 and quality(4, 10) == 0   # fewer than 5 cases, or below 51 %


def test_ltf_is_15m_to_2h_and_htf_4h_and_up():
    assert LTF_FRAMES == ("15m", "30m", "45m", "1h", "2h")
    assert [side_of(f) for f in TIMEFRAMES].count("HTF") == len(TIMEFRAMES) - 5


def test_only_the_rules_own_points_count():
    assert score({"1M": ["Elliott|12345 sonu|uzamasız", "SFP|uyumsuzluk yok|"]}, TABLE).total == 0          # siblings lend nothing
    assert score({"1M": ["Harmonik|Bat|"]}, TABLE).total == 0          # nothing proven, nothing earned


def test_a_category_counts_its_best_ltf_and_its_best_htf():
    s = score({"15m": ["SFP|RSI uyumsuz|"], "4h": ["SFP|RSI uyumsuz|"]}, TABLE)
    assert s.categories["SFP"]["points"] == pytest.approx(8 + 20) and s.categories["SFP"]["frame"] == "4h" and s.categories["SFP"]["also"] == ["15m"]


def test_the_same_side_on_more_frames_adds_at_most_ten_percent():
    one = score({"1h": ["SFP|RSI uyumsuz|"]}, TABLE)
    three = score({"15m": ["SFP|RSI uyumsuz|"], "30m": ["SFP|RSI uyumsuz|"], "1h": ["SFP|RSI uyumsuz|"]}, TABLE)
    assert three.total == pytest.approx(one.total * 1.10)
    two = score({"30m": ["SFP|RSI uyumsuz|"], "1h": ["SFP|RSI uyumsuz|"], "45m": ["SFP|uyumsuzluk yok|"]}, TABLE)          # 45m earned nothing
    assert two.total == pytest.approx(one.total * 1.05)


def test_one_category_alone_is_never_a_trade():
    alone = score({"1M": ["Elliott|12345 sonu|diyagonal"]}, TABLE)
    assert alone.total == 50 and kind_of(alone, TABLE) is None
    both = score({"1M": ["Elliott|12345 sonu|diyagonal", "SFP|RSI uyumsuz|"]}, TABLE)
    assert both.total == 70 and kind_of(both, TABLE) == "SWING"


def test_the_score_never_exceeds_100():
    big = {**TABLE, "points": {f: {"Elliott|12345 sonu|diyagonal": 60.0, "SFP|RSI uyumsuz": 60.0} for f in TIMEFRAMES}}
    assert score({f: ["Elliott|12345 sonu|diyagonal", "SFP|RSI uyumsuz|"] for f in TIMEFRAMES}, big).total == 100


def test_the_stored_tables_follow_the_agreed_shape():
    for asset, t in tables().items():
        assert set(t["points"]) <= set(TIMEFRAMES) and all(v > 0 for d in t["points"].values() for v in d.values())
        assert sum(t["weights"].values()) <= 100.5          # every category at its best on both sides makes 100
        for side, share in (("HTF", 70), ("LTF", 30)):
            best: dict[str, float] = {}
            for f, d in t["points"].items():
                if side_of(f) == side:
                    for k, v in d.items():
                        best[k.split("|")[0]] = max(best.get(k.split("|")[0], 0.0), v)
            assert not best or sum(best.values()) == pytest.approx(share, abs=0.2)
        assert list(t["limits"].values()) == sorted(t["limits"].values())
        assert set(t["evidence"]) == set(t["limits"])


def fib(side=-1):
    """Short: last top 100.8, reaction low 96.8, swept to 101. Long is the mirror around 100."""
    return Fib(side, 100 - 0.8 * side, 100 + 3.2 * side, 100 - side, False)


def event(side=-1, **tags):
    return Event(T0.timestamp(), side, "15m", ("Uyumsuzluk|RSI|tepede anlık",), 100.0, 101.0 if side == -1 else 99.0, 2.0, tags, fib(side))


def test_a_plan_only_when_a_limit_is_reached():
    shown, plan = run.judge("BTCUSDT", event(**{"15m": ["SFP|RSI uyumsuz|"]}), TABLE)
    assert shown["kind"] is None and plan is None and shown["score"] == 8
    shown, plan = run.judge("BTCUSDT", event(**{"1M": ["Elliott|12345 sonu|diyagonal"]}), TABLE)
    assert shown["score"] == 50 and shown["kind"] is None and plan is None          # enough points, but a single category
    enough = {"1M": ["Elliott|12345 sonu|diyagonal"], "15m": ["SFP|RSI uyumsuz|"]}
    shown, plan = run.judge("BTCUSDT", event(**enough), TABLE)
    assert (plan.kind, plan.direction, plan.stop) == ("SCALP", "SHORT", 102.45)          # the fib stop (100.8 + 0.412 x 4) is farther than 101 + 0.25 x ATR
    assert plan.evidence["proven"] is False and plan.confirmations == enough and plan.trigger == ["Uyumsuzluk|RSI|tepede anlık"]
    _, long = run.judge("BTCUSDT", event(1, **enough), TABLE)
    assert (long.direction, long.stop) == ("LONG", 97.55)
    shown, none = run.judge("BTCUSDT", replace(event(**enough), fib=None), TABLE)
    assert none is None and "fib" in shown["noPlan"]


# ---------- virtual trades

@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session


CATEGORIES = {"SFP": {"points": 18.0, "frame": "1h", "rule": "SFP|RSI uyumsuz|"}, "Elliott": {"points": 12.0, "frame": "4h", "rule": "Elliott|12345 sonu|uzamasız"}}


def plan(side=-1, kind="SCALP", asset="BTCUSDT", **more):
    """Entry 100, stop 2.448 % away, 25x: half at +-2 %, then the scalp fib (leg 4)."""
    return planning.make(asset, side, kind, T0.timestamp(), 50, 100.0, 100 - 2 * side, fib(side), "15m", CATEGORIES, EVIDENCE, ("Uyumsuzluk|RSI|tepede anlık",), {"1h": ["SFP|RSI uyumsuz|"]}, **more)


def candle(i, high, low, close=None, opened=None):
    return Candle(T0 + timedelta(minutes=15 * i), opened if opened is not None else low, high, low, close if close is not None else low, 1.0, 0.5)


def test_one_open_trade_per_asset_and_direction(db):
    assert market.open_trade(db, plan()) is not None
    assert market.open_trade(db, plan(kind="SWING")) is None
    assert market.open_trade(db, plan(1)) is not None
    assert market.open_trade(db, plan(asset="XAU")) is not None


def test_the_plan_of_a_scalp_and_the_order_of_its_targets():
    p = plan()
    assert (p.stop, p.stop_percent, p.leverage) == (102.45, 2.448, 25)
    # +50 % on the cash is 2 % at 25x; the scalp TP is 2.088 % away: close enough, the half moves there and 20 units are left for the market sell
    assert [(s["zone"], s["price"], s["units"]) for s in p.steps] == [("HALF_AT_SCALP_TP", 97.91, 50), ("TP1", 97.19, 10), ("TP2", 95.86, 10), ("TP3", 94.33, 10), ("MARKET_SELL", 92.99, 20)]
    s = plan(kind="SCALP_SWING")
    assert [(x["zone"], x["units"]) for x in s.steps] == [("HALF_AT_SCALP_TP", 50), ("TREND_1.272", 10), ("TREND_2.618", 10), ("TREND_3.618", 10), ("TREND_4.618", 10), ("TREND_5.618", 10)]
    assert s.steps[1]["price"] == pytest.approx(101 - 1.272 * 4, abs=0.01)
    swing = plan(kind="SWING")
    assert swing.leverage == 10 and [x["zone"] for x in swing.steps][:2] == ["TREND_1.272", "HALF"]          # +50 % at 10x is 5 %, after 1.272


def test_a_full_winner_is_recorded_step_by_step_and_compounds(db):
    t = market.open_trade(db, plan())
    s = planning.size(50, 2.448, "SCALP")
    assert (t.leverage, t.balance_before, t.margin_usd) == (25, 1000.0, round(10 * s.margin_percent, 2))
    notional = t.notional_usd
    lines = market.follow(db, "BTCUSDT", [candle(0, 100.5, 97.5, 98), candle(1, 98, 95, 96), candle(2, 96, 92, 93)])
    assert [(e.kind, e.units, e.units_left) for _, e in lines] == [("HALF_AT_SCALP_TP", 50, 50), ("TP1", 10, 40), ("TP2", 10, 30), ("TP3", 10, 20), ("MARKET_SELL", 20, 0)]
    gross = (0.5 * 2.09 + 0.1 * 2.81 + 0.1 * 4.14 + 0.1 * 5.67 + 0.2 * 7.01) / 100
    assert t.pnl_usd == pytest.approx(notional * (gross - 0.001), abs=0.01)
    a = market.account(db)
    assert a.balance == pytest.approx(1000 + t.pnl_usd) and (t.exit_reason, t.balance_after) == ("MARKET_SELL", pytest.approx(a.balance))
    r = market.record(t, market.events_of(db, t.id))
    assert r["status"] == "CLOSED" and r["openedAtTsi"] == "25.11.2026 12:00" and len(r["takeProfits"]) == 5 and r["stopped"] is None
    assert r["maxProfit"]["percent"] == 8.0 and r["maxProfit"]["roiPercent"] == 200.0
    again = market.open_trade(db, plan())          # the next trade is sized from the bigger balance
    assert again.notional_usd / again.balance_before == pytest.approx(notional / 1000) and again.notional_usd > notional


def test_after_the_half_the_stop_is_the_entry(db):
    t = market.open_trade(db, plan())
    market.follow(db, "BTCUSDT", [candle(0, 100.5, 97.8, 98)])
    assert (t.stop_now, t.units_left, t.closed_at) == (100.0, 50, None)
    assert market.record(t, market.events_of(db, t.id))["status"] == "PARTIAL"
    market.follow(db, "BTCUSDT", [candle(0, 100.5, 97.8, 98), candle(1, 100.2, 98, 99)])          # a candle already seen is not counted twice
    assert (t.exit_reason, t.units_left) == ("ENTRY_STOP", 0) and t.result_r > 0
    r = market.record(t, market.events_of(db, t.id))
    assert r["stopped"]["zone"] == "ENTRY_STOP" and r["stopped"]["units"] == 50


def test_a_candle_that_takes_the_half_and_comes_back_closes_at_the_entry(db):
    t = market.open_trade(db, plan())
    market.follow(db, "BTCUSDT", [candle(0, 100.5, 97.8, 100.2)])
    assert t.exit_reason == "ENTRY_STOP" and [e.kind for e in market.events_of(db, t.id)] == ["OPEN", "HALF_AT_SCALP_TP", "ENTRY_STOP"]


@pytest.mark.parametrize(("bars", "price"), [
    ([candle(0, 102.5, 99, opened=100)], 102.45),
    ([candle(0, 103, 90, opened=100)], 102.45),                        # both in one candle: the stop counts
    ([candle(0, 105, 103, opened=104)], 104),                          # opened beyond the stop: filled there, worse than the stop
])
def test_how_a_short_loses(db, bars, price):
    t = market.open_trade(db, plan())
    market.follow(db, "BTCUSDT", bars)
    assert (t.exit_reason, t.exit_price) == ("STOP", price) and t.result_r < -1
    assert market.account(db).balance < 1000
    assert market.record(t, market.events_of(db, t.id))["stopped"]["pnlUsd"] < 0


def test_a_trade_has_no_time_limit_and_old_candles_are_not_looked_at(db):
    t = market.open_trade(db, plan(1))
    market.follow(db, "BTCUSDT", [candle(-1, 110, 90)] + [candle(i, 101, 99, 100.5) for i in range(1500)])
    assert t.closed_at is None and market.open_trades(db, "BTCUSDT") == [t]
    assert (t.best_price, t.worst_price) == (101, 99)
    r = market.record(t, market.events_of(db, t.id))
    assert r["status"] == "OPEN" and r["durationHours"] == 375 and r["openPnlUsd"] == pytest.approx(t.notional_usd * 0.005, abs=0.01)


def test_account_and_performance_count_wins_and_losses(db):
    assert market.account_out(db) | {"openTrades": 0} == market.account_out(db)
    assert market.account_out(db)["equity"] == 1000 and market.performance([])["averageR"] is None
    win = market.open_trade(db, plan())
    market.follow(db, "BTCUSDT", [candle(0, 100.5, 92, 92)])
    lost = market.open_trade(db, plan(asset="XAU"))
    market.follow(db, "XAU", [candle(0, 103, 99, opened=100)])
    market.open_trade(db, plan(asset="SPX"))
    a = market.account_out(db)
    assert (a["won"], a["lost"], a["openTrades"]) == (1, 1, 1) and a["balance"] == pytest.approx(1000 + win.pnl_usd + lost.pnl_usd - 0.05 / 100 * market.open_trades(db, "SPX")[0].notional_usd, abs=0.02)
    p = market.performance([win, lost])
    assert (p["n"], p["won"], p["lost"], p["winRate"], p["longestLosingStreak"]) == (2, 1, 1, 0.5, 1)
    assert p["byRule"]["SFP|RSI uyumsuz|"] == {"n": 2, "won": 1, "lost": 1, "averageR": p["averageR"]} and set(p["byExit"]) == {"MARKET_SELL", "STOP"}


# ---------- the engine was off

def test_a_missed_trade_is_only_noted_and_followed(db):
    bars = [candle(0, 100.5, 97.8, 98), candle(1, 100.2, 98, 99)]
    m = market.note_missed(db, plan(), bars)
    assert m is not None and market.open_trades(db) == [] and market.account(db).balance == 1000
    assert market.note_missed(db, plan(), bars) is None          # the same stretch is not noted twice
    market.follow_missed(db, "BTCUSDT", bars)
    market.follow_missed(db, "BTCUSDT", bars)
    out = market.missed_out(m)
    assert out["status"] == "MISSED" and out["atTsi"] == "25.11.2026 12:00" and [f["zone"] for f in out["wouldBe"]["fills"]] == ["HALF_AT_SCALP_TP", "ENTRY_STOP"]
    assert out["wouldBe"]["exitReason"] == "ENTRY_STOP" and out["wouldBe"]["resultR"] > 0 and out["confirmations"] == {"1h": ["SFP|RSI uyumsuz|"]}
    a = market.account_out(db)
    assert (a["missed"], a["won"], a["balance"]) == (1, 0, 1000)


def test_nothing_is_missed_while_a_real_trade_is_open(db):
    market.open_trade(db, plan())
    assert market.note_missed(db, plan(), []) is None and market.note_missed(db, plan(1), []) is not None


def test_a_late_start_never_opens_a_trade(monkeypatch):
    p, t = plan(), T0.timestamp()

    class Base:
        t = [T0.timestamp() - 900 * k for k in (3, 2, 1)]

    class FakeScanner:
        def __init__(self, *a): self.base = Base
        def trigger(self, when, side): return ("15m", 0, ()) if side == -1 else None
        def scan(self, i, side, found): return Base.t[i] + 900

    class FakeFeed:
        data = {"15m": [candle(-1, 101, 99)]}
        def hole(self): return None
        def cache(self): return {}

    monkeypatch.setattr(run, "Scanner", FakeScanner)
    monkeypatch.setattr(run, "judge", lambda asset, e, table: ({"time": e}, replace(p, time=e)))
    monkeypatch.setattr(run, "tables", lambda: {"XYZ": TABLE})
    on_time = run.look("XYZ", FakeFeed(), T0 + timedelta(seconds=5), t - 900)
    assert [x.time for x in on_time[1]] == [t] and on_time[2] == []
    back = run.look("XYZ", FakeFeed(), T0 + timedelta(seconds=5), t - 2700)          # it was off for two closes: only noted
    assert [x.time for x in back[1]] == [t] and [x.time for x in back[2]] == [t - 1800, t - 900]
    late = run.look("XYZ", FakeFeed(), T0 + timedelta(minutes=8), t - 900)          # started 8 minutes after the close
    assert late[1] == [] and [x.time for x in late[2]] == [t]
    assert run.look("XYZ", FakeFeed(), T0 + timedelta(seconds=5))[2] == []          # the very first run has nothing to compare with


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
    d = web.get("/api/portfolio/u1/market-plan", headers=ME).json()["data"]
    assert d["iqScore"] == 50
    assert d["items"][0]["size"] == {"marginPercent": 1.63, "leverage": 25, "notionalPercent": 40.85, "riskPercent": 1.0}          # 1 % / 2.448 % stop
    assert web.get("/api/portfolio/u1/market-plan", headers={"X-User-Id": "u2"}).status_code == 403


def test_the_detail_has_every_event_confirmation_and_both_stories(web, db):
    t = market.open_trade(db, plan())
    market.follow(db, "BTCUSDT", [candle(0, 100.5, 97.8, 98), candle(1, 100.2, 98, 99)])
    d = web.get(f"/api/portfolio/market/trades/{t.id}", headers=ME).json()["data"]
    assert [e["kind"] for e in d["events"]] == ["OPEN", "HALF_AT_SCALP_TP", "ENTRY_STOP"] and d["events"][0]["atTsi"] == "25.11.2026 12:00"
    assert d["confirmations"] == {"1h": ["SFP|RSI uyumsuz|"]} and d["asset"] == "BTC"
    a = d["analysis"]
    assert a["facts"]["confirmationCount"] == 1 and "SFP: RSI uyumsuz" in a["trader"] and "girişteki stop" in a["trader"]
    assert "dalga sayımı" in a["standard"] and "yeterli kanıt yok" in a["standard"] and "Elliott" not in a["standard"]
    assert web.get("/api/portfolio/market/trades/none", headers=ME).status_code == 404


def test_trades_account_and_performance_need_the_gateway(web, db):
    market.open_trade(db, plan())
    items = web.get("/api/portfolio/market/trades?asset=BTC&status=OPEN", headers=ME).json()["data"]["items"]
    assert len(items) == 1 and "confirmations" not in items[0] and items[0]["leverage"] == 25
    assert web.get("/api/portfolio/market/trades?asset=GOLD", headers=ME).json()["data"]["items"] == []
    assert web.get("/api/portfolio/market/trades?status=CLOSED", headers=ME).json()["data"]["items"] == []
    assert web.get("/api/portfolio/market/account", headers=ME).json()["data"]["startBalance"] == 1000
    assert web.get("/api/portfolio/market/performance", headers=ME).json()["data"]["n"] == 0
    assert web.get("/api/portfolio/market/missed", headers=ME).json()["data"]["items"] == []
    market.note_missed(db, plan(1), [])
    assert web.get("/api/portfolio/market/missed?asset=BTC", headers=ME).json()["data"]["items"][0]["reason"] == "ENGINE_OFF"
    assert web.get("/api/portfolio/market/view").status_code == web.get("/api/portfolio/market/account").status_code == 401
