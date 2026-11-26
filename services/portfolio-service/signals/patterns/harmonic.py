"""Harmonic XABCD patterns (Carney's ratios, RULES.md 6) on alternating ZigZag points.

complete_patterns(): five consecutive points X-A-B-C-D whose ratios match a pattern.
developing_patterns(): four points X-A-B-C whose ratios match so far, with the PRZ where D should complete; this is
  what a plan watches ("if price reaches the PRZ, look for the LTF confirmation").
Bullish pattern = X low, A high, B low, C high, D low (D is a buying zone); bearish = the mirror.

Ratios (absolute legs): B = AB / XA, C = BC / AB, D = AD / XA (retracement of XA from A; > 1 means beyond X),
BC projection = CD / BC, AB=CD = CD / AB. Tolerance +-3% (fib.TOLERANCE). Required for every pattern: C within
0.382-0.886 of AB and CD >= AB.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signals.patterns.fib import Level, Zone, cluster, fit_to_targets, in_range, near
from signals.structure.pivots import LOW
from signals.structure.zigzag import SwingPoint

BULLISH, BEARISH = "bullish", "bearish"


@dataclass(frozen=True)
class PatternSpec:
    name: str
    b: tuple[float, float] | float      # a point ratio, or a (low, high) range of XA
    d: float                            # the defining XA level of D
    bc: tuple[float, float]             # CD / BC range
    abcd: tuple[float, ...]             # usual AB=CD ratios (fit only, not required)
    invalid_xa: float                   # beyond this XA level the pattern is wrong (our choice, RULES.md 6)


SPECS = [
    PatternSpec("Gartley", 0.618, 0.786, (1.27, 1.618), (1.0,), 1.0),
    PatternSpec("Bat", (0.382, 0.5), 0.886, (1.618, 2.618), (1.0, 1.27), 1.13),
    PatternSpec("Alternate Bat", (0.0, 0.382), 1.13, (2.0, 3.618), (1.618,), 1.272),
    PatternSpec("Butterfly", 0.786, 1.27, (1.618, 2.618), (1.0, 1.27), 1.414),
    PatternSpec("Crab", (0.382, 0.618), 1.618, (2.24, 3.618), (1.27, 1.618), 2.0),
    PatternSpec("Deep Crab", (0.886, 0.999), 1.618, (2.24, 3.618), (1.27,), 2.0),
]
C_RANGE = (0.382, 0.886)


@dataclass
class HarmonicPattern:
    name: str
    direction: str                      # BULLISH (D is a low: buy) or BEARISH (D is a high: sell)
    points: tuple[SwingPoint, ...]      # X, A, B, C (+ D)
    ratios: dict[str, float]
    fit: float                          # 0-100
    known_at: int
    prz: Zone | None = None             # developing only
    invalidation: float | None = None
    target: float | None = None         # first target: 0.382 of AD (from the PRZ's defining level)


def _b_ok(spec: PatternSpec, rb: float) -> bool:
    if isinstance(spec.b, tuple):
        low, high = spec.b
        return (rb <= high * 1.03) if low == 0.0 else in_range(rb, low, high)
    return near(rb, spec.b)


def _legs(run: Sequence[SwingPoint]) -> tuple[int, list[float]] | None:
    sign = 1 if run[0].kind == LOW else -1            # bullish: X low -> v = price; bearish: v = -price
    v = [sign * p.price for p in run]
    xa, ab, bc = v[1] - v[0], v[1] - v[2], v[3] - v[2]
    if xa <= 0 or ab <= 0 or bc <= 0:
        return None
    return sign, v


def developing_patterns(points: Sequence[SwingPoint]) -> list[HarmonicPattern]:
    found = []
    for i in range(len(points) - 3):
        run = tuple(points[i:i + 4])
        legs = _legs(run)
        if legs is None:
            continue
        sign, v = legs
        xa, ab, bc = v[1] - v[0], v[1] - v[2], v[3] - v[2]
        rb, rc = ab / xa, bc / ab
        if not in_range(rc, *C_RANGE):
            continue
        for spec in SPECS:
            if not _b_ok(spec, rb):
                continue
            d_v = v[1] - spec.d * xa                     # the defining XA level
            cd = v[3] - d_v
            if cd <= 0 or not in_range(cd / bc, *spec.bc) or cd < ab * 0.97:
                continue                                 # D at its XA level would break BC or CD >= AB
            to_price = lambda x: x / sign
            anchor = Level(f"XA {spec.d}", to_price(d_v))
            others = [Level(f"BC {k}", to_price(v[3] - k * bc)) for k in spec.bc]
            others += [Level(f"AB=CD {k}", to_price(v[3] - k * ab)) for k in spec.abcd]
            prz = cluster([anchor] + others, 0.05 * xa, anchor=anchor)
            fit = round(100 * (fit_to_targets(cd / ab, list(spec.abcd)) + 1 + 1) / 3, 1)
            found.append(HarmonicPattern(
                name=spec.name, direction=BULLISH if sign == 1 else BEARISH, points=run,
                ratios={"B": rb, "C": rc, "D_at_xa": spec.d, "BC_at_D": cd / bc, "ABCD_at_D": cd / ab},
                fit=fit, known_at=run[-1].confirmed_at, prz=prz,
                invalidation=to_price(v[1] - spec.invalid_xa * xa),
                target=to_price(d_v + 0.382 * (v[1] - d_v))))
    return found


def complete_patterns(points: Sequence[SwingPoint]) -> list[HarmonicPattern]:
    found = []
    for i in range(len(points) - 4):
        run = tuple(points[i:i + 5])
        legs = _legs(run)
        if legs is None:
            continue
        sign, v = legs
        xa, ab, bc, cd = v[1] - v[0], v[1] - v[2], v[3] - v[2], v[3] - v[4]
        if cd <= 0:
            continue
        rb, rc, rd = ab / xa, bc / ab, (v[1] - v[4]) / xa
        if not in_range(rc, *C_RANGE) or cd < ab * 0.97:
            continue
        for spec in SPECS:
            if not (_b_ok(spec, rb) and near(rd, spec.d) and in_range(cd / bc, *spec.bc)):
                continue
            fit = round(100 * (fit_to_targets(rd, [spec.d]) + fit_to_targets(cd / ab, list(spec.abcd)) + 1) / 3, 1)
            found.append(HarmonicPattern(
                name=spec.name, direction=BULLISH if sign == 1 else BEARISH, points=run,
                ratios={"B": rb, "C": rc, "D": rd, "BC": cd / bc, "ABCD": cd / ab}, fit=fit,
                known_at=run[-1].confirmed_at, invalidation=(v[1] - spec.invalid_xa * xa) / sign,
                target=(v[4] + 0.382 * (v[1] - v[4])) / sign))
    return found
