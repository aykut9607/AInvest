"""Live confirmation engine: sizes, candles, the forming bar. Nothing here needs data files or the internet."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from signals.data.candles import Candle
from signals.indicators.rsi_divergence import rsi
from signals.live import feed, plan
from signals.live.scan import LiveFrame, period_frame
from signals.live.study import after

UTC = timezone.utc


# ---------- sizes

@pytest.mark.parametrize(("iq", "margin"), [(0, 1.0), (50, 5.5), (100, 10.0), (140, 10.0)])
def test_cash_per_trade_is_1_to_10_percent_by_the_score(iq, margin):
    assert plan.margin_percent(iq) == margin


@pytest.mark.parametrize("iq", range(0, 101, 5))
@pytest.mark.parametrize("stop", [0.2, 0.5, 1.0, 2.5, 8.0, 40.0])
def test_a_stop_never_costs_more_than_the_allowed_risk(iq, stop):
    s = plan.size(iq, stop)
    assert 1 <= s.leverage <= plan.LEVERAGE_CAP
    assert s.leverage == 1 or s.risk_percent <= plan.RISK_PER_TRADE + 1e-9
    assert s.leverage == 1 or s.leverage * stop <= 100 * plan.STOP_TO_LIQUIDATION


def test_kind_is_the_highest_limit_reached():
    limits = {"SCALP": 20, "SCALP_SWING": 30, "SWING": 40}
    assert [plan.kind_of(s, limits) for s in (19.9, 20, 35, 80)] == [None, "SCALP", "SCALP_SWING", "SWING"]
    assert plan.kind_of(99, {}) is None          # an asset whose score proved nothing never trades


def test_plan_direction_and_first_target():
    p = plan.make("BTCUSDT", -1, "SCALP", 0.0, 33.33, 100.0, 102.0, "15m", {}, {})
    assert (p.direction, p.stop_percent, p.first_target, p.score) == ("SHORT", 2.0, 97.0, 33.3)
    assert plan.make("BTCUSDT", 1, "SCALP", 0.0, 1, 100.0, 98.0, "15m", {}, {}).first_target == 103.0
    with pytest.raises(ValueError):
        plan.make("BTCUSDT", -1, "SCALP", 0.0, 1, 100.0, 99.0, "15m", {}, {})


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
