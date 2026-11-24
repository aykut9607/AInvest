"""EXT bands of MENTOR_VIEW.md; the levels must equal the ones the training panel showed on 24 Nov 2026."""

from datetime import datetime, timedelta, timezone

import pytest

from signals.data.candles import Candle
from signals.rules import ext_detect as ext
from signals.structure.pivots import HIGH, LOW

MONDAY = datetime(2026, 11, 16, tzinfo=timezone.utc)


def ref(low=100.0, high=110.0):
    return ext.RefRange("Pazartesi", low, high, MONDAY + timedelta(days=1), MONDAY + timedelta(days=7))


def test_bands_match_the_panel():
    monday = ref(63905.01, 65696.16)
    assert monday.band(HIGH) == pytest.approx((65900.35, 66079.47), abs=0.01)
    assert monday.band(LOW) == pytest.approx((63521.70, 63700.82), abs=0.01)
    month = ref(76325.98, 87220.00)
    assert month.band(HIGH) == pytest.approx((88461.92, 89551.32), abs=0.01)
    week = ref(55130.00, 65696.16)
    assert week.band(LOW) == pytest.approx((52868.84, 53925.46), abs=0.01)


def hours(closes, highs=None, lows=None, start=MONDAY + timedelta(days=1)):
    out = []
    for i, c in enumerate(closes):
        h = (highs or {}).get(i, c + 0.2)
        lo = (lows or {}).get(i, c - 0.2)
        out.append(Candle(time=start + i * timedelta(hours=1), open=c, high=h, low=lo, close=c, volume=1))
    return out


def test_sweep_and_real_break():
    sweep, = ext.ext_events(hours([108, 110.5, 109], highs={1: 111.5}), [ref()])
    assert (sweep.side, sweep.kind, sweep.touch, sweep.index, sweep.extreme) == (HIGH, ext.SWEEP, 1, 2, 111.5)
    broken, = ext.ext_events(hours([102, 98.5, 97], lows={1: 98.0}), [ref()])
    assert (broken.side, broken.kind, broken.index) == (LOW, ext.BREAK, 2)
    assert ext.ext_events(hours([108, 110.5, 109]), [ref()]) == []                   # 110.7 never reached the band (111.14)


def test_a_range_counts_only_after_it_closed_and_until_the_next_one():
    before = hours([109], highs={0: 111.5}, start=MONDAY + timedelta(hours=5))
    after = hours([109], highs={0: 111.5}, start=MONDAY + timedelta(days=8))
    assert ext.ext_events(before, [ref()]) == [] and ext.ext_events(after, [ref()]) == []


def test_reference_ranges_are_complete_periods():
    daily = [Candle(time=datetime(2026, 8, 31, tzinfo=timezone.utc) + timedelta(days=i), open=100, high=101 + i, low=99 - i, close=100, volume=1) for i in range(45)]
    mondays = ext.reference_ranges(daily, "Pazartesi")
    assert mondays[0].high == 101 and mondays[0].known.weekday() == 1
    weeks = ext.reference_ranges(daily, "Hafta")
    assert weeks[0].high == 107 and weeks[0].known == datetime(2026, 9, 7, tzinfo=timezone.utc) and len(weeks) == 6
    months = ext.reference_ranges(daily, "Ay")
    assert [(m.known.month, m.until.month) for m in months] == [(10, 11)]
