"""Draw a count with its verdict (own SVG pictures, no copied material).

  .\\venv\\Scripts\\python.exe -m signals.rules.elliott_draw                          rebuild elliott-visuals.html
  .\\venv\\Scripts\\python.exe -m signals.rules.elliott_draw 100 130 98 160 140 180   judge these turning points:
      prints the verdict of every model and writes data/reports/elliott-check.html (git-ignored)
"""

from __future__ import annotations

import html
import sys
from collections.abc import Sequence
from pathlib import Path

from signals.data.download import SERVICE_DIR
from signals.rules import elliott_check as ec

HERE = Path(__file__).parent
W, H, PAD_X, PAD_TOP, PAD_BOTTOM = 380, 230, 46, 32, 32

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--muted:#667085;--grid:#e3e6eb;--motive:#2a6fd6;--corr:#8a93a3;
--bad:#c62828;--good:#1b7f3b;--guide:#9a6200}
@media (prefers-color-scheme:dark){:root{--bg:#111317;--card:#1a1d23;--ink:#eceff4;--muted:#9aa4b2;--grid:#2c313a;
--motive:#6aa5f8;--corr:#8d97a6;--bad:#ff7b72;--good:#56c271;--guide:#e3a94a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,"Segoe UI",sans-serif}
main{max-width:1240px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:34px 0 10px}
p{max-width:78ch}.lead{color:var(--muted);margin:0 0 8px}.note{margin:6px 0 0;font-size:13.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(370px,100%),1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--grid);border-radius:8px;padding:12px 14px;margin:0}
.card h3{font-size:15px;margin:0 0 2px}.card svg{width:100%;height:auto;display:block}
.v{font-weight:600}.v.bad{color:var(--bad)}.v.good{color:var(--good)}
ul{margin:6px 0 0;padding-left:18px;font-size:13.5px}li.unknown,li.ok{color:var(--muted)}
li.violation{color:var(--bad)}li.guide{color:var(--guide)}
.prices{font:12.5px ui-monospace,Consolas,monospace;color:var(--muted)}
svg text{fill:var(--ink);font:600 13px system-ui,"Segoe UI",sans-serif;paint-order:stroke;stroke:var(--card);stroke-width:4px;stroke-linejoin:round}svg tspan.p{fill:var(--muted);font-weight:400;font-size:11px}
svg text.lim{fill:var(--bad);font-size:11px}svg text.gl{fill:var(--guide);font-size:11px}
.m{stroke:var(--motive);stroke-width:2.2}.c{stroke:var(--corr);stroke-width:2.2}
.sub{stroke:var(--muted);stroke-width:1.3;fill:none}.dash{stroke:var(--bad);stroke-width:1.3;stroke-dasharray:5 4}
.dashg{stroke:var(--guide);stroke-width:1.3;stroke-dasharray:5 4}.chan{stroke:var(--good);stroke-width:1.2;stroke-dasharray:3 3}
.dot{fill:var(--ink)}.dotbad{fill:var(--bad)}
"""

LABELS = {"impulse": list("012345"), "diagonal": list("012345"), "zigzag": ["", "A", "B", "C"], "flat": ["", "A", "B", "C"],
          "triangle": ["", "A", "B", "C", "D", "E"], "wxy": ["", "a", "b", "W", "X", "a", "b", "Y"]}
NAMES = {"impulse": "İtki", "diagonal": "Diyagonal", "zigzag": "Zigzag", "flat": "Yassı", "triangle": "Üçgen"}
RED, AMBER = "dash", "dashg"


def svg(prices: Sequence[float], labels: Sequence[str], limits: Sequence[tuple[float, str, str]] = (),
        bad: frozenset[int] | set[int] = frozenset(), lines: Sequence[tuple[int, int, float]] = (),
        sub: Sequence[tuple[float, float]] = (), motive_first: bool = True) -> str:
    """limits: (price, text, RED/AMBER); lines: (point i, point j, extended to time); sub: inner path (time, price).
    Points are one time step apart. motive_first: the first leg runs in the main direction (blue)."""
    t_end = max([len(prices) - 1.0, *[to for _, _, to in lines]])

    def on_line(i: int, j: int, time: float) -> float:
        return prices[i] + (prices[j] - prices[i]) / (j - i) * (time - i)

    every = [*prices, *[p for p, _, _ in limits], *[p for _, p in sub], *[on_line(i, j, to) for i, j, to in lines]]
    low, high = min(every), max(every)

    def x(time: float) -> float:
        return PAD_X + time / t_end * (W - 2 * PAD_X)

    def y(price: float) -> float:
        return PAD_TOP + (high - price) / ((high - low) or 1.0) * (H - PAD_TOP - PAD_BOTTOM)

    def at_left(price: float) -> bool:
        """A limit's name goes to the side where the path stays further from the line."""
        n = max(1, len(prices) // 3)
        return min(abs(y(p) - y(price)) for p in prices[:n]) > min(abs(y(p) - y(price)) for p in prices[-n:])

    def anchor(k: int) -> tuple[float, str]:
        """Long words on the first and last points stay inside the picture."""
        if len(labels[k]) > 8 and k == 0:
            return 6, "start"
        if len(labels[k]) > 8 and x(k) > W - PAD_X - 1:
            return W - 6, "end"
        return x(k), "middle"

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{" ".join(f"{p:g}" for p in prices)}">']
    for price, text, css in limits:
        out.append(f'<line class="{css}" x1="6" x2="{W - 6}" y1="{y(price):.1f}" y2="{y(price):.1f}"/>'
                   f'<text class="{"lim" if css == RED else "gl"}" x="{6 if at_left(price) else W - 6}" y="{y(price) - 4:.1f}" '
                   f'text-anchor="{"start" if at_left(price) else "end"}">{html.escape(text)}</text>')
    for i, j, to in lines:
        out.append(f'<line class="chan" x1="{x(i):.1f}" y1="{y(prices[i]):.1f}" x2="{x(to):.1f}" y2="{y(on_line(i, j, to)):.1f}"/>')
    for k in range(len(prices) - 1):
        css = "m" if (k % 2 == 0) == motive_first else "c"
        out.append(f'<line class="{css}" x1="{x(k):.1f}" y1="{y(prices[k]):.1f}" x2="{x(k + 1):.1f}" y2="{y(prices[k + 1]):.1f}"/>')
    if sub:
        path = " ".join(f"{x(a):.1f},{y(b):.1f}" for a, b in sub)
        out.append(f'<polyline class="sub" points="{path}"/>')
    for k, price in enumerate(prices):
        is_top = prices[1] < price if k == 0 else prices[k - 1] < price
        out.append(f'<circle class="{"dotbad" if k in bad else "dot"}" cx="{x(k):.1f}" cy="{y(price):.1f}" r="4">'
                   f'<title>{labels[k]} {price:g}</title></circle>'
                   f'<text x="{anchor(k)[0]:.1f}" y="{y(price) + (-9 if is_top else 19):.1f}" text-anchor="{anchor(k)[1]}">'
                   f'{labels[k]} <tspan class="p">{price:g}</tspan></text>')
    return "".join(out) + "</svg>"


def card(title: str, verdict: ec.Verdict | None, picture: str, prices: Sequence[float], note: str = "") -> str:
    head = items = ""
    if verdict is not None:
        name = NAMES[verdict.model]
        if verdict.violations:
            rules = ", ".join(dict.fromkeys(f.rule for f in verdict.violations))
            head = f'<div class="v bad">✕ {name} değil: {rules}</div>'
        else:
            head = f'<div class="v good">✓ {name} olabilir (fiyat kuralları tamam)</div>'
        items = "".join(f'<li class="{f.level}">{f.rule}: {html.escape(f.text)}</li>' for f in verdict.findings)
        items = f"<ul>{items}</ul>"
    note = f'<p class="note">{note}</p>' if note else ""
    return (f'<figure class="card"><h3>{html.escape(title)}</h3>{head}{picture}'
            f'<div class="prices">{" → ".join(f"{p:g}" for p in prices)}</div>{items}{note}</figure>')


def judged(title: str, verdict: ec.Verdict, note: str = "", lines: Sequence[tuple[int, int, float]] = (),
           sub: Sequence[tuple[float, float]] = ()) -> str:
    limits = [(f.limit, f.rule, RED if f.level == ec.VIOLATION else AMBER) for f in verdict.findings if f.limit is not None]
    bad = {f.point for f in verdict.violations if f.point is not None}
    picture = svg(verdict.prices, LABELS[verdict.model], limits, bad, lines, sub,
                  motive_first=verdict.model in ("impulse", "diagonal"))
    return card(title, verdict, picture, verdict.prices, note)


def page(title: str, body: str, lead: str = "") -> str:
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>'
            f'<style>{CSS}</style></head><body><main><h1>{html.escape(title)}</h1><p class="lead">{lead}</p>{body}</main></body></html>')


def section(title: str, cards: Sequence[str]) -> str:
    return f'<h2>{html.escape(title)}</h2><div class="grid">{"".join(cards)}</div>'


def handbook() -> str:
    imp, dia, zig, flat, tri = ec.check_impulse, ec.check_diagonal, ec.check_zigzag, ec.check_flat, ec.check_triangle
    up, start3 = [50, 70, 60, 98, 82, 104], [50, 70, 60]
    ambiguous, wxy = [60, 90, 72, 104], [100, 84, 92, 76, 88, 72, 80, 64]
    mixed = [100, 88, 95, 80, 97, 84, 96, 83]
    parts = [
        section("1. İtki: kesin kurallar", [
            judged("Geçerli yükselen itki", imp(up)),
            judged("Geçerli düşen itki (aynı kurallar, ayna)", imp([104, 84, 94, 56, 72, 50])),
            judged("2. dalga başlangıcın altına indi", imp([50, 70, 47, 98, 82, 104]), "Sonradan yükselmesi hatayı düzeltmez."),
            judged("3. dalga 1'in tepesini geçemedi", imp([50, 70, 58, 68])),
            judged("3. dalga en kısa", imp([50, 74, 64, 84, 76, 102]), "En uzun olması şart değil; en kısa olamaz."),
            judged("4. dalga 1'in alanına girdi", imp([50, 70, 60, 98, 66, 104]), "Örtüşme tek başına diyagonal kanıtı değildir."),
            judged("4'ün bitişi temiz ama fitili girdi", imp([50, 70, 60, 98, 78, 104], wave4_path_extreme=67),
                   "4'ün bütün yolu sayılır; kapanış beklenmez.",
                   sub=[(3, 98), (3.3, 76), (3.45, 88), (3.65, 67), (3.8, 83), (4, 78)]),
            judged("Güdük 5 (ihlal değil, uyarı)", imp([50, 70, 60, 104, 84, 100]),
                   "5'in içi tamamlanmış beşli olmalı. Bitmemiş harekete 'güdük' denmez."),
        ]),
        section("2. İç yapı, belirsizlik, geçersizlik", [
            judged("3. dalganın içi de aynı kurallara tabidir (E-05)", imp(up),
                   "İçi: 60 → 70 → 65 → 87 → 80 → 98. i, iii, v = 10, 22, 18; iv (80) i'nin tepesine (70) girmiyor.",
                   sub=[(2, 60), (2.2, 70), (2.4, 65), (2.65, 87), (2.8, 80), (3, 98)]),
            card("Aynı dört nokta, iki yorum", None, svg(ambiguous, ["0", "1 / A", "2 / B", "i / C"]), ambiguous,
                 "İçi 5-3-5 ise (1)-(2)-i de olabilir, A-B-C de. Ayıran şey üst derece ve sonraki fiyat. Ana + alternatif yazılır."),
            card("Geçersizlik dereceye göre", None,
                 svg(ambiguous, ["(0)", "(1)", "(2)", "1"], [(72, "altı: yalnız küçük 1-2 biter", AMBER),
                                                             (60, "altı: büyük (1)-(2) biter", RED)]), ambiguous,
                 "Küçük sayımın bozulması büyük sayımı otomatik bitirmez."),
        ]),
        section("3. Diyagonal", [
            judged("Geçerli daralan diyagonal adayı", dia([60, 100, 76, 110, 94, 116]),
                   "Konum 1/A (öncü) ya da 5/C (bitiş) olmalı; 3. dalga olamaz.", lines=[(1, 3, 6), (2, 4, 6)]),
            judged("4, 2'nin dibini aştı", dia([60, 100, 76, 110, 72, 116])),
            judged("5, 3'ten uzun", dia([60, 100, 76, 110, 94, 132])),
        ]),
        section("4. Zigzag ve yassı", [
            judged("Geçerli zigzag adayı (5-3-5)", zig([100, 76, 88, 62])),
            judged("B, A'nın başını geçti: zigzag değil", zig([100, 76, 103, 62]),
                   "Aynı uçlar genişleyen yassı olabilir: A'nın içi üçlü mü?"),
            judged("B çok derin: şüpheli zigzag", zig([100, 76, 96, 70])),
            judged("Normal yassı (3-3-5)", flat([100, 80, 98, 78])),
            judged("Genişleyen yassı", flat([100, 80, 105, 72]), "B'nin yeni tepe yapması yeni yükseliş değildir."),
            judged("Kaçan yassı", flat([100, 80, 106, 84])),
        ]),
        section("5. Üçgen ve karmaşık düzeltme", [
            judged("Geçerli daralan üçgen adayı", tri([100, 70, 94, 76, 89, 80]),
                   "Konum: 4, B, X; 2'nin tamamı olamaz. E çizgiye değmek zorunda değil.", lines=[(1, 3, 5.4), (2, 4, 5.4)]),
            judged("D, B'yi geçti: daralma yok", tri([100, 70, 94, 76, 97, 80])),
            card("W-X-Y (çift zigzag)", None, svg(wxy, LABELS["wxy"], motive_first=False), wxy,
                 "ABC bozuldu diye sonradan WXY yapılmaz. Tür belli değilse: 'düzeltme sürüyor, tür belirsiz' → plan yok."),
            card("W-X-Y (zigzag + yassı): yatay", None, svg(mixed, LABELS["wxy"], motive_first=False), mixed,
                 "E-63: X, W'nin b'sinden yüksek olabilir; Y, W'nin sonunu geçmek zorunda değil."),
            judged("B başlangıcı geçti: kaçan üçgen uyarısı", tri([100, 70, 103, 78, 96, 84])),
        ]),
        section("6. Ölçüm ve kanal", [
            card("3. dalga hedefi (0-1-2 uzatması)", None,
                 svg(start3, list("012"), [(80, "1 × [1] → 80", AMBER), (92.36, "1,618 × [1] → 92,36", AMBER)]), start3,
                 "Hedef 2'nin sonundan ölçülür: 60 + k × (70 − 50). Giriş fiyatından ölçülmez."),
            card("5. dalga bölgesi", None,
                 svg(up[:5], list("01234"), [(102, "[5] = [1] → 102", AMBER), (105.48, "0,618 × [3] → 105,48", AMBER)]), up[:5],
                 "4'ün sonundan ölçülür. Aynı bacaktan çıkan seviyeler birbirinin bağımsız kanıtı değildir."),
            card("Kanal: 2–4 çizgisi", None, svg([50, 70, 60, 98, 82, 112], list("012345"), lines=[(2, 4, 5.3)]),
                 [50, 70, 60, 98, 82, 112],
                 "Paraleli 3'ten geçer. Kanala değmemek ihlal değildir; kanal kırılması uyarıdır, kural kırılması sayımı eler."),
        ]),
    ]
    lead = ("Kendi çizimlerimiz ve kendi sayılarımız; kararları elliott_check.py hesaplar. Mavi: ana yöndeki dalgalar, gri: karşı "
            "dalgalar, kırmızı: ihlal, sarı: kılavuz/uyarı. Numaralar ELLIOTT.md'deki kurallardır. Yeşil karar 'olabilir' "
            "demektir, 'kesin' değil.")
    return page("Elliott kural görselleri", "".join(parts), lead)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")        # the Windows console default (cp1254) cannot print everything
    if len(sys.argv) == 1:
        path = HERE / "elliott-visuals.html"
        path.write_text(handbook(), encoding="utf-8")
    else:
        verdicts = ec.judge([float(a) for a in sys.argv[1:]])
        for v in verdicts:
            print(f"\n{NAMES[v.model]}: {'olabilir' if v.possible else 'DEĞİL'}")
            for f in v.findings:
                print(f"  [{f.level:9}] {f.rule}: {f.text}")
        path = SERVICE_DIR / "data" / "reports" / "elliott-check.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page("Sayım kontrolü", section("Modeller", [judged(NAMES[v.model], v) for v in verdicts])),
                        encoding="utf-8")
    print(f"\n{path}")


if __name__ == "__main__":
    main()
