r"""Which stop and which targets: every past trigger the score lets trade, played again on the 15m candles with other stops and exits.

  .\venv\Scripts\python.exe -m signals.live.plan_study [asset ...]     -> data/reports/plan_study.json

Stop = the study's stop (extreme + 0.25 ATR(1h), live_<asset>_<seed>.json) times a factor: 0.5 (closer) ... 3 (farther). Exits:
  - "tek hedef R": everything at R x stop distance;
  - "yarı 1R + R2": half at 1R, the stop to entry, the rest at R2.
Inside a candle the stop counts first; a trade still open after HORIZON 15m candles is closed at that close. Fees are paid (plan.FEE_PERCENT of
the position = FEE / stop distance in R). Results in R (1R = the loss at the stop = 1 % of the account in the live plan). A setting is chosen on
the FIRST 70 % only; the last 30 % and the shuffled prices show whether it holds.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from signals.live import fit
from signals.live.plan import FEE_PERCENT
from signals.live.replay import cache_of
from signals.live.scan import Scanner
from signals.live.score import kind_of, score, tables
from signals.scoring.confirm import ASSETS
from signals.scoring.run import OUT

HORIZON = 2880                         # 15m candles: 30 days
STOPS = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
SINGLE = (0.5, 1.0, 1.5, 2.0, 3.0)
HALF_THEN = (2.0, 3.0)


def first(hit: np.ndarray) -> int:
    return int(hit.argmax()) if hit.any() else len(hit)


def play(h: np.ndarray, lo: np.ndarray, end: float, side: int, entry: float, d: float) -> dict[str, float]:
    """R of every exit for one trade with a stop d % away."""
    move = lambda price: 100 * side * (price - entry) / entry / d          # in R
    fav_r = 100 * side * ((h if side == 1 else lo) - entry) / entry / d          # best price of each candle, in R
    adv_r = 100 * side * ((lo if side == 1 else h) - entry) / entry / d          # worst price of each candle, in R
    stop_at = first(adv_r <= -1)
    out: dict[str, float] = {}
    fee = FEE_PERCENT / d
    for r in SINGLE:
        t = first(fav_r >= r)
        out[f"tek {r:g}R"] = (r if t < stop_at else -1.0 if stop_at < len(h) else move(end)) - fee
    k = first(fav_r >= 1.0)
    for r2 in HALF_THEN:
        if k >= stop_at:          # the stop came first (or on the same candle)
            out[f"yarı 1R + {r2:g}R"] = (-1.0 if stop_at < len(h) else move(end)) - fee
            continue
        rest_adv, rest_fav = adv_r[k + 1:], fav_r[k + 1:]
        back, t2 = first(rest_adv <= 0), first(rest_fav >= r2)
        rest = r2 if t2 < back else 0.0 if back < len(rest_adv) else move(end)
        out[f"yarı 1R + {r2:g}R"] = 0.5 + 0.5 * rest - fee
    return out


def job(asset: str, seed: int) -> tuple[str, int, list]:
    sc = Scanner(asset, cache_of(asset, seed))
    b = sc.base.x.bars
    table = tables()[asset]
    names, rows = fit.load(asset, seed)
    split = rows[0][0] + (rows[-1][0] - rows[0][0]) * fit.SPLIT
    out = []
    for r in rows:
        when, side, _, entry, d0 = r[:5]
        tags = {f: [names[x] for x in v] for f, v in r[8].items()}
        if kind_of(score(tags, table), table) is None:
            continue
        i = sc.base.closed_at(when)
        if i is None or i + 1 >= len(b.close):
            continue
        h, lo = b.high[i + 1:i + 1 + HORIZON], b.low[i + 1:i + 1 + HORIZON]
        end = float(b.close[min(i + HORIZON, len(b.close) - 1)])
        res = {f"stop x{m:g}": play(h, lo, end, side, entry, d0 * m) for m in STOPS}
        out.append({"part": "first70" if when <= split else "last30", "stop": d0, "r": res})
    return asset, seed, out


def summary(trades: list) -> dict:
    """(stop, exit) -> {n, won, averageR, errorR}."""
    keys = {(s, e) for t in trades for s, v in t["r"].items() for e in v}
    out = {}
    for s, e in sorted(keys):
        x = np.array([t["r"][s][e] for t in trades])
        if len(x):
            out[f"{s} | {e}"] = {"n": len(x), "won": round(float((x > 0).mean()), 3), "averageR": round(float(x.mean()), 3), "errorR": round(float(x.std() / len(x) ** 0.5), 3)}
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    chosen = [x for x in sys.argv[1:] if x in ASSETS] or list(ASSETS)
    jobs = [(a, s) for a in chosen for s in (0, 1)]
    result: dict = {}
    with ProcessPoolExecutor(max_workers=3) as pool:
        for asset, seed, trades in pool.map(job, *zip(*jobs)):
            parts = {"shuffled": trades} if seed == 1 else {p: [t for t in trades if t["part"] == p] for p in ("first70", "last30")}
            for p, ts in parts.items():
                result.setdefault(asset, {})[p] = summary(ts)
    (OUT / "plan_study.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for asset, parts in result.items():
        first70 = parts["first70"]
        best = sorted(first70, key=lambda k: -first70[k]["averageR"])
        print("==", asset, "(ilk %70'e göre sıralı; R ± hata, işlem, kazanan)")
        for k in best:
            row = [parts[p].get(k) for p in ("first70", "last30", "shuffled")]
            print(f"  {k:28s}", " | ".join(f"{v['averageR']:+.2f}±{v['errorR']:.2f} n{v['n']} %{100 * v['won']:.0f}" if v else "-" for v in row))


if __name__ == "__main__":
    main()
