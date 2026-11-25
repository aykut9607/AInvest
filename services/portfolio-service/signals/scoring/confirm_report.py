r"""Rule tree x timeframe x asset: what every confirmation was worth (confirm.py).

  .\venv\Scripts\python.exe -m signals.scoring.confirm_report   -> signals/rules/confirmations.html, data/reports/confirm_points.json
"""

from __future__ import annotations

import html
import json
import sys
from bisect import bisect_left
from statistics import median

from signals.data.candles import TIMEFRAMES
from signals.rules import rules_catalog as rc
from signals.scoring.confirm import ASSETS
from signals.scoring.reaction import p_value
from signals.scoring.rule_events import SPAN
from signals.scoring.run import OUT

NAME = {"BTCUSDT": "BTC", "XAU": "Altın", "SPX": "S&P"}
MIN_N, FDR, MAX_POINTS, SURE, SPLIT = 30, 0.05, 15, 0.84, 0.7
ORDER = ("Elliott", "Harmonik", "Uyumsuzluk", "SFP", "Price action", "Fibonacci", "Key level", "Hacim profili", "Smart money", "Önceki dönem", "EXT bandı", "Funding")
ONE_ONLY = ("Elliott", "Harmonik")              # one category = one confirmation; the others count rule by rule


def load(asset: str, seed: int) -> dict:
    return json.loads((OUT / f"confirm_{asset}_{seed}.json").read_text(encoding="utf-8"))


def split(rows: list) -> tuple[list, list]:
    if not rows:
        return [], []
    cut = rows[0][0] + (rows[-1][0] - rows[0][0]) * SPLIT
    return [r for r in rows if r[0] <= cut], [r for r in rows if r[0] > cut]


def keys(row) -> set[str]:
    out = set()
    for tag in row[6]:
        c, r, v = tag.split("|")
        out |= {c, f"{c}|{r}"} | ({tag} if v else set())
    return out


def stats(rows: list) -> dict[str, dict]:
    """Every key: cases with it against cases without it."""
    tagged = [keys(r) for r in rows]
    n, w, l = len(rows), sum(r[3] for r in rows), sum(r[4] for r in rows)
    have: dict[str, list] = {}
    for r, s in zip(rows, tagged):
        for k in s:
            have.setdefault(k, []).append(r)
    out = {}
    for k, a in have.items():
        m, wa, la = len(a), sum(r[3] for r in a), sum(r[4] for r in a)
        s = {"n": m}
        if m >= 5 and n - m >= 5:
            p1, p0 = wa / m, (w - wa) / (n - m)
            se = (p1 * (1 - p1) / m + p0 * (1 - p0) / (n - m)) ** 0.5
            s.update(rate=p1, rest=p0, move=median(r[2] for r in a), after=la / m, after_rest=(l - la) / (n - m), p=p_value(wa, m, w - wa, n - m),
                     low=p_value(m - wa, m, n - m - (w - wa), n - m), se=100 * se)
        out[k] = s
    return out


def diff(s: dict) -> float:
    return 100 * (s["rate"] - s["rest"])


def analyse() -> dict:
    all_: dict = {}
    for a in ASSETS:
        real, fake = load(a, 0), load(a, 1)
        for f in TIMEFRAMES:
            fit, exam = split(real.get(f, []))
            if len(fit) < 5:
                continue
            all_[(a, f)] = {"fit_rows": fit, "exam_rows": exam, "fake_rows": fake.get(f, []), "fit": stats(fit), "exam": stats(exam), "fake": stats(fake.get(f, [])),
                            "rate": sum(r[3] for r in fit) / len(fit), "thr": median(r[5] for r in fit)}
    pool = sorted((s for d in all_.values() for s in d["fit"].values() if s["n"] >= MIN_N and "p" in s), key=lambda s: s["p"])
    cut = max((s["p"] for i, s in enumerate(pool, 1) if s["p"] <= FDR * i / len(pool)), default=0.0)
    for d in all_.values():
        d["points"], d["candidate"] = {}, {}
        for k, s in d["fit"].items():
            if "p" not in s:
                continue
            g = d["fake"].get(k, {})
            geo = max(0.0, diff(g)) if g.get("n", 0) >= MIN_N and "p" in g and not k.startswith("Funding") else 0.0       # what shuffled prices give for free
            s["geo"] = geo
            s["good"] = s["n"] >= MIN_N and s["p"] <= cut and diff(s) > geo
            s["bad"] = s["n"] >= MIN_N and s["low"] <= cut
            edge = diff(s) - SURE * s["se"] - geo
            if s["good"] and edge >= 1:
                d["candidate"][k] = round(min(MAX_POINTS, edge))
                e = d["exam"].get(k, {})
                if e.get("n", 0) >= 15 and "p" in e and diff(e) > geo:
                    d["points"][k] = d["candidate"][k]
    return all_


def best(tags: list[str], pts: dict[str, int]) -> dict[str, int]:
    """Confirmation -> points at one top: the most specific matching entry, one per rule (one per category for Elliott and harmonics)."""
    out: dict[str, int] = {}
    for tag in tags:
        c, r, v = tag.split("|")
        p = max(pts.get(k, 0) for k in (c, f"{c}|{r}", tag))
        name = c if c in ONE_ONLY else f"{c}|{r}"
        if p:
            out[name] = max(out.get(name, 0), p)
    return out


def scores(all_: dict, part: str, kind: str = "candidate") -> dict:
    """(asset, frame) -> [(score, row)]: own points plus those of the lower frames whose pivot is this very top (each rule once)."""
    out = {}
    for a in ASSETS:
        frames = [f for f in TIMEFRAMES if (a, f) in all_]
        table = {f: [(r, best(r[6], all_[(a, f)][kind])) for r in (sorted(all_[(a, f)]["fit_rows"] + all_[(a, f)]["exam_rows"]) if part != "fake_rows" else all_[(a, f)]["fake_rows"])] for f in frames}
        times = {f: [r[0] for r, _ in v] for f, v in table.items()}
        for i, f in enumerate(frames):
            rows = all_[(a, f)][part]
            wanted = {(r[0], r[1]) for r in rows}
            span, res = SPAN[f].total_seconds(), []
            for r, own in table[f]:
                if (r[0], r[1]) not in wanted:
                    continue
                total = dict(own)
                for g in frames[:i]:
                    k = bisect_left(times[g], r[0])
                    while k < len(times[g]) and times[g][k] < r[0] + span:
                        q, pts = table[g][k]
                        if q[1] == r[1] and abs(q[7] - r[7]) <= 1e-4 * r[7]:
                            for n, p in pts.items():
                                total[n] = max(total.get(n, 0), p)
                        k += 1
                res.append((sum(total.values()), len(total), r))
            out[(a, f)] = res
    return out


def pct(v: float) -> str:
    return f"%{100 * v:.0f}"


def cell(d: dict | None, k: str) -> str:
    s = d["fit"].get(k) if d else None
    if not s or "p" not in s:
        return f'<td class="az">{s["n"] if s else ""}</td>'
    css = "saygı" if s["good"] else "ters" if s["bad"] else "az" if s["n"] < MIN_N else "yok"
    e, g = d["exam"].get(k, {}), d["fake"].get(k, {})
    tip = (f"çalıştı {pct(s['rate'])}, bu onay yokken {pct(s['rest'])}; ortanca hareket %{s['move']:.1f}; tepe kesinleştikten sonra {pct(s['after'])} / {pct(s['after_rest'])}; "
           f"son %30: {pct(e['rate']) + ' / ' + pct(e['rest']) + ' (' + str(e['n']) + ' kez)' if 'p' in e else 'az örnek'}; karıştırılmış fiyatta fark {diff(g):+.0f}" if "p" in g else
           f"çalıştı {pct(s['rate'])}, bu onay yokken {pct(s['rest'])}; ortanca hareket %{s['move']:.1f}")
    point = d["points"].get(k)
    return f'<td class="{css}" title="{tip}"><b>{pct(s["rate"])}</b> <i>{diff(s):+.0f}</i><br><small>{s["n"]} kez{f" · <b>{point} puan</b>" if point else ""}</small></td>'


def tree(a: str, all_: dict) -> str:
    ks = {k for f in TIMEFRAMES if (a, f) in all_ for k, s in all_[(a, f)]["fit"].items() if s["n"] >= 5}
    cats = sorted({k.split("|")[0] for k in ks}, key=lambda c: ORDER.index(c) if c in ORDER else 99)
    head = "".join(f"<th>{f}</th>" for f in TIMEFRAMES)
    body = ""
    row = lambda k, name, css: f'<tr class="{css}"><td>{html.escape(name)}</td>' + "".join(cell(all_.get((a, f)), k) for f in TIMEFRAMES) + "</tr>"
    for c in cats:
        body += row(c, c, "cat")
        for r in sorted(k for k in ks if k.count("|") == 1 and k.startswith(c + "|")):
            body += row(r, "— " + r.split("|")[1], "rule")
            for v in sorted(k for k in ks if k.startswith(r + "|")):
                body += row(v, "— — " + v.split("|")[2], "var")
    base = "".join(f'<td>{pct(all_[(a, f)]["rate"])}<br><small>eşik %{all_[(a, f)]["thr"]:.1f}</small></td>' if (a, f) in all_ else "<td></td>" for f in TIMEFRAMES)
    return f'<div class="scroll"><table class="bt left tree"><tr><th>Kural</th>{head}</tr><tr><td><i>bütün tepe/dipler</i></td>{base}</tr>{body}</table></div>'


BUCKETS = ((0, 1), (1, 10), (10, 20), (20, 30), (30, 40), (40, 55), (55, 999))


def score_tables(a: str, sc: dict) -> str:
    out = ""
    for f in TIMEFRAMES:
        if (a, f) not in sc["fit_rows"]:
            continue
        rows = ""
        for lo, hi in BUCKETS:
            tds = ""
            for part in ("fit_rows", "exam_rows", "fake_rows"):
                s = [r for p, _, r in sc[part].get((a, f), []) if lo <= p < hi]
                tds += (f'<td>{pct(sum(r[3] for r in s) / len(s))} <small>({len(s)})</small></td><td>{pct(sum(r[4] for r in s) / len(s))}</td><td>%{median(r[2] for r in s):.1f}</td>' if len(s) >= 5
                        else f"<td><small>({len(s)})</small></td><td></td><td></td>")
            rows += f'<tr><td>{lo if hi - lo == 1 else f"{lo}–{hi - 1}" if hi < 999 else f"{lo}+"}</td>{tds}</tr>'
        out += (f'<details{" open" if f in ("1h", "4h") else ""}><summary>{f}</summary><div class="scroll"><table class="bt"><tr><th rowspan="2">Toplam puan</th><th colspan="3">İlk %70</th><th colspan="3">Son %30</th><th colspan="3">Karıştırılmış fiyat</th></tr>'
                f'<tr>{"<th>çalıştı</th><th>kesinleştikten sonra</th><th>ortanca hareket</th>" * 3}</tr>{rows}</table></div></details>')
    return out


CSS = """
.tree .cat td{font-weight:700;border-top:2px solid var(--muted)}.tree .rule td:first-child{font-weight:600}.tree .var td:first-child{color:var(--muted)}
.tree td:first-child{position:sticky;left:0;background:var(--bg);min-width:230px}main{max-width:1500px}
"""


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    all_ = analyse()
    sc = {p: scores(all_, p) for p in ("fit_rows", "exam_rows", "fake_rows")}
    from signals.scoring.report import CSS as REPORT_CSS
    lead = ("Her satır bir kural, her sütun bir zaman dilimi. Aday = o dilimde oluşan tepe ya da dip (önünde 5, arkasında 2 mum). <b>Çalıştı</b> = 15 dakikalık mumlarda, tepe/dip geçilmeden, o dilimin 3 ATR'si kadar hareket geldi "
            "(40 mum içinde; 1w 2 ATR / 26 mum, 1M 1,5 ATR / 12 mum; ortanca eşik sütunun başında). Hücrede: çalışma oranı, yanında bu onayın <b>olmadığı</b> tepe/diplerden farkı, altında kaç kez oluştuğu ve aldığı puan. Yeşil: anlamlı iyi ve karıştırılmış fiyattaki "
            "farktan da büyük. Kırmızı: anlamlı kötü. Soluk: 30'dan az örnek. Puan = emin olunan fark (en çok 15), son %30'da da tutan kurala. Hücrenin üstüne gelince ayrıntı çıkar.")
    blocks = "".join(f'<h2 id="{a}">{NAME[a]}</h2>{tree(a, all_)}<h3>{NAME[a]}: toplam puan ne kadar yüksekse o kadar mı iyi?</h3>'
                     f"<p>Toplam puan = o tepedeki bütün onayların puanları (aynı tepedeki alt dilim onayları dahil; Elliott ve harmonik birer onay sayılır).</p>{score_tables(a, sc)}" for a in ASSETS)
    page = ('<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Onay backtesti</title>'
            f"<style>{rc.CSS}{rc.CHART_CSS}{rc.EXTRA_CSS}{REPORT_CSS}{CSS}</style></head><body><main><h1>Onay backtesti: kural × zaman dilimi × parite</h1><p class=\"lead\">{lead}</p>"
            f"<p>{' · '.join(f'<a href=#{a}>{NAME[a]}</a>' for a in ASSETS)}</p>{blocks}</main></body></html>")
    (rc.HERE / "confirmations.html").write_text(page, encoding="utf-8")
    (OUT / "confirm_points.json").write_text(json.dumps({"version": "v3", "points": {f"{a} {f}": d["points"] for (a, f), d in all_.items()}, "fit": {f"{a} {f}": d["fit"] for (a, f), d in all_.items()},
                                                         "exam": {f"{a} {f}": d["exam"] for (a, f), d in all_.items()}}, ensure_ascii=False), encoding="utf-8")
    for a in ASSETS:
        print("==", a)
        for f in TIMEFRAMES:
            if (a, f) in all_:
                d = all_[(a, f)]
                line = []
                for lo, hi in ((0, 10), (20, 30), (30, 40), (40, 55), (55, 999)):
                    c = []
                    for part in ("fit_rows", "exam_rows", "fake_rows"):
                        s = [r for p, _, r in sc[part].get((a, f), []) if lo <= p < hi]
                        c.append(f"{100 * sum(r[3] for r in s) / len(s):.0f}>{100 * sum(r[4] for r in s) / len(s):.0f}({len(s)})" if len(s) >= 10 else "-")
                    line.append(f"{lo}+: " + " / ".join(c))
                print(f, len(d["fit_rows"]), f"eşik %{d['thr']:.1f}", pct(d["rate"]), "puan alan", len(d["points"]), "|", " | ".join(line))


if __name__ == "__main__":
    main()
