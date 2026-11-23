"""Detectors for SMART_MONEY.md (advanced lessons): candles, FVG, order block, breaker, range, supply / demand, equal highs and
lows, key levels, Power of 3. Every object carries `known_at`: the bar from whose close on it may be used (no look-ahead).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from signals.data.candles import Candle
from signals.rules.pa_detect import DOWN, MSB, UP, structure_breaks
from signals.structure.pivots import HIGH, LOW
from signals.structure.zigzag import SwingPoint, wilder_atr


@dataclass(frozen=True)
class Zone:
    kind: str
    direction: str            # UP: support / long idea, DOWN: resistance / short idea
    index: int                # bar the zone comes from
    low: float
    high: float
    known_at: int
    quality: tuple[str, ...] = ()

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2


def first_touch(candles: Sequence[Candle], zone: Zone) -> int | None:
    for i in range(zone.known_at + 1, len(candles)):
        c = candles[i]
        if (c.low <= zone.high) if zone.direction == UP else (c.high >= zone.low):
            return i
    return None


def closed_through(candles: Sequence[Candle], zone: Zone, start: int) -> int | None:
    """First close beyond the far side of the zone (the zone failed)."""
    for i in range(start, len(candles)):
        if (candles[i].close < zone.low) if zone.direction == UP else (candles[i].close > zone.high):
            return i
    return None


# ---------- candles (SM-01 ... SM-04)

PIN, ENGULFING, DOJI, INSIDE = "pin bar", "engulfing", "doji", "inside bar"


def candle_patterns(candles: Sequence[Candle]) -> list[tuple[int, str, str | None]]:
    """(bar, pattern, direction or None)"""
    out: list[tuple[int, str, str | None]] = []
    for i, c in enumerate(candles):
        span = c.high - c.low
        if span <= 0:
            continue
        body, up_wick, down_wick = abs(c.close - c.open), c.high - max(c.open, c.close), min(c.open, c.close) - c.low
        if body <= span / 3 and down_wick >= 0.6 * span:
            out.append((i, PIN, UP))
        elif body <= span / 3 and up_wick >= 0.6 * span:
            out.append((i, PIN, DOWN))
        elif body <= 0.1 * span:
            out.append((i, DOJI, None))
        if i:
            p = candles[i - 1]
            if c.high < p.high and c.low > p.low:
                out.append((i, INSIDE, None))
            if p.close < p.open and c.close > c.open and c.close > p.open and c.open <= p.close:
                out.append((i, ENGULFING, UP))
            if p.close > p.open and c.close < c.open and c.close < p.open and c.open >= p.close:
                out.append((i, ENGULFING, DOWN))
    return out


# ---------- fair value gap (SM-60 ...)

def fair_value_gaps(candles: Sequence[Candle], min_atr: float = 0.0) -> list[Zone]:
    atr = wilder_atr(candles)
    out = []
    for i in range(2, len(candles)):
        a, c = candles[i - 2], candles[i]
        if a.high < c.low:
            low, high, direction = a.high, c.low, UP
        elif a.low > c.high:
            low, high, direction = c.high, a.low, DOWN
        else:
            continue
        if min_atr and (atr[i] is None or high - low < min_atr * atr[i]):
            continue
        out.append(Zone("FVG", direction, i - 1, low, high, i))
    return out


# ---------- order block (SM-40 ...) and breaker (SM-50 ...)

def order_blocks(candles: Sequence[Candle], points: Sequence[SwingPoint]) -> list[Zone]:
    """The last opposite candle before the move whose CLOSE broke structure. Zone = the whole candle (the lesson enters at
    its 0.5). Quality: 'FVG' the move left a gap, 'sweep' the origin took out the previous swing first."""
    out = []
    gaps = fair_value_gaps(candles)
    for b in structure_breaks(candles, points):
        window = range(b.level_index, b.index + 1)
        if b.direction == UP:
            origin = min(window, key=lambda i: candles[i].low)
            block = next((i for i in range(origin + 1, b.level_index - 1, -1)
                          if i < b.index and candles[i].close < candles[i].open), None)
        else:
            origin = max(window, key=lambda i: candles[i].high)
            block = next((i for i in range(origin + 1, b.level_index - 1, -1)
                          if i < b.index and candles[i].close > candles[i].open), None)
        if block is None:
            continue
        quality = []
        if any(g.direction == b.direction and block < g.index <= b.index for g in gaps):
            quality.append("FVG")
        before = [p for p in points if p.kind == (LOW if b.direction == UP else HIGH) and p.index < b.level_index]
        if before:
            last = before[-1].price
            extreme = candles[origin].low if b.direction == UP else candles[origin].high
            if (extreme < last) if b.direction == UP else (extreme > last):
                quality.append("sweep")
        out.append(Zone("OB", b.direction, block, candles[block].low, candles[block].high, b.index, tuple(quality)))
    return out


def breakers(candles: Sequence[Candle], points: Sequence[SwingPoint]) -> list[Zone]:
    """After an MSB the broken swing changes its role: the candle of the broken low is resistance, of the broken high support.
    Zone: from the swing's extreme to the far side of its candle body."""
    out = []
    for b in structure_breaks(candles, points):
        if b.kind != MSB:
            continue
        c = candles[b.level_index]
        low, high = (c.low, max(c.open, c.close)) if b.direction == DOWN else (min(c.open, c.close), c.high)
        out.append(Zone("Breaker", b.direction, b.level_index, low, high, b.index))
    return out


# ---------- supply / demand (SM-10 ...)

def supply_demand(candles: Sequence[Candle], max_base: int = 3, base_atr: float = 0.6, move_atr: float = 1.5) -> list[Zone]:
    """A base of 1-3 small candles left by one strong candle (body >= move_atr x ATR). Zone = the base's range."""
    atr = wilder_atr(candles)
    out = []
    for i in range(1, len(candles)):
        a = atr[i - 1]
        if a is None:
            continue
        c = candles[i]
        if abs(c.close - c.open) < move_atr * a:
            continue
        base = []
        for j in range(i - 1, max(-1, i - 1 - max_base), -1):
            if abs(candles[j].close - candles[j].open) > base_atr * a:
                break
            base.append(j)
        if base:
            out.append(Zone("Arz-talep", UP if c.close > c.open else DOWN, base[-1], min(candles[j].low for j in base),
                            max(candles[j].high for j in base), i))
    return out


# ---------- range (SM-20 ...)

@dataclass(frozen=True)
class Range:
    start: int
    low: float
    high: float
    known_at: int
    points: tuple[SwingPoint, ...]

    @property
    def eq(self) -> float:
        return (self.low + self.high) / 2


@dataclass(frozen=True)
class Deviation:
    range: Range
    side: str                 # HIGH or LOW: which border was taken
    index: int                # first bar beyond the border
    back_index: int           # close back inside
    extreme: float


def ranges(points: Sequence[SwingPoint], tolerance: float = 0.15, min_bars: int = 20) -> list[Range]:
    """Four alternating swings over at least `min_bars` bars whose two tops and two bottoms agree within `tolerance` x the height."""
    out = []
    for s in range(len(points) - 3):
        run = tuple(points[s:s + 4])
        if run[-1].index - run[0].index < min_bars:
            continue
        tops, lows = [p.price for p in run if p.kind == HIGH], [p.price for p in run if p.kind == LOW]
        high, low = max(tops), min(lows)
        if max(tops) - min(tops) <= tolerance * (high - low) and max(lows) - min(lows) <= tolerance * (high - low):
            out.append(Range(run[0].index, low, high, run[-1].confirmed_at, run))
    return out


def deviations(candles: Sequence[Candle], rng: Range, back_bars: int = 3, watch: int = 120) -> list[Deviation]:
    """A border is passed by a wick or close and a close within `back_bars` is back inside. Two closes outside beyond that
    end the range (a real breakout)."""
    out, i = [], rng.known_at + 1
    while i < min(len(candles), rng.known_at + 1 + watch):
        c = candles[i]
        side = HIGH if c.high > rng.high else LOW if c.low < rng.low else None
        if side is None:
            i += 1
            continue
        back = next((j for j in range(i, min(len(candles), i + back_bars + 1)) if rng.low < candles[j].close < rng.high), None)
        if back is None:
            break
        part = candles[i:back + 1]
        out.append(Deviation(rng, side, i, back, max(x.high for x in part) if side == HIGH else min(x.low for x in part)))
        i = back + 1
    return out


# ---------- liquidity: equal highs / lows (SM-70 ...)

def equal_levels(candles: Sequence[Candle], points: Sequence[SwingPoint], within_atr: float = 0.25) -> list[tuple[SwingPoint, SwingPoint]]:
    atr = wilder_atr(candles)
    out = []
    for kind in (HIGH, LOW):
        same = [p for p in points if p.kind == kind]
        for a, b in zip(same, same[1:]):
            if atr[b.index] is not None and abs(a.price - b.price) <= within_atr * atr[b.index]:
                out.append((a, b))
    return sorted(out, key=lambda pair: pair[1].index)


# ---------- key levels (SM-80 ...)

def key_levels(daily: Sequence[Candle], when: datetime) -> dict[str, float]:
    """Levels known at `when` (00:00 of a day) from daily candles: previous day / week / month high, mid, low; Monday range (from
    Tuesday on); day, week, month opens need the open of the running period's first candle."""
    past = [c for c in daily if c.time < when]
    out: dict[str, float] = {}

    def add(name: str, part: list[Candle]) -> None:
        if part:
            high, low = max(c.high for c in part), min(c.low for c in part)
            out.update({f"{name} yüksek": high, f"{name} orta": (high + low) / 2, f"{name} düşük": low})

    add("Önceki gün", past[-1:])
    monday = (when - timedelta(days=when.weekday()))
    add("Önceki hafta", [c for c in past if monday - timedelta(days=7) <= c.time < monday])
    month = when.replace(day=1)
    previous = (month - timedelta(days=1)).replace(day=1)
    add("Önceki ay", [c for c in past if previous <= c.time < month])
    if when > monday:
        add("Pazartesi", [c for c in past if c.time == monday])
    for name, start in (("Hafta açılışı", monday), ("Ay açılışı", month)):
        first = next((c for c in past if c.time >= start), None)
        if first is not None:
            out[name] = first.open
    return out


# ---------- Power of 3 (SM-90 ...), 1h candles, UTC sessions

ASIA, LONDON, NEW_YORK = (0, 8), (8, 13), (13, 21)


@dataclass(frozen=True)
class PowerOf3:
    day: datetime
    first: int                # index of the day's first 1h bar
    low: float                # Asian range
    high: float
    swept: str                # HIGH / LOW taken in London with a 1h close back inside
    back_index: int
    distribution: int | None  # first New York bar beyond the opposite side
    known_at: int             # last London bar: only then is it certain that just one side was taken


def power_of_3(hourly: Sequence[Candle]) -> list[PowerOf3]:
    out = []
    days: dict = {}
    for i, c in enumerate(hourly):
        days.setdefault(c.time.date(), []).append(i)
    for day, idx in days.items():
        part = lambda session: [i for i in idx if session[0] <= hourly[i].time.hour < session[1]]
        asia, london, ny = part(ASIA), part(LONDON), part(NEW_YORK)
        if len(asia) < 8 or len(london) < 5 or not ny:
            continue
        low, high = min(hourly[i].low for i in asia), max(hourly[i].high for i in asia)
        swept = {HIGH: any(hourly[i].high > high for i in london), LOW: any(hourly[i].low < low for i in london)}
        if swept[HIGH] == swept[LOW]:
            continue
        side = HIGH if swept[HIGH] else LOW
        start = next(i for i in london if (hourly[i].high > high if side == HIGH else hourly[i].low < low))
        back = next((i for i in london if i >= start and low < hourly[i].close < high), None)
        if back is None:
            continue
        go = next((i for i in ny if (hourly[i].low < low if side == HIGH else hourly[i].high > high)), None)
        out.append(PowerOf3(hourly[idx[0]].time, idx[0], low, high, side, back, go, london[-1]))
    return out
