"""The user's four Fibonacci drawings as numbers (FIBONACCI.md). The level sets are the user's TradingView settings.

  trend_extension(p0, p1, p2)  level k = p2 + k x (p1 - p0)            three points: wave start, wave end, pullback end
  retracement(start, end)      level r = end - r x (end - start)       0 = end of the move, 1 = its start
  monday_range(high, low)      level r = high - r x (high - low)       0 = Monday high, 1 = Monday low; negative = above
"""

from __future__ import annotations

from dataclasses import dataclass

SUPPORT, EQUAL, TRIGGER, TARGET, FAR, POCKET, MIDDLE, EDGE, SWEEP, DEEP, MINOR = (
    "support", "equal", "trigger", "target", "far", "pocket", "middle", "edge", "sweep", "deep", "minor")


@dataclass(frozen=True)
class FibLevel:
    ratio: float
    price: float
    role: str


# roles follow the colours of the user's drawings
TREND = {0.618: SUPPORT, 0.786: SUPPORT, 1.0: EQUAL, 1.272: TRIGGER, 1.414: TARGET, 1.618: TARGET,
         **{r: FAR for r in (1.79, 2.0, 2.618, 2.79, 3.0, 3.618, 3.79, 4.0, 4.618, 4.79, 5.0, 5.618, 5.79, 6.0, 6.618, 6.79,
                             7.0, 7.618)}}
TREND_FINE = {0.0: EDGE, 0.236: MINOR, 0.382: MINOR, 0.5: MIDDLE, 0.618: SUPPORT, 0.786: SUPPORT, 0.886: MINOR, 1.0: EQUAL,
              1.114: SWEEP, 1.214: SWEEP, 1.272: TRIGGER, 1.34: MINOR, 1.382: MINOR, 1.618: TARGET, 2.618: FAR, 3.618: FAR,
              4.236: FAR}
RETRACEMENT = {0.0: EDGE, 0.114: MINOR, 0.236: MINOR, 0.34: POCKET, 0.382: POCKET, 0.5: MIDDLE, 0.618: POCKET, 0.66: POCKET,
               0.709: POCKET, 0.786: DEEP, 0.886: DEEP, 1.0: EDGE}
MONDAY = {-2.618: FAR, -1.618: FAR, -0.618: DEEP, -0.214: SWEEP, -0.114: SWEEP, 0.5: MIDDLE, 1.114: SWEEP, 1.214: SWEEP,
          1.618: DEEP, 2.618: FAR, 3.618: FAR}


def trend_extension(p0: float, p1: float, p2: float, levels: dict[float, str] = TREND) -> list[FibLevel]:
    if not min(p0, p1) <= p2 <= max(p0, p1):
        raise ValueError("point 2 must lie between points 0 and 1 (the pullback may not pass the start)")
    return [FibLevel(k, p2 + k * (p1 - p0), role) for k, role in sorted(levels.items())]


def retracement(start: float, end: float, levels: dict[float, str] = RETRACEMENT) -> list[FibLevel]:
    if start == end:
        raise ValueError("the move has no length")
    return [FibLevel(r, end - r * (end - start), role) for r, role in sorted(levels.items())]


def monday_range(high: float, low: float, levels: dict[float, str] = MONDAY) -> list[FibLevel]:
    if high <= low:
        raise ValueError("high must be above low")
    return [FibLevel(r, high - r * (high - low), role) for r, role in sorted(levels.items())]


def wave1_end_as_extension(p0: float, p1: float, p2: float) -> float:
    """The extension level at which wave 1 ended = wave 2's retracement ratio. Below it wave 4 breaks E-04."""
    return (p1 - p2) / (p1 - p0)


def extension_as_retracement(k: float, e3: float) -> float:
    """Level k of the 0-1-2 extension written as a retracement of wave 3 when wave 3 ended at extension e3."""
    return 1 - k / e3
