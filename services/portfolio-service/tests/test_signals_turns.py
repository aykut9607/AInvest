"""Confirmations at turning points: the parts that need no data files."""

from datetime import datetime, timedelta, timezone

from signals.data.candles import Candle
from signals.scoring.turns import Path15, elliott_kinds, harmonic_names, key_levels, make_levels
from signals.scoring.turns_report import idea
from signals.structure.zigzag import SwingPoint

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
DAY = timedelta(days=1)


def daily(*rows):
    return [Candle(START + i * DAY, o, h, l, c, 1.0) for i, (o, h, l, c) in enumerate(rows)]


def points(*prices):
    up = prices[1] > prices[0]
    return [SwingPoint("low" if (i % 2 == 0) == up else "high", i * 10, p, i * 10) for i, p in enumerate(prices)]


def test_key_level_is_the_body_turn_known_after_the_second_candle():
    cs = daily((88000, 91000, 87500, 90500), (90500, 90950, 88000, 88500), (88500, 89000, 87000, 88000))
    assert key_levels(cs, "D") == [(START + 2 * DAY, 90500, -1)]
    higher = daily((88000, 91000, 87500, 90500), (90500, 92000, 88000, 88500), (88500, 89000, 87000, 88000))
    assert key_levels(higher, "D") == []                              # the next day traded well above it: not a key level


def test_a_level_is_used_up_by_its_first_touch():
    path = Path15([Candle(START + i * timedelta(minutes=15), p, p + 1, p - 1, p, 1.0) for i, p in enumerate([100] * 10 + [110] * 100 + [100] * 10 + [110] * 10)])
    t = path.t
    lv = make_levels([(float(t[0]), 110.0, -1, None)], path)
    assert lv.hit(-1, float(t[12]), 110.2, 0.5)                       # the first touch
    assert not lv.hit(-1, float(t[-1]), 110.2, 0.5)                   # the second time it is no longer fresh
    assert not lv.hit(1, float(t[12]), 110.2, 0.5)                    # a resistance does not act on a bottom


def test_reaction_counts_only_until_the_top_is_exceeded():
    path = Path15([Candle(START + i * timedelta(minutes=15), p, p + 0.5, p - 0.5, p, 1.0) for i, p in enumerate([99, 97, 95, 99, 101, 80])])
    assert path.reaction(float(path.t[0]), float(path.t[-1]) + 900, 100.0, -1) == 100.0 - 94.5      # 80 comes after the new high: not counted


def test_elliott_and_harmonic_names_at_the_last_point():
    assert any(k.startswith("itki 12345") for k in elliott_kinds(points(100, 110, 105, 125, 118, 130)))
    assert "ABC zigzag" in elliott_kinds(points(130, 110, 120, 100))
    assert "AB=CD" in harmonic_names(points(100, 120, 108, 128))
    assert idea("RSI uyumsuzluk") == "Uyumsuzluk" and idea("Fib reshort/relong 4h") == "Fib reshort/relong"
