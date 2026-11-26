"""Turning scanner candidates into tradeable setups for the backtest (and later for the live plan).

Elliott 0-1-2-3-4 (wave 5 to come): a rising impulse is sold at the wave-5 zone (short), a falling one bought (long);
  stop = the count's invalidation level, target = the key level (end of wave 4).
Elliott S-A-B (C to come): the correction is expected to end in the C zone, then the trend resumes: a falling A
  (correction of a rise) is bought at the C zone, a rising A sold. Target = B, stop = 2.618 x A.
Harmonic X-A-B-C: bullish patterns are bought at the PRZ, bearish ones sold; stop = the pattern's invalidation level,
  target = 0.382 of AD.
Only the main model is traded: of the candidates that end at the same swing point, the best fit (RULES.md 5).
A setup whose zone price is already past when it becomes known is skipped (there is nothing left to wait for).
"""

from __future__ import annotations

from collections.abc import Sequence

from signals.backtest.engine import LONG, SHORT, Setup
from signals.data.candles import Candle
from signals.patterns.elliott import DOWN, UP, abc_counts, impulse_counts
from signals.patterns.harmonic import BULLISH, developing_patterns
from signals.structure.zigzag import SwingPoint


def _best_per_end(candidates, key=lambda c: c.points[-1].index):
    best = {}
    for c in candidates:
        k = key(c)
        if k not in best or c.fit > best[k].fit:
            best[k] = c
    return list(best.values())


def _still_ahead(candles: Sequence[Candle], known_at: int, direction: str, zone) -> bool:
    if known_at >= len(candles):
        return False
    close = candles[known_at].close
    return zone.low > close if direction == SHORT else zone.high < close


def _describe(points: Sequence[SwingPoint], candles: Sequence[Candle]) -> str:
    return " ".join(f"{candles[p.index].time:%Y-%m-%d}:{p.price:.2f}" for p in points)


def elliott_setups(candles: Sequence[Candle], points: Sequence[SwingPoint], asset: str, timeframe: str) -> list[Setup]:
    setups = []
    developing = [c for c in impulse_counts(points) if not c.complete and c.wave5_zone is not None]
    for count in _best_per_end(developing):
        direction = SHORT if count.direction == UP else LONG
        if not _still_ahead(candles, count.known_at, direction, count.wave5_zone):
            continue
        setups.append(Setup(f"Elliott wave-5 zone ({count.kind})", asset, timeframe, direction, count.known_at,
                            count.wave5_zone, count.invalidation, count.key_level, _describe(count.points, candles)))
    corrections = [c for c in abc_counts(points) if len(c.points) == 3 and c.c_zone is not None]
    for count in _best_per_end(corrections, key=lambda c: (c.points[-1].index, c.kind)):
        direction = LONG if count.direction == DOWN else SHORT
        if not _still_ahead(candles, count.known_at, direction, count.c_zone):
            continue
        setups.append(Setup(f"Elliott C zone ({count.kind})", asset, timeframe, direction, count.known_at,
                            count.c_zone, count.invalidation, count.points[2].price, _describe(count.points, candles)))
    return setups


def harmonic_setups(candles: Sequence[Candle], points: Sequence[SwingPoint], asset: str, timeframe: str) -> list[Setup]:
    setups = []
    for pattern in _best_per_end(developing_patterns(points), key=lambda p: (p.points[-1].index, p.name)):
        direction = LONG if pattern.direction == BULLISH else SHORT
        if not _still_ahead(candles, pattern.known_at, direction, pattern.prz):
            continue
        setups.append(Setup(f"Harmonic {pattern.name} PRZ", asset, timeframe, direction, pattern.known_at,
                            pattern.prz, pattern.invalidation, pattern.target, _describe(pattern.points, candles)))
    return setups
