"""The four drawings must give the prices TradingView shows on the user's chart (BTCUSDT.P, 23 Nov 2026)."""

import pytest

from signals.rules import fib_tools as ft
from signals.rules.fib_draw import handbook


def prices(levels):
    return {lv.ratio: round(lv.price, 1) for lv in levels}


def test_trend_extension_matches_the_chart():
    got = prices(ft.trend_extension(57755.8, 66937.7, 62240.0))
    for ratio, shown in {0.618: 67914.4, 0.786: 69457.0, 1.0: 71421.9, 1.272: 73919.4, 1.414: 75223.2, 1.618: 77096.3,
                         1.79: 78675.6, 2.0: 80603.8, 2.618: 86278.2, 2.79: 87857.5, 3.0: 89785.7, 4.0: 98967.6}.items():
        assert got[ratio] == pytest.approx(shown, abs=0.11)


def test_retracement_matches_the_chart():
    got = prices(ft.retracement(55100.0, 64572.5))
    for ratio, shown in {0.114: 63492.6, 0.34: 61351.9, 0.382: 60954.0, 0.5: 59836.3, 0.618: 58718.5, 0.66: 58320.7,
                         0.709: 57856.5, 0.786: 57127.1, 0.886: 56179.9}.items():
        assert got[ratio] == pytest.approx(shown, abs=0.11)


def test_monday_range_matches_the_chart():
    got = prices(ft.monday_range(64572.5, 60350.0))
    for ratio, shown in {-2.618: 75627.0, -0.618: 67182.0, -0.214: 65476.1, -0.114: 65053.9, 0.5: 62461.3, 1.114: 59868.6,
                         1.214: 59446.4, 1.618: 57740.5, 3.618: 49295.5}.items():
        assert got[ratio] == pytest.approx(shown, abs=0.11)


def test_falling_structure_is_the_mirror():
    up, down = ft.trend_extension(100, 160, 130), ft.trend_extension(160, 100, 130)
    assert [round(a.price + b.price, 6) for a, b in zip(up, down)] == [260.0] * len(up)


def test_pullback_beyond_the_start_is_rejected():
    with pytest.raises(ValueError):
        ft.trend_extension(100, 160, 95)
    with pytest.raises(ValueError):
        ft.monday_range(100, 100)


def test_green_zone_is_a_retracement_of_wave_3():
    # wave 3 at 1.618: the 0.618 level is exactly the 0.618 retracement of wave 3, 0.786 is about one half
    assert ft.extension_as_retracement(0.618, 1.618) == pytest.approx(0.618, abs=0.001)
    assert ft.extension_as_retracement(0.786, 1.618) == pytest.approx(0.514, abs=0.001)
    assert ft.wave1_end_as_extension(57755.8, 66937.7, 62240.0) == pytest.approx(0.512, abs=0.001)


def test_handbook_draws_without_external_resources():
    page = handbook()
    assert page.count("<svg") == 7 and "http" not in page
