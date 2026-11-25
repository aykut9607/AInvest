r"""The live loop of 4.4: at every 15m close look for a divergence (15m, 30m, 45m, 1h in this order); if there is one, scan every rule on all 12
timeframes, score it, and follow a VIRTUAL trade when the score reaches a limit. No order is ever sent.

  .\venv\Scripts\python.exe -m signals.live.run            loop (Ctrl+C stops it); needs portfolio_db and the internet (Binance public data)
  .\venv\Scripts\python.exe -m signals.live.run once       one pass
  .\venv\Scripts\python.exe -m signals.live.run once dry   one pass, printed, nothing stored (no database needed)
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from signals.live import plan as planning
from signals.live.feed import LIVE_ASSETS, Feed
from signals.live.scan import BASE, Event, Scanner
from signals.live.auxvol import SOURCES, AuxVolume
from signals.live.score import kind_of, score, tables
from signals.live.study import funding_tags, stop_price

WAIT_AFTER_CLOSE = 5          # seconds until the exchange has the closed candle
LATE = 120                    # seconds after the close a trade may still be opened
MISSED_DAYS = 30              # how far back a stop of the engine is looked at


def judge(asset: str, event: Event, table: dict) -> tuple[dict, planning.Plan | None]:
    """(what the screen shows about this scan, the plan if a limit was reached)."""
    s = score(event.tags, table)
    kind = kind_of(s, table)
    shown = {"time": event.time, "direction": "SHORT" if event.side == -1 else "LONG", "triggerFrame": event.frame, "trigger": list(event.reasons), "price": event.entry,
             "score": s.total, "kind": kind, "categories": s.categories, "confirmations": event.tags}
    stop = stop_price(event)
    if kind is None or 100 * abs(stop - event.entry) / event.entry < planning.MIN_STOP:
        return shown, None
    if event.fib is None:
        return shown | {"noPlan": "no leg to draw a fib on"}, None
    e = table["evidence"][kind]
    plan = planning.make(asset, event.side, kind, event.time, s.total, event.entry, stop, event.fib, event.frame, s.categories,
                         {"proven": e["proven"], **{k: e[k] for k in ("last30", "shuffled")}}, event.reasons, event.tags)
    return (shown, plan) if plan else (shown | {"noPlan": "entry in the dear half of the fib, or the last target pays less than 1.5 x the stop"}, None)


def missed(asset: str, scanner: Scanner, table: dict, since: float, until: float) -> list[planning.Plan]:
    """Plans of the 15m closes after `since` and before `until`: the engine was not running, nothing may be opened any more. Every close is scanned
    with what was known then (the scanner never reads later bars)."""
    out = []
    since = max(since, until - MISSED_DAYS * 86400)
    for i in range(len(scanner.base.t)):
        when = float(scanner.base.t[i]) + BASE
        if not since < when < until:
            continue
        for side in (-1, 1):
            found = scanner.trigger(when, side)
            plan = judge(asset, scanner.scan(i, side, found), table)[1] if found else None
            if plan:
                out.append(plan)
    return out


def look(asset: str, feed: Feed, now: datetime, since: float | None = None) -> tuple[dict, list[planning.Plan], list[planning.Plan]]:
    """One pass over the newest closed 15m bar: (scan for the screen, plans, plans missed since the last pass)."""
    hole = feed.hole()
    last = feed.data["15m"][-1]
    closed_at = last.time.timestamp() + BASE
    scan = {"asset": asset, "dataUntil": closed_at, "problem": hole, "triggers": []}
    if hole:
        return scan, [], []
    if now.timestamp() - closed_at > 2 * BASE:
        return scan | {"problem": "the newest candle is old: no live data"}, [], []
    table, plans = tables()[asset], []
    scanner = Scanner(asset, feed.cache(), funding_tags() if asset == "BTCUSDT" else None, AuxVolume(asset) if asset in SOURCES else None)
    for side in (-1, 1):
        found = scanner.trigger(closed_at, side)
        if found:
            shown, plan = judge(asset, scanner.scan(len(scanner.base.t) - 1, side, found), table)
            scan["triggers"].append(shown)
            plans += [plan] if plan else []
    gone = missed(asset, scanner, table, since, closed_at) if since else []
    if now.timestamp() - closed_at > LATE:          # just started, or a slow pass: that price is gone
        return scan | {"late": True}, [], gone + plans
    return scan, plans, gone


def session():
    from sqlalchemy.orm import sessionmaker

    from db.session import get_engine
    return sessionmaker(bind=get_engine())()


def last_pass(asset: str) -> float | None:
    from services import market
    with session() as db:
        at = market.last_scan(db, asset)
    return at.timestamp() if at else None


def store(asset: str, scan: dict, plans: list[planning.Plan], gone: list[planning.Plan], candles: list) -> list[str]:
    from services import market
    lines = []
    with session() as db:
        for t, e in market.follow(db, asset, candles):
            lines.append(f"{t.direction} {e.kind} at {e.price} ({e.units:g} units, {e.pnl_usd:+.2f} USD)")
        for p in gone:
            m = market.note_missed(db, p, candles)
            if m:
                lines.append(f"MISSED (engine was off) {p.direction} {p.kind} score {p.score} entry {p.entry} at {market.tsi(m.at)}")
        market.follow_missed(db, asset, candles)
        for p in plans:
            t = market.open_trade(db, p)
            if t:
                lines.append(f"virtual {p.direction} {p.kind} score {p.score} entry {p.entry} stop {p.stop} {t.leverage}x margin {t.margin_usd} USD")
        market.save_scan(db, asset, datetime.fromtimestamp(scan["dataUntil"], timezone.utc), scan)
        db.commit()
    return lines


def one_pass(feeds: dict[str, Feed], dry: bool) -> None:
    now = datetime.now(timezone.utc)
    for asset, feed in feeds.items():
        try:
            feed.refresh(now)
            scan, plans, gone = look(asset, feed, now, None if dry else last_pass(asset))
            lines = [str(p.as_dict()) for p in plans] if dry else store(asset, scan, plans, gone, feed.data["15m"])
            print(f"{now:%H:%M:%S} {asset}", scan["problem"] or "", [(t["direction"], t["triggerFrame"], t["score"], t["kind"]) for t in scan["triggers"]] or "no trigger", *lines, flush=True)
        except Exception as error:          # one bad pass (network, database) must not end the loop
            print(f"{now:%H:%M:%S} {asset} failed: {type(error).__name__} {error}", flush=True)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    dry = "dry" in sys.argv
    feeds = {a: Feed(a) for a in LIVE_ASSETS}
    one_pass(feeds, dry)
    while "once" not in sys.argv:
        time.sleep(BASE - time.time() % BASE + WAIT_AFTER_CLOSE)
        one_pass(feeds, dry)


if __name__ == "__main__":
    main()
