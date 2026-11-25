r"""Every trigger of the past with its confirmations and what price did next: the data the score and its limits are chosen from.

  .\venv\Scripts\python.exe -m signals.live.study [asset ...]     -> data/reports/live_<asset>_<seed>.json (seed 1 = shuffled prices)

Entry = close of the trigger bar. Stop = the extreme plus STOP_ROOM x ATR(1h). On the 15m candles after it (HORIZON bars, the stop counts
first inside a bar): the largest move in favour before the stop, whether the stop was hit, and where price was at the end.
"""

from __future__ import annotations

import json
import sys
from bisect import bisect_right
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from signals.live.auxvol import SOURCES, AuxVolume
from signals.live.plan import MIN_STOP
from signals.live.scan import Event, Scanner
from signals.scoring.confirm import ASSETS
from signals.scoring.run import OUT
from signals.scoring.turns import load_full, ts

STOP_ROOM = 0.25
HORIZON = 480          # 15m bars (5 days) this study looks ahead; a virtual trade itself has no time limit


def stop_price(e: Event) -> float:
    return e.extreme - e.side * STOP_ROOM * e.atr_1h


def after(high: np.ndarray, low: np.ndarray, close: np.ndarray, i: int, side: int, entry: float, stop: float, horizon: int = HORIZON) -> tuple | None:
    """(largest favourable move %, stopped, move % at the end) from the bars after i; None when the future is not complete."""
    if i + horizon >= len(close):
        return None
    h, lo, c = high[i + 1:i + 1 + horizon], low[i + 1:i + 1 + horizon], close[i + horizon]
    hit = h >= stop if side == -1 else lo <= stop
    z = int(hit.argmax()) if hit.any() else len(h)
    best = 0.0 if z == 0 else (entry - lo[:z].min() if side == -1 else h[:z].max() - entry)
    return round(100 * max(0.0, best) / entry, 3), z < len(h), round(100 * side * (c - entry) / entry, 3)


def funding_tags():
    """BTC funding beyond +-0.05 % against the crowd, known at the time (kept with 1d)."""
    from signals.data import derivatives
    rows = derivatives.load("funding")
    t, v = [ts(a) for a, _ in rows], [b for _, b in rows]

    def extra(when: float, side: int) -> dict:
        i = bisect_right(t, when) - 1
        return {"1d": {"Funding|aşırı|±%0,05"}} if i >= 0 and when - t[i] < 9 * 3600 and -side * v[i] >= 0.0005 else {}
    return extra


def job(asset: str, seed: int) -> str:
    if seed == 0:
        cache = load_full(asset)
    else:
        from signals.scoring.null import null_cache
        cache = null_cache(asset, seed, lambda c: c)
    sc = Scanner(asset, cache, funding_tags() if asset == "BTCUSDT" and seed == 0 else None, AuxVolume(asset) if asset in SOURCES and seed == 0 else None)
    b = sc.base.x.bars
    names: dict[str, int] = {}
    rows = []
    for i, e in sc.events():
        stop = stop_price(e)
        distance = 100 * abs(stop - e.entry) / e.entry
        got = after(b.high, b.low, b.close, i, e.side, e.entry, stop)
        if got is None or distance < MIN_STOP:
            continue
        rows.append([e.time, e.side, e.frame, round(e.entry, 2), round(distance, 3), *(v.item() if hasattr(v, "item") else v for v in got),
                     {f: [names.setdefault(t, len(names)) for t in v] for f, v in e.tags.items()}])
    path = OUT / f"live_{asset}_{seed}.json"
    path.write_text(json.dumps({"names": list(names), "rows": rows}, ensure_ascii=False), encoding="utf-8")
    return f"{asset} {seed} {len(rows)}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    jobs = [(a, s) for a in ([x for x in sys.argv[1:] if x in ASSETS] or ASSETS) for s in (0, 1)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for line in pool.map(job, *zip(*jobs)):
            print(line, flush=True)


if __name__ == "__main__":
    main()
