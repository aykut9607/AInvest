r"""Category weights, rule qualities and trade limits from the backtests -> table.json, and how each score band did.

  .\venv\Scripts\python.exe -m signals.live.fit

Weights: from the rule backtest at tops and bottoms (confirm_points.json, first 70 %, confirmed on the last 30 %), one table for all three assets.
For every category the best rule of every timeframe, averaged over the timeframes and over the assets that have the data; square root, scaled
to 100; Elliott is never below the highest (Aykut). "Worked" is the same difficulty on every asset (confirm.WORKED).
Limits: from the past triggers (live_<asset>_0.json). A limit is the score only the strongest triggers of the FIRST 70 % reached; what those
triggers earned on the last 30 %, after fees, is stored next to it. Nothing is chosen on the last 30 %.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from signals.data.candles import TIMEFRAMES
from signals.live.plan import FEE_PERCENT
from signals.live.score import TABLE, eligible, score
from signals.scoring.confirm import ASSETS
from signals.scoring.confirm_report import SURE
from signals.scoring.run import OUT

MIN_CASES = 50
SHARES = {"SCALP": 0.10, "SCALP_SWING": 0.04, "SWING": 0.015}          # strongest part of all triggers that may become a trade
TARGET = 1.5                  # R: the smallest reward allowed
SPLIT = 0.7
MIN_EVIDENCE = 100


def edges(points: dict, asset: str) -> tuple[dict[str, float], dict[str, float], set[str]]:
    """(rule -> its proven edge averaged over the 12 timeframes, category -> that of its best rules, rules that were measured at all)."""
    cells: dict[str, dict[str, float]] = {}
    measured: set[str] = set()
    for f in TIMEFRAMES:
        key = f"{asset} {f}"
        earned = points["points"].get(key, {})
        for k, s in points["fit"].get(key, {}).items():
            if "|" not in k or s["n"] < MIN_CASES or "p" not in s:          # rules only: the total of a whole category is not a rule
                continue
            measured.add(k)
            if k in earned:
                cells.setdefault(k, {})[f] = 100 * (s["rate"] - s["rest"]) - SURE * s["se"] - s["geo"]
    rules = {k: sum(v.values()) / len(TIMEFRAMES) for k, v in cells.items()}
    groups = {c: sum(max((v.get(f, 0.0) for k, v in cells.items() if k.split("|")[0] == c), default=0.0) for f in TIMEFRAMES) / len(TIMEFRAMES) for c in {k.split("|")[0] for k in measured}}
    return rules, groups, measured


def common(points: dict) -> tuple[dict, dict]:
    """(category weights adding up to 100, rule qualities 0-1), the SAME for every asset: the proven edge averaged over the assets that have the data
    for it (funding, volume and CVD only on BTC). One table, because a rule should not be worth three times as much only because an asset has
    fewer rules; an asset without some data simply cannot reach 100."""
    per = [edges(points, a) for a in ASSETS]
    mean = lambda values: sum(values) / len(values)
    names = {k for r, _, _ in per for k in r}
    rules = {k: mean([r.get(k, 0.0) for r, _, m in per if k in m]) for k in names}
    raw = {c: mean([g[c] for _, g, _ in per if c in g]) for c in {k.split("|")[0] for k in names}}
    raw = {c: v ** 0.5 for c, v in raw.items() if v > 0}          # the differences are uncertain: shrunk towards equal weights
    raw["Elliott"] = max(raw.values())                            # Aykut: the highest
    total = sum(raw.values())
    top = {c: max(v for k, v in rules.items() if k.split("|")[0] == c) for c in raw}
    return {c: round(100 * v / total, 1) for c, v in sorted(raw.items(), key=lambda x: -x[1])}, {k: round(v / top[k.split("|")[0]], 3) for k, v in rules.items()}


def load(asset: str, seed: int) -> tuple[list, list]:
    d = json.loads((OUT / f"live_{asset}_{seed}.json").read_text(encoding="utf-8"))
    return d["names"], sorted(d["rows"], key=lambda r: r[0])


def scored(asset: str, seed: int, table: dict) -> dict:
    names, rows = load(asset, seed)
    stop, mfe, end = (np.array([r[k] for r in rows]) for k in (4, 5, 7))
    stopped = np.array([bool(r[6]) for r in rows])
    reach = mfe / stop
    result = np.where(reach >= TARGET, TARGET, np.where(stopped, -1.0, end / stop)) - FEE_PERCENT / stop
    t = np.array([r[0] for r in rows])
    scores = [score({f: [names[x] for x in v] for f, v in r[8].items()}, table) for r in rows]
    return {"score": np.array([s.total if eligible(s) else 0.0 for s in scores]), "result": result, "won": reach >= TARGET,
            "two": mfe >= 2.0, "move": mfe, "fit": t <= t[0] + (t[-1] - t[0]) * SPLIT, "side": np.array([r[1] for r in rows])}


def band(d: dict, m: np.ndarray) -> dict:
    n = int(m.sum())
    if not n:
        return {"n": 0}
    r = d["result"][m]
    return {"n": n, "won": round(float(d["won"][m].mean()), 3), "two_percent": round(float(d["two"][m].mean()), 3), "average_move": round(float(d["move"][m].mean()), 2),
            "average_r": round(float(r.mean()), 3), "error_r": round(float(r.std() / n ** 0.5), 3)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    points = json.loads((OUT / "confirm_points.json").read_text(encoding="utf-8"))
    out = {}
    weights, quality = common(points)
    for a in ASSETS:
        table = {"weights": weights, "quality": quality}
        real, fake = scored(a, 0, table), scored(a, 1, table)
        fit = real["fit"]
        limits = {k: round(float(np.quantile(real["score"][fit], 1 - s)), 1) for k, s in SHARES.items()}
        evidence = {}
        for k, limit in limits.items():
            up = min((v for v in limits.values() if v > limit), default=10**9)
            inside = lambda d: (d["score"] >= limit) & (d["score"] < up)
            evidence[k] = {"first70": band(real, inside(real) & fit), "last30": band(real, inside(real) & ~fit), "shuffled": band(fake, inside(fake))}
            e = evidence[k]["last30"]
            evidence[k]["proven"] = e["n"] >= MIN_EVIDENCE and e["average_r"] - 2 * e["error_r"] > 0
        table |= {"limits": limits, "evidence": evidence, "base": {"first70": band(real, fit), "last30": band(real, ~fit)}}
        out[a] = table
        print("==", a, weights)
        print("  puan dağılımı (ilk %70): ortanca", round(float(np.median(real["score"][fit])), 1), "en yüksek", round(float(real["score"].max()), 1), "sınırlar", limits)
        print("  taban", table["base"])
        for k, e in evidence.items():
            print("  ", k, limits[k], e)
        edges = [0, 10, 15, 20, 25, 30, 35, 40, 50, 101]
        for lo, hi in zip(edges, edges[1:]):
            row = [band(d, (d["score"] >= lo) & (d["score"] < hi) & m) for d, m in ((real, fit), (real, ~fit), (fake, np.ones(len(fake["score"]), bool)))]
            print(f"   {lo}-{hi}: " + " | ".join(f"n{b['n']} {100 * b['won']:.0f}% {b['average_r']:+.2f}R %2:{100 * b['two_percent']:.0f}" if b["n"] >= 20 else f"n{b['n']}" for b in row))
    TABLE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
