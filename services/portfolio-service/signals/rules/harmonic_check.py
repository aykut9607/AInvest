"""Judge a proposed harmonic XABC(D) against the numbered rules of HARMONIC.md.

Ratios (absolute legs): B = AB / XA, C = BC / AB, D = AD / XA (> 1: beyond X), BC projection = CD / BC, AB=CD = CD / AB.
Ratios have the +-3% tolerance; the two structural limits (B never beyond X, Gartley's D never beyond X) have none.
With four points (X-A-B-C) D is taken at its defining XA level: "what would the pattern look like if it completes there".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signals.patterns.fib import TOLERANCE, in_range, near
from signals.rules.elliott_check import GUIDE, OK, UNKNOWN, VIOLATION, Finding, Verdict, _alternates, _n, _normalise


@dataclass(frozen=True)
class Spec:
    name: str
    b: tuple[float, float]                    # accepted range of B; equal ends = one ratio
    b_preferred: tuple[float, float] | None   # inside b, what Carney prefers
    d: float                                  # defining XA level
    bc: tuple[float, float | None]            # BC projection; None = no maximum stated by the source
    abcd_min: float | None                    # minimum CD / AB where the source states one
    abcd_usual: tuple[float, ...]             # usual CD / AB (guide)
    d_never_beyond_x: bool = False


SPECS = {s.name: s for s in (
    Spec("Gartley", (0.618, 0.618), None, 0.786, (1.27, 1.618), None, (1.0,), True),
    Spec("Bat", (0.382, 0.5), (0.5, 0.5), 0.886, (1.618, 2.618), 1.0, (1.0, 1.27)),
    Spec("Alternate Bat", (0.0, 0.382), None, 1.13, (2.0, None), 1.0, ()),
    Spec("Butterfly", (0.786, 0.786), None, 1.27, (1.618, 2.618), 1.0, (1.0, 1.27)),
    Spec("Crab", (0.382, 0.618), None, 1.618, (2.24, 3.618), 1.0, ()),
    Spec("Deep Crab", (0.886, 1.0), None, 1.618, (2.24, 3.618), 1.0, (1.0, 1.27)),
)}
C_RANGE = (0.382, 0.886)


def ratios(prices: Sequence[float], d_at: float | None = None) -> dict[str, float]:
    _, v = _normalise(prices)
    xa, ab, bc = v[1] - v[0], v[1] - v[2], v[3] - v[2]
    d = v[4] if len(v) == 5 else v[1] - d_at * xa
    cd = v[3] - d
    return {"B": ab / xa, "C": bc / ab, "D": (v[1] - d) / xa, "BC": cd / bc, "ABCD": cd / ab}


def check(name: str, prices: Sequence[float]) -> Verdict:
    """X-A-B-C (D still to come) or X-A-B-C-D."""
    if len(prices) not in (4, 5):
        raise ValueError("give X A B C or X A B C D")
    if not _alternates(prices):
        raise ValueError("turning points must alternate (up, down, up, ...)")
    spec = SPECS[name]
    sign, v = _normalise(prices)
    r = ratios(prices, spec.d)
    complete = len(prices) == 5
    d_price = sign * (v[1] - spec.d * (v[1] - v[0]))
    verdict = Verdict(name, list(prices))
    add = verdict.findings.append

    def put(rule: str, good: bool, text: str, point: int | None = None, limit: float | None = None) -> None:
        add(Finding(rule, OK if good else VIOLATION, text, None if good else limit, None if good else point))

    low, high = spec.b
    if low == high:
        put("H-03", near(r["B"], low), f"B = {r['B']:.3f} (olması gereken {low})", 2, sign * (v[1] - low * (v[1] - v[0])))
    else:
        inside = (low == 0.0 or r["B"] >= low * (1 - TOLERANCE)) and r["B"] <= high * (1 + TOLERANCE)
        put("H-03", inside, f"B = {r['B']:.3f} (aralık {low}–{high})", 2)
    if v[2] <= v[0]:
        add(Finding("H-02", VIOLATION, f"B ({_n(prices[2])}) X'i ({_n(prices[0])}) aştı", prices[0], 2))
    put("H-01", in_range(r["C"], *C_RANGE) and r["C"] < 1, f"C = {r['C']:.3f} (aralık 0,382–0,886 AB)", 3)

    where = "" if complete else f" (D {_n(d_price)}'de olursa)"
    if complete:
        put("H-04", near(r["D"], spec.d), f"D = {r['D']:.3f} XA (olması gereken {spec.d})", 4, d_price)
    else:
        add(Finding("H-04", OK, f"D beklenen: {_n(d_price)} ({spec.d} XA)"))
    if spec.d_never_beyond_x and complete and v[4] < v[0]:
        add(Finding("H-06", VIOLATION, f"D ({_n(prices[4])}) X'i ({_n(prices[0])}) geçti", prices[0], 4))
    bc_low, bc_high = spec.bc
    bc_ok = r["BC"] >= bc_low * (1 - TOLERANCE) and (bc_high is None or r["BC"] <= bc_high * (1 + TOLERANCE))
    limit_text = f"{bc_low}–{bc_high}" if bc_high else f"en az {bc_low}"
    put("H-05", bc_ok, f"BC uzatması = {r['BC']:.2f} ({limit_text}){where}", 4 if complete else 3)
    if spec.abcd_min is not None:
        put("H-07", r["ABCD"] >= spec.abcd_min * (1 - TOLERANCE), f"CD = {r['ABCD']:.2f} × AB (en az {spec.abcd_min}){where}",
            4 if complete else 3)
    if spec.abcd_usual:
        near_usual = any(near(r["ABCD"], k) for k in spec.abcd_usual)
        add(Finding("H-08", OK if near_usual else GUIDE,
                    f"CD = {r['ABCD']:.2f} × AB; alışılmış " + " / ".join(f"{k:g}" for k in spec.abcd_usual) + where))
    if spec.b_preferred and verdict.possible and not in_range(r["B"], *spec.b_preferred):
        add(Finding("H-09", GUIDE, f"B = {r['B']:.3f}; ideali {spec.b_preferred[0]}"))
    add(Finding("H-20", UNKNOWN, "PRZ'de tepki (kapanış + LTF onayı) oran hesabıyla bilinmez"))
    return verdict


def judge(prices: Sequence[float]) -> list[Verdict]:
    """All patterns, the possible ones first, then by how little is broken."""
    return sorted((check(name, prices) for name in SPECS), key=lambda v: len(v.violations))
