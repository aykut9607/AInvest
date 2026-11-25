r"""Rule tree x timeframe x asset: what every confirmation was worth (confirm.py).

  .\venv\Scripts\python.exe -m signals.scoring.confirm_report   -> signals/rules/confirmations.html, data/reports/confirm_points.json
"""

from __future__ import annotations

import html
import json
import sys
from bisect import bisect_left
from statistics import mean, median

from signals.data.candles import TIMEFRAMES
from signals.rules import rules_catalog as rc
from signals.scoring.confirm import ASSETS, WORKED
from signals.scoring.reaction import p_value
from signals.scoring.rule_events import SPAN
from signals.scoring.run import OUT

NAME = {"BTCUSDT": "BTC", "XAU": "Altın", "SPX": "S&P"}
MIN_N, FDR, SURE, SPLIT = 30, 0.05, 0.84, 0.7
FULL = 100               # points of one asset when every confirmation it has is present
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
            q1, q0 = (wa + 1) / (m + 2), (w - wa + 1) / (n - m + 2)          # never zero: 35 of 35 is not certainty
            se = (q1 * (1 - q1) / m + q0 * (1 - q0) / (n - m)) ** 0.5
            good = [r[2] for r in a if r[3]]
            s.update(rate=p1, rest=p0, avg=mean(good) if good else 0.0, mid=median(good) if good else 0.0, after=la / m, after_rest=(l - la) / (n - m), p=p_value(wa, m, w - wa, n - m),
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
                            "rate": sum(r[3] for r in fit) / len(fit), "avg": mean([r[2] for r in fit if r[3]] or [0.0])}
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
                d["candidate"][k] = edge
                e = d["exam"].get(k, {})
                if e.get("n", 0) >= 15 and "p" in e and diff(e) > geo:
                    d["points"][k] = d["candidate"][k]
    for a in ASSETS:                                   # to 100: the best value of every confirmation of the asset adds up to FULL
        for kind in ("points", "candidate"):
            frames = [d for (b, _), d in all_.items() if b == a]
            top: dict[str, float] = {}
            for d in frames:
                for k in d["fit"]:
                    if "|" in k:                          # what best() can give: the rule's own value or that of its category
                        p = max(d[kind].get(x, 0.0) for x in (k.split("|")[0], "|".join(k.split("|")[:2]), k))
                        top[name_of(k)] = max(top.get(name_of(k), 0.0), p)
            full = sum(top.values()) or 1.0
            for d in frames:
                d[kind] = {k: round(FULL * p / full, 1) for k, p in d[kind].items()}
    return all_


def name_of(key: str) -> str:
    """The confirmation a key belongs to: the rule, or the whole category for Elliott and harmonics."""
    parts = key.split("|")
    return parts[0] if parts[0] in ONE_ONLY else "|".join(parts[:2])


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


def point_of(d: dict, k: str) -> float:
    return d["points"].get(k, 0)


def fmt(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def cell(d: dict | None, k: str) -> str:
    s = d["fit"].get(k) if d else None
    if not s or "p" not in s:
        return f'<td class="az">{s["n"] if s else ""}</td>'
    css = "saygı" if point_of(d, k) else "az" if s["n"] < MIN_N else "yok"
    e, g = d["exam"].get(k, {}), d["fake"].get(k, {})
    tip = (f"çalıştı {pct(s['rate'])}, bu onay yokken {pct(s['rest'])} (fark {diff(s):+.1f}); çalışanlarda ortalama hareket %{s['avg']:.1f}, ortanca %{s['mid']:.1f}; tepe kesinleştikten sonra {pct(s['after'])} / {pct(s['after_rest'])}; "
           f"son %30: {pct(e['rate']) + ' / ' + pct(e['rest']) + ' (' + str(e['n']) + ' kez)' if 'p' in e else 'az örnek'}; karıştırılmış fiyatta fark {diff(g):+.0f}" if "p" in g else
           f"çalıştı {pct(s['rate'])}, bu onay yokken {pct(s['rest'])}; çalışanlarda ortalama hareket %{s['avg']:.1f}, ortanca %{s['mid']:.1f}")
    point = point_of(d, k)
    return f'<td class="{css}" title="{tip}"><b>{pct(s["rate"])}</b> <i>yokken {pct(s["rest"])}</i><br><small>ort. %{s["avg"]:.1f} · {s["n"]} kez{f"<br><b>{fmt(point)} puan</b>" if point else ""}</small></td>'


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
    base = "".join(f'<td>{pct(all_[(a, f)]["rate"])}<br><small>ort. %{all_[(a, f)]["avg"]:.1f}</small></td>' if (a, f) in all_ else "<td></td>" for f in TIMEFRAMES)
    return f'<div class="scroll"><table class="bt left tree"><tr><th>Kural</th>{head}</tr><tr><td><i>bütün tepe/dipler</i></td>{base}</tr>{body}</table></div>'


BUCKETS = ((0, 0.01), (0.01, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 40), (40, 999))


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
                tds += (f'<td>{pct(sum(r[3] for r in s) / len(s))} <small>({len(s)})</small></td><td>{pct(sum(r[4] for r in s) / len(s))}</td><td>%{mean([r[2] for r in s if r[3]] or [0.0]):.1f}</td>' if len(s) >= 5
                        else f"<td><small>({len(s)})</small></td><td></td><td></td>")
            rows += f'<tr><td>{"0" if hi < 1 else f"{lo:.0f}–{hi}" if hi < 999 else f"{lo}+"}</td>{tds}</tr>'
        out += (f'<details{" open" if f in ("1h", "4h") else ""}><summary>{f}</summary><div class="scroll"><table class="bt"><tr><th rowspan="2">Toplam puan</th><th colspan="3">İlk %70</th><th colspan="3">Son %30</th><th colspan="3">Karıştırılmış fiyat</th></tr>'
                f'<tr>{"<th>çalıştı</th><th>kesinleştikten sonra</th><th>ortalama hareket</th>" * 3}</tr>{rows}</table></div></details>')
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
    lead = ("Her satır bir kural, her sütun bir zaman dilimi. Aday = o dilimde oluşan tepe ya da dip (önünde 5, arkasında 2 mum). <b>Çalıştı</b> = 15 dakikalık mumlarda, tepe/dip (0,25 ATR'den fazla) geçilmeden en az <b>BTC'de %2, altında %0,52, S&P'de %0,57</b> hareket geldi (oynaklığa göre aynı zorluk) (o dilimin 40 mumu içinde; 1w 26, 1M 12). "
            "Hücrede: çalışma oranı, yanında bu onayın <b>olmadığı</b> tepe/diplerin oranı; altında çalışanların <b>ortalama</b> hareketi, kaç kez oluştuğu ve puanı. Yeşil: puan aldı (onay varken oran, yokken ve karıştırılmış fiyattaki "
            "farktan anlamlı büyük, son %30'da da tutmuş). Renksiz: puan almadı; eksi puan yok. Soluk: 30'dan az örnek. Puan 100 üzerinden: bir paritenin bütün onayları aynı anda olsa 100 eder (Elliott ve harmonik birer onay). Hücrenin üstüne gelince ayrıntı çıkar.")
    blocks = "".join(f'<h2 id="{a}">{NAME[a]}</h2>{tree(a, all_)}<h3>{NAME[a]}: toplam puan ne kadar yüksekse o kadar mı iyi?</h3>'
                     f"<p>Toplam puan = o tepedeki bütün onayların puanları (aynı tepedeki alt dilim onayları dahil; Elliott ve harmonik birer onay sayılır).</p>{score_tables(a, sc)}" for a in ASSETS)
    page = ('<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Onay backtesti</title>'
            f"<style>{rc.CSS}{rc.CHART_CSS}{rc.EXTRA_CSS}{REPORT_CSS}{CSS}</style></head><body><main><h1>Onay backtesti: kural × zaman dilimi × parite</h1><p class=\"lead\">{lead}</p>"
            f"<p>{' · '.join(f'<a href=#{a}>{NAME[a]}</a>' for a in ASSETS)}</p>{blocks}</main></body></html>")
    (rc.HERE / "confirmations.html").write_text(page, encoding="utf-8")
    (OUT / "confirm_points.json").write_text(json.dumps({"version": "v4", "worked_percent": WORKED, "points": {f"{a} {f}": d["points"] for (a, f), d in all_.items()}, "fit": {f"{a} {f}": d["fit"] for (a, f), d in all_.items()},
                                                         "exam": {f"{a} {f}": d["exam"] for (a, f), d in all_.items()}}, ensure_ascii=False), encoding="utf-8")
    for a in ASSETS:
        print("==", a)
        for f in TIMEFRAMES:
            if (a, f) in all_:
                d = all_[(a, f)]
                line = []
                for lo, hi in ((0, 5), (10, 20), (20, 30), (30, 40), (40, 999)):
                    c = []
                    for part in ("fit_rows", "exam_rows", "fake_rows"):
                        s = [r for p, _, r in sc[part].get((a, f), []) if lo <= p < hi]
                        c.append(f"{100 * sum(r[3] for r in s) / len(s):.0f}>{100 * sum(r[4] for r in s) / len(s):.0f}({len(s)})" if len(s) >= 10 else "-")
                    line.append(f"{lo}+: " + " / ".join(c))
                print(f, len(d["fit_rows"]), f"ort %{d['avg']:.1f}", pct(d["rate"]), "puan alan", len(d["points"]), "|", " | ".join(line))


if __name__ == "__main__":
    main()
