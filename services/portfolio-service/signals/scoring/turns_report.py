r"""What each confirmation at a top / bottom was worth (turns.py), one by one, and how many together.

  .\venv\Scripts\python.exe -m signals.scoring.turns_report     -> signals/rules/confirmations.html, data/reports/turn_points.json
"""

from __future__ import annotations

import html
import json
import sys
from statistics import median

from signals.data.candles import TIMEFRAMES
from signals.rules import rules_catalog as rc
from signals.scoring.reaction import p_value
from signals.scoring.run import OUT
from signals.scoring.turns import ASSETS, BASES, SPLIT

NAME = {"BTCUSDT": "BTC", "XAU": "Altın", "SPX": "S&P"}
MIN_N, FDR, MAX_POINTS, SURE = 30, 0.05, 15, 0.84
BASE_TITLE = {"15m": "15m tepe/dip (scalp)", "1h": "1h tepe/dip (scalp / gün içi)", "4h": "4h tepe/dip (swing)", "1d": "1D tepe/dip (swing)"}
# which confirmations are one idea (counted once in a total)
IDEA = {"RSI uyumsuzluk": "Uyumsuzluk", "CVD uyumsuzluk": "Uyumsuzluk (CVD)", "Hacim uyumsuzluk": "Uyumsuzluk (hacim)", "RSI Trend Devam": "Trend Devam", "CVD Trend Devam": "Trend Devam",
        "SFP + uyumsuzluk": "SFP", "Önceki dönem": "Önceki dönem seviyesi"}


def idea(group: str) -> str:
    return "Fib reshort/relong" if group.startswith("Fib") else "Trend fib hedefi" if group.startswith("Trend fib") else IDEA.get(group, group)


def load(asset: str, seed: int) -> dict:
    return json.loads((OUT / f"turns_{asset}_{seed}.json").read_text(encoding="utf-8"))


def split(rows: list) -> tuple[list, list]:
    if not rows:
        return [], []
    cut = rows[0][0] + (rows[-1][0] - rows[0][0]) * SPLIT
    return [r for r in rows if r[0] <= cut], [r for r in rows if r[0] > cut]


def names(row) -> set[str]:
    """A candidate's confirmations at three levels: idea, group, member."""
    out = set()
    for c in row[6]:
        g, m = c.split("|")
        out |= {f"* {idea(g)}", f"{g}|*", c}
    return out


def stat(rows: list, key: str, tagged: list[set]) -> dict:
    a = [r for r, s in zip(rows, tagged) if key in s]
    b = [r for r, s in zip(rows, tagged) if key not in s]
    if not a or not b:
        return {"n": len(a)}
    wa, wb, la, lb = sum(r[3] for r in a), sum(r[3] for r in b), sum(r[4] for r in a), sum(r[4] for r in b)
    p1, p0 = wa / len(a), wb / len(b)
    se = (p1 * (1 - p1) / len(a) + p0 * (1 - p0) / len(b)) ** 0.5
    return {"n": len(a), "rate": p1, "rest": p0, "move": median(r[2] for r in a), "move_rest": median(r[2] for r in b), "after": la / len(a), "after_rest": lb / len(b),
            "p": p_value(wa, len(a), wb, len(b)), "p_after": p_value(la, len(a), lb, len(b)), "p_low": p_value(len(a) - wa, len(a), len(b) - wb, len(b)),
            "sure": 100 * (p1 - p0 - SURE * se)}


def analyse(asset: str, base: str) -> dict:
    fit, exam = split(load(asset, 0)[base])
    fake = load(asset, 1)[base]
    tags = {"fit": [names(r) for r in fit], "exam": [names(r) for r in exam], "fake": [names(r) for r in fake]}
    keys = sorted(set().union(*tags["fit"]) if tags["fit"] else set())
    rows = {k: {"key": k, "fit": stat(fit, k, tags["fit"]), "exam": stat(exam, k, tags["exam"]), "fake": stat(fake, k, tags["fake"])} for k in keys}
    return {"rows": rows, "n": (len(fit), len(exam)), "rate": sum(r[3] for r in fit) / max(1, len(fit)), "after": sum(r[4] for r in fit) / max(1, len(fit)),
            "threshold": median(r[5] for r in fit) if fit else 0, "fit": fit, "exam": exam, "fake": fake}


def verdicts(all_: dict) -> None:
    """Benjamini-Hochberg over every confirmation of every asset and base (fit part); the points of the ones that passed."""
    pool = sorted((v["fit"] for d in all_.values() for v in d["rows"].values() if v["fit"].get("n", 0) >= MIN_N and "p" in v["fit"]), key=lambda s: s["p"])
    cut = max((s["p"] for i, s in enumerate(pool, 1) if s["p"] <= FDR * i / len(pool)), default=0.0)
    for d in all_.values():
        for v in d["rows"].values():
            f, e = v["fit"], v["exam"]
            f["good"] = f.get("n", 0) >= MIN_N and f.get("p", 1) <= cut
            f["bad"] = f.get("n", 0) >= MIN_N and f.get("p_low", 1) <= cut
            # what the same confirmation "gains" on shuffled prices is geometry, not respect: it is taken off (funding is not in the prices)
            fake = v["fake"]
            v["geometry"] = max(0.0, 100 * (fake["rate"] - fake["rest"])) if fake.get("n", 0) >= MIN_N and "rate" in fake and "Funding" not in v["key"] else 0.0
            v["edge"] = f.get("sure", 0) - v["geometry"]
            v["candidate"] = round(min(MAX_POINTS, v["edge"])) if f["good"] and v["edge"] >= 1 else 0
            v["points"] = v["candidate"] if e.get("n", 0) >= 15 and "rate" in e and 100 * (e["rate"] - e["rest"]) > v["geometry"] else 0


def total(row, rows: dict) -> int:
    """Points of one candidate: the best confirmation of each idea."""
    best: dict[str, int] = {}
    for c in row[6]:
        g = c.split("|")[0]
        p = max(rows.get(k, {}).get("candidate", 0) for k in (c, f"{g}|*", f"* {idea(g)}"))
        best[idea(g)] = max(best.get(idea(g), 0), p)
    return sum(best.values())


def ideas(row) -> int:
    return len({idea(c.split("|")[0]) for c in row[6]})


def pct(v) -> str:
    return f"%{100 * v:.0f}"


def cell(s: dict, kind: str = "") -> str:
    if "rate" not in s:
        return f'<td class="az">{s.get("n", 0)}</td>'
    css = "saygı" if s.get("good") else "ters" if s.get("bad") else "az" if s["n"] < MIN_N else "yok"
    return f'<td class="{css if kind == "fit" else ""}"><b>{pct(s["rate"])}</b> <i>{100 * (s["rate"] - s["rest"]):+.0f}</i><br><small>{s["n"]} kez</small></td>'


def buckets(d: dict) -> str:
    out = []
    for title, fn, edges in (("Kaç farklı onay vardı?", ideas, ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 99))),
                             ("Toplam puan", lambda r: total(r, d["rows"]), ((0, 1), (1, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 99)))):
        rows = []
        for lo, hi in edges:
            tds = ""
            for part in ("fit", "exam", "fake"):
                s = [r for r in d[part] if lo <= fn(r) < hi]
                tds += f'<td>{pct(sum(r[3] for r in s) / len(s)) if s else "–"} <small>({len(s)})</small></td><td>{pct(sum(r[4] for r in s) / len(s)) if s else "–"}</td><td>%{median(r[2] for r in s):.1f}</td>' if s else "<td>–</td><td>–</td><td>–</td>"
            rows.append(f'<tr><td>{lo if hi == lo + 1 else f"{lo}–{hi - 1}" if hi < 99 else f"{lo}+"}</td>{tds}</tr>')
        out.append(f'<p class="tt">{title}</p><div class="scroll"><table class="bt"><tr><th></th><th colspan="3">İlk %70</th><th colspan="3">Son %30 (sınav)</th><th colspan="3">Karıştırılmış fiyat</th></tr>'
                   f'<tr><th></th>{"<th>çalıştı</th><th>onaydan sonra</th><th>ort. hareket</th>" * 3}</tr>{"".join(rows)}</table></div>')
    return "".join(out)


def block(asset: str, base: str, d: dict) -> str:
    order = sorted(d["rows"].items(), key=lambda kv: (-kv[1]["points"], -kv[1]["candidate"], -kv[1]["fit"].get("rate", 0) + kv[1]["fit"].get("rest", 0)))
    body = {"idea": "", "member": ""}
    for k, v in order:
        f = v["fit"]
        if f.get("n", 0) < 10:
            continue
        title = k[2:] if k.startswith("* ") else k.replace("|*", " (hepsi)").replace("|", " · ")
        body["idea" if k.startswith("* ") else "member"] += (
            f'<tr><td>{html.escape(title)}</td>{cell(f, "fit")}<td>%{f.get("move", 0):.1f} / %{f.get("move_rest", 0):.1f}</td><td>{pct(f["after"]) if "after" in f else "–"} / {pct(f["after_rest"]) if "after" in f else "–"}</td>'
            f'{cell(v["exam"])}{cell(v["fake"])}<td>{v["candidate"] or ""}</td><td><b>{v["points"] or ""}</b></td></tr>')
    head = ('<tr><th>Onay</th><th>Çalıştı (onaysızdan fark)</th><th>Hareket: onaylı / onaysız</th><th>Onaydan sonra: onaylı / onaysız</th><th>Sınav (son %30)</th><th>Karıştırılmış fiyat</th><th>Aday puan</th><th>Puan</th></tr>')
    return (f'<h3 id="{asset}-{base}">{NAME[asset]} · {BASE_TITLE[base]}</h3><p>{d["n"][0]} tepe/dip (sınavda {d["n"][1]}). Çalıştı = tepe/dip geçilmeden en az <b>%{d["threshold"]:.1f}</b> hareket. '
            f'Bütün adaylarda çalışma oranı {pct(d["rate"])}.</p><div class="scroll"><table class="bt left">{head}{body["idea"]}</table></div>{buckets(d)}'
            f'<details><summary>Alt kurallar tek tek (Elliott türleri, her dilimin uyumsuzluğu, her seviye…)</summary><div class="scroll"><table class="bt left">{head}{body["member"]}</table></div></details>')


def overview(all_: dict) -> str:
    """Every idea: rate difference per asset and base, side by side."""
    keys = sorted({k for d in all_.values() for k in d["rows"] if k.startswith("* ")})
    rows = ""
    for k in keys:
        rows += f"<tr><td>{html.escape(k[2:])}</td>" + "".join(cell(all_[(a, b)]["rows"].get(k, {"fit": {"n": 0}})["fit"], "fit") for a in ASSETS for b in BASES) + "</tr>"
    head = "".join(f'<th colspan="{len(BASES)}">{NAME[a]}</th>' for a in ASSETS)
    return (f'<h2>Hepsi bir arada</h2><div class="scroll"><table class="bt left"><tr><th rowspan="2">Onay</th>{head}</tr><tr>{"".join(f"<th>{b}</th>" for _ in ASSETS for b in BASES)}</tr>{rows}</table></div>')


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    all_ = {(a, b): analyse(a, b) for a in ASSETS for b in BASES}
    verdicts(all_)
    from signals.scoring.report import CSS as REPORT_CSS
    lead = ("Yöntem: 15m, 1h, 4h ve 1D'de oluşan her tepe ve dip bir adaydır. Her birinde hangi onaylar vardı (o an bilinen), sonra 15 dakikalık mumlarda tepe/dip <b>geçilmeden</b> ne kadar hareket geldi? "
            "Eşik: 15m'de 0,25, 1h'te 0,5, 4h'te 1, 1D'de 2 günlük ATR (BTC'de yaklaşık %1, %2, %4, %8); süre 1, 3, 10, 40 gün. Yanındaki fark, o onayın <b>olmadığı</b> tepe/diplere göredir. "
            "Onaydan sonra = tepe kesinleştiği mumun kapanışından itibaren aynı hareket. Yeşil: anlamlı iyi, kırmızı: anlamlı kötü. Puan = farkın %80 emin olunan kısmı <b>eksi karıştırılmış fiyatta kendiliğinden çıkan fark</b> (en çok 15); son %30'da da bunun üstünde kalan onay alır.")
    nav = " · ".join(f'<a href="#{a}-{b}">{NAME[a]} {b}</a>' for a in ASSETS for b in BASES)
    page = ('<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Onaylar</title>'
            f"<style>{rc.CSS}{rc.CHART_CSS}{rc.EXTRA_CSS}{REPORT_CSS}</style></head><body><main><h1>Tepe ve diplerde onaylar</h1><p class=\"lead\">{lead}</p><p>{nav}</p>"
            f"{overview(all_)}{''.join(block(a, b, all_[(a, b)]) for a in ASSETS for b in BASES)}</main></body></html>")
    (rc.HERE / "confirmations.html").write_text(page, encoding="utf-8")
    out = {f"{a} {b}": {k: {"points": v["points"], "candidate": v["candidate"], "geometry": v["geometry"], "fit": v["fit"], "exam": v["exam"], "fake": v["fake"]} for k, v in all_[(a, b)]["rows"].items()} for a in ASSETS for b in BASES}
    (OUT / "turn_points.json").write_text(json.dumps({"version": "v2", "rules": out}, ensure_ascii=False), encoding="utf-8")
    for (a, b), d in all_.items():
        good = sum(v["fit"].get("good", False) for v in d["rows"].values())
        fake = sum(v["fake"].get("n", 0) >= MIN_N and v["fake"].get("p", 1) < 0.01 for v in d["rows"].values())
        print(a, b, d["n"], "oran", pct(d["rate"]), f"eşik %{d['threshold']:.1f}", "onay", len(d["rows"]), "anlamlı iyi", good, "puan alan", sum(v["points"] > 0 for v in d["rows"].values()), "sahte p<.01", fake)


if __name__ == "__main__":
    main()
