r"""Points table v1 (per asset) and its exam on the untouched last 30 % of the data.

  .\venv\Scripts\python.exe -m signals.scoring.points          -> data/reports/points.json, points.html, combo.html

points   what we are 80 % sure of: (respect - control) in percentage points minus 0.84 standard errors, at most 15. Only tests with at least
         30 cases, p < 0.01 against the harder control and at least 1 point.
exam     the same test, the same code, on the last 30 % of the candles that no measurement had used, next to shuffled prices of that part.
         A rule that is not ahead of its control there (p < 0.20, respect at least 50 %) gets 0 points. The exam data is used up by this: the next model needs new data.
family   rules of one family say the same thing; only the best one of a family counts in a total
"""

from __future__ import annotations

import html
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from signals.scoring.combo import CONTEXTS, active, stream
from signals.scoring.null import null_cache
from signals.scoring.reaction import DOWN, KS, UP, Event, p_value, play
from signals.scoring.report import ASSET_NAME, SETS, main_k
from signals.scoring.rule_events import SPAN, TESTS, Context, load_all
from signals.scoring.run import OUT, run_frame, wanted

MAX_POINTS, SURE = 15, 0.84
WARM, NULLS = 400, 4
FAMILY = {k: f for f, names in CONTEXTS.items() for keys in names.values() for k in keys}
PREFIX = (("fr_", "fib"), ("ote", "fib"), ("zone_", "fib"), ("ft_", "uzatma"), ("fvg", "bölge"), ("ob", "bölge"), ("sd", "bölge"), ("body", "bölge"), ("breaker", "bölge"),
          ("sfp", "sfp"), ("deviation", "sfp"), ("range", "sfp"), ("equal", "sfp"), ("rsi", "uyumsuzluk"), ("cvd", "uyumsuzluk"), ("vol_", "uyumsuzluk"),
          ("e_", "elliott"), ("one_E", "elliott"), ("h_", "harmonik"), ("one_H", "harmonik"), ("wedge", "formasyon"), ("triangle", "formasyon"), ("diamond", "formasyon"),
          ("pattern", "formasyon"), ("ext", "seviye"), ("prev", "seviye"), ("npoc", "seviye"), ("va", "seviye"), ("bias", "seviye"), ("open", "seviye"), ("mond", "seviye"),
          ("round", "seviye"), ("bos", "yapı"), ("msb", "yapı"), ("choch", "yapı"), ("break", "yapı"), ("trendline", "yapı"), ("pin", "mum"), ("engulf", "mum"))
NOT_A_RULE = ("fr_none", "ft_none")              # comparison ratios
TITLE = {t.key: t for t in TESTS}


def family(key: str) -> str:
    return FAMILY.get(key) or next((f for p, f in PREFIX if key.startswith(p)), "diğer")


def safe_edge(wins: float, n: int, base: float, base_n: int) -> float:
    """Percentage points by which we are 80 % sure the rule beats its control."""
    p = wins / n
    se = (p * (1 - p) / n + base * (1 - base) / max(base_n, 1)) ** 0.5
    return 100 * (p - base - SURE * se)


def pick() -> list[dict]:
    rows = json.loads((OUT / "rule_results.json").read_text(encoding="utf-8"))
    out = []
    for r in rows:
        if "error" in r or r["n"] < 30 or r["null_n"] < 30 or r["key"] in NOT_A_RULE or r["asset"] not in ASSET_NAME or not wanted(r["asset"], r["frame"], r["key"]):
            continue
        k = main_k(r["frame"])
        edge = safe_edge(r["wins"][k], r["n"], r["base"][k], r["null_n"])
        if r["p"][k] < 0.01 and edge >= 1:
            out.append({"asset": r["asset"], "frame": r["frame"], "key": r["key"], "family": family(r["key"]), "n": r["n"], "rate": r["wins"][k] / r["n"],
                        "base": r["base"][k], "p": r["p"][k], "points": round(min(MAX_POINTS, edge)), "atr_pct": r["atr_pct"], "k": KS[k]})
    return out


def exam_slice(candles):
    return candles[max(0, int(len(candles) * 0.7) - WARM):]


def exam_job(asset: str, seed: int, keys: tuple[str, ...]) -> dict:
    cache = load_all(asset, exam_slice) if seed == 0 else null_cache(asset, seed, exam_slice)
    frames = [f for (a, f) in list(cache) if a == asset]
    return {f: run_frame(asset, f, cache, keys, WARM) for f in frames}


def net_job(asset: str, seed: int, chosen: list[dict], exam: bool) -> list[list]:
    """At every close of 1h: points for up minus points for down (best of each family; an event counts for 6 bars of its frame).
    A case = the first hour the net score reaches a bucket. -> [score, respected per k]"""
    part = exam_slice if exam else None
    cache = (load_all(asset, part) if part else load_all(asset)) if seed == 0 else (null_cache(asset, seed, part) if part else null_cache(asset, seed))
    x = Context(asset, "1h", cache)
    now = np.array([x.known(i).timestamp() for i in range(len(x.candles))])
    best = {d: {} for d in (UP, DOWN)}
    for c in chosen:
        h = x if c["frame"] == "1h" else x.other(c["frame"])
        if h is None:
            continue
        rows = stream(h, (c["key"],))
        for d in (UP, DOWN):
            on = active(np.array([r[0].timestamp() for r in rows if r[1] == d]), now, 6 * SPAN[c["frame"]].total_seconds())
            best[d][c["family"]] = np.maximum(best[d].get(c["family"], np.zeros(len(now))), on * c["points"])
    net = sum(best[UP].values(), np.zeros(len(now))) - sum(best[DOWN].values(), np.zeros(len(now)))
    out, busy = [], -1
    for i in range(WARM if exam else 30, len(x.candles) - 2):
        s = net[i]
        if abs(s) < 1 or i <= busy:
            continue
        r = play(x.bars, Event(i, UP if s > 0 else DOWN))
        if r:
            out.append([float(abs(s)), [bool(w) for w, _ in r[1]]])
            busy = r[1][1][1]
    return out


BUCKETS = ((1, 10), (10, 15), (15, 20), (20, 30), (30, 999))


def bucket_table(cases: list[list]) -> list[list]:
    out = []
    for lo, hi in BUCKETS:
        part = [w for s, w in cases if lo <= s < hi]
        out.append([len(part), [sum(w[k] for w in part) for k in range(len(KS))]])
    return out


def combos() -> tuple[list[dict], dict]:
    data = json.loads((OUT / "combo.json").read_text(encoding="utf-8"))
    rows, sane = [], {"real": 0, "check": 0, "judged": 0}
    for asset, d in data.items():
        for which in ("real", "check"):
            mine = d[which]["pairs"]
            for name, (n, wins) in mine.items():
                low, trig, ctx = name.split("|")
                if ctx == "-" or n < 40:
                    continue
                n0 = sum(x["pairs"].get(name, [0])[0] for x in d["null"])
                w0 = sum(x["pairs"].get(name, [0, [0]])[1][0] for x in d["null"])
                an, aw = mine[f"{low}|{trig}|-"]
                rest_n, rest_w = an - n, aw[0] - wins[0]
                if n0 < 40 or rest_n < 40:
                    continue
                p = max(p_value(wins[0], n, w0, n0), p_value(wins[0], n, rest_w, rest_n))
                sane["judged"] += which == "real"
                sane[which] += p < 0.01
                if which == "real":
                    rows.append({"asset": asset, "low": low, "trigger": trig, "context": ctx, "n": n, "rate": wins[0] / n, "alone": rest_w / rest_n, "null": w0 / n0,
                                 "rate2": wins[1] / n, "p": p})
    rows.sort(key=lambda r: r["p"])
    cut = max((r["p"] for i, r in enumerate(rows, 1) if r["p"] <= 0.10 * i / len(rows)), default=0.0)
    for r in rows:
        r["sure"] = r["p"] <= cut
    return rows, sane


def pct(v: float) -> str:
    return f"%{100 * v:.0f}"


def render(chosen: list[dict], buckets: dict, pairs: list[dict], sane: dict, data: dict) -> tuple[str, str]:
    esc, parts = html.escape, []
    for name, assets in SETS:
        mine = sorted((c for c in chosen if c["asset"] in assets), key=lambda c: (-c["final"], -c["points"]))
        body = "".join(
            f'<tr><td>{esc(TITLE[c["key"]].title)}<br><small>{TITLE[c["key"]].rules}</small></td><td>{c["family"]}</td><td>{c["frame"]}</td><td>{c["n"]}</td>'
            f'<td><b>{pct(c["rate"])}</b> / {pct(c["base"])}</td><td>{c["points"]}</td>'
            f'<td class="{"saygı" if c["final"] else "ters" if c["exam_n"] >= 20 else "az"}">{pct(c["exam_rate"]) if c["exam_n"] else "–"} / {pct(c["exam_base"])}<br><small>{c["exam_n"]} kez</small></td>'
            f'<td><b>{c["final"]}</b></td><td>{c["net_pct"]:+.2f}</td></tr>' for c in mine)
        b = buckets[name]
        rows = "".join(f'<tr><td>{lo}–{hi if hi < 999 else "+"}</td>' + "".join(
            f'<td>{n and pct(w[1] / n) or "–"}<br><small>{n} kez</small></td><td>{nn and pct(nw[1] / nn) or "–"}</td>' for (n, w), (nn, nw) in ((b["fit"][i], b["fit_null"][i]), (b["exam"][i], b["exam_null"][i]))) + "</tr>"
            for i, (lo, hi) in enumerate(BUCKETS))
        parts.append(f'<h3>{name}: {sum(c["final"] > 0 for c in mine)} kural puan aldı ({len(mine)} adaydan)</h3><div class="scroll"><table class="bt left"><tr><th>Kural testi</th><th>Aile</th><th>Dilim</th>'
                     f'<th>Kaç kez</th><th>Saygı / kontrol</th><th>Aday puan</th><th>Sınav: saygı / kontrol</th><th>Puan v1</th><th>İşlem başı % (komisyon sonrası)</th></tr>{body}</table></div>'
                     f'<p class="tt">Toplam puan ne kadar yüksekse o kadar mı iyi? (1h, 2 ATR; aile başına en iyi kural)</p><div class="scroll"><table class="bt"><tr><th>Net puan</th><th>Kalibrasyon</th><th>karıştırılmış</th>'
                     f'<th>Sınav (son %30)</th><th>karıştırılmış</th></tr>{rows}</table></div>')
    points = ('<h2 id="puan">Puan tablosu v1 (parite başına)</h2><p>Aday puan = saygı ile kontrol arasındaki farkın %80 güvenli alt sınırı (en çok 15). Sınav = hiç kullanılmamış '
              "son %30'da aynı test; orada kontrolün önünde kalamayan (p &lt; 0,20), saygısı %50'nin altında olan ya da 20'den az örneği olan kural 0 alır. Son sütun: ilk %70'teki işlem başı beklenti, gidiş-dönüş %0,1 ücret düşülmüş; eksi ise kural tek başına işlem "
              "açtırmaz, yalnız onay olur.</p>" + "".join(parts))
    top = [r for r in pairs if r["sure"]] or pairs[:25]
    body = "".join(f'<tr><td>{ASSET_NAME[r["asset"]]}</td><td>{r["low"]} {esc(r["trigger"])}</td><td>{esc(r["context"])}</td><td>{r["n"]}</td><td class="{"saygı" if r["sure"] else "yok"}"><b>{pct(r["rate"])}</b></td>'
                   f'<td>{pct(r["alone"])}</td><td>{pct(r["null"])}</td><td>{pct(r["rate2"])}</td><td>{r["p"]:.4f}</td></tr>' for r in top[:60])
    count_rows = ""
    for a, d in data.items():
        for s in range(-3, 5):
            def tot(src):
                n = sum(v[0] for k, v in src["counts"].items() if (int(k.split("|")[1]) == s or (s == 4 and int(k.split("|")[1]) > 4) or (s == -3 and int(k.split("|")[1]) < -3)))
                w = sum(v[1][0] for k, v in src["counts"].items() if (int(k.split("|")[1]) == s or (s == 4 and int(k.split("|")[1]) > 4) or (s == -3 and int(k.split("|")[1]) < -3)))
                return n, w
            n, w = tot(d["real"])
            nn, nw = map(sum, zip(*(tot(x) for x in d["null"])))
            if n:
                count_rows += f'<tr><td>{ASSET_NAME[a]}</td><td>{s if -3 < s < 4 else ("≤ −3" if s == -3 else "≥ 4")}</td><td>{n}</td><td><b>{pct(w / n)}</b></td><td>{pct(nw / nn) if nn else "–"}</td></tr>'
    combo = (f'<h2 id="combo">Birlikte testler: LTF tetik + HTF bağlam</h2><p>{sane["judged"]} çift ölçüldü. Şart: hem karıştırılmış fiyattaki aynı çiftten hem de bağlamsız aynı tetikten iyi olmak. '
             f'p &lt; 0,01: gerçek veride {sane["real"]}, sahte veride {sane["check"]}. Yeşil: çoklu deneme düzeltmesini (%10) geçen.</p><div class="scroll"><table class="bt left"><tr><th>Parite</th><th>LTF tetik</th>'
             f'<th>HTF bağlam (aynı yön)</th><th>Kaç kez</th><th>Saygı (1 ATR)</th><th>bağlamsız</th><th>karıştırılmış</th><th>2 ATR</th><th>p</th></tr>{body}</table></div>'
             '<p class="tt">Aynı yönü gösteren farklı aile sayısı arttıkça saygı artıyor mu? (bütün LTF tetikleri, 1 ATR; eksi = aileler karşı yönde)</p><div class="scroll"><table class="bt"><tr><th>Parite</th>'
             f'<th>Net aile sayısı</th><th>Kaç kez</th><th>Saygı</th><th>karıştırılmış</th></tr>{count_rows}</table></div>')
    return points, combo


def main() -> None:
    chosen = pick()
    assets = sorted({c["asset"] for c in chosen})
    keys = {a: tuple(sorted({c["key"] for c in chosen if c["asset"] == a})) for a in assets}
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs = [(a, s) for a in assets for s in range(NULLS + 1)]
        exam = dict(zip(jobs, pool.map(exam_job, *zip(*[(a, s, keys[a]) for a, s in jobs]))))
        for c in chosen:
            k = main_k(c["frame"])
            real = exam[(c["asset"], 0)].get(c["frame"], {}).get(c["key"], {})
            nulls = [exam[(c["asset"], s)].get(c["frame"], {}).get(c["key"], {}) for s in range(1, NULLS + 1)]
            n0, w0 = sum(x.get("n", 0) for x in nulls), sum(x["wins"][k] for x in nulls if x.get("n"))
            c["exam_n"] = real.get("n", 0)
            c["exam_rate"] = real["wins"][k] / real["n"] if real.get("n") else 0.0
            c["exam_base"] = w0 / n0 if n0 else 0.5
            c["exam_p"] = p_value(real["wins"][k], real["n"], w0, n0) if real.get("n") else 1.0
            c["final"] = c["points"] if c["exam_n"] >= 20 and c["exam_p"] < 0.20 and c["exam_rate"] >= 0.5 else 0
            c["net_pct"] = (2 * c["rate"] - 1) * c["k"] * c["atr_pct"] - 0.1
        table = {name: [c for c in chosen if c["asset"] in a] for name, a in SETS}
        main_asset = {"BTC": "BTCUSDT", "Altın": "XAU", "S&P": "SPX"}
        jobs = [(n, s, e) for n in main_asset for s in range(NULLS + 1) for e in (False, True)]
        # the bucket test uses the CANDIDATE points, so the exam column is honest
        nets = dict(zip(jobs, pool.map(net_job, *zip(*[(main_asset[n], s, [c for c in table[n] if c["asset"] == main_asset[n]], e) for n, s, e in jobs]))))
    buckets = {n: {"fit": bucket_table(nets[(n, 0, False)]), "exam": bucket_table(nets[(n, 0, True)]),
                   "fit_null": bucket_table(sum((nets[(n, s, False)] for s in range(1, NULLS + 1)), [])),
                   "exam_null": bucket_table(sum((nets[(n, s, True)] for s in range(1, NULLS + 1)), []))} for n in main_asset}
    pairs, sane = combos()
    points, combo = render(chosen, buckets, pairs, sane, json.loads((OUT / "combo.json").read_text(encoding="utf-8")))
    (OUT / "points.html").write_text(points, encoding="utf-8")
    (OUT / "combo.html").write_text(combo, encoding="utf-8")
    (OUT / "points.json").write_text(json.dumps({"version": "v1", "rules": chosen, "buckets": buckets, "pairs": pairs, "pair_check": sane}, ensure_ascii=False), encoding="utf-8")
    print({n: (len(t), sum(c["final"] > 0 for c in t)) for n, t in table.items()}, sane)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
