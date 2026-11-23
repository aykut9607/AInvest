"""Judge a proposed Elliott count against the numbered rules of ELLIOTT.md.

Input: the prices of the labelled turning points, start point first (0-1-2-3-4-5, S-A-B-C, S-A-B-C-D-E).
Output: findings with the rule number, the numbers that break or support it, and what could NOT be checked.
Prices alone can prove a count wrong; they can never prove it right (inner structure, position and the path inside a
wave are missing), so the best verdict here is "possible".
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

VIOLATION, GUIDE, OK, UNKNOWN = "violation", "guide", "ok", "unknown"


@dataclass(frozen=True)
class Finding:
    rule: str                        # number in ELLIOTT.md, e.g. "E-04"
    level: str
    text: str
    limit: float | None = None       # price line the finding is about (drawn on the picture)
    point: int | None = None         # index of the offending point


@dataclass
class Verdict:
    model: str
    prices: list[float]
    findings: list[Finding] = field(default_factory=list)

    @property
    def violations(self) -> list[Finding]:
        return [f for f in self.findings if f.level == VIOLATION]

    @property
    def possible(self) -> bool:
        return not self.violations


def _n(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", " ")


def _normalise(prices: Sequence[float]) -> tuple[int, list[float]]:
    """(sign, prices mirrored so that the first wave rises)"""
    sign = 1 if prices[1] > prices[0] else -1
    return sign, [sign * p for p in prices]


def _alternates(prices: Sequence[float]) -> bool:
    steps = [b - a for a, b in zip(prices, prices[1:])]
    return all(s != 0 for s in steps) and all(a * b < 0 for a, b in zip(steps, steps[1:]))


def _start(model: str, prices: Sequence[float], allowed: Sequence[int]) -> Verdict:
    if len(prices) not in allowed:
        raise ValueError(f"{model}: expected {allowed} points, got {len(prices)}")
    if not _alternates(prices):
        raise ValueError("turning points must alternate (up, down, up, ...)")
    return Verdict(model, list(prices))


def check_impulse(prices: Sequence[float], wave4_path_extreme: float | None = None) -> Verdict:
    """0-1-2 up to 0-1-2-3-4-5. wave4_path_extreme: the deepest wick inside wave 4 if it is not the end of wave 4."""
    v = _start("impulse", prices, (3, 4, 5, 6))
    sign, p = _normalise(prices)
    add = v.findings.append
    w1, w2 = p[1] - p[0], p[1] - p[2]
    if p[2] <= p[0]:
        add(Finding("E-01", VIOLATION, f"2. dalga ({_n(prices[2])}) 1'in başlangıcına ({_n(prices[0])}) ulaştı ya da geçti "
                                       f"(geri alma %{100 * w2 / w1:.0f})", prices[0], 2))
    else:
        add(Finding("E-01", OK, f"2. dalga 1'in %{100 * w2 / w1:.0f}'ini geri aldı"))
    w3 = p[3] - p[2] if len(p) >= 4 else 0.0
    if len(p) >= 4:
        if p[3] <= p[1]:
            add(Finding("E-02", VIOLATION, f"3. dalga ({_n(prices[3])}) 1'in sonunu ({_n(prices[1])}) geçemedi",
                        prices[1], 3))
        else:
            add(Finding("E-02", OK, "3. dalga 1'in sonunu geçti"))
    if len(p) >= 5:
        deepest = p[4] if wave4_path_extreme is None else min(p[4], sign * wave4_path_extreme)
        if deepest <= p[1]:
            add(Finding("E-04", VIOLATION, f"4. dalga {_n(sign * deepest)} ile 1'in alanına ({_n(prices[1])}) girdi",
                        prices[1], 4))
        else:
            add(Finding("E-04", OK, f"4. dalga 1'in sonuna ({_n(prices[1])}) değmedi"))
    if len(p) == 6:
        w5 = p[5] - p[4]
        lengths = f"[1]={_n(w1)}, [3]={_n(w3)}, [5]={_n(w5)}"
        if w3 < w1 and w3 < w5:
            add(Finding("E-03", VIOLATION, f"3. dalga en kısa: {lengths}", None, 3))
        else:
            add(Finding("E-03", OK, f"3. dalga en kısa değil: {lengths}"))
        if p[5] <= p[3]:
            add(Finding("E-17", GUIDE, "güdük 5: 3'ün sonunu geçmedi; içi tamamlanmış beşli olmalı", prices[3], 5))
    elif len(p) == 5 and w3 < w1:
        add(Finding("E-03", GUIDE, f"[3] < [1]: 5. dalga {_n(w3)} boyunu geçerse 3 en kısa kalır", sign * (p[4] + w3)))
    add(Finding("E-05", UNKNOWN, "iç yapı (1-3-5 beşli, 2-4 düzeltici, 3 mutlaka itki) uç fiyatlardan bilinmez"))
    if len(p) >= 5 and wave4_path_extreme is None:
        add(Finding("E-04", UNKNOWN, "4'ün yolundaki fitiller verilmedi; yalnız bitişi kontrol edildi"))
    return v


def check_diagonal(prices: Sequence[float], times: Sequence[float] | None = None) -> Verdict:
    """Complete contracting diagonal 0-5 (without times the points are taken as equally spaced)."""
    v = _start("diagonal", prices, (6,))
    t = list(times) if times is not None else list(range(6))
    sign, p = _normalise(prices)
    add = v.findings.append
    w1, w3, w5 = p[1] - p[0], p[3] - p[2], p[5] - p[4]
    if p[2] <= p[0]:
        add(Finding("E-21", VIOLATION, f"2 ({_n(prices[2])}) 1'in tamamını geri aldı", prices[0], 2))
    if p[3] <= p[1]:
        add(Finding("E-22", VIOLATION, f"3 ({_n(prices[3])}) 1'in sonunu geçemedi", prices[1], 3))
    if p[4] <= p[2]:
        add(Finding("E-23", VIOLATION, f"4 ({_n(prices[4])}) 2'nin sonunu ({_n(prices[2])}) aştı: 3'ü tamamen geri aldı",
                    prices[2], 4))
    if w3 >= w1:
        add(Finding("E-24", VIOLATION, f"daralan modelde [3] < [1] olmalı: [1]={_n(w1)}, [3]={_n(w3)}", None, 3))
    if w5 >= w3:
        add(Finding("E-24", VIOLATION, f"daralan modelde [5] < [3] olmalı: [3]={_n(w3)}, [5]={_n(w5)}",
                    sign * (p[4] + w3), 5))
    if p[4] > p[1]:
        add(Finding("E-25", GUIDE, "4 ile 1 örtüşmüyor: diyagonalin alışılmış özelliği yok, önce itki olarak sına"))
    slope13, slope24 = (p[3] - p[1]) / (t[3] - t[1]), (p[4] - p[2]) / (t[4] - t[2])
    if slope24 <= slope13:
        add(Finding("E-26", VIOLATION, "1–3 ve 2–4 çizgileri yakınsamıyor"))
    else:
        apex = (p[1] - slope13 * t[1] - p[2] + slope24 * t[2]) / (slope24 - slope13)
        if apex <= t[5]:
            add(Finding("E-26", VIOLATION, "yapı, çizgilerin kesişme noktasından sonra bitiyor"))
        else:
            add(Finding("E-26", OK, "çizgiler yakınsıyor, yapı kesişmeden önce bitiyor"
                                    + ("" if times is not None else " (eşit zaman aralığı varsayımıyla)")))
    add(Finding("E-20", UNKNOWN, "konum (öncü: 1/A, bitiş: 5/C) ve iç yapı (5-3-5-3-5 / 3-3-3-3-3) bilinmez"))
    return v


def check_zigzag(prices: Sequence[float]) -> Verdict:
    """S-A-B or S-A-B-C."""
    v = _start("zigzag", prices, (3, 4))
    _, p = _normalise(prices)                # A "rises" in this space
    add = v.findings.append
    a = p[1] - p[0]
    rb = (p[1] - p[2]) / a
    if p[2] <= p[0]:
        add(Finding("E-31", VIOLATION, f"B ({_n(prices[2])}) A'nın başlangıcına ({_n(prices[0])}) ulaştı ya da geçti",
                    prices[0], 2))
    else:
        add(Finding("E-31", OK, f"B, A'nın %{100 * rb:.0f}'ini geri aldı"))
        if rb >= 0.786:
            add(Finding("E-33", GUIDE, "B ≥ 0,786: zigzag şüpheli, yassı ihtimaline bak"))
    if len(p) == 4:
        add(Finding("E-34", OK, f"C = {(p[3] - p[2]) / a:.2f} × A"))
        if p[3] <= p[1]:
            add(Finding("E-34", GUIDE, "C, A'nın sonunu geçmedi: kısa C ya da düzeltme bitmedi", prices[1], 3))
    add(Finding("E-32", UNKNOWN, "iç yapı (5-3-5) uç fiyatlardan bilinmez"))
    return v


def check_flat(prices: Sequence[float]) -> Verdict:
    """S-A-B-C. Prices cannot rule a flat out (its defining rule is the inner 3-3-5); they only name its kind."""
    v = _start("flat", prices, (4,))
    _, p = _normalise(prices)
    add = v.findings.append
    a = p[1] - p[0]
    rb, rc = (p[1] - p[2]) / a, (p[3] - p[2]) / a
    if p[2] < p[0]:
        kind = "genişleyen" if p[3] > p[1] else "kaçan (running)"
    else:
        kind = "normal"
    add(Finding("E-41", OK, f"tip adayı: {kind} yassı (B %{100 * rb:.0f} A, C = {rc:.2f} × A)"))
    if rb < 0.9:
        add(Finding("E-42", GUIDE, f"B = %{100 * rb:.0f} A: yassıda B genelde A'nın başına yaklaşır (≥ %90)"))
    if kind.startswith("kaçan"):
        add(Finding("E-43", GUIDE, "kaçan yassı, bitmemiş C'ye bahane olmasın: C'nin beşlisi tamam mı?"))
    if kind == "normal" and p[3] < p[1]:
        add(Finding("E-42", GUIDE, "C, A'nın sonuna ulaşmadı"))
    add(Finding("E-40", UNKNOWN, "iç yapı (3-3-5) bilinmez; ilk soru: A üçlü mü beşli mi?"))
    return v


def check_triangle(prices: Sequence[float], times: Sequence[float] | None = None) -> Verdict:
    """Complete contracting triangle S-A-B-C-D-E."""
    v = _start("triangle", prices, (6,))
    t = list(times) if times is not None else list(range(6))
    _, p = _normalise(prices)                # A "rises" in this space
    add = v.findings.append
    if p[2] < p[0]:
        add(Finding("E-55", GUIDE, f"B ({_n(prices[2])}) A'nın başlangıcını ({_n(prices[0])}) geçti: kaçan üçgen olabilir",
                    prices[0], 2))
    if p[3] >= p[1]:
        add(Finding("E-52", VIOLATION, f"C ({_n(prices[3])}) A'nın sonunu ({_n(prices[1])}) geçti: daralma yok", prices[1], 3))
    if p[4] <= p[2]:
        add(Finding("E-52", VIOLATION, f"D ({_n(prices[4])}) B'nin sonunu ({_n(prices[2])}) geçti: daralma yok", prices[2], 4))
    if p[5] >= p[3]:
        add(Finding("E-52", VIOLATION, f"E ({_n(prices[5])}) C'nin sonunu ({_n(prices[3])}) geçti", prices[3], 5))
    converging = (p[3] - p[1]) / (t[3] - t[1]) < (p[4] - p[2]) / (t[4] - t[2])
    add(Finding("E-51", OK, "A–C ve B–D çizgileri yakınsıyor") if converging
        else Finding("E-51", VIOLATION, "A–C ve B–D çizgileri yakınsamıyor"))
    add(Finding("E-50", UNKNOWN, "konum (4, B, X; 2'nin tamamı olamaz) ve iç yapı (3-3-3-3-3) bilinmez"))
    return v


def judge(prices: Sequence[float]) -> list[Verdict]:
    """Every model the number of points allows, the possible ones first."""
    checks = {3: (check_impulse, check_zigzag), 4: (check_impulse, check_zigzag, check_flat), 5: (check_impulse,),
              6: (check_impulse, check_diagonal, check_triangle)}
    if len(prices) not in checks:
        raise ValueError("give 3 to 6 turning points, start point first")
    return sorted((check(prices) for check in checks[len(prices)]), key=lambda v: len(v.violations))
