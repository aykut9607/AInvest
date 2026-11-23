"""Price-action rules (signals/rules/PRICE_ACTION.md) on small hand-made series."""

from datetime import datetime, timedelta, timezone

from signals.data.candles import Candle
from signals.rules import pa_detect as pa
from signals.structure.pivots import HIGH, LOW
from signals.structure.zigzag import SwingPoint

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def path(prices, step=5):
    """Straight legs of `step` bars between the turning points; swings are confirmed two bars after the turn."""
    candles, points = [], []
    for k in range(len(prices) - 1):
        a, b = prices[k], prices[k + 1]
        for j in range(step):
            o, c = a + (b - a) * j / step, a + (b - a) * (j + 1) / step
            candles.append(Candle(time=T0 + timedelta(days=len(candles)), open=o, high=max(o, c), low=min(o, c), close=c, volume=1))
    for k in range(1, len(prices) - 1):
        kind = HIGH if prices[k] > prices[k - 1] else LOW
        points.append(SwingPoint(kind, k * step - 1, prices[k], k * step + 1))
    return candles, points


def kinds(candles, points):
    return [(b.kind, b.direction, b.level) for b in pa.structure_breaks(candles, points)]


def test_swing_labels():
    _, points = path([100, 120, 110, 130, 115, 125, 105, 110])
    assert [label for _, label in pa.swing_labels(points)] == ["HH", "HL", "LH", "LL"]


def test_downtrend_bos_then_msb_is_the_high_that_made_the_low():
    candles, points = path([100, 82, 92, 70, 82, 58, 70, 50, 75, 62, 88])
    got = kinds(candles, points)
    assert got[:3] == [("BOS", "down", 82), ("BOS", "down", 70), ("BOS", "down", 58)]
    assert got[3:] == [("MSB", "up", 70), ("BOS", "up", 75)]


def test_uptrend_is_the_mirror():
    candles, points = path([50, 68, 58, 80, 68, 92, 80, 100, 75, 88, 62])
    got = kinds(candles, points)
    assert got[-2:] == [("MSB", "down", 80), ("BOS", "down", 75)]


def test_a_reaction_high_below_the_protected_high_is_not_an_msb():
    candles, points = path([100, 82, 92, 70, 82, 50, 60, 54, 72, 66, 78])     # 60 is broken, 82 (made the low) is not
    assert all(kind != "MSB" for kind, _, _ in kinds(candles, points))


def test_a_wick_is_not_a_break():
    candles, points = path([100, 82, 92, 84, 90])
    i = len(candles) - 3
    c = candles[i]
    candles[i] = Candle(time=c.time, open=c.open, high=c.high, low=70, close=c.close, volume=1)
    assert kinds(candles, points) == []


def test_body_levels_are_the_turns_of_the_bodies():
    mk = lambda i, o, c: Candle(time=T0 + timedelta(days=31 * i), open=o, high=max(o, c) + 5, low=min(o, c) - 5, close=c, volume=1)
    got = pa.body_levels([mk(0, 10, 20), mk(1, 20, 15), mk(2, 15, 12), mk(3, 12, 18)])
    assert [(lv.price, lv.kind) for lv in got] == [(20, HIGH), (12, LOW)]


def find(prices):
    candles, points = path(prices)
    return candles, pa.converging_patterns(candles, points)


def test_rising_wedge_breaks_down():
    candles, found = find([50, 80, 62, 86, 74, 90, 60])
    wedge = [p for p in found if p.kind == pa.RISING_WEDGE]
    assert wedge and wedge[0].break_direction == pa.DOWN and wedge[0].lower[2] > wedge[0].upper[2] > 0


def test_symmetric_triangle_either_way():
    for tail, way in ((110, pa.UP), (60, pa.DOWN)):
        _, found = find([60, 100, 70, 94, 76, 88, tail] if way == pa.DOWN else [60, 100, 70, 94, 76, 88, 82, tail])
        assert any(p.kind == pa.SYMMETRIC for p in found)


def test_a_big_leg_before_small_swings_is_not_part_of_the_pattern():
    _, found = find([60, 140, 80, 98, 86, 94, 60])
    assert not any(p.points[0].price == 140 for p in found)


def test_parallel_channel_is_no_pattern():
    _, found = find([50, 80, 60, 90, 70, 100, 70])
    assert found == []


def test_diamond_widens_then_narrows():
    candles, points = path([80, 88, 74, 96, 66, 90, 73, 60])
    got = pa.diamonds(candles, points)
    assert len(got) == 1 and got[0].height == 30
    candles, points = path([80, 88, 74, 84, 78, 83, 79, 60])              # only narrowing
    assert pa.diamonds(candles, points) == []


def test_trend_line_needs_three_rising_bottoms_and_a_close_to_break():
    candles, points = path([50, 70, 60, 80, 70, 90, 80, 100, 60, 88, 70])
    lines = [t for t in pa.trend_lines(candles, points) if t.direction == pa.UP]
    assert lines and lines[0].break_index is not None
    assert candles[lines[0].break_index].close < lines[0].at(lines[0].break_index)
