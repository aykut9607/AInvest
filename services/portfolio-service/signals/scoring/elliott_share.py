r"""How much Elliott is in the chart? (occurrence, not reaction)

Two questions per asset and timeframe, always next to the same measurement on shuffled prices (blocks of 20 bars put in random order:
the same candles, but no real wave structure), because random prices also produce "waves":
  rules     of all 5-leg zigzag runs, how many keep E-01 / E-02 / E-03 / E-04 (and all of them)
  turns     of the major turns (zigzag 6 ATR), how many are the end of a 1-5 impulse, diagonal, ABC or triangle of the finer zigzag (2 ATR)
"""

from __future__ import annotations

import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor

from signals.data.candles import ASSETS, TIMEFRAMES, Candle
from signals.patterns.elliott import abc_counts, impulse_counts
from signals.rules import elliott_check
from signals.scoring.rule_events import load_all
from signals.scoring.run import MIN_BARS, OUT
from signals.structure.zigzag import zigzag

BLOCK, SHUFFLES = 20, 8
NAMES = ("itki", "diyagonal", "ABC", "üçgen", "herhangi biri")


def shuffled(candles: list[Candle], seed: int) -> list[Candle]:
    rng = random.Random(seed)
    shapes = [(c.open / p.close, c.high / p.close, c.low / p.close, c.close / p.close, c.volume) for p, c in zip(candles, candles[1:])]
    blocks = [shapes[i:i + BLOCK] for i in range(0, len(shapes), BLOCK)]
    rng.shuffle(blocks)
    out, last = [candles[0]], candles[0].close
    for (o, h, l, c, v), src in zip((s for b in blocks for s in b), candles[1:]):
        out.append(Candle(src.time, last * o, last * h, last * l, last * c, v))
        last *= c
    return out


def shares(candles: list[Candle]) -> dict[str, float]:
    out: dict[str, float] = {}
    fine = zigzag(candles, multiple=2.0)
    runs = [fine[i:i + 6] for i in range(len(fine) - 5)]
    keep = {"E-01": 0, "E-02": 0, "E-03": 0, "E-04": 0, "hepsi": 0}
    ends = {n: set() for n in NAMES}
    for run in runs:
        sign = 1 if run[0].kind == "low" else -1
        p = [sign * q.price for q in run]
        w1, w3, w5 = p[1] - p[0], p[3] - p[2], p[5] - p[4]
        ok = {"E-01": p[2] > p[0], "E-02": p[3] > p[1], "E-03": not (w3 < w1 and w3 < w5), "E-04": p[4] > p[1]}
        for k, v in ok.items():
            keep[k] += v
        keep["hepsi"] += all(ok.values())
        prices, times = [q.price for q in run], [q.index for q in run]
        if elliott_check.check_triangle(prices, times).possible:
            ends["üçgen"].add(run[-1].index)
    for c in impulse_counts(fine):
        if c.complete:
            ends["itki" if c.kind.lower().startswith("imp") else "diyagonal"].add(c.points[-1].index)
    ends["ABC"] = {c.points[-1].index for c in abc_counts(fine) if len(c.points) == 4}
    ends["herhangi biri"] = set().union(*ends.values())
    for k, v in keep.items():
        out[k] = v / len(runs) if runs else 0.0
    major = [p.index for p in zigzag(candles, multiple=6.0)]
    for n in NAMES:
        out["dönüş " + n] = sum(i in ends[n] for i in major) / len(major) if major else 0.0
    out["n_run"], out["n_dönüş"] = len(runs), len(major)
    return out


def one(asset: str, frame: str) -> dict | None:
    candles = load_all(asset)[(asset, frame)]
    if len(candles) < MIN_BARS * 2:
        return None
    real = shares(candles)
    fakes = [shares(shuffled(candles, s)) for s in range(SHUFFLES if len(candles) < 60000 else 3)]
    return {"asset": asset, "frame": frame, "real": real,
            "fake": {k: sum(f[k] for f in fakes) / len(fakes) for k in real}, "fake_max": {k: max(f[k] for f in fakes) for k in real}}


def main() -> None:
    jobs = [(a, f) for a in (sys.argv[1:] or list(ASSETS)) for f in TIMEFRAMES]
    with ProcessPoolExecutor(max_workers=3) as pool:
        rows = [r for r in pool.map(one, *zip(*jobs)) if r]
    (OUT / "elliott_share.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(len(rows), "series")


if __name__ == "__main__":
    main()
