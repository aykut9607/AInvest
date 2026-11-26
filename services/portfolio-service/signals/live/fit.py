r"""Points per rule and timeframe, trade limits from the backtests -> table.json, and how each score band did.

  .\venv\Scripts\python.exe -m signals.live.fit

Points: from the rule backtest at tops and bottoms (confirm_points.json, first 70 %): every rule its own success, one table per asset (Aykut,
26 Nov; how they are made: signals/live/score.py). Weights (only shown on the screen): what each category can add at most, HTF + LTF.
Limits: from the past triggers (live_<asset>_0.json). A limit is the score only the strongest triggers of the FIRST 70 % reached; what those
triggers earned on the last 30 %, after fees, is stored next to it. Nothing is chosen on the last 30 %.
"""

from __future__ import annotations

import json
import sys

import numpy as np

from signals.data.candles import TIMEFRAMES
from signals.live.plan import FEE_PERCENT
from signals.live.score import SHARE, TABLE, eligible, score, side_of
from signals.scoring.confirm import ASSETS
from signals.scoring.run import OUT

MIN_CASES = 50
SHARES = {"SCALP": 0.10, "SCALP_SWING": 0.04, "SWING": 0.015}          # strongest part of all triggers that may become a trade
TARGET = 1.5                  # R: the smallest reward allowed
SPLIT = 0.7
MIN_EVIDENCE = 100
NO_TRADE = 101.0              # a limit no score reaches


def table_of(points: dict, asset: str) -> dict:
    """{points: frame -> rule -> points, weights: category -> the most it can add (best HTF + best LTF rule)}."""
    pts = {f: points["points"].get(f"{asset} {f}", {}) for f in TIMEFRAMES}
    weights: dict[str, float] = {}
    for side in SHARE:
        best: dict[str, float] = {}
        for f, d in pts.items():
            if side_of(f) == side:
                for k, v in d.items():
                    best[k.split("|")[0]] = max(best.get(k.split("|")[0], 0.0), v)
        for c, v in best.items():
            weights[c] = weights.get(c, 0.0) + v
    return {"points": pts, "weights": {c: round(v, 1) for c, v in sorted(weights.items(), key=lambda x: -x[1])}}


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
    for a in ASSETS:
        table = table_of(points, a)
        real, fake = scored(a, 0, table), scored(a, 1, table)
        fit = real["fit"]
        limits = {k: round(float(np.quantile(real["score"][fit], 1 - s)), 1) for k, s in SHARES.items()}
        if int((real["score"][fit] > 0).sum()) < MIN_CASES:          # too few scored triggers: a limit of 0 would let any two categories trade
            limits = {k: NO_TRADE for k in SHARES}
        evidence = {}
        for k, limit in limits.items():
            up = min((v for v in limits.values() if v > limit), default=10**9)
            inside = lambda d: (d["score"] >= limit) & (d["score"] < up)
            evidence[k] = {"first70": band(real, inside(real) & fit), "last30": band(real, inside(real) & ~fit), "shuffled": band(fake, inside(fake))}
            e = evidence[k]["last30"]
            evidence[k]["proven"] = e["n"] >= MIN_EVIDENCE and e["average_r"] - 2 * e["error_r"] > 0
        table |= {"limits": limits, "evidence": evidence, "base": {"first70": band(real, fit), "last30": band(real, ~fit)}}
        out[a] = table
        print("==", a, table["weights"])
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
