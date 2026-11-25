"""Live confirmation engine: sizes, candles, the forming bar. Nothing here needs data files or the internet."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from signals.data.candles import Candle
from signals.indicators.rsi_divergence import rsi
from signals.live import feed, fibs, plan
from signals.live.scan import LiveFrame, period_frame
from signals.live.study import after

UTC = timezone.utc


# ---------- sizes

@pytest.mark.parametrize(("iq", "margin"), [(0, 1.0), (50, 5.5), (100, 10.0), (140, 10.0)])
def test_cash_at_10x_is_1_to_10_percent_by_the_score(iq, margin):
    assert plan.margin_percent(iq) == margin


@pytest.mark.parametrize("kind", plan.KINDS)
@pytest.mark.parametrize("iq", range(0, 101, 10))
@pytest.mark.parametrize("stop", [0.2, 0.5, 1.0, 2.5, 3.0, 8.0, 40.0])
def test_a_stop_never_costs_more_than_the_allowed_risk(iq, stop, kind):
    s = plan.size(iq, stop, kind)
    assert 1 <= s.leverage <= plan.LEVERAGE_CAP[kind]
    assert s.risk_percent <= plan.RISK_PER_TRADE + 0.005 and s.notional_percent <= 10 * plan.margin_percent(iq) + 1e-9
    assert s.leverage == 1 or s.leverage * stop <= 100 * plan.STOP_TO_LIQUIDATION + 1e-9
    assert s.margin_percent == pytest.approx(s.notional_percent / s.leverage, abs=0.006)


def test_higher_leverage_means_less_cash_for_the_same_position():
    assert plan.size(50, 3.0).leverage == 25 and plan.size(50, 3.2).leverage == 23 and plan.size(50, 7.5).leverage == 10
    scalp, swing = plan.size(50, 2.0, "SCALP"), plan.size(50, 2.0, "SWING")
    assert (scalp.leverage, swing.leverage) == (25, 10) and scalp.notional_percent == swing.notional_percent
    assert (scalp.margin_percent, swing.margin_percent) == (2.0, 5.0)          # 10 USD at 10x = 4 USD at 25x


# ---------- the two fibs

PHOTO = fibs.Fib(1, 67460.3, 70182.5, 67800.0, False)


def test_the_scalp_fib_gives_the_published_prices():
    got = [PHOTO.scalp(r) for r in (fibs.STOP, *reversed(fibs.LIQUIDITY), *fibs.REENTRY, *(r for _, r in fibs.SCALP))]
    assert got == pytest.approx([66338.5, 66725.4, 67155.5, 67776.1, 68037.5, 69425.8, 69915.8, 70825.0, 71864.9, 72774.1], abs=0.3)


def test_the_units_of_the_published_plan():
    p = plan.make("BTCUSDT", 1, "SCALP", 0.0, 50, 67900.0, 67300.0, PHOTO, "30m", {}, {})
    assert (p.leverage, p.stop) == (25, 66338.75)
    assert [(s["zone"], s["units"]) for s in p.steps] == [("HALF_AT_SCALP_TP", 50), ("TP1", 10), ("TP2", 10), ("TP3", 10), ("MARKET_SELL", 20)]


@pytest.mark.parametrize("kind", plan.KINDS)
@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("leg", [0.4, 1.0, 3.0, 8.0, 20.0])
@pytest.mark.parametrize("leverage", [1, 5, 10, 25])
def test_every_ladder_closes_exactly_100_units_in_order(kind, side, leg, leverage):
    f = fibs.Fib(side, 100 - 0.5 * side, 100 + (leg - 0.5) * side, 100 - 0.6 * side, False)
    steps = plan.ladder(kind, side, 100.0, leverage, f)
    assert sum(s.units for s in steps) == 100 and all(s.units > 0 for s in steps)
    assert [s.price for s in steps] == sorted((s.price for s in steps), reverse=side == -1)
    assert sum(s.moves_stop for s in steps) == 1 and all(side * (s.price - 100) >= 0.19 for s in steps)
    assert len({s.zone for s in steps}) == len(steps)


def test_the_fib_uses_the_last_low_and_the_reaction_after_it():
    low = np.array([110 - i * 0.5 for i in range(30)] + [95.0] + [97, 99, 101, 103, 102, 100, 98, 97, 96] + [94.5])
    high = low + 1
    f = fibs.draw(high, low, len(low) - 1, 1, 1.0)
    assert (f.start, f.end, f.extreme, f.redrawn) == (95.0, 104.0, 94.5, False)
    deep = np.append(low[:-1], 90.0)          # far beyond the stop level of that fib: drawn again from the new low
    g = fibs.draw(deep + 1, deep, len(deep) - 1, 1, 1.0)
    assert (g.start, g.end, g.redrawn) == (90.0, 104.0, True)
    m = fibs.draw(-low, -high, len(low) - 1, -1, 1.0)          # the mirror
    assert (m.start, m.end, m.extreme) == (-95.0, -104.0, -94.5)
    flat = np.full(60, 100.0)
    assert fibs.draw(flat + 0.1, flat, 59, 1, 1.0) is None
    late = np.append(low, [80.0] * 5)
    assert fibs.draw(np.append(high, [81.0] * 5), late, len(low) - 1, 1, 1.0) == f          # what comes later changes nothing


def test_kind_is_the_highest_limit_reached():
    limits = {"SCALP": 20, "SCALP_SWING": 30, "SWING": 40}
    assert [plan.kind_of(s, limits) for s in (19.9, 20, 35, 80)] == [None, "SCALP", "SCALP_SWING", "SWING"]
    assert plan.kind_of(99, {}) is None          # an asset whose score proved nothing never trades


def test_a_plan_needs_a_stop_on_the_right_side_and_a_target_worth_it():
    f = fibs.Fib(-1, 100.8, 96.8, 101.0, False)
    p = plan.make("BTCUSDT", -1, "SCALP", 0.0, 33.33, 100.0, 101.0, f, "15m", {}, {})
    assert (p.direction, p.stop, p.score, p.final_target) == ("SHORT", 102.45, 33.3, 92.99)
    assert plan.make("BTCUSDT", -1, "SCALP", 0.0, 1, 100.0, 108.0, f, "15m", {}, {}) is None          # 8 % risk for 7 %
    assert plan.make("BTCUSDT", -1, "SCALP", 0.0, 1, 98.7, 101.0, f, "15m", {}, {}) is None          # below the middle of the fib (98.8): the dear half for a short
    with pytest.raises(ValueError):
        plan.make("BTCUSDT", -1, "SCALP", 0.0, 1, 103.0, 101.0, f, "15m", {}, {})


def test_volume_of_another_market_is_only_used_where_it_exists(tmp_path, monkeypatch):
    from signals.live import auxvol
    (tmp_path / "x.csv").write_text("open_time,volume,taker_buy_volume\n" + "".join(f"1970-01-01T00:{15 * i:02d}:00+00:00,{v},{b}\n" for i, (v, b) in enumerate([(10, 8), (4, 1), (0, 0)])), encoding="utf-8")
    monkeypatch.setattr(auxvol, "RAW_DIR", tmp_path)
    monkeypatch.setattr(auxvol, "SOURCES", {"XAU": ("x.csv", 900.0, True), "SPX": ("x.csv", 3600.0, False)})
    v, c = auxvol.AuxVolume("XAU").of(np.array([0.0, 900.0, 1800.0, 9000.0]), 900.0)
    assert list(v[:2]) == [10, 4] and list(c[:2]) == [6, 4] and np.isnan(v[2:]).all()          # buys minus sells, added up
    assert auxvol.AuxVolume("XAU").of(np.array([0.0]), 1800.0)[0][0] == 14
    assert auxvol.AuxVolume("SPX").of(np.array([0.0]), 900.0) == (None, None)          # hourly volume says nothing about 15 minutes


def test_the_end_of_wave_2():
    from signals.patterns.elliott import SwingPoint
    from signals.scoring.confirm import elliott
    from signals.structure.zigzag import HIGH, LOW
    def points(*prices): return [SwingPoint(LOW if i % 2 == 0 else HIGH, i * 5, p, i * 5 + 2) for i, p in enumerate(prices)]
    assert "2. dalga sonu|başlangıcı belirsiz" in elliott(points(100, 110, 104))
    assert "2. dalga sonu|önceki 12345'in bittiği yerden" in elliott(points(100, 110, 104), {0: 1}, 20)
    assert not any(x.startswith("2. dalga") for x in elliott(points(100, 110, 107)) | elliott(points(100, 110, 100.5)) | elliott(points(100, 110, 99)))


# ---------- what price did after a trigger

def test_the_stop_counts_before_the_target_inside_one_bar():
    high, low, close = np.array([100, 101, 103, 90.0]), np.array([100, 99, 90, 80.0]), np.array([100, 100, 95, 85.0])
    assert after(high, low, close, 0, -1, 100.0, 102.0, 3) == (1.0, True, 15.0)          # 99 was reached, then the stop; 80 does not count
    assert after(high, low, close, 0, -1, 100.0, 110.0, 3) == (20.0, False, 15.0)
    assert after(high, low, close, 1, -1, 100.0, 110.0, 3) is None                       # the future is not complete


# ---------- levels of a calendar period

@pytest.mark.parametrize(("name", "frame"), [("Key level|günlük|test edilmemiş", "1d"), ("Key level|haftalık|test edilmemiş", "1w"), ("Key level|3 aylık|test edilmemiş", "1M"),
                                             ("Key level|yıllık|test edilmemiş", "1M"), ("Önceki dönem|önceki gün LOW|", "1d"), ("Hacim profili|nPOC hafta|dokunulmamış", "1w"),
                                             ("EXT bandı|Pazartesi|1,114–1,214", "1d"), ("EXT bandı|Ay|1,114–1,214", "1M"), ("Hacim profili|önceki ay VAL|", "1M")])
def test_period_levels_count_once_on_their_own_timeframe(name, frame):
    assert period_frame(name) == frame


# ---------- the bar that is still forming

def test_forming_rsi_is_the_rsi_of_the_unfinished_bar():
    closes = [100 + 3 * np.sin(i / 3) + i * 0.05 for i in range(80)]

    fake = LiveFrame.__new__(LiveFrame)
    d = np.diff(np.array(closes[:-1]), prepend=closes[0])
    fake.up, fake.down = LiveFrame._rma(np.maximum(d, 0)), LiveFrame._rma(np.maximum(-d, 0))
    fake.x = type("X", (), {"bars": type("B", (), {"close": np.array(closes[:-1])})})
    assert fake.forming_rsi(79, closes[-1]) == pytest.approx(rsi(closes)[-1], abs=1e-9)


def bar(t, o, h, lo, c, v=1.0, buy=0.5):
    return Candle(t, o, h, lo, c, v, buy)


def test_forming_bar_is_built_from_the_15m_candles_of_the_open_period():
    t0 = datetime(2026, 11, 25, 8, tzinfo=UTC)
    base = [bar(t0 + timedelta(minutes=15 * i), 100 + i, 102 + i, 99 + i, 101 + i) for i in range(6)]          # 08:00 ... 09:15
    closed = [bar(t0, 100, 105, 99, 104, 4, 2)]
    out = feed._with_forming(closed, base, "1h")
    assert [c.time.hour for c in out] == [8, 9]
    assert (out[-1].open, out[-1].high, out[-1].low, out[-1].close, out[-1].volume) == (104, 107, 103, 106, 2.0)
    assert feed._with_forming(out, base, "1h") == out          # already there: nothing is added twice


@pytest.mark.parametrize(("frame", "start"), [("45m", (25, 8, 15)), ("4h", (25, 8, 0)), ("1d", (25, 0, 0)), ("1w", (23, 0, 0)), ("1M", (1, 0, 0))])
def test_period_starts(frame, start):
    d, h, m = start
    assert feed.start_of(datetime(2026, 11, 25, 8, 45, tzinfo=UTC), frame) == datetime(2026, 11, d, h, m, tzinfo=UTC)


def test_running_klines_are_not_candles_and_pages_are_followed():
    t0 = datetime(2026, 11, 25, tzinfo=UTC)
    now = t0 + timedelta(minutes=15 * 1500 + 7)

    def get(url):
        start = int(url.split("startTime=")[1].split("&")[0])
        first = (start // 1000 - int(t0.timestamp())) // 900
        rows = []
        for i in range(first, min(first + 1000, 1501)):          # the last one is still running
            o = int(t0.timestamp() * 1000) + i * 900_000
            rows.append([o, "1", "2", "0.5", "1.5", "10", o + 899_999, "0", 1, "6", "0", "0"])
        return rows
    got = feed.fetch("BTCUSDT", "15m", t0, now, get)
    assert len(got) == 1500 and got[-1].time == t0 + timedelta(minutes=15 * 1499)
    assert got[0].taker_buy_volume == 6.0
