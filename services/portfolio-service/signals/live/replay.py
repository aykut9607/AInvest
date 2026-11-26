r"""The past played again with the plan and the position management of the live engine: every trade, one compounding account.

  .\venv\Scripts\python.exe -m signals.live.replay [asset ...]      -> data/reports/replay_<asset>_<seed>.json and signals/live/replay.json (summary)
  .\venv\Scripts\python.exe -m signals.live.replay year             -> data/reports/replay_year.json: the last 365 days, each asset and all three together

Triggers and confirmations come from study.py (live_<asset>_<seed>.json, seed 1 = shuffled prices). One open trade per asset and direction, no time
limit, sizes from the CURRENT balance. A rehearsal of the rules, not a promise: the rules were chosen on the first 70 % of this very data.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from signals.live import fibs, fit
from signals.live import plan as planning
from signals.live.manage import FEE_SIDE, Position
from signals.live.scan import BASE, Scanner
from signals.live.score import kind_of, score, tables
from signals.scoring.confirm import ASSETS
from signals.scoring.run import OUT
from signals.scoring.turns import load_full

SUMMARY = Path(__file__).with_name("replay.json")
YEAR = Path(__file__).with_name("year.json")
IQ, START = 50, 1000.0          # an average user


def cache_of(asset: str, seed: int) -> dict:
    if seed == 0:
        return load_full(asset)
    from signals.scoring.null import null_cache
    return null_cache(asset, seed, lambda c: c)


def plans(asset: str, seed: int, scanner: Scanner) -> tuple[list, dict]:
    """(plans in time order, how many triggers were left out and why)."""
    table = tables()[asset]
    names, rows = fit.load(asset, seed)
    out, left = [], defaultdict(int)
    for r in rows:
        when, side, frame, entry = r[:4]
        tags = {f: [names[x] for x in v] for f, v in r[8].items()}
        s = score(tags, table)
        kind = kind_of(s, table)
        if kind is None:
            left["score"] += 1
            continue
        fr = scanner.frames[frame]
        j, b = fr.closed_at(when), fr.x.bars
        f = fibs.draw(b.high, b.low, j, side, float(b.atr[j - 1]))
        p = f and planning.make(asset, side, kind, when, s.total, entry, f.extreme, f, frame, s.categories, {}, (), tags)
        if not p:
            left["fib" if f is None else "half" if side * (entry - f.scalp(planning.ENTRY_HALF)) > 0 else "reward"] += 1
            continue
        out.append(p)
    return out, dict(left)


def play(todo: list, series: dict[str, tuple], iq: int = IQ, start: float = START) -> list[dict]:
    """Every trade with its fills; all assets are paid from one compounding account. `series`: asset -> (open time, open, high, low, close) of the 15m bars."""
    todo = sorted(todo, key=lambda p: p.time)
    times = np.unique(np.concatenate([s[0] for s in series.values()]))
    balance, live, done, k, i = start, [], [], 0, 0
    while i < len(times):
        if not live:          # nothing open: jump to the bar whose close is the next plan
            if k >= len(todo):
                break
            i = max(i, int(np.searchsorted(times, todo[k].time - BASE)))
            if i >= len(times):
                break
        for rec, pos in list(live):
            t, o, h, lo, c = series[rec["asset"]]
            b = int(np.searchsorted(t, times[i]))
            if b >= len(t) or t[b] != times[i]:
                continue
            for x in pos.candle(o[b], h[b], lo[b], c[b]):
                pnl = rec["notionalUsd"] * x.percent / 100
                balance += pnl
                rec["fills"].append({"time": int(times[i] + BASE), "zone": x.kind, "price": round(float(x.price), 2), "units": x.units, "left": x.units_left, "pnlUsd": round(float(pnl), 2)})
            if pos.closed:
                close(rec, pos, balance)
                live.remove((rec, pos))
                done.append(rec)
        now = times[i] + BASE          # trades are opened at the close of this bar and followed from the next one
        while k < len(todo) and todo[k].time <= now:
            p = todo[k]
            k += 1
            if p.time < now or any(r["asset"] == p.asset and r["direction"] == p.direction for r, _ in live):
                continue
            s = planning.size(iq, p.stop_percent, p.kind)
            notional = balance * s.notional_percent / 100
            rec = {"asset": p.asset, "direction": p.direction, "kind": p.kind, "time": int(p.time), "entry": p.entry, "stop": p.stop, "stopPercent": p.stop_percent, "leverage": s.leverage,
                   "marginUsd": round(float(balance * s.margin_percent / 100), 2), "notionalUsd": float(notional), "balanceBefore": round(float(balance), 2), "score": p.score, "frame": p.trigger_frame,
                   "categories": p.categories, "confirmations": p.confirmations, "steps": p.steps, "redrawn": p.fib["redrawn"], "fills": []}
            balance -= notional * FEE_SIDE / 100
            live.append((rec, Position(1 if p.direction == "LONG" else -1, p.entry, p.stop, p.steps)))
        i += 1
    for rec, pos in live:
        close(rec, pos, balance, float(series[rec["asset"]][4][-1]))
        done.append(rec)
    return sorted(done, key=lambda r: r["time"])


def close(rec: dict, pos: Position, balance: float, price: float | None = None) -> None:
    net = pos.net_percent + (pos.open_percent(price) if price else 0)
    favour = 100 * pos.side * (pos.best - pos.entry) / pos.entry
    rec |= {"status": "OPEN" if price else "CLOSED", "exit": pos.exit_reason, "unitsLeft": pos.units_left, "resultR": round(net / pos.stop_percent, 3), "pnlUsd": round(rec["notionalUsd"] * net / 100, 2),
            "roiPercent": round(net * rec["leverage"], 1), "maxProfitPercent": round(favour, 2), "maxProfitRoi": round(favour * rec["leverage"], 1),
            "maxLossPercent": round(100 * pos.side * (pos.worst - pos.entry) / pos.entry, 2), "balanceAfter": round(balance, 2), "notionalUsd": round(rec["notionalUsd"], 2)}


def stats(trades: list[dict]) -> dict:
    d = [x for x in trades if x["status"] == "CLOSED"]
    if not d:
        return {"n": 0}
    r = np.array([x["resultR"] for x in d])
    win, loss = r[r > 0], r[r <= 0]
    exits = defaultdict(int)
    for x in d:
        exits[x["exit"]] += 1
    streak = longest = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        longest = max(longest, streak)
    hours = np.array([(x["fills"][-1]["time"] - x["time"]) / 3600 for x in d])
    return {"n": len(d), "won": int(len(win)), "lost": int(len(loss)), "winRate": round(len(win) / len(d), 3), "averageR": round(float(r.mean()), 3),
            "errorR": round(float(r.std() / len(r) ** 0.5), 3), "averageWinR": round(float(win.mean()), 2) if len(win) else None, "averageLossR": round(float(loss.mean()), 2) if len(loss) else None,
            "profitFactor": round(float(win.sum() / -loss.sum()), 2) if len(loss) and loss.sum() else None, "halfReached": round(sum(any(f["zone"].startswith("HALF") for f in x["fills"]) for x in d) / len(d), 3),
            "longestLosingStreak": longest, "medianHours": round(float(np.median(hours)), 1), "exits": dict(sorted(exits.items(), key=lambda x: -x[1]))}


def curve(trades: list[dict], start: float = START) -> dict:
    """The account over the closed trades."""
    peak = worst = 0.0
    value = start
    for x in sorted((x for x in trades if x["status"] == "CLOSED"), key=lambda x: x["fills"][-1]["time"]):
        value = x["balanceAfter"]
        peak = max(peak, value, start)
        worst = max(worst, 1 - value / peak)
    return {"start": start, "end": round(value, 2), "percent": round(100 * (value / start - 1), 1), "maxDrawdownPercent": round(100 * worst, 1)}


def job(asset: str, seed: int) -> tuple[str, int, dict]:
    sc = Scanner(asset, cache_of(asset, seed))
    b = sc.base.x.bars
    todo, left = plans(asset, seed, sc)
    series = {asset: (sc.base.t, b.open, b.high, b.low, b.close)}
    rows = fit.load(asset, seed)[1]
    split = rows[0][0] + (rows[-1][0] - rows[0][0]) * fit.SPLIT
    out = {"plans": len(todo), "leftOut": left, "split": int(split)}
    every: list[dict] = []
    for name, part in (("first70", [p for p in todo if p.time <= split]), ("last30", [p for p in todo if p.time > split])):
        trades = play(part, series)          # its own account, from 1000
        out[name] = {"all": stats(trades), **{k: stats([x for x in trades if x["kind"] == k]) for k in planning.KINDS}, "account": curve(trades)}
        if name == "last30":
            every = trades
    if seed == 0:
        (OUT / f"replay_{asset}_{seed}.json").write_text(json.dumps(every, ensure_ascii=False), encoding="utf-8")
    return asset, seed, out


def year_job(asset: str, seed: int) -> tuple[str, int, list, tuple]:
    sc = Scanner(asset, cache_of(asset, seed))
    b = sc.base.x.bars
    return asset, seed, plans(asset, seed, sc)[0], (sc.base.t, b.open, b.high, b.low, b.close)


def year(days: int = 365) -> None:
    """The last year of every asset alone and of all three from one account."""
    got: dict[int, dict] = {0: {}, 1: {}}
    with ProcessPoolExecutor(max_workers=3) as pool:
        for asset, seed, todo, series in pool.map(year_job, *zip(*[(a, s) for a in ASSETS for s in (0, 1)])):
            got[seed][asset] = (todo, series)
    end = max(s[0][-1] for _, s in got[0].values())
    begin = end - days * 86400
    out: dict = {"from": int(begin), "to": {a: int(s[0][-1]) for a, (_, s) in got[0].items()}, "real": {}, "shuffled": {}}
    for seed, name in ((0, "real"), (1, "shuffled")):
        for who in [(a,) for a in ASSETS] + [tuple(ASSETS)]:
            series = {a: tuple(x[got[seed][a][1][0] >= begin] for x in got[seed][a][1]) for a in who}
            trades = play([p for a in who for p in got[seed][a][0] if p.time >= begin + BASE], series)
            key = who[0] if len(who) == 1 else "ALL"
            out[name][key] = {"all": stats(trades), **{k: stats([x for x in trades if x["kind"] == k]) for k in planning.KINDS}, "account": curve(trades), **({"trades": trades} if seed == 0 else {})}
            print(name, key, out[name][key]["account"], {k: out[name][key]["all"].get(k) for k in ("n", "won", "lost", "winRate", "averageR", "errorR", "profitFactor", "exits")},
                  {k: (out[name][key][k].get("n"), out[name][key][k].get("winRate"), out[name][key][k].get("averageR")) for k in planning.KINDS})
    (OUT / "replay_year.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    # what the screen shows: the numbers of every account and the trades of the common one (confirmations as indexes, they repeat a lot)
    names: dict[str, int] = {}
    trades = [t | {"confirmations": {f: [names.setdefault(x, len(names)) for x in v] for f, v in t["confirmations"].items()}} for t in out["real"]["ALL"]["trades"]]
    small = {"from": out["from"], "to": out["to"], **{n: {k: {x: y for x, y in v.items() if x != "trades"} for k, v in out[n].items()} for n in ("real", "shuffled")}, "trades": trades, "names": list(names)}
    YEAR.write_text(json.dumps(small, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    if "year" in sys.argv:
        return year()
    chosen = [x for x in sys.argv[1:] if x in ASSETS] or list(ASSETS)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {}
    jobs = [(a, s) for a in chosen for s in (0, 1)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for asset, seed, out in pool.map(job, *zip(*jobs)):
            summary.setdefault(asset, {})["real" if seed == 0 else "shuffled"] = out
            print(asset, seed, out["plans"], out["leftOut"])
            for part in ("first70", "last30"):
                print("  ", part, out[part]["account"], out[part]["all"])
                for k in planning.KINDS:
                    print("      ", k, {x: out[part][k].get(x) for x in ("n", "winRate", "averageR", "errorR", "profitFactor", "halfReached", "medianHours")})
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
