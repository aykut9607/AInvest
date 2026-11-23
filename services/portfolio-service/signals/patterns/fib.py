"""Fibonacci helpers shared by the Elliott and harmonic scanners (RULES.md 4).

Prices are handled "up-normalised": v = sign x price, with sign +1 for a structure that rises from its start and -1 for
one that falls. Every rule can then be written once, for the rising case; levels go back to prices with price = v / sign.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TOLERANCE = 0.03          # +-3% relative: 0.786 accepts 0.762 .. 0.810 (user's choice, 23 Nov 2026)
FALLOFF = 0.15            # outside the tolerance a ratio's fit drops linearly to 0 over another 15%


def near(x: float, target: float, tol: float = TOLERANCE) -> bool:
    return target != 0 and abs(x / target - 1) <= tol


def in_range(x: float, low: float, high: float, tol: float = TOLERANCE) -> bool:
    return low * (1 - tol) <= x <= high * (1 + tol)


def fit_to_targets(x: float, targets: list[float], tol: float = TOLERANCE) -> float:
    """1.0 when x is within the tolerance of one of the targets, falling to 0 further away."""
    if not targets:
        return 0.0
    best = min(abs(x / t - 1) for t in targets if t != 0)
    return 1.0 if best <= tol else max(0.0, 1 - (best - tol) / FALLOFF)


def fit_to_range(x: float, low: float, high: float, tol: float = TOLERANCE) -> float:
    if in_range(x, low, high, tol):
        return 1.0
    distance = (low - x) / low if x < low else (x - high) / high
    return max(0.0, 1 - (distance - tol) / FALLOFF)


@dataclass(frozen=True)
class Level:
    name: str             # e.g. "2-3-4 ext 1.0", "[5]=[1]", "XA 0.786"
    price: float


@dataclass(frozen=True)
class Zone:
    low: float
    high: float
    members: tuple[Level, ...] = field(default_factory=tuple)

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2


def cluster(levels: list[Level], width: float, anchor: Level | None = None) -> Zone | None:
    """The tightest group of levels: the level with most neighbours within `width` (absolute price distance), or the
    group around `anchor` when one is given (the harmonic PRZ is built around its defining XA level). On a tie the
    level listed first wins, so callers list the most common ratio first (e.g. C = A before C = 1.618 A).
    A single level becomes a zone of +-width/4 around it."""
    if not levels:
        return None
    if anchor is None:
        neighbours = [sum(abs(o.price - lv.price) <= width for o in levels) for lv in levels]
        centre = levels[max(range(len(levels)), key=lambda i: (neighbours[i], -i))]
    else:
        centre = anchor
    members = tuple(sorted((lv for lv in levels if abs(lv.price - centre.price) <= width), key=lambda lv: lv.price))
    if anchor is not None and anchor not in members:
        members = tuple(sorted(members + (anchor,), key=lambda lv: lv.price))
    low, high = min(m.price for m in members), max(m.price for m in members)
    if low == high:
        low, high = low - width / 4, high + width / 4
    return Zone(low=low, high=high, members=members)
