r"""Measure every test of rule_events on every asset and timeframe, on real and on shuffled prices.

  .\venv\Scripts\python.exe -m signals.scoring.run [ASSET] [@key]      -> data/reports/rule_results*.json (local, git-ignored)
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor

from signals.data.candles import ASSETS, LTF, TIMEFRAMES
from signals.data.download import SERVICE_DIR
from signals.scoring.null import null_cache
from signals.scoring.reaction import KS, measure, p_value
from signals.scoring.rule_events import TESTS, Context, load_all

OUT = SERVICE_DIR / "data" / "reports"
INTRADAY_FRAMES = LTF + ["4h", "6h", "12h"]
MIN_BARS = 100
SEEDS = 6                            # shuffles that make the control
CHECK = 7                            # one more shuffle, judged as if it were real: it must look like luck
NOT_SHUFFLED = ("oi_", "fund_")      # open interest and funding are not shuffled with the price: compared with a coin flip only


VOLUME = ("prev_d_V", "prev_w_V", "prev_m_V", "prev_d_POC", "prev_w_POC", "prev_m_POC", "npoc", "va_", "valpoc", "vol_", "sfp_volume", "sfp_both", "sfp_none",
          "pattern_volume", "chaos", "absorption", "cvd", "oi_", "fund_")


def wanted(asset: str, frame: str, key: str) -> bool:
    """Gold and the S&P: 15m-12h from the long spot series (no volume), 1d and above and the volume rules from the futures."""
    if asset in ("XAU", "SPX"):
        return frame in INTRADAY_FRAMES and not key.startswith(VOLUME)
    if asset in ("GC", "ES"):
        return frame not in INTRADAY_FRAMES or (key.startswith(VOLUME) and frame in ("1h", "2h", "4h"))
    return True


def run_frame(asset: str, frame: str, cache: dict, keys: tuple[str, ...] = (), start: int = 0) -> dict[str, dict]:
    if len(cache[(asset, frame)]) < MIN_BARS:
        return {}
    x, rows = Context(asset, frame, cache), {}
    for t in TESTS:
        if frame not in t.frames or (keys and not t.key.startswith(keys)) or not wanted(asset, frame, t.key):
            continue
        try:
            events = t.run(x)
            events, control = events if isinstance(events, tuple) else (events, None)
            if start:                                       # exam: the first bars are only a run-up
                events = [e for e in events if e.index >= start]
            r = measure(x.bars, events, control)
        except Exception as error:                      # one broken detector must not hide the others; it is reported as broken
            rows[t.key] = {"error": f"{type(error).__name__}: {error}"}
            continue
        rows[t.key] = {"seen": r.seen, "n": r.n, "wins": r.wins, "own_n": r.own_n, "own": r.own, "atr_pct": round(r.percent, 3),
                       "samples": [(x.times[i].isoformat(), d, p, w) for i, d, p, w in r.samples[-5:]]}
    return rows


def job(asset: str, seed: int, keys: tuple[str, ...] = ()) -> dict:
    """Every frame of one asset; seed 0 = real prices."""
    cache = load_all(asset) if seed == 0 else null_cache(asset, seed)
    return {frame: run_frame(asset, frame, cache, keys) for frame in TIMEFRAMES}


def judge(real: dict, nulls: list[dict], shuffled: bool) -> dict:
    """One test on one series next to its control (pooled shuffles, and the rule's own group when it has one): the harder one counts."""
    n, n0 = real["n"], sum(x["n"] for x in nulls)
    out = {**real, "null_n": n0 if shuffled else 30, "base": [], "p": [], "worse": []}
    for k in range(len(KS)):
        w0 = sum(x["wins"][k] for x in nulls)
        choices = [(w0, n0) if shuffled else (500, 1000)] + ([(real["own"][k], real["own_n"])] if real["own_n"] else [])
        p, base = max((p_value(real["wins"][k], n, w, m), w / m if m else 0.0) for w, m in choices)
        out["p"].append(p)
        out["base"].append(round(base, 4))
        w, m = choices[0]
        out["worse"].append(p_value(n - real["wins"][k], n, m - w, m))        # worse than the shuffled control?
    return out


def main() -> None:
    keys = tuple(a[1:] for a in sys.argv[1:] if a.startswith("@"))          # "@sfp" = only the tests whose key starts with sfp
    assets = [a for a in sys.argv[1:] if a in ASSETS] or list(ASSETS)
    jobs = [(a, s) for a in assets for s in range(CHECK + 1)]
    results = {}
    with ProcessPoolExecutor(max_workers=4) as pool:
        for key, got in zip(jobs, pool.map(job, *zip(*[(a, s, keys) for a, s in jobs]))):
            results[key] = got
            print(*key, flush=True)
    for name, seed in (("rule_results", 0), ("rule_results_check", CHECK)):
        rows = []
        for a in assets:
            for frame in TIMEFRAMES:
                for key, real in results[(a, seed)][frame].items():
                    row = {"asset": a, "frame": frame, "key": key}
                    nulls = [results[(a, s)][frame].get(key, {}) for s in range(1, SEEDS + 1)]
                    if "error" in real:
                        rows.append({**row, **real})
                    else:
                        rows.append({**row, **judge(real, [x for x in nulls if "n" in x], not key.startswith(NOT_SHUFFLED))})
        path = OUT / f"{name}.json"
        fresh = {(r["asset"], r["frame"], r["key"]) for r in rows}
        if path.exists():                              # a partial run replaces only what it measured
            rows += [r for r in json.loads(path.read_text(encoding="utf-8")) if (r["asset"], r["frame"], r["key"]) not in fresh]
        (OUT / f"{name}.json").write_text(json.dumps(rows), encoding="utf-8")
        judged = [r for r in rows if r.get("n", 0) >= 30 and r["null_n"] >= 30]
        print(name, len(judged), "judged;", sum(r["p"][0] < 0.01 for r in judged), "better at p<0.01,", sum(r["worse"][0] < 0.01 for r in judged),
              "worse;", sum("error" in r for r in rows), "errors", flush=True)


if __name__ == "__main__":
    main()
