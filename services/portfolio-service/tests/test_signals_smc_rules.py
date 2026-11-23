"""Smart-money rules (signals/rules/SMART_MONEY.md) on small hand-made series."""

from datetime import datetime, timedelta, timezone

from signals.data.candles import Candle
from signals.rules import smc_detect as sm
from signals.rules.pa_detect import DOWN, UP
from signals.structure.pivots import HIGH, LOW
from signals.structure.zigzag import SwingPoint
from tests.test_signals_pa_rules import path

T0 = datetime(2026, 1, 5, tzinfo=timezone.utc)          # a Monday


def bars(rows, step=timedelta(days=1), start=T0):
    return [Candle(time=start + i * step, open=o, high=h, low=lo, close=c, volume=1) for i, (o, h, lo, c) in enumerate(rows)]


def test_candle_patterns():
    got = sm.candle_patterns(bars([(50, 52, 40, 51), (50, 51, 46, 47), (46.5, 53, 46, 52.5), (52, 55, 49, 52.1), (51, 56, 48, 54), (53, 54.5, 50, 52)]))
    names = {(i, n, d) for i, n, d in got}
    assert {(0, sm.PIN, UP), (2, sm.ENGULFING, UP), (3, sm.DOJI, None), (5, sm.INSIDE, None)} <= names


def test_bullish_and_bearish_gap_and_no_gap_when_wicks_meet():
    rows = [(50, 53, 49, 52), (52, 62, 51.5, 61), (61, 64, 57, 63)]
    gap, = sm.fair_value_gaps(bars(rows))
    assert (gap.direction, gap.low, gap.high, gap.known_at, gap.mid) == (UP, 53, 57, 2, 55)
    gap, = sm.fair_value_gaps(bars([(-o, -lo, -h, -c) for o, h, lo, c in rows]))
    assert (gap.direction, gap.low, gap.high) == (DOWN, -57, -53)
    assert sm.fair_value_gaps(bars([(50, 57, 49, 52), (52, 62, 51.5, 61), (61, 64, 57, 63)])) == []


def test_first_touch_and_failure_of_a_zone():
    zone = sm.Zone("x", UP, 0, 50, 54, 1)
    cs = bars([(60, 61, 59, 60)] * 3 + [(58, 59, 53, 57), (57, 58, 48, 49)])
    assert sm.first_touch(cs, zone) == 3 and sm.closed_through(cs, zone, 3) == 4


def test_order_block_is_the_last_opposite_candle_before_the_break():
    candles, points = path([100, 120, 105, 130, 112, 150])
    blocks = [z for z in sm.order_blocks(candles, points) if z.direction == UP]
    assert blocks
    for z in blocks:
        c = candles[z.index]
        assert c.close < c.open and z.low == c.low and z.high == c.high and z.index < z.known_at


def test_breaker_needs_an_msb_and_turns_the_role():
    candles, points = path([50, 68, 58, 80, 68, 92, 80, 100, 75, 88, 62])
    zone, = sm.breakers(candles, points)
    assert zone.direction == DOWN and zone.low == 80                 # the broken HL is resistance now
    candles, points = path([50, 68, 58, 80, 68, 92, 80, 100])
    assert sm.breakers(candles, points) == []


def test_supply_demand_needs_a_small_base_and_a_strong_candle():
    quiet = [(50, 52, 48, 50.5)] * 20
    zone, = sm.supply_demand(bars(quiet + [(50.5, 60, 50, 59.5)]))
    assert zone.direction == UP and (zone.low, zone.high) == (48, 52)
    assert sm.supply_demand(bars(quiet + [(50.5, 53, 50, 52)])) == []


def swings(prices, gap=8):
    return [SwingPoint(HIGH if i % 2 == 0 else LOW, i * gap, p, i * gap + 2) for i, p in enumerate(prices)]


def test_range_and_its_equilibrium():
    rng, = sm.ranges(swings([100, 60, 98, 61]))
    assert (rng.low, rng.high, rng.eq) == (60, 100, 80)
    assert sm.ranges(swings([100, 60, 85, 61])) == [] and sm.ranges(swings([100, 60, 98, 61], gap=3)) == []


def test_deviation_comes_back_inside_and_a_breakout_does_not():
    rng = sm.Range(0, 60, 100, 0, ())
    fake = bars([(80, 82, 78, 80), (62, 63, 55, 58), (58, 66, 57, 65), (65, 70, 64, 69)])
    dev, = sm.deviations(fake, rng)
    assert (dev.side, dev.index, dev.back_index, dev.extreme) == (LOW, 1, 2, 55)
    real = bars([(80, 82, 78, 80)] + [(58, 59, 50, 52)] * 6)
    assert sm.deviations(real, rng) == []


def test_equal_highs():
    cs = bars([(50, 55, 45, 50)] * 60)                               # ATR 10
    points = [SwingPoint(HIGH, 20, 90, 22), SwingPoint(LOW, 25, 70, 27), SwingPoint(HIGH, 30, 91, 32), SwingPoint(LOW, 35, 60, 37)]
    (a, b), = sm.equal_levels(cs, points)
    assert (a.index, b.index) == (20, 30)


def test_key_levels_use_only_the_past():
    daily = bars([(100 + i, 110 + i, 90 + i, 105 + i) for i in range(10)])           # Mon 5 Jan ... Wed 14 Jan
    levels = sm.key_levels(daily, T0 + timedelta(days=9))                            # Wed 14 Jan 00:00
    assert levels["Önceki gün yüksek"] == 118 and levels["Önceki gün düşük"] == 98
    assert levels["Önceki hafta yüksek"] == 116 and levels["Önceki hafta düşük"] == 90
    assert levels["Pazartesi yüksek"] == 117 and levels["Hafta açılışı"] == 107
    assert "Pazartesi yüksek" not in sm.key_levels(daily, T0 + timedelta(days=7))    # Monday itself is not closed yet


def test_power_of_3():
    rows = [(100, 101, 99, 100)] * 8 + [(100, 100, 96, 99.5)] + [(100, 101, 99, 100)] * 4 + [(100, 106, 100, 105)] + [(105, 106, 104, 105)] * 10
    po, = sm.power_of_3(bars(rows, timedelta(hours=1)))
    assert (po.swept, po.back_index, po.distribution, po.known_at) == (LOW, 8, 13, 12)
    both = rows[:9] + [(100, 104, 99, 100)] + rows[10:]
    assert sm.power_of_3(bars(both, timedelta(hours=1))) == []
