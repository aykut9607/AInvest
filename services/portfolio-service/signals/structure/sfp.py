"""SFP (swing failure pattern): a sweep of the last swing low/high that fails (RULES.md 3).

Bullish, on the candles of the timeframe being looked at:
  one candle: the candle trades below the last confirmed pivot low and closes back ABOVE it;
  two candles: the candle closes below the pivot low and the very next candle closes back above it.
Bearish: the mirror around the last confirmed pivot high.
A pivot gives at most one SFP. If price closes beyond it and the next candle does not come back, the break is real and
that level is dropped. Only pivots already confirmed before the sweep candle are used (no look-ahead).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signals.data.candles import Candle
from signals.structure.pivots import Pivot, pivot_highs, pivot_lows

BULLISH = "bullish"
BEARISH = "bearish"


@dataclass(frozen=True)
class Sfp:
    direction: str        # BULLISH (swept a low) or BEARISH (swept a high)
    level: float          # the swept pivot's price
    pivot_index: int      # bar of the swept pivot
    sweep_index: int      # bar that went beyond the level
    confirmed_at: int     # bar whose close came back (= sweep_index for one candle, +1 for two candles)
    candles: int          # 1 or 2
    extreme: float        # lowest low (bullish) / highest high (bearish) of the sweep: a natural invalidation level


def _scan(candles: Sequence[Candle], levels: list[Pivot], direction: str) -> list[Sfp]:
    found: list[Sfp] = []
    queue = sorted(levels, key=lambda p: p.confirmed_at)
    next_level = 0
    active: Pivot | None = None     # the most recent confirmed pivot not yet used or broken
    i = 0
    while i < len(candles):
        # a pivot confirmed at bar k may be swept from bar k + 1 on
        while next_level < len(queue) and queue[next_level].confirmed_at < i:
            active = queue[next_level]
            next_level += 1
        if active is None:
            i += 1
            continue

        c = candles[i]
        level = active.value
        beyond = c.low < level if direction == BULLISH else c.high > level
        if not beyond:
            i += 1
            continue

        closed_back = c.close > level if direction == BULLISH else c.close < level
        if closed_back:
            found.append(Sfp(direction, level, active.index, i, i, 1, c.low if direction == BULLISH else c.high))
            active = None
            i += 1
            continue

        # closed beyond: an SFP only if the next candle closes back
        if i + 1 < len(candles):
            n = candles[i + 1]
            if (n.close > level) if direction == BULLISH else (n.close < level):
                extreme = min(c.low, n.low) if direction == BULLISH else max(c.high, n.high)
                found.append(Sfp(direction, level, active.index, i, i + 1, 2, extreme))
        active = None   # used (SFP) or broken for real
        i += 1
    return found


def find_sfps(candles: Sequence[Candle], left: int = 5, right: int = 5) -> list[Sfp]:
    """Bullish and bearish SFPs, ordered by the bar they are confirmed at."""
    lows = pivot_lows([c.low for c in candles], left, right)
    highs = pivot_highs([c.high for c in candles], left, right)
    return sorted(_scan(candles, lows, BULLISH) + _scan(candles, highs, BEARISH), key=lambda s: s.confirmed_at)
