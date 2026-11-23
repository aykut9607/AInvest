"""Elliott wave candidates from alternating ZigZag points (RULES.md 5).

What it does:
  impulse_counts(): every run of consecutive swing points 0-1-2-3-4 (wave 5 still to come) or 0-1-2-3-4-5 (complete)
    that passes the hard rules, with its type (3rd / 5th / 1st extended), how well the guideline ratios fit (0-100),
    and for 0-4 the wave-5 target zone, the invalidation level, the micro invalidation and the key level.
  abc_counts(): runs S-A-B-C (complete) or S-A-B (C to come) that fit a zigzag or a flat, with the C target zone.
The scanner never claims "the" count: it lists every candidate that survives the hard rules, best fit first. Main and
alternative model = the first two.

Hard rules (a candidate breaking one is dropped):
  1. wave 2 never goes beyond the start of wave 1        3. wave 4 never enters wave 1's territory (else diagonal)
  2. wave 3 is never the shortest of 1, 3, 5             5. in a zigzag, B never goes beyond the start of A
(rule 4, "no triangle in wave 2", is about sub-wave shapes and is checked once triangles are scanned.)
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from signals.patterns.fib import Level, Zone, cluster, fit_to_range, fit_to_targets, in_range, near
from signals.structure.pivots import HIGH, LOW
from signals.structure.zigzag import SwingPoint

UP, DOWN = "up", "down"
EXT_3RD, EXT_5TH, EXT_1ST, EXT_NONE = "3rd", "5th", "1st", "none"
IMPULSE, DIAGONAL = "impulse", "diagonal"
ZIGZAG, FLAT = "zigzag", "flat"


@dataclass
class ImpulseCount:
    direction: str                       # UP: 0 is a low, the impulse rises (a top forms at 5); DOWN: the mirror
    points: tuple[SwingPoint, ...]       # 5 (0..4, wave 5 to come) or 6 (complete)
    kind: str                            # IMPULSE or DIAGONAL (wave 4 overlaps wave 1)
    extension: str                       # which of 1/3/5 is (or looks) extended
    ratios: dict[str, float]
    fit: float                           # 0-100, guideline fit (not a trading score)
    known_at: int                        # bar from which the whole count is known (last point confirmed)
    wave5_zone: Zone | None = None       # 0..4 only: where wave 5 is expected to end
    invalidation: float | None = None    # price beyond which the count / the reversal plan is wrong
    micro_invalidation: float | None = None
    key_level: float | None = None       # breaking it confirms the turn (end of wave 4)
    notes: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return len(self.points) == 6


@dataclass
class AbcCount:
    direction: str                       # direction of wave A: DOWN = a correction of a rise
    points: tuple[SwingPoint, ...]       # S, A, B (+ C)
    kind: str                            # ZIGZAG or FLAT
    ratios: dict[str, float]
    fit: float
    known_at: int
    c_zone: Zone | None = None           # S-A-B only: where C is expected to end
    invalidation: float | None = None


def _sign(first: SwingPoint) -> int:
    return 1 if first.kind == LOW else -1


def _v(point: SwingPoint, sign: int) -> float:
    return sign * point.price


def impulse_counts(points: Sequence[SwingPoint]) -> list[ImpulseCount]:
    """All 0-4 and 0-5 candidates over the swing points, best fit first within the same end point."""
    found: list[ImpulseCount] = []
    for start in range(len(points)):
        for size in (5, 6):
            run = tuple(points[start:start + size])
            if len(run) == size:
                count = _impulse(run)
                if count is not None:
                    found.append(count)
    return sorted(found, key=lambda c: (c.points[-1].index, -c.fit))


def _impulse(run: tuple[SwingPoint, ...]) -> ImpulseCount | None:
    sign = _sign(run[0])
    p = [_v(pt, sign) for pt in run]
    w1, w3 = p[1] - p[0], p[3] - p[2]
    w2, w4 = p[1] - p[2], p[3] - p[4]
    if w1 <= 0 or w3 <= 0 or w2 <= 0 or w4 <= 0:
        return None
    if p[2] <= p[0]:                       # rule 1: wave 2 beyond the start of wave 1
        return None
    if p[3] <= p[1]:                       # wave 3 must carry beyond wave 1
        return None
    w5 = p[5] - p[4] if len(p) == 6 else None
    if w5 is not None and w5 <= 0:
        return None
    if w5 is not None and w3 < w1 and w3 < w5:   # rule 2: wave 3 the shortest
        return None

    kind = IMPULSE
    if p[4] <= p[1]:                       # rule 3: overlap -> only a (contracting) diagonal is allowed
        contracting = w3 < w1 and (w5 is None or w5 < w3)
        if not contracting or p[4] <= p[2]:
            return None
        kind = DIAGONAL

    r2, r4, e3 = w2 / w1, w4 / w3, w3 / w1
    if e3 >= 1.618 * 0.97:
        extension = EXT_3RD
    elif w1 > w3:
        extension = EXT_1ST
    elif near(w1, w3, 0.2):
        extension = EXT_5TH
    else:
        extension = EXT_NONE
    ratios = {"r2": r2, "r4": r4, "e3": e3}

    # guideline fit: wave 2 depth, wave 4 depth, wave 3 extension, alternation in price and time (RULES.md 5)
    t2 = run[2].index - run[1].index
    t4 = run[4].index - run[3].index
    alternation = 1.0 if (r2 >= 0.5) != (r4 >= 0.5) or (t4 >= 1.5 * t2) or (t2 >= 1.5 * t4) else 0.5
    parts = [
        fit_to_targets(r2, [0.382, 0.5, 0.618]),
        fit_to_range(r4, 0.236, 0.382) if kind == IMPULSE else fit_to_range(r4, 0.5, 0.886),
        fit_to_targets(e3, [1.0, 1.618, 2.618]) if extension != EXT_1ST else 1.0,
        alternation,
    ]
    notes: list[str] = []
    if w5 is not None:
        r5 = w5 / w1
        ratios["r5_w1"] = r5
        ratios["r5_w3"] = w5 / w3
        targets5 = [1.0] if extension != EXT_5TH else [1.618]
        parts.append(max(fit_to_targets(r5, targets5), fit_to_targets(w5 / w3, [0.618, 1.0, 1.618])))
        if p[5] <= p[3]:
            notes.append("truncated 5th (wave 5 did not exceed wave 3)")
    fit = round(100 * sum(parts) / len(parts), 1)

    count = ImpulseCount(direction=UP if sign == 1 else DOWN, points=run, kind=kind, extension=extension,
                         ratios=ratios, fit=fit, known_at=run[-1].confirmed_at, notes=notes)
    if w5 is None:
        _wave5_plan(count, p, sign, w1, w3)
    return count


def _wave5_plan(count: ImpulseCount, p: list[float], sign: int, w1: float, w3: float) -> None:
    """Where wave 5 should end (0-4 known) and the levels of the reversal plan at that zone."""
    to_price = lambda v: v / sign
    levels = [Level(f"2-3-4 ext {k}", to_price(p[4] + k * w3)) for k in (0.618, 1.0, 1.618)]
    levels.append(Level("[5]=[1]", to_price(p[4] + w1)))
    if count.extension == EXT_5TH:
        levels += [Level("[5]=1.618x(0-3)", to_price(p[4] + 1.618 * (p[3] - p[0]))),
                   Level("[5]=1.618x[1]", to_price(p[4] + 1.618 * w1))]
    if count.extension == EXT_3RD and w3 > 2.618 * w1:
        count.notes.append("wave 3 > 2.618 x wave 1: truncated 5th risk near 0.618 x [1] (no new extreme)")
        levels.append(Level("truncated 5 = 0.618x[1]", to_price(p[4] + 0.618 * w1)))
    # rule 2 while wave 5 runs: if wave 3 is shorter than wave 1, wave 5 must stay shorter than wave 3
    if w3 < w1:
        cap = p[4] + w3
        levels = [lv for lv in levels if sign * lv.price <= cap * (1 + 1e-12)]
        count.notes.append("wave 3 < wave 1: wave 5 is capped at the length of wave 3")
    if not levels:
        return
    width = 0.15 * w3                                       # levels within 15% of wave 3 belong together
    zone = cluster(levels, width)
    count.wave5_zone = zone
    # invalidation of the reversal plan: the next target level beyond the zone (in v-space "beyond" = larger);
    # if wave 5 runs through every level it is extending and the reversal idea is wrong
    zone_far_v = max(sign * zone.low, sign * zone.high)
    further = [sign * lv.price for lv in levels] + [p[4] + 2.618 * w3]
    beyond = sorted(v for v in further if v > zone_far_v + 1e-9)
    count.invalidation = to_price(beyond[0] if beyond else zone_far_v + 0.5 * width)
    count.micro_invalidation = to_price(zone_far_v)
    count.key_level = to_price(p[4])


def abc_counts(points: Sequence[SwingPoint]) -> list[AbcCount]:
    """Zigzag / flat candidates S-A-B-C and S-A-B (C to come), best fit first within the same end point."""
    found: list[AbcCount] = []
    for start in range(len(points)):
        for size in (3, 4):
            run = tuple(points[start:start + size])
            if len(run) == size:
                found += _abc(run)
    return sorted(found, key=lambda c: (c.points[-1].index, -c.fit))


def _abc(run: tuple[SwingPoint, ...]) -> list[AbcCount]:
    # wave A falls when S is a high: normalise so that A is a DROP in v-space -> sign = -1 for S high
    sign = -1 if run[0].kind == HIGH else 1
    s, a, b = (-sign * pt.price for pt in run[:3])        # in this space A goes down: s > a, b between
    leg_a, leg_b = s - a, b - a
    if leg_a <= 0 or leg_b <= 0:
        return []
    rb = leg_b / leg_a
    c = -sign * run[3].price if len(run) == 4 else None
    rc = (b - c) / leg_a if c is not None else None
    direction = DOWN if run[0].kind == HIGH else UP
    to_price = lambda v: -v / sign
    found = []
    for kind in (ZIGZAG, FLAT):
        if kind == ZIGZAG:
            if b >= s or rb >= 0.786 * 0.97:               # rule 5, and B at 0.786+ is not a zigzag
                continue
            parts = [fit_to_targets(rb, [0.382, 0.5, 0.618])]
            c_targets = [1.0, 1.618]
        else:
            if not in_range(rb, 0.9, 1.382):
                continue
            parts = [fit_to_range(rb, 0.9, 1.382)]
            c_targets = [1.0, 1.236, 1.618]
        if rc is not None:
            if rc <= 0:
                continue
            parts.append(fit_to_targets(rc, c_targets) if kind == ZIGZAG else fit_to_range(rc, 1.0, 1.618))
        count = AbcCount(direction=direction, points=run, kind=kind,
                         ratios={"rb": rb, **({"rc": rc} if rc is not None else {})},
                         fit=round(100 * sum(parts) / len(parts), 1), known_at=run[-1].confirmed_at)
        if rc is None:
            # C measured from B (C = k x A); the reversal plan at the end of C is wrong once C runs 2.618 x A
            levels = [Level(f"C={k}xA", to_price(b - k * leg_a)) for k in c_targets]
            count.c_zone = cluster(levels, 0.15 * leg_a)
            count.invalidation = to_price(b - 2.618 * leg_a)
        found.append(count)
    return found
