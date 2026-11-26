"""Pivots, the same way TradingView's ta.pivothigh / ta.pivotlow find them.

A bar is a pivot high when its value is above the `left` bars before it and not below the `right` bars after it
(a pivot low: the mirror). The pivot is only KNOWN once the `right`-th bar after it has closed: that bar is the
confirmation bar, and a replay/backtest may use the pivot only from there on (no look-ahead).

Ties: on the left side the pivot must be strictly higher (lower), on the right side equal is allowed, so of two equal
highs next to each other the first one is the pivot. This matches how ta.pivothigh is commonly reproduced; it is checked
against TradingView labels when the rules are validated (RULES.md 3).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

HIGH = "high"
LOW = "low"


@dataclass(frozen=True)
class Pivot:
    kind: str            # HIGH or LOW
    index: int           # bar of the pivot itself
    value: float         # the series value at the pivot (price, RSI, CVD ...)
    confirmed_at: int    # bar from which the pivot is known: index + right


def pivots(values: Sequence[float | None], left: int, right: int, kind: str) -> list[Pivot]:
    """All pivots of one kind, oldest first. None values (warm-up of an indicator) never form or break a pivot."""
    if left < 1 or right < 0:
        raise ValueError("left must be >= 1 and right >= 0")
    found = []
    for i in range(left, len(values) - right):
        center = values[i]
        if center is None:
            continue
        window_left = values[i - left:i]
        window_right = values[i + 1:i + 1 + right]
        if any(v is None for v in window_left) or any(v is None for v in window_right):
            continue
        if kind == HIGH:
            is_pivot = all(center > v for v in window_left) and all(center >= v for v in window_right)
        else:
            is_pivot = all(center < v for v in window_left) and all(center <= v for v in window_right)
        if is_pivot:
            found.append(Pivot(kind=kind, index=i, value=center, confirmed_at=i + right))
    return found


def pivot_highs(values: Sequence[float | None], left: int = 5, right: int = 5) -> list[Pivot]:
    return pivots(values, left, right, HIGH)


def pivot_lows(values: Sequence[float | None], left: int = 5, right: int = 5) -> list[Pivot]:
    return pivots(values, left, right, LOW)
