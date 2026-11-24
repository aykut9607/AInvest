"""EXT bands (MENTOR_VIEW.md, MB-20): 1.114-1.214 of a closed reference range (Monday, previous week, previous month), above the
high and below the low. Price that enters the band and closes back inside the range = sweep; a close beyond the band = real break.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from signals.data.candles import Candle
from signals.structure.pivots import HIGH, LOW

EXT1, EXT2 = 0.114, 0.214
SWEEP, BREAK = "süpürme", "gerçek kırılım"


@dataclass(frozen=True)
class RefRange:
    name: str
    low: float
    high: float
    known: datetime           # the reference candle / period has closed
    until: datetime           # the range is replaced by the next one

    def band(self, side: str) -> tuple[float, float]:
        size = self.high - self.low
        if side == HIGH:
            return self.high + EXT1 * size, self.high + EXT2 * size
        return self.low - EXT2 * size, self.low - EXT1 * size


@dataclass(frozen=True)
class ExtEvent:
    range: RefRange
    side: str                 # HIGH or LOW
    kind: str                 # SWEEP or BREAK
    touch: int                # bar that reached the band
    index: int                # bar whose close decided it
    extreme: float            # furthest price up to then


def reference_ranges(daily: Sequence[Candle], kind: str) -> list[RefRange]:
    """kind: "Pazartesi", "Hafta" or "Ay" (UTC periods). Only complete periods."""
    by = {c.time: c for c in daily}
    out = []
    if kind == "Pazartesi":
        for c in daily:
            if c.time.weekday() == 0:
                out.append(RefRange(kind, c.low, c.high, c.time + timedelta(days=1), c.time + timedelta(days=7)))
        return out
    groups: dict[datetime, list[Candle]] = {}
    for c in daily:
        key = c.time - timedelta(days=c.time.weekday()) if kind == "Hafta" else c.time.replace(day=1)
        groups.setdefault(key, []).append(c)
    for key, part in sorted(groups.items()):
        end = key + timedelta(days=7) if kind == "Hafta" else (key + timedelta(days=32)).replace(day=1)
        if part[0].time != key or end - timedelta(days=1) not in by:
            continue
        until = end + timedelta(days=7) if kind == "Hafta" else (end + timedelta(days=32)).replace(day=1)
        out.append(RefRange(kind, min(c.low for c in part), max(c.high for c in part), end, until))
    return out


def ext_events(candles: Sequence[Candle], ranges: Sequence[RefRange]) -> list[ExtEvent]:
    """First decided event per range and side: after the band is reached, the first close back inside the range (SWEEP) or beyond
    the band (BREAK). `candles` are the closes that count (the lower timeframe)."""
    out = []
    times = [c.time for c in candles]
    from bisect import bisect_left
    for r in ranges:
        first, last = bisect_left(times, r.known), bisect_left(times, r.until)
        for side in (HIGH, LOW):
            low, high = r.band(side)
            touch, extreme = None, None
            for i in range(first, last):
                c = candles[i]
                edge = c.high if side == HIGH else c.low
                if touch is None and ((edge >= low) if side == HIGH else (edge <= high)):
                    touch = i
                if touch is None:
                    continue
                extreme = edge if extreme is None else (max(extreme, edge) if side == HIGH else min(extreme, edge))
                if (c.close > high) if side == HIGH else (c.close < low):
                    out.append(ExtEvent(r, side, BREAK, touch, i, extreme))
                    break
                if r.low < c.close < r.high:
                    out.append(ExtEvent(r, side, SWEEP, touch, i, extreme))
                    break
    return sorted(out, key=lambda e: e.index)
