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
from signals.live.score import SHARE, combine, side_of
from signals.scoring.confirm import ASSETS, WORKED
from signals.scoring.rule_events import SPAN
from signals.scoring.run import OUT

NAME = {"BTCUSDT": "BTC", "XAU": "Altın", "SPX": "S&P"}
SURE, SPLIT = 0.84, 0.7
# Aykut, 26 Nov: the score is the rule's own success. quality = max(Wilson lower bound at 80 %, 0.8 x rate); at least 5 cases and 51 %, else 0
MIN_CASES, Z, FLOOR, MIN_QUALITY = 5, 1.2816, 0.8, 0.51


def wilson(k: int, n: int) -> float:
    p = k / n
    return (p + Z * Z / (2 * n) - Z * (p * (1 - p) / n + Z * Z / (4 * n * n)) ** 0.5) / (1 + Z * Z / n)


def quality(k: int, n: int) -> float:
    if n < MIN_CASES:
        return 0.0
    q = max(wilson(k, n), FLOOR * k / n)
    return q if q >= MIN_QUALITY else 0.0
ORDER = ("Elliott", "Harmonik", "Uyumsuzluk", "SFP", "Price action", "Fibonacci", "Key level", "Hacim profili", "Smart money", "Önceki dönem", "EXT bandı", "Funding")


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
    """Every key: how often it was seen, how often it worked, its quality, the move of those that worked."""
    have: dict[str, list] = {}
    for r in rows:
        for k in keys(r):
            have.setdefault(k, []).append(r)
    out = {}
    for k, a in have.items():
        m, wa = len(a), sum(r[3] for r in a)
        good = [r[2] for r in a if r[3]]
        out[k] = {"n": m, "k": wa, "rate": wa / m, "q": quality(wa, m), "after": sum(r[4] for r in a) / m,
                  "avg": mean(good) if good else 0.0, "mid": median(good) if good else 0.0}
    return out


def own(rows: list) -> set[str]:
    """The keys a tag maps to exactly (the rule with its variant): only these earn points, a category total or a parent rule never does."""
    return {tag if tag.split("|")[2] else "|".join(tag.split("|")[:2]) for r in rows for tag in r[6]}


def analyse() -> dict:
    all_: dict = {}
    for a in ASSETS:
        real, fake = load(a, 0), load(a, 1)
        for f in TIMEFRAMES:
            fit, exam = split(real.get(f, []))
            if len(fit) < 5:
                continue
            all_[(a, f)] = {"fit_rows": fit, "exam_rows": exam, "fake_rows": fake.get(f, []), "fit": stats(fit), "exam": stats(exam), "fake": stats(fake.get(f, [])),
                            "rate": sum(r[3] for r in fit) / len(fit), "avg": mean([r[2] for r in fit if r[3]] or [0.0]), "points": {}}
    for a in ASSETS:                     # HTF shares 70 of the 100, LTF 30, in proportion to the qualities (Aykut)
        frames = {f: d for (b, f), d in all_.items() if b == a}
        mine = {f: own(d["fit_rows"]) for f, d in frames.items()}
        for side, share in SHARE.items():
            top: dict[str, float] = {}
            for f, d in frames.items():
                if side_of(f) != side:
                    continue
                for k in mine[f]:
                    q = d["fit"].get(k, {}).get("q", 0.0)
                    c = k.split("|")[0]
                    top[c] = max(top.get(c, 0.0), q)
            scale = share / (sum(top.values()) or 1.0)
            for f, d in frames.items():
                if side_of(f) == side:
                    d["points"] = {k: round(d["fit"][k]["q"] * scale, 2) for k in mine[f] if d["fit"].get(k, {}).get("q", 0.0) > 0}
    return all_


def found_at(tags: list[str], pts: dict[str, float]) -> dict[str, tuple[float, str]]:
    """category -> (points, rule): the best own rule of every category at one top on one timeframe."""
    out: dict[str, tuple[float, str]] = {}
    for tag in tags:
        k = tag if tag.split("|")[2] else "|".join(tag.split("|")[:2])
        p, c = pts.get(k, 0.0), tag.split("|")[0]
        if p > out.get(c, (0.0, ""))[0]:
            out[c] = (p, k)
    return out


def scores(all_: dict, part: str) -> dict:
    """(asset, frame) -> [(score, categories, row)]: the live score of the top, with the rules of the lower frames whose pivot is this very top."""
    out = {}
    for a in ASSETS:
        frames = [f for f in TIMEFRAMES if (a, f) in all_]
        table = {f: [(r, found_at(r[6], all_[(a, f)]["points"])) for r in (sorted(all_[(a, f)]["fit_rows"] + all_[(a, f)]["exam_rows"]) if part != "fake_rows" else all_[(a, f)]["fake_rows"])] for f in frames}
        times = {f: [r[0] for r, _ in v] for f, v in table.items()}
        for i, f in enumerate(frames):
            rows = all_[(a, f)][part]
            wanted = {(r[0], r[1]) for r in rows}
            span, res = SPAN[f].total_seconds(), []
            for r, mine in table[f]:
                if (r[0], r[1]) not in wanted:
                    continue
                found = {c: {f: v} for c, v in mine.items()}
                for g in frames[:i]:
                    k = bisect_left(times[g], r[0])
                    while k < len(times[g]) and times[g][k] < r[0] + span:
                        q, theirs = table[g][k]
                        if q[1] == r[1] and abs(q[7] - r[7]) <= 1e-4 * r[7]:
                            for c, v in theirs.items():
                                found.setdefault(c, {})[g] = v
                        k += 1
                s = combine(found)
                res.append((s.total, len(s.categories), r))
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
    if not s:
        return '<td class="az"></td>'
    point = point_of(d, k)
    css = "saygı" if point else "az" if s["n"] < MIN_CASES else "yok"
    e = d["exam"].get(k, {})
    tip = (f"{s['k']}/{s['n']} çalıştı ({pct(s['rate'])}); kalite {pct(s['q'])} (Wilson %80 ile oranın 0,8 katının büyüğü; en az 5 kez ve %51); "
           f"çalışanlarda ortalama hareket %{s['avg']:.1f}, ortanca %{s['mid']:.1f}; son %30: " + (f"{e['k']}/{e['n']} ({pct(e['rate'])})" if e.get("n") else "yok"))
    return (f'<td class="{css}" title="{tip}"><b>{pct(s["rate"])}</b> <i>{s["k"]}/{s["n"]}</i><br><small>kalite {pct(s["q"])} · ort. %{s["avg"]:.1f}'
            f'{f"<br><b>{fmt(point)} puan</b>" if point else ""}</small></td>')


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
    need = "".join(f"<td>%{fmt(WORKED[a][f])}</td>" for f in TIMEFRAMES)
    return f'<div class="scroll"><table class="bt left tree"><tr><th>Kural</th>{head}</tr><tr><td><i>çalıştı sayılan hareket</i></td>{need}</tr>{body}</table></div>'


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
    lead = ("Her satır bir kural, her sütun bir zaman dilimi. Aday = o dilimde oluşan tepe ya da dip (önünde 5, arkasında 2 mum). <b>Çalıştı</b> = fiyat tepeyi hiç geçmeden, "
            "tepeden en az şu kadar döndü (o dilimin 40 mumu içinde; 1w 26, 1M 12): <b>LTF (15m–2h)</b> BTC %2, altın ve S&P %1,5; <b>HTF</b> 4h'de BTC %4, altın ve S&P %3, "
            "üst dilimlerde bir tepenin 4h'deki kadar sık ulaştığı hareket (tablonun ilk satırı). "
            "Hücrede: çalışma oranı ve kaç kezde kaç kez; altında <b>kalite</b> = Wilson %80 güven alt sınırı ile oranın 0,8 katının büyüğü (en az 5 kez ve %51, yoksa 0), çalışanların ortalama hareketi ve puanı. "
            "Puan yalnız kuralın kendi oranından: 100'ün 70'i HTF'ye, 30'u LTF'ye, kalitelerle orantılı; her kategorinin iki taraftaki en iyi kuralı aynı anda olsa 100 eder. "
            "Yeşil: puan aldı. Soluk: 5'ten az örnek. Ölçüm verinin ilk %70'inde; hücrenin üstüne gelince son %30 da görünür.")
    blocks = "".join(f'<h2 id="{a}">{NAME[a]}</h2>{tree(a, all_)}<h3>{NAME[a]}: toplam puan ne kadar yüksekse o kadar mı iyi?</h3>'
                     f"<p>Toplam puan = o tepedeki bütün onayların puanları (aynı tepedeki alt dilim onayları dahil; Elliott ve harmonik birer onay sayılır).</p>{score_tables(a, sc)}" for a in ASSETS)
    page = ('<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Onay backtesti</title>'
            f"<style>{rc.CSS}{rc.CHART_CSS}{rc.EXTRA_CSS}{REPORT_CSS}{CSS}</style></head><body><main><h1>Onay backtesti: kural × zaman dilimi × parite</h1><p class=\"lead\">{lead}</p>"
            f"<p>{' · '.join(f'<a href=#{a}>{NAME[a]}</a>' for a in ASSETS)}</p>{blocks}</main></body></html>")
    (rc.HERE / "confirmations.html").write_text(page, encoding="utf-8")
    (OUT / "confirm_points.json").write_text(json.dumps({"version": "v5", "worked_percent": WORKED, "share": SHARE, "points": {f"{a} {f}": d["points"] for (a, f), d in all_.items()}, "fit": {f"{a} {f}": d["fit"] for (a, f), d in all_.items()},
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
