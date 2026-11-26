r"""One page: every non-book rule with its words, its picture, how often it occurred and how often price respected it.

  .\venv\Scripts\python.exe -m signals.scoring.report        -> signals/rules/rule-tests.html
"""

from __future__ import annotations

import html
import json
import sys

from signals.data.candles import ASSETS, LTF, TIMEFRAMES
from signals.rules import rules_catalog as rc
from signals.scoring.reaction import wilson
from signals.scoring.rule_events import TESTS
from signals.scoring.run import OUT, wanted

MIN_N, FDR = 30, 0.05
ASSET_NAME = {"BTCUSDT": "BTC", "XAU": "Altın (15m–12h)", "GC": "Altın vadeli (1D+, hacim)", "SPX": "S&P (15m–12h)", "ES": "S&P vadeli (1D+, hacim)"}

# rules without a measurement: why
PROCESS = set("E-06 E-07 E-08 E-09 E-21 E-22 E-23 E-25 E-28 E-43 E-44 E-53 E-54 E-55 E-60 E-63 E-73 H-02 H-06 H-09 H-23 FT-01 FT-04a "
              "FT-05c MB-07 E-G1 E-G2 E-G3 E-G4 E-G5 E-G6 E-G7 E-G8 E-G9 E-61 E-62 E-70 E-72 E-74 E-82 E-83 E-90 E-91 E-92 E-93 E-94 E-95 E-98 E-99 E-101 "
              "E-102 F-01 F-02 F-04 F-05 F-07 FR-01 FT-05a FT-05b FM-06 H-10 H-11 H-12 H-13 H-14 PA-01 PA-02 PA-06 PA-09 PA-11 PA-36 PA-38 "
              "PA-39 SM-05 SM-24 SM-57 SM-62 SM-72 SM-73 SM-83 SM-93 SM-98 PR-02 PR-22 PR-23 PR-41 PR-62 PR-72 PR-73 MB-03 MB-12 MB-13 MB-14 "
              "MB-15 MB-23 MB-25".split())
CME = "CME 29.05.2026'dan beri 7/24, yeni boşluk yok"
NO_DATA = {"E-100": "korelasyon için ETH, gümüş, Nasdaq, DXY verisi yok", "PR-26": "likidasyon haritası için açık veri yok",
           "PR-71": "BTC.D, USDT.D, TOTAL verisi yok", "MB-24": "opsiyon, korku-açgözlülük verisi yok", "PR-50": CME, "PR-51": CME,
           "SM-97": "yön söylemiyor, yalnız hareket büyüklüğü", "SM-03": "doji yön söylemiyor", "SM-04": "inside bar yön söylemiyor",
           "PR-60c": "tek örnek, kural değil", "E-84": "OBO / bayrak tespit kodu yok"}
SHARE: set[str] = set()


def main_k(frame: str) -> int:
    """Aykut, 25 Nov: respect = 1 ATR on the lower frames, 2 ATR on the higher frames (index into reaction.KS)."""
    return 0 if frame in LTF else 1


def why_untested(rule: str) -> str:
    if rule.startswith("RK-"):
        return "süreç / risk kuralı: fiyat tepkisi ölçülmez, puan almaz (sistem ayarı)"
    if rule in NO_DATA:
        return "ölçülemedi: " + NO_DATA[rule]
    if rule in PROCESS:
        return "tanım / yöntem kuralı: tek başına tepki beklenmez, öbür testlerin içinde kullanılır; puan almaz"
    return "ayrı testi henüz yok (sonraki tur)"


def load() -> dict:
    """(test, asset, frame) -> result with its verdict. Benjamini-Hochberg over every judged test of every asset and frame."""
    rows = [r for r in json.loads((OUT / "rule_results.json").read_text(encoding="utf-8")) if r["asset"] in ASSET_NAME and wanted(r["asset"], r["frame"], r["key"])]
    for r in rows:
        if "error" not in r:
            k = main_k(r["frame"])
            r["k"], r["p_main"] = k, r["p"][k]
            r["p_worse"] = r["worse"][k]
    good = sorted((r for r in rows if r.get("n", 0) >= MIN_N and r["null_n"] >= MIN_N), key=lambda r: r["p_main"])
    cut = max((r["p_main"] for k, r in enumerate(good, 1) if r["p_main"] <= FDR * k / len(good)), default=0.0)
    for r in rows:
        r["state"] = ("hata" if "error" in r else "az" if r["n"] < MIN_N or r["null_n"] < MIN_N else
                      "saygı" if r["p_main"] <= cut else "ters" if r["p_worse"] <= cut else "yok")
    return {(r["key"], r["asset"], r["frame"]): r for r in rows}


def cell(r: dict | None) -> str:
    if r is None:
        return "<td></td>"
    if "error" in r:
        return f'<td class="err" title="{html.escape(r["error"])}">hata</td>'
    if r["n"] == 0:
        return f'<td class="az" title="oluşum {r["seen"]}">0</td>'
    rate = [w / r["n"] for w in r["wins"]]
    k = r["k"]
    low, high = wilson(r["wins"][k], r["n"])
    tip = (f"oluşum {r['seen']}, ölçülen {r['n']}, saygının %95 aralığı {100 * low:.0f}–{100 * high:.0f} | 1 ATR (%{r['atr_pct']}): %{100 * rate[0]:.0f}, kontrol %{100 * r['base'][0]:.0f} | 2 ATR: %{100 * rate[1]:.0f} / "
           f"%{100 * r['base'][1]:.0f} | 3 ATR: %{100 * rate[2]:.0f} / %{100 * r['base'][2]:.0f}")
    return (f'<td class="{r["state"]}" title="{tip}"><b>%{100 * rate[k]:.0f}</b> <i>{100 * (rate[k] - r["base"][k]):+.0f}</i>'
            f'<br><small>{r["n"]} kez</small></td>')


def test_table(keys: list[str], table: dict) -> str:
    out = []
    for t in (t for t in TESTS if t.key in keys):
        rows = []
        for a in ASSET_NAME:
            cells = [table.get((t.key, a, f)) for f in TIMEFRAMES]
            if any(cells):
                rows.append(f"<tr><th>{ASSET_NAME[a]}</th>" + "".join(cell(c) for c in cells) + "</tr>")
        head = "".join(f"<th>{f}</th>" for f in TIMEFRAMES)
        out.append(f'<p class="tt">{html.escape(t.title)} <code>{t.key}</code></p><div class="scroll"><table class="bt">'
                   f'<tr><th></th>{head}</tr>{"".join(rows)}</table></div>')
    return "".join(out)


def pooled(keys: list[str], table: dict, assets: tuple[str, ...], frames: list[str]) -> str:
    """All of a rule's tests on these frames together: respect, control, number of cases (colour: how many single cells passed)."""
    rs = [table[(k, a, f)] for k in keys for a in assets for f in frames if (k, a, f) in table and table[(k, a, f)].get("n", 0) and "k" in table[(k, a, f)]]
    n = sum(r["n"] for r in rs)
    if not n:
        return "<td>–</td>"
    rate, base = sum(r["wins"][r["k"]] for r in rs) / n, sum(r["base"][r["k"]] * r["n"] for r in rs) / n
    good, judged = sum(r["state"] == "saygı" for r in rs), sum(r["state"] in ("saygı", "yok", "ters") for r in rs)
    css = "saygı" if good else "az" if n < MIN_N or not judged else "yok"
    return f'<td class="{css}" title="{good} / {judged} ölçüm anlamlı iyi"><b>%{100 * rate:.0f}</b> <i>{100 * (rate - base):+.0f}</i><br><small>{n} kez</small></td>'


SETS = (("BTC", ("BTCUSDT",)), ("Altın", ("XAU", "GC")), ("S&P", ("SPX", "ES")))


def summary(by_rule: dict, table: dict) -> str:
    rows = []
    for f in rc.FAMILIES:
        if f.key == "kitap":
            continue
        for r in rc.read_rules((rc.HERE / f.words).read_text(encoding="utf-8")):
            keys = by_rule.get(r.id, [])
            words = rc.rich(r.words if len(r.words) < 110 else r.words[:107] + "…")
            if keys:
                cells = "".join(pooled(keys, table, a, LTF) + pooled(keys, table, a, [t for t in TIMEFRAMES if t not in LTF]) for _, a in SETS)
            else:
                cells = f'<td colspan="6" class="none">{why_untested(r.id)}</td>'
            rows.append(f'<tr><td><b>{r.id}</b> {words}</td>{cells}</tr>')
    head = "".join(f'<th colspan="2">{n}</th>' for n, _ in SETS)
    return ('<h2 id="ozet">Kural kural özet</h2><p>LTF = 15m–2h (1 ATR), HTF = 4h ve üstü (2 ATR); kuralın bütün testleri birlikte. Yeşil: en az bir dilimde '
            'anlamlı iyi. Bir kuralın birden çok testi varsa hepsi sayılır; ayrıntı aşağıda kuralın kendi kutusunda.</p><div class="scroll"><table class="bt left">'
            f'<tr><th rowspan="2">Kural</th>{head}</tr><tr>{"<th>LTF</th><th>HTF</th>" * 3}</tr>{"".join(rows)}</table></div>')


def samples(keys: list[str], table: dict) -> str:
    out = []
    for k in keys[:3]:
        for a, f in (("BTCUSDT", "4h"), ("BTCUSDT", "1h"), ("XAU", "1h"), ("SPX", "1h")):
            r = table.get((k, a, f))
            if r and r.get("samples"):
                out.append(f"<li>{ASSET_NAME[a]} {f}: " + " · ".join(f'{t[:16].replace("T", " ")} {"↑" if d > 0 else "↓"} {p:,.0f} {"✓" if w[r["k"]] else "✗"}' for t, d, p, w in r["samples"]) + "</li>")
    return f'<details><summary>Son örnekler (UTC; ↑↓ beklenen yön, ✓ saygı): TradingView\'de kontrol et</summary><ul>{"".join(out)}</ul></details>' if out else ""


def share_section() -> str:
    path = OUT / "elliott_share.json"
    if not path.exists():
        return ""
    rows = [r for r in json.loads(path.read_text(encoding="utf-8")) if wanted(r["asset"], r["frame"], "")]
    names = [("hepsi", "4 kesin kuralı tutan 5 bacak"), ("dönüş itki", "dönüş = itki sonu"), ("dönüş ABC", "dönüş = ABC sonu"),
             ("dönüş üçgen", "dönüş = üçgen sonu"), ("dönüş diyagonal", "dönüş = diyagonal sonu"), ("dönüş herhangi biri", "dönüş = herhangi biri")]
    body = "".join(f"<tr><th>{ASSET_NAME[r['asset']]} {r['frame']}</th><td>{r['real']['n_dönüş']}</td>" + "".join(
        f'<td class="{"saygı" if r["real"][k] > r["fake_max"][k] else "yok"}"><b>%{100 * r["real"][k]:.0f}</b> '
        f'<small>rastgele %{100 * r["fake"][k]:.0f}</small></td>' for k, _ in names) + "</tr>" for r in rows)
    return ('<h2 id="share">Elliott grafikte ne kadar var?</h2><p>Büyük dönüşlerin (6 ATR) kaçı bir dalga sayımının sonu? Yanındaki sayı, aynı '
            "mumların karıştırılmış halinde (gerçek dalga yok) bulunan paydır. Yeşil: gerçek grafik, karıştırılmışların hepsinden yüksek.</p>"
            '<div class="scroll"><table class="bt"><tr><th></th><th>büyük dönüş</th>' + "".join(f"<th>{n}</th>" for _, n in names)
            + f"</tr>{body}</table></div>")


def ranking(table: dict) -> str:
    out, titles = [], {t.key: t for t in TESTS}
    for a in ASSET_NAME:
        best = sorted((r for r in table.values() if r["asset"] == a and r["state"] == "saygı"), key=lambda r: -(r["wins"][r["k"]] / r["n"] - r["base"][r["k"]]))
        body = "".join(f'<tr><td>{html.escape(titles[r["key"]].title)}</td><td>{titles[r["key"]].rules}</td><td>{r["frame"]}</td>{cell(r)}</tr>'
                       for r in best)
        out.append(f"<h3>{ASSET_NAME[a]}: kontrolden anlamlı iyi {len(best)} ölçüm</h3>" + (
            '<div class="scroll"><table class="bt left"><tr><th>Test</th><th>Kural</th><th>Dilim</th><th>Saygı</th></tr>'
            f"{body}</table></div>" if best else "<p>Yok.</p>"))
    return "".join(out)


CSS = """
.bt{border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
.bt td,.bt th{padding:4px 8px;border:1px solid var(--grid);text-align:center}
.bt td i{font-style:normal;color:var(--muted)}.bt .saygı{background:color-mix(in srgb,var(--good) 28%,transparent)}
.bt .ters{background:rgba(204,51,51,.28)}.bt .az,.bt .err{color:var(--muted);opacity:.65}.scroll{overflow-x:auto}
.tt{margin:10px 0 4px;font-weight:600;font-size:14px}.left td:first-child{text-align:left}.none a,p a{color:var(--motive)}.none{color:var(--muted);font-size:13.5px}
main{max-width:1250px}.pair.one{border-top:1px solid var(--grid);padding:8px 0}.pair.one figure{max-width:560px}
"""


def extra_sections() -> str:
    """Combination and points tables, when they have been made (combo.py, points.py)."""
    return "".join((OUT / n).read_text(encoding="utf-8") for n in ("points.html", "combo.html") if (OUT / n).exists())


def build() -> tuple[str, dict]:
    table = load()
    by_rule: dict[str, list[str]] = {}
    for t in TESTS:
        for r in t.rules.split():
            by_rule.setdefault(r, []).append(t.key)
    parts, nav, count = [], [], {"kural": 0, "ölçülen": 0, "Elliott payı": 0, "görselsiz": 0, "görseli çizilecek": 0}
    for f in rc.FAMILIES:
        if f.key == "kitap":
            continue
        rules = rc.read_rules((rc.HERE / f.words).read_text(encoding="utf-8"))
        pictures = rc.read_pictures(f.key, (rc.HERE / f.pictures).read_text(encoding="utf-8")) if f.pictures else []
        items, used = [], set()
        for r in rules:
            count["kural"] += 1
            mine = [(i, p) for i, p in enumerate(pictures) if r.id in p.rules]
            art = "".join(p.body for i, p in mine if i not in used)
            used |= {i for i, _ in mine}
            keys = by_rule.get(r.id, [])
            count["ölçülen"] += bool(keys)
            count["Elliott payı"] += r.id in SHARE
            note = ""
            if not mine:
                count["görselsiz"] += 1
                draw = bool(keys) or why_untested(r.id).startswith("ayrı")
                count["görseli çizilecek"] += draw
                note = "Görsel yok: çizilecek." if draw else "Görsel yok: koymak mantıklı değil (çizilecek bir şekil yok)."
            elif not art:
                note = "Görseli, aynı görseli paylaşan önceki kuralda."
            measured = test_table(keys, table) + samples(keys, table) if keys else f'<p class="none">{why_untested(r.id)}</p>'
            if r.id in SHARE:
                measured = '<p class="none">Gerçekleşme oranı yukarıdaki "Elliott grafikte ne kadar var?" tablosunda.</p>' + measured * bool(keys)
            items.append(f'<section class="pair one"><ul class="bare">{rc.rule_html(r)}</ul>{art}<p class="none">{note}</p>{measured}</section>')
        nav.append(f'<a href="#{f.key}">{f.name}</a>')
        parts.append(f'<h2 id="{f.key}">{f.name}</h2>' + "".join(items))
    lead = ("Her hücre: <b>saygı oranı</b>, yanında kontrolden farkı (puan), altında kaç kez ölçüldüğü. Saygı = kural oluştuktan sonra fiyat, kuralın "
            "yönünde 1 ATR (15m–2h) ya da 2 ATR (4h ve üstü) gitti ve bunu ters yönde aynı kadar gitmeden yaptı (60 mum içinde). Kontrol = aynı kuralın aynı kodla "
            "karıştırılmış fiyatta aldığı oran. Yeşil: kontrolden anlamlı iyi (çoklu deneme düzeltmeli). Kırmızı: kontrolden anlamlı kötü. Soluk: 30'dan az örnek. Verinin ilk "
            "%70'i; son %30 yalnız puan sınavında kullanıldı. Hücrenin üstüne gelince 2 ve 3 ATR sonuçları çıkar.")
    page = ('<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Kural backtesti</title><style>{rc.CSS}{rc.CHART_CSS}{rc.EXTRA_CSS}{CSS}</style></head><body><main>"
            f'<h1>Kural backtesti (kitaplar hariç)</h1><p><b>Bu sayfa eski yöntemdir (girişten ±ATR yarışı).</b> Geçerli yöntem: <a href="confirmations.html">tepe ve diplerde onaylar</a>.</p><p class="lead">{lead}</p>'
            f'<div class="top"><input id="q" type="search" placeholder="Ara: SM-30, SFP, fib…" aria-label="Kural ara"><div>{"".join(nav)}</div></div>'
            f'<p><a href="#puan">Puan tablosu</a> · <a href="#combo">Birlikte testler</a> · <a href="#ozet">Kural kural özet</a> · <a href="#share">Elliott payı</a></p>'
            f"{extra_sections()}{ranking(table)}{summary(by_rule, table)}{share_section()}{''.join(parts)}</main><script>{rc.SCRIPT}</script></body></html>")
    return page, count


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    page, count = build()
    (rc.HERE / "rule-tests.html").write_text(page, encoding="utf-8")
    print(count)


if __name__ == "__main__":
    main()
