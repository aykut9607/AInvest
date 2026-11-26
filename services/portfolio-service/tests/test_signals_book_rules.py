"""Book rules (signals/rules/BOOKS.md)."""

from datetime import datetime, timedelta, timezone

import pytest

from signals.data.candles import Candle
from signals.rules import book_detect as bk

T0 = datetime(2026, 11, 23, tzinfo=timezone.utc)


def bar(i, price, volume, step=timedelta(minutes=15)):
    return Candle(time=T0 + i * step, open=price, high=price, low=price, close=price, volume=volume)


def test_vwap_weighs_by_volume_and_restarts_every_day():
    rows = bk.session_vwap([bar(0, 100, 1), bar(1, 110, 3), bar(96, 50, 2)])
    assert [r.value for r in rows] == [100, 107.5, 50]
    assert rows[1].deviation == pytest.approx(4.3301, abs=1e-4) and rows[2].deviation == 0


def test_sides_near_and_far_from_vwap():
    v = bk.Vwap(100, 4)
    assert bk.allowed_sides(101, v) == set()
    assert bk.allowed_sides(103, v) == {"long"} and bk.allowed_sides(97, v) == {"short"}
    assert bk.allowed_sides(105, v) == {"long", "short"}
    assert bk.allowed_sides(105, bk.Vwap(100, 0)) == set()


def test_a_trade_towards_vwap_needs_room():
    v = bk.Vwap(100, 4)
    assert bk.room_to_vwap(entry=130, stop=140, vwap=v) and not bk.room_to_vwap(entry=115, stop=125, vwap=v)
    assert not bk.room_to_vwap(entry=130, stop=120, vwap=v)          # stop on the VWAP side: the trade goes away from it


def test_opening_range_is_the_first_us_hour():
    cs = [bar(i, 100 + i, 1) for i in range(96)]                      # winter: US open 14:30 UTC = bar 58
    assert bk.opening_range(cs, T0) == (158, 161)


def test_ema_matches_the_worked_example_and_the_oscillator_difference():
    closes = [1450.0] * 21 + [1500.0]
    assert bk.ema(closes, 21)[20] == 1450 and bk.ema(closes, 21)[21] == pytest.approx(1454.545, abs=1e-3)      # the book rounds 2/22 to 0.09
    assert bk.ema(closes, 30) == [None] * 22
    osc = bk.elliott_oscillator([float(x) for x in range(60)])
    assert osc[33] is None and osc[-1] == pytest.approx(15.0)                                                 # lag difference 17 - 2


def test_break_volume():
    cs = [bar(i, 100, 10) for i in range(20)] + [bar(20, 105, 30), bar(21, 103, 8), bar(22, 101, 6)]
    assert bk.volume_confirms(cs, 20, 22) is True
    assert bk.volume_confirms(cs[:20] + [bar(20, 105, 9)] + cs[21:], 20, 22) is False
    assert bk.volume_confirms(cs, 19, 22) is None


def test_concentration():
    assert bk.concentration([1.0]) == 1 and bk.concentration([0.25] * 4) == 0.25
    with pytest.raises(ValueError):
        bk.concentration([0.5, 0.6])


def test_regime_turns_at_twenty_percent():
    assert bk.regime_20([100, 110, 119, 120, 150, 121, 120, 100, 119, 120]) == [None, None, None, "bull", "bull", "bull", "bear", "bear", "bear", "bull"]


def test_stop_distance_and_round_numbers():
    day = [Candle(time=T0 + timedelta(days=i), open=100, high=105, low=95, close=100, volume=1) for i in range(20)]
    assert bk.average_daily_range(day, 20) == 10 and bk.average_daily_range(day, 19) is None
    assert bk.stop_is_far_enough(100, 89, 10) and not bk.stop_is_far_enough(100, 95, 10)
    assert bk.stop_beyond_round(60010, "long", 1000) == 59980 and bk.stop_beyond_round(59990, "short", 1000) == 60020
    assert bk.stop_beyond_round(59990, "long", 1000) == 59990 and bk.stop_beyond_round(60400, "long", 1000) == 60400


def test_extreme_uses_only_its_own_past():
    values = [float(i % 100) for i in range(300)] + [99.5, -1.0, 50.0]
    assert [bk.extreme(values, i) for i in (300, 301, 302)] == ["high", "low", None]
    assert bk.extreme(values, 150) is None


def test_range_break_and_three_closes():
    cs = [bar(i, 100 + i % 2, 1) for i in range(20)] + [bar(20, 103, 1), bar(21, 104, 1), bar(22, 100.5, 1)]
    assert bk.range_break(cs, 20) == "up" and bk.range_break(cs, 19) is None and bk.range_break(cs, 22) is None
    assert bk.break_holds(cs, 20, 101, "up") is False and bk.break_holds(cs, 20, 101, "up", days=2) is True
    assert bk.break_holds(cs, 21, 101, "up") is None


def test_rolling_windows_and_payoff():
    assert bk.rolling_win_share([0.1, -0.05, 0.1, -0.2], 2) == pytest.approx(2 / 3)
    assert bk.rolling_win_share([0.1], 2) is None
    assert bk.payoff_ratio([3000, -5000]) == 0.6 and bk.payoff_ratio([1, 2]) is None
