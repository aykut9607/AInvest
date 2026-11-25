r"""Category weights, rule qualities and trade limits from the backtests -> table.json, and how each score band did.

  .\venv\Scripts\python.exe -m signals.live.fit

Weights: from the rule backtest at tops and bottoms (confirm_points.json, first 70 %, confirmed on the last 30 %): for every category the best
rule of every timeframe, averaged over the timeframes - a category that works on many timeframes weighs more than one lucky cell. Square
root and scaled to 100 per asset; Elliott is never below the highest (Aykut). A category that proved nothing on an asset weighs 0 there.
Limits: from the past triggers (live_<asset>_0.json). A limit is the score only the strongest triggers of the FIRST 70 % reached; what those
triggers earned on the last 30 %, after fees, is stored next to it. Nothing is chosen on the last 30 %.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from signals.data.candles import TIMEFRAMES
from signals.live.plan import FEE_PERCENT
from signals.live.score import TABLE, score
from signals.scoring.confirm import ASSETS
from signals.scoring.run import OUT

MIN_CASES = 50
SHARES = {"SCALP": 0.10, "SCALP_SWING": 0.04, "SWING": 0.015}          # strongest part of all triggers that may become a trade
TARGET = 1.5                  # R: the smallest reward allowed
SPLIT = 0.7
MIN_EVIDENCE = 100


def weights_of(asset: str, points: dict) -> tuple[dict, dict]:
    """(category weights adding up to 100, rule qualities 0-1) of one asset."""
    cells: dict[str, dict[str, float]] = {}
    for f in TIMEFRAMES:
        key = f"{asset} {f}"
        for k, p in points["points"].get(key, {}).items():
            if "|" in k and points["fit"][key][k]["n"] >= MIN_CASES:          # rules only: the total of a whole category is not a rule
                cells.setdefault(k, {})[f] = p
    raw: dict[str, float] = {}
    for c in {k.split("|")[0] for k in cells}:
        raw[c] = sum(max((v.get(f, 0.0) for k, v in cells.items() if k.split("|")[0] == c), default=0.0) for f in TIMEFRAMES) / len(TIMEFRAMES)
    if not raw:
        return {}, {}
    raw = {c: v ** 0.5 for c, v in raw.items()}          # the differences are uncertain: shrunk towards equal weights
    raw["Elliott"] = max(raw.values())
    total = sum(raw.values())
    mean = {k: sum(v.values()) / len(TIMEFRAMES) for k, v in cells.items()}
    top = {c: max((m for k, m in mean.items() if k.split("|")[0] == c), default=1.0) or 1.0 for c in raw}
    quality = {k: round(m / top[k.split("|")[0]], 3) for k, m in mean.items()}
    return {c: round(100 * v / total, 1) for c, v in sorted(raw.items(), key=lambda x: -x[1])}, quality


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
    return {"score": np.array([score({f: [names[x] for x in v] for f, v in r[8].items()}, table).total for r in rows]), "result": result, "won": reach >= TARGET,
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
    for a in ASSETS:
        weights, quality = weights_of(a, points)
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
