"""Price-action detectors for PRICE_ACTION.md (intermediate lessons): market structure, levels, trend lines, wedges, triangles,
diamonds. Everything uses confirmed swings only (a swing exists from its confirmation bar on), so nothing looks ahead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signals.data.candles import Candle
from signals.structure.pivots import HIGH, LOW
from signals.structure.zigzag import SwingPoint

UP, DOWN = "up", "down"
BOS, MSB, CHOCH = "BOS", "MSB", "CHoCH"


# ---------- market structure (PA-01 ... PA-06)

def swing_labels(points: Sequence[SwingPoint]) -> list[tuple[SwingPoint, str]]:
    """HH / LH for tops and HL / LL for bottoms, each against the previous top / bottom."""
    last: dict[str, float] = {}
    out = []
    for p in points:
        if p.kind in last:
            higher = p.price > last[p.kind]
            out.append((p, ("HH" if higher else "LH") if p.kind == HIGH else ("HL" if higher else "LL")))
        last[p.kind] = p.price
    return out


@dataclass(frozen=True)
class Break:
    kind: str                 # BOS (with the trend) or MSB (against it)
    direction: str
    index: int                # bar whose CLOSE broke the level
    level: float
    level_index: int          # bar of the swing that was broken


def structure_breaks(candles: Sequence[Candle], points: Sequence[SwingPoint]) -> list[Break]:
    """Walk the bars. Trend up: close above the last top = BOS; close below the protected low (the last bottom before the
    top that made the newest BOS) = MSB and the trend turns. The mirror for a downtrend."""
    out: list[Break] = []
    waiting = sorted(points, key=lambda p: p.confirmed_at)
    k, trend = 0, None
    top = bottom = None                         # newest unbroken swings
    protected = None                            # swing whose break is an MSB
    last_top = last_bottom = None               # newest swings, broken or not
    broke_at = -1                               # bar of the newest break
    for i, c in enumerate(candles):
        while k < len(waiting) and waiting[k].confirmed_at < i:
            p = waiting[k]
            if p.kind == HIGH:
                top = last_top = p
            else:
                bottom = last_bottom = p
            # a fast break: the swing that made it is confirmed only after the break, and protects from its confirmation on
            if protected is not None and p.kind == protected.kind and protected.index < p.index <= broke_at:
                protected = p
            k += 1
        if protected is not None:
            against = c.close < protected.price if trend == UP else c.close > protected.price
            if against:
                trend, broke_at = (DOWN if trend == UP else UP), i
                out.append(Break(MSB, trend, i, protected.price, protected.index))
                broken = protected
                protected = last_top if trend == DOWN else last_bottom
                # levels the turn has already left behind are stale: only a NEW swing can give the next BOS
                if trend == DOWN and bottom is not None and (bottom is broken or bottom.price >= c.close):
                    bottom = None
                if trend == UP and top is not None and (top is broken or top.price <= c.close):
                    top = None
                continue
        if top is not None and c.close > top.price and trend in (UP, None):
            out.append(Break(BOS, UP, i, top.price, top.index))
            trend, protected, top, broke_at = UP, last_bottom, None, i
        elif bottom is not None and c.close < bottom.price and trend in (DOWN, None):
            out.append(Break(BOS, DOWN, i, bottom.price, bottom.index))
            trend, protected, bottom, broke_at = DOWN, last_top, None, i
    return out


def choch_breaks(candles: Sequence[Candle], points: Sequence[SwingPoint]) -> list[Break]:
    """CHoCH: the first close beyond the newest INNER swing against the trend while the protected swing still holds, i.e. the early
    sign before an MSB (one per leg: again only after a new BOS or MSB). What is an MSB on a lower timeframe is usually only a
    CHoCH on the higher one."""
    out: list[Break] = []
    turns = {b.index: b for b in structure_breaks(candles, points)}
    waiting = sorted(points, key=lambda p: p.confirmed_at)
    k, trend, fresh = 0, None, False
    top = bottom = None
    for i, c in enumerate(candles):
        while k < len(waiting) and waiting[k].confirmed_at < i:
            if waiting[k].kind == HIGH:
                top = waiting[k]
            else:
                bottom = waiting[k]
            k += 1
        if i in turns:
            trend, fresh = turns[i].direction, True
            continue
        if trend is None or not fresh:
            continue
        inner = top if trend == DOWN else bottom
        if inner is not None and (c.close > inner.price if trend == DOWN else c.close < inner.price):
            out.append(Break(CHOCH, UP if trend == DOWN else DOWN, i, inner.price, inner.index))
            fresh = False
    return out


# ---------- horizontal levels (PA-20 ...)

@dataclass(frozen=True)
class Level:
    price: float
    index: int                # bar of the turn
    kind: str                 # HIGH: closes turned down here, LOW: turned up


def body_levels(candles: Sequence[Candle]) -> list[Level]:
    """Where the candle bodies turn: an up candle followed by a down candle (its close), and the mirror."""
    out = []
    for i in range(len(candles) - 1):
        a, b = candles[i], candles[i + 1]
        if a.close > a.open and b.close < b.open:
            out.append(Level(a.close, i, HIGH))
        elif a.close < a.open and b.close > b.open:
            out.append(Level(a.close, i, LOW))
    return out


def monthly(candles: Sequence[Candle]) -> list[Candle]:
    """Calendar months from daily candles."""
    out: list[Candle] = []
    for c in candles:
        if out and (out[-1].time.year, out[-1].time.month) == (c.time.year, c.time.month):
            m = out[-1]
            out[-1] = Candle(time=m.time, open=m.open, high=max(m.high, c.high), low=min(m.low, c.low), close=c.close,
                             volume=m.volume + c.volume)
        else:
            out.append(Candle(time=c.time, open=c.open, high=c.high, low=c.low, close=c.close, volume=c.volume))
    return out


# ---------- two-line patterns (PA-30 ...)

RISING_WEDGE, FALLING_WEDGE, SYMMETRIC = "rising wedge", "falling wedge", "symmetric triangle"


@dataclass(frozen=True)
class Pattern:
    kind: str
    points: tuple[SwingPoint, ...]
    upper: tuple[int, float, float]      # anchor bar, price there, slope per bar
    lower: tuple[int, float, float]
    apex: float                          # bar where the lines meet
    height: float                        # widest part
    break_index: int | None              # first close outside after the pattern was known
    break_direction: str | None

    def line(self, side: str, i: float) -> float:
        anchor, price, slope = self.upper if side == "upper" else self.lower
        return price + slope * (i - anchor)


def converging_patterns(candles: Sequence[Candle], points: Sequence[SwingPoint], touches: int = 5,
                        tolerance: float = 0.1, min_bars: int = 15, min_leg: float = 0.5) -> list[Pattern]:
    """Runs of `touches` alternating swings between two converging lines; the lines go through the first and last top and
    the first and last bottom, the swings between may miss their line by `tolerance` x the height. Every leg must keep at
    least `min_leg` of the leg before it: a big move followed by small swings is not part of the pattern. The height is
    measured where both lines already exist (the second swing)."""
    out = []
    for s in range(len(points) - touches + 1):
        run = tuple(points[s:s + touches])
        tops, bottoms = [p for p in run if p.kind == HIGH], [p for p in run if p.kind == LOW]
        if len(tops) < 2 or len(bottoms) < 2:
            continue
        up = (tops[0].index, tops[0].price, (tops[-1].price - tops[0].price) / (tops[-1].index - tops[0].index))
        lo = (bottoms[0].index, bottoms[0].price,
              (bottoms[-1].price - bottoms[0].price) / (bottoms[-1].index - bottoms[0].index))
        if up[2] >= lo[2]:
            continue
        start, end = run[0].index, run[-1].index
        at = lambda ln, i: ln[1] + ln[2] * (i - ln[0])
        second = run[1].index
        height = at(up, second) - at(lo, second)
        if height <= 0 or at(up, end) <= at(lo, end) or end - start < min_bars:
            continue
        legs = [abs(q.price - p.price) for p, q in zip(run, run[1:])]
        if any(later < min_leg * earlier for earlier, later in zip(legs, legs[1:])):
            continue
        apex = second + height / (lo[2] - up[2])
        if not end < apex <= end + 1.5 * (end - start):
            continue
        if any(abs(p.price - at(up, p.index)) > tolerance * height for p in tops) or \
                any(abs(p.price - at(lo, p.index)) > tolerance * height for p in bottoms):
            continue
        if any(c.close > at(up, start + j) + tolerance * height or c.close < at(lo, start + j) - tolerance * height
               for j, c in enumerate(candles[start:end + 1])):
            continue
        flat = 0.15 * height / (end - start)                            # slopes smaller than this count as flat
        if up[2] > flat and lo[2] > flat:
            kind = RISING_WEDGE
        elif up[2] < -flat and lo[2] < -flat:
            kind = FALLING_WEDGE
        elif up[2] < -flat and lo[2] > flat:
            kind = SYMMETRIC
        else:
            continue
        known, bi, bd = run[-1].confirmed_at, None, None
        for i in range(end + 1, min(len(candles), int(apex) + 1)):
            if candles[i].close > at(up, i):
                bi, bd = i, UP
            elif candles[i].close < at(lo, i):
                bi, bd = i, DOWN
            if bi is not None:
                break
        if bi is not None and bi < known:
            continue                                                    # broke before the last swing was even confirmed
        out.append(Pattern(kind, run, up, lo, apex, height, bi, bd))
    return out


@dataclass(frozen=True)
class Diamond:
    points: tuple[SwingPoint, ...]       # six alternating swings
    break_index: int | None
    break_direction: str | None
    height: float


def diamonds(candles: Sequence[Candle], points: Sequence[SwingPoint]) -> list[Diamond]:
    """Six alternating swings a b c d e f: first wider (c beyond a, d beyond b), then narrower (e inside c, f inside d).
    Right-hand boundaries: c-e and d-f; the break is a close outside them."""
    out = []
    for s in range(len(points) - 5):
        a, b, c, d, e, f = run = tuple(points[s:s + 6])
        sign = 1 if a.kind == HIGH else -1
        v = [sign * p.price for p in run]
        if not (v[2] > v[0] and v[3] < v[1] and v[4] < v[2] and v[5] > v[3]):
            continue
        top_line = (c, e) if a.kind == HIGH else (d, f)
        low_line = (d, f) if a.kind == HIGH else (c, e)
        at = lambda ln, i: ln[0].price + (ln[1].price - ln[0].price) / (ln[1].index - ln[0].index) * (i - ln[0].index)
        bi = bd = None
        for i in range(f.confirmed_at, min(len(candles), f.confirmed_at + 2 * (f.index - a.index))):
            if at(top_line, i) <= at(low_line, i):
                break
            if candles[i].close > at(top_line, i):
                bi, bd = i, UP
            elif candles[i].close < at(low_line, i):
                bi, bd = i, DOWN
            if bi is not None:
                break
        out.append(Diamond(run, bi, bd, abs(c.price - d.price)))
    return out


# ---------- trend lines (PA-10 ...)

@dataclass(frozen=True)
class TrendLine:
    direction: str                       # UP: rising support through bottoms, DOWN: falling resistance through tops
    touches: tuple[SwingPoint, ...]      # three swings
    break_index: int | None              # first close beyond the line
    retest_index: int | None             # first touch of the line from the other side after the break

    def at(self, i: float) -> float:
        a, b = self.touches[0], self.touches[-1]
        return a.price + (b.price - a.price) / (b.index - a.index) * (i - a.index)


def trend_lines(candles: Sequence[Candle], points: Sequence[SwingPoint], tolerance: float = 0.005,
                retest_bars: int = 20) -> list[TrendLine]:
    """Three consecutive bottoms (tops) on one rising (falling) line; the middle one within `tolerance` of it."""
    out = []
    for kind, direction in ((LOW, UP), (HIGH, DOWN)):
        same = [p for p in points if p.kind == kind]
        for a, b, c in zip(same, same[1:], same[2:]):
            sign = 1 if direction == UP else -1
            if not (sign * a.price < sign * b.price < sign * c.price):
                continue
            line = lambda i: a.price + (c.price - a.price) / (c.index - a.index) * (i - a.index)
            if abs(b.price / line(b.index) - 1) > tolerance:
                continue
            if any(sign * candles[i].close < sign * line(i) for i in range(a.index, c.index)):
                continue
            bi = next((i for i in range(c.confirmed_at, len(candles)) if sign * candles[i].close < sign * line(i)), None)
            ri = None
            if bi is not None:
                for i in range(bi + 1, min(len(candles), bi + 1 + retest_bars)):
                    if (candles[i].high >= line(i)) if direction == UP else (candles[i].low <= line(i)):
                        ri = i
                        break
            out.append(TrendLine(direction, (a, b, c), bi, ri))
    return out
