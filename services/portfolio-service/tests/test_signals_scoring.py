"""Reaction measurement and its shuffled-price control (no data files needed)."""

from datetime import datetime, timedelta, timezone

import pytest

from signals.data.candles import Candle, bucket_session, bucket_start_3d, in_threes, session_date, session_start
from signals.scoring.null import shuffle
from signals.scoring.reaction import DOWN, UP, Bars, Event, measure, p_value, play, wilson

START = datetime(2024, 1, 1, tzinfo=timezone.utc)


def bars(closes, wick=0.5, step=timedelta(hours=1)):
    out, last = [], closes[0]
    for i, c in enumerate(closes):
        out.append(Candle(START + i * step, last, max(last, c) + wick, min(last, c) - wick, c, 10.0 + i))
        last = c
    return out


def flat_then(*tail):
    return [100.0 + (i % 2) for i in range(40)] + list(tail)


def test_signal_is_respected_when_price_goes_its_way_first():
    b = Bars(bars(flat_then(103, 106, 110, 115, 118, 120)))
    won = play(b, Event(40, UP))[1]
    assert won[0][0] and not play(b, Event(40, DOWN))[1][0][0]


def test_level_needs_price_on_the_right_side_and_a_touch():
    b = Bars(bars(flat_then(99, 96, 92, 95, 99, 104, 108)))
    assert play(b, Event(38, UP, 150.0)) is None                      # above the price: not a support ahead
    assert play(b, Event(38, UP, 50.0)) is None                       # never reached
    assert play(b, Event(38, UP, 95.0))[0] == 42                      # first bar whose low reaches it


def test_a_touch_bar_that_runs_through_the_level_is_not_respect():
    closes = flat_then(60.0, 130.0, 140.0, 150.0)
    b = Bars(bars(closes))
    assert not play(b, Event(38, UP, 98.0))[1][0][0]


def test_overlapping_cases_are_counted_once():
    b = Bars(bars([100.0 + (i % 2) * 0.1 for i in range(120)], wick=5.0))
    r = measure(b, [Event(i, UP) for i in range(30, 40)])
    assert r.seen == 10 and r.n < 10


def test_shuffle_keeps_every_bar_shape_and_changes_the_order():
    source = bars([100 + (i * 7919 % 13) for i in range(24 * 60)])
    out = shuffle(source, 1, 4)
    shape = lambda cs: sorted(round((c.high - c.low) / p.close, 9) for p, c in zip(cs, cs[1:]))
    assert len(out) == len(source) and [c.time for c in out] == [c.time for c in source]
    assert shape(out) == shape(source)
    assert [round(c.volume) for c in out] != [round(c.volume) for c in source]
    assert out[-1].close == pytest.approx(source[-1].close)           # the same returns multiply to the same end


def test_p_value_and_wilson():
    assert p_value(50, 100, 500, 1000) == pytest.approx(0.5)
    assert p_value(70, 100, 500, 1000) < 0.001 and p_value(30, 100, 500, 1000) > 0.999
    low, high = wilson(50, 100)
    assert 0.40 < low < 0.5 < high < 0.60


def test_three_day_blocks():
    assert bucket_start_3d(datetime(2026, 11, 18, 5, tzinfo=timezone.utc)).date().isoformat() == "2026-11-16"   # Binance's own 3d opens
    days = bars([100.0] * 8, step=timedelta(days=1))
    assert [c.time.day for c in in_threes(days)] == [1, 4]            # the running block (7, 8 January) is left out


def test_gold_and_sp_sessions_follow_new_york_in_summer_and_winter():
    utc = lambda *a: datetime(*a, tzinfo=timezone.utc)
    assert session_date(utc(2026, 7, 5, 22, 0)).isoformat() == "2026-07-06"       # Sunday 18:00 New York (summer) = Monday's session
    assert session_date(utc(2026, 1, 4, 22, 30)).isoformat() == "2026-01-04"      # winter: 17:30 New York, still the old day
    assert bucket_session(utc(2026, 7, 6, 3, 15), 240) == utc(2026, 7, 6, 2, 0)   # 22:00 New York
    assert bucket_session(utc(2026, 1, 6, 3, 15), 240) == utc(2026, 1, 6, 3, 0)   # 22:00 New York
    assert session_start(utc(2026, 7, 6)) == utc(2026, 7, 5, 22) and session_start(utc(2026, 1, 6)) == utc(2026, 1, 5, 23)


def test_points_are_the_sure_part_of_the_edge():
    from signals.scoring.points import family, safe_edge
    assert safe_edge(60, 100, 0.5, 10**15) == pytest.approx(10 - 0.84 * 100 * (0.6 * 0.4 / 100) ** 0.5)
    assert safe_edge(600, 1000, 0.5, 10**6) > safe_edge(60, 100, 0.5, 10**6)          # the same edge is worth more with more cases
    assert family("fr_0.618") == family("ote") == "fib" and family("sfp_rsi") == "sfp"
