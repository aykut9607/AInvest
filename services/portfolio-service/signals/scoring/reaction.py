"""How often did price RESPECT a rule after the rule occurred? (4.4, Aykut's design of 25 Nov)

Two numbers per rule, asset and timeframe, never mixed:
  occurrence  how many times the rule happened (n)
  respect     in how many of them price then moved in the rule's direction

A rule gives events of two types:
  signal  known at the close of a bar, entry at that close
  level   a price known in advance; the event is the first touch, entry at the level
Respect = price covers k x ATR(14) in the rule's direction before it covers k x ATR against it, within HORIZON bars. The same
distance both ways makes a coin flip ~50 %. Neither side reached = not respected. Both in one bar = not respected (the order inside
a bar is unknown); on the touch bar only the adverse side counts, for the same reason.

The number alone means nothing: the control is the same rule on shuffled prices (null.py). Some rules bring their own control group
on top (e.g. the signals against the higher timeframe); then both have to be beaten.
Only the first SPLIT of every series is used; the rest stays untouched for the final check.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np

from signals.data.candles import Candle
from signals.structure.zigzag import wilder_atr

HORIZON = 60                # bars
WAIT = 200                  # bars to wait for the touch of a level
SPLIT = 0.7                 # share of the bars used for calibration
KS = (1.0, 2.0, 3.0)        # reaction sizes in ATR
UP, DOWN = 1, -1
WARMUP = 20


class Bars:
    """Arrays of one series."""

    def __init__(self, candles: Sequence[Candle]):
        self.open = np.array([c.open for c in candles])
        self.high = np.array([c.high for c in candles])
        self.low = np.array([c.low for c in candles])
        self.close = np.array([c.close for c in candles])
        self.volume = np.array([c.volume for c in candles])
        self.atr = np.array([np.nan if a is None else a for a in wilder_atr(candles)])
        self.end = len(candles)


@dataclass(frozen=True)
class Event:
    index: int                      # signal: the bar whose close decided it; level: the bar from which the level is known
    direction: int                  # UP / DOWN: the expected reaction
    price: float | None = None      # level events only
    until: int | None = None        # level events: last bar of the wait; target events: last bar of the race
    target: float | None = None     # signal events with their own finish lines instead of k x ATR
    stop: float | None = None


def race(b: Bars, i: int, entry: float, direction: int, unit: float, level: bool) -> list[tuple[bool, int]]:
    """For every k: (respected, bar at which it was decided). `i` is the entry bar."""
    stop = min(b.end, i + 1 + HORIZON)
    high, low = b.high[i + 1:stop], b.low[i + 1:stop]
    out = []
    for k in KS:
        target, against = entry + direction * k * unit, entry - direction * k * unit
        if level and ((b.low[i] <= against) if direction == UP else (b.high[i] >= against)):
            out.append((False, i))
            continue
        hit = high >= target if direction == UP else low <= target
        bad = low <= against if direction == UP else high >= against
        first_hit = int(hit.argmax()) if hit.any() else 10**9
        first_bad = int(bad.argmax()) if bad.any() else 10**9
        last = min(first_hit, first_bad)
        out.append((first_hit < first_bad, i + 1 + last if last < 10**9 else stop - 1))
    return out


def find_touch(b: Bars, e: Event) -> int | None:
    """First bar after `index` that reaches the level; None if the level is not ahead of the price."""
    if e.index + 1 >= b.end:
        return None
    here = b.close[e.index]
    if (here <= e.price) if e.direction == UP else (here >= e.price):
        return None
    last = min(b.end - 1, e.until if e.until is not None else e.index + WAIT)
    side = b.low[e.index + 1:last + 1] <= e.price if e.direction == UP else b.high[e.index + 1:last + 1] >= e.price
    return e.index + 1 + int(side.argmax()) if side.any() else None


def play(b: Bars, e: Event) -> tuple[int, list[tuple[bool, int]]] | None:
    """(entry bar, race result) or None when it cannot be judged."""
    if not WARMUP <= e.index < b.end - 2:
        return None
    if e.price is None:
        i, entry, unit = e.index, b.close[e.index], b.atr[e.index]
    else:
        i = find_touch(b, e)
        if i is None or i >= b.end - 2:
            return None
        entry = min(e.price, b.open[i]) if e.direction == UP else max(e.price, b.open[i])
        unit = b.atr[i - 1]
    if math.isnan(unit) or unit <= 0:
        return None
    if e.target is not None:
        last = min(b.end, (e.until or i + HORIZON) + 1)
        high, low = b.high[i + 1:last], b.low[i + 1:last]
        hit, bad = (high >= e.target, low <= e.stop) if e.direction == UP else (low <= e.target, high >= e.stop)
        a, z = int(hit.argmax()) if hit.any() else 10**9, int(bad.argmax()) if bad.any() else 10**9
        return i, [(a < z, i + 1 + min(a, z) if min(a, z) < 10**9 else last - 1)] * len(KS)
    return i, race(b, i, entry, e.direction, unit, e.price is not None)


def wilson(wins: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p, d = wins / n, 1 + z * z / n
    mid = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def p_value(wins: float, n: int, base_wins: float, base_n: int) -> float:
    """One-sided two-proportion test: how often luck alone gives a respect rate this far above the control's."""
    if n == 0 or base_n == 0:
        return 1.0
    pool = (wins + base_wins) / (n + base_n)
    se = math.sqrt(max(1e-12, pool * (1 - pool) * (1 / n + 1 / base_n)))
    return 0.5 * math.erfc((wins / n - base_wins / base_n) / se / math.sqrt(2))


@dataclass
class Result:
    seen: int = 0                                   # occurrences in the calibration period (a level may never be touched)
    n: int = 0                                      # occurrences that were judged
    wins: list[int] = field(default_factory=lambda: [0] * len(KS))
    own_n: int = 0                                  # the rule's own control group
    own: list[int] = field(default_factory=lambda: [0] * len(KS))
    samples: list[tuple[int, int, float, list[bool]]] = field(default_factory=list)      # entry bar, direction, entry price, respected per k
    percent: float = 0.0                            # median size of 1 ATR in percent of the price


def measure(b: Bars, events: Sequence[Event], control: Sequence[Event] | None = None) -> Result:
    """A case that starts before the previous one of the same direction was decided (at 1 ATR) is skipped: it would be the same case
    counted twice."""
    res, busy, sizes, played = Result(), {UP: -1, DOWN: -1}, [], []
    for e in events:
        if WARMUP <= e.index < b.end - 2:
            res.seen += 1
            r = play(b, e)
            if r:
                played.append((r[0], e, r[1]))
    for i, e, outcome in sorted(played, key=lambda x: x[0]):
        if i <= busy[e.direction]:
            continue
        busy[e.direction] = outcome[0][1]
        res.n += 1
        sizes.append(b.atr[i] / b.close[i] * 100)
        res.samples.append((i, e.direction, float(b.close[i] if e.price is None else e.price), [bool(w) for w, _ in outcome]))
        for k, (won, _) in enumerate(outcome):
            res.wins[k] += won
    res.percent = float(np.median(sizes)) if sizes else 0.0
    for e in control or ():
        r = play(b, e)
        if r:
            res.own_n += 1
            for k, (won, _) in enumerate(r[1]):
                res.own[k] += won
    return res
