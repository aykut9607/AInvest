"""Draw a harmonic pattern with its verdict (own SVG pictures).

  .\\venv\\Scripts\\python.exe -m signals.rules.harmonic_draw                      rebuild harmonic-visuals.html
  .\\venv\\Scripts\\python.exe -m signals.rules.harmonic_draw 100 200 138.2 183 121.4    judge X A B C D
  .\\venv\\Scripts\\python.exe -m signals.rules.harmonic_draw 100 200 138.2 183          judge X A B C (D to come)
"""

from __future__ import annotations

import html
import sys
from collections.abc import Sequence
from pathlib import Path

from signals.data.download import SERVICE_DIR
from signals.rules import harmonic_check as hc
from signals.rules.elliott_check import GUIDE, VIOLATION, Verdict
from signals.rules.elliott_draw import AMBER, H, PAD_BOTTOM, PAD_TOP, PAD_X, RED, W, page, section

HERE = Path(__file__).parent


def svg(prices: Sequence[float], limits: Sequence[tuple[float, str, str]], bad: set[int], d_price: float | None,
        ratio: dict[str, float]) -> str:
    """The classic two-triangle picture. d_price: where D is expected (drawn dashed) when only X-A-B-C are given."""
    drawn = [*prices, d_price] if d_price is not None else list(prices)
    every = [*drawn, *[p for p, _, _ in limits]]
    low, high = min(every), max(every)

    def x(i: float) -> float:
        return PAD_X + i / 4 * (W - 2 * PAD_X)

    def y(price: float) -> float:
        return PAD_TOP + (high - price) / ((high - low) or 1.0) * (H - PAD_TOP - PAD_BOTTOM)

    def line(i: int, j: int, css: str) -> str:
        return f'<line class="{css}" x1="{x(i):.1f}" y1="{y(drawn[i]):.1f}" x2="{x(j):.1f}" y2="{y(drawn[j]):.1f}"/>'

    def triangle(*idx: int) -> str:
        return f'<polygon style="fill:var(--motive);opacity:.13" points="{" ".join(f"{x(i):.1f},{y(drawn[i]):.1f}" for i in idx)}"/>'

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{" ".join(f"{p:g}" for p in prices)}">', triangle(0, 1, 2)]
    if len(drawn) == 5:
        out.append(triangle(2, 3, 4))
    for price, text, css in limits:
        out.append(f'<line class="{css}" x1="6" x2="{W - 6}" y1="{y(price):.1f}" y2="{y(price):.1f}"/>'
                   f'<text class="{"lim" if css == RED else "gl"}" x="{W - 6}" y="{y(price) - 4:.1f}" text-anchor="end">'
                   f'{html.escape(text)}</text>')
    out += [line(k, k + 1, "dashg" if d_price is not None and k == 3 else "m") for k in range(len(drawn) - 1)]
    out.append(line(0, 2, "chan") + line(1, 3, "chan"))
    if len(drawn) == 5:
        out.append(line(2, 4, "chan") + line(0, 4, "chan"))
    tags = {2: f"{ratio['B']:.3f}", 3: f"{ratio['C']:.3f}", 4: f"{ratio['D']:.3f} XA"}
    for k, price in enumerate(drawn):
        is_top = drawn[1] < price if k == 0 else drawn[k - 1] < price
        expected = d_price is not None and k == 4
        out.append(f'<circle class="{"dotbad" if k in bad else "dot"}" cx="{x(k):.1f}" cy="{y(price):.1f}" r="4">'
                   f'<title>{"XABCD"[k]} {price:g}</title></circle>'
                   f'<text x="{x(k):.1f}" y="{y(price) + (-9 if is_top else 19):.1f}" text-anchor="middle">'
                   f'{"XABCD"[k]}{"?" if expected else ""} <tspan class="p">{tags.get(k, "")}</tspan></text>')
    return "".join(out) + "</svg>"


def card(title: str, verdict: Verdict, note: str = "") -> str:
    spec = hc.SPECS[verdict.model]
    prices = verdict.prices
    expected = prices[1] - spec.d * (prices[1] - prices[0]) if len(prices) == 4 else None
    limits = [(f.limit, f.rule, RED if f.level == VIOLATION else AMBER) for f in verdict.findings
              if f.limit is not None and f.level in (VIOLATION, GUIDE)]
    bad = {f.point for f in verdict.violations if f.point is not None}
    picture = svg(prices, limits, bad, expected, hc.ratios(prices, spec.d))
    if verdict.violations:
        rules = ", ".join(dict.fromkeys(f.rule for f in verdict.violations))
        head = f'<div class="v bad">✕ {verdict.model} değil: {rules}</div>'
    else:
        head = f'<div class="v good">✓ {verdict.model} olabilir (oranlar tamam)</div>'
    items = "".join(f'<li class="{f.level}">{f.rule}: {html.escape(f.text)}</li>' for f in verdict.findings)
    note = f'<p class="note">{note}</p>' if note else ""
    shown = " → ".join(f"{p:g}" for p in prices)
    return (f'<figure class="card"><h3>{html.escape(title)}</h3>{head}{picture}<div class="prices">{shown}</div>'
            f'<ul>{items}</ul>{note}</figure>')


def build(name: str, b: float, c: float, d: float | None = None) -> list[float]:
    """X-A-B-C-D of a bullish pattern with X = 100, A = 200 and the given ratios."""
    level_b = 200 - 100 * b
    level_c = level_b + c * 100 * b
    return [100, 200, round(level_b, 1), round(level_c, 1), round(200 - 100 * (hc.SPECS[name].d if d is None else d), 1)]


VALID = {"Gartley": (0.618, 0.75), "Bat": (0.5, 0.618), "Alternate Bat": (0.382, 0.85), "Butterfly": (0.786, 0.618),
         "Crab": (0.618, 0.786), "Deep Crab": (0.886, 0.5)}


def handbook() -> str:
    good = [card(f"Geçerli yükselen {name}", hc.check(name, build(name, b, c))) for name, (b, c) in VALID.items()]
    bat = build("Bat", *VALID["Bat"])
    parts = [
        section("1. Altı formasyon (yükselen: D alım bölgesi; düşen = ayna)", good),
        section("2. Aynı ilkeyle düşen örnek ve gelişen formasyon", [
            card("Düşen Bat (D satış bölgesi)", hc.check("Bat", [300 - p for p in bat])),
            card("Gelişen Bat: D henüz yok", hc.check("Bat", bat[:4]), "Plan burada yapılır: D bölgesi beklenir, gelince onay aranır."),
            card("Fiyat D'de durmadı", hc.check("Bat", [*bat[:4], 106]), "0,886'yı geçip 0,94'e indi: Bat tamamlanmadı, yeni ada çevrilmez."),
        ]),
        section("3. Hatalı etiketler", [
            card("B 0,55: Gartley değil", hc.check("Gartley", [100, 200, 145, 186, 121.4]), "Gartley'de B tam 0,618 olmalı."),
            card("Gartley'de D, X'i geçti", hc.check("Gartley", [100, 200, 138.2, 184, 97])),
            card("Kelebekte B 0,70", hc.check("Butterfly", build("Butterfly", 0.70, 0.618))),
            card("Bat'ta BC yalnız 1,3", hc.check("Bat", [100, 200, 150, 195, 136]), "Bat için BC en az 1,618; D de yerinde değil."),
            card("B, X'i aştı: Deep Crab değil", hc.check("Deep Crab", [100, 200, 98.5, 145, 38.2])),
            card("B 0,382 ile Crab: imkânsız birleşim", hc.check("Crab", build("Crab", 0.382, 0.886)),
                 "D 1,618'de olunca BC 4,6'ya çıkar; 3,618 sınırı hiçbir C ile sağlanamaz."),
        ]),
    ]
    lead = ("Kendi çizimlerimiz (X = 100, A = 200); kararları harmonic_check.py hesaplar. Numaralar HARMONIC.md'deki kurallardır. "
            "Yeşil karar 'oranlar tamam' demektir; işlem için bölgede dönüş onayı ayrıca gerekir.")
    return page("Harmonik kural görselleri", "".join(parts), lead)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 1:
        path = HERE / "harmonic-visuals.html"
        path.write_text(handbook(), encoding="utf-8")
    else:
        verdicts = hc.judge([float(a) for a in sys.argv[1:]])
        for v in verdicts:
            print(f"\n{v.model}: {'olabilir' if v.possible else 'DEĞİL'}")
            for f in v.findings:
                print(f"  [{f.level:9}] {f.rule}: {f.text}")
        path = SERVICE_DIR / "data" / "reports" / "harmonic-check.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page("Harmonik kontrolü", section("Formasyonlar", [card(v.model, v) for v in verdicts])), encoding="utf-8")
    print(f"\n{path}")


if __name__ == "__main__":
    main()
