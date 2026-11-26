"""4.4 on paper: stores the newest scan, opens, follows and closes virtual trades and keeps the paper account. Nothing here talks to an exchange."""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import MarketScan, VirtualAccount, VirtualMissedTrade, VirtualTrade, VirtualTradeEvent
from signals.data.candles import Candle
from signals.live import plan as planning
from signals.live.manage import FEE_SIDE, Position
from signals.live.plan import Plan

BAR = timedelta(minutes=15)
TSI = timezone(timedelta(hours=3), "TSİ")
ACCOUNT = "demo"
ACCOUNT_IQ, ACCOUNT_START = 50, 1000.0          # an average user with 1000 USD


def utc(value: datetime) -> datetime:
    """SQLite gives naive times back; all times are UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def tsi(value: datetime | None) -> str | None:
    return utc(value).astimezone(TSI).strftime("%d.%m.%Y %H:%M") if value else None


def save_scan(db: Session, asset: str, scanned_at: datetime, payload: dict) -> None:
    db.merge(MarketScan(asset=asset, scanned_at=scanned_at, payload=payload))


def account(db: Session) -> VirtualAccount:
    """The paper account; the first call opens it. Locked while a pass changes it, so two loops cannot spend the same money."""
    found = db.scalars(select(VirtualAccount).where(VirtualAccount.id == ACCOUNT).with_for_update()).one_or_none()
    if found is None:
        found = VirtualAccount(id=ACCOUNT, iq_score=ACCOUNT_IQ, start_balance=ACCOUNT_START, balance=ACCOUNT_START)
        db.add(found)
        db.flush()
    return found


def open_trades(db: Session, asset: str | None = None) -> list[VirtualTrade]:
    query = select(VirtualTrade).where(VirtualTrade.closed_at.is_(None))
    return list(db.scalars(query.where(VirtualTrade.asset == asset) if asset else query))


def events_of(db: Session, trade_id: str) -> list[VirtualTradeEvent]:
    return list(db.scalars(select(VirtualTradeEvent).where(VirtualTradeEvent.trade_id == trade_id).order_by(VirtualTradeEvent.seq)))


def open_trade(db: Session, plan: Plan) -> VirtualTrade | None:
    """One open trade per asset and direction; a second signal in the same direction is the same idea."""
    if any(t.direction == plan.direction for t in open_trades(db, plan.asset)):
        return None
    a = account(db)
    s = planning.size(a.iq_score, plan.stop_percent, plan.kind)
    at = datetime.fromtimestamp(plan.time, timezone.utc)
    notional, before = a.balance * s.notional_percent / 100, a.balance
    fee = notional * FEE_SIDE / 100
    a.balance -= fee
    trade = VirtualTrade(id=str(uuid.uuid4()), asset=plan.asset, direction=plan.direction, kind=plan.kind, opened_at=at, entry=plan.entry, stop=plan.stop, target=plan.final_target,
                         plan=plan.as_dict(), account_id=a.id, leverage=s.leverage, margin_usd=round(before * s.margin_percent / 100, 2), notional_usd=notional, balance_before=before,
                         pnl_usd=-fee, net_percent=-FEE_SIDE, stop_now=plan.stop, units_left=100.0, best_price=plan.entry, worst_price=plan.entry, last_price=plan.entry, followed_until=at)
    db.add(trade)
    db.flush()
    db.add(VirtualTradeEvent(id=str(uuid.uuid4()), trade_id=trade.id, seq=0, at=at, kind="OPEN", price=plan.entry, units=100.0, units_left=100.0, pnl_usd=-fee, balance_after=a.balance))
    db.flush()
    return trade


def follow(db: Session, asset: str, candles: list[Candle]) -> list[tuple[VirtualTrade, VirtualTradeEvent]]:
    """Runs every open trade through the 15m candles it has not seen yet, in time order over all of them (they share one account)."""
    opened = open_trades(db, asset)
    if not opened:
        return []
    a, out = account(db), []
    books = [(t, _position(db, t), len(events_of(db, t.id))) for t in opened]
    first = min(utc(t.followed_until) for t in opened)
    for c in candles:
        if c.time < first:
            continue
        end = c.time + BAR
        for k, (t, p, seq) in enumerate(books):
            if p.closed or c.time < utc(t.followed_until):
                continue
            for f in p.candle(c.open, c.high, c.low, c.close):
                pnl = t.notional_usd * f.percent / 100
                a.balance += pnl
                t.pnl_usd += pnl
                e = VirtualTradeEvent(id=str(uuid.uuid4()), trade_id=t.id, seq=seq, at=end, kind=f.kind, price=f.price, units=f.units, units_left=f.units_left, pnl_usd=pnl, balance_after=a.balance)
                seq += 1
                db.add(e)
                out.append((t, e))
            books[k] = (t, p, seq)
            t.followed_until, t.last_price = end, c.close
            t.stop_now, t.units_left, t.best_price, t.worst_price, t.net_percent = p.stop_now, p.units_left, p.best, p.worst, p.net_percent
            if p.closed:
                t.closed_at, t.exit_price, t.exit_reason = end, out[-1][1].price, p.exit_reason
                t.result_r, t.balance_after = round(p.result_r, 3), a.balance
    db.flush()
    return out


# ---------- conditions met while the engine was off

def last_scan(db: Session, asset: str) -> datetime | None:
    scan = db.get(MarketScan, asset)
    return utc(scan.scanned_at) if scan else None


def open_missed(db: Session, asset: str) -> list[VirtualMissedTrade]:
    return list(db.scalars(select(VirtualMissedTrade).where(VirtualMissedTrade.asset == asset, VirtualMissedTrade.closed_at.is_(None))))


def note_missed(db: Session, plan: Plan, candles: list[Candle], reason: str = "ENGINE_OFF") -> VirtualMissedTrade | None:
    """Same rule as a real one: not while a trade (real or noted) of that asset and direction is open at that moment."""
    at = datetime.fromtimestamp(plan.time, timezone.utc)
    follow_missed(db, plan.asset, candles, at)
    real = db.scalars(select(VirtualTrade).where(VirtualTrade.asset == plan.asset, VirtualTrade.direction == plan.direction, VirtualTrade.opened_at <= at))
    if any(t.closed_at is None or utc(t.closed_at) > at for t in real) or any(m.direction == plan.direction for m in open_missed(db, plan.asset)):
        return None
    if db.scalars(select(VirtualMissedTrade.id).where(VirtualMissedTrade.asset == plan.asset, VirtualMissedTrade.direction == plan.direction, VirtualMissedTrade.at >= at)).first():
        return None          # this stretch was already looked at
    m = VirtualMissedTrade(id=str(uuid.uuid4()), asset=plan.asset, direction=plan.direction, kind=plan.kind, at=at, noted_at=datetime.now(timezone.utc), reason=reason, entry=plan.entry, stop=plan.stop,
                           plan=plan.as_dict(), state={"stopNow": plan.stop, "unitsLeft": 100.0, "best": plan.entry, "worst": plan.entry, "netPercent": -FEE_SIDE, "last": plan.entry, "fills": []}, followed_until=at)
    db.add(m)
    db.flush()
    return m


def follow_missed(db: Session, asset: str, candles: list[Candle], until: datetime | None = None) -> None:
    for m in open_missed(db, asset):
        s, start = dict(m.state), utc(m.followed_until)
        p = Position(1 if m.direction == "LONG" else -1, m.entry, m.stop, m.plan["steps"], s["stopNow"], s["unitsLeft"], s["best"], s["worst"], s["netPercent"])
        p.taken, fills = {f["zone"] for f in s["fills"]}, list(s["fills"])
        for c in candles:
            end = c.time + BAR
            if c.time < start or (until and end > until):
                continue
            fills += [{"zone": f.kind, "price": f.price, "units": f.units, "atTsi": tsi(end)} for f in p.candle(c.open, c.high, c.low, c.close)]
            m.followed_until, s["last"] = end, c.close
            if p.closed:
                m.closed_at, m.exit_reason, m.result_r = end, p.exit_reason, round(p.result_r, 3)
                break
        m.state = s | {"stopNow": p.stop_now, "unitsLeft": p.units_left, "best": p.best, "worst": p.worst, "netPercent": p.net_percent, "fills": fills}
    db.flush()


def missed_out(m: VirtualMissedTrade) -> dict:
    side = 1 if m.direction == "LONG" else -1
    s, lev = m.state, m.plan["leverage"]
    away = lambda price: 100 * side * (price - m.entry) / m.entry
    return {"id": m.id, "direction": m.direction, "kind": m.kind, "status": "MISSED", "reason": m.reason, "at": utc(m.at).isoformat(), "atTsi": tsi(m.at), "notedAtTsi": tsi(m.noted_at), "entry": m.entry,
            "stop": m.stop, "stopPercent": m.plan["stop_percent"], "leverage": lev, "steps": m.plan["steps"], "fib": m.plan["fib"], "score": m.plan["score"], "triggerFrame": m.plan["trigger_frame"],
            "trigger": m.plan["trigger"], "categories": m.plan["categories"], "confirmations": m.plan["confirmations"],
            "wouldBe": {"status": "CLOSED" if m.closed_at else "OPEN", "closedAtTsi": tsi(m.closed_at), "exitReason": m.exit_reason, "resultR": m.result_r, "netPercent": round(s["netPercent"], 3),
                        "roiPercent": round(s["netPercent"] * lev, 1), "unitsLeft": s["unitsLeft"], "fills": s["fills"], "maxProfitPercent": round(away(s["best"]), 2), "maxProfitRoi": round(away(s["best"]) * lev, 1)}}


def _position(db: Session, t: VirtualTrade) -> Position:
    p = Position(1 if t.direction == "LONG" else -1, t.entry, t.stop, t.plan["steps"], t.stop_now, t.units_left, t.best_price, t.worst_price, t.net_percent)
    p.taken = {e.kind for e in events_of(db, t.id)}
    return p


# ---------- what the screen shows

def record(t: VirtualTrade, events: list[VirtualTradeEvent]) -> dict:
    """Everything about one trade; times also in Turkish time (TSİ)."""
    side = 1 if t.direction == "LONG" else -1
    away = lambda price: 100 * side * (price - t.entry) / t.entry
    ended = utc(t.closed_at) if t.closed_at else utc(t.followed_until)
    floating = t.notional_usd * t.units_left / 100 * away(t.last_price) / 100 if t.closed_at is None else 0.0
    taken = [e for e in events if e.kind not in ("OPEN", "STOP", "ENTRY_STOP")]
    last = events[-1] if events else None
    stopped = last if last and last.kind in ("STOP", "ENTRY_STOP") else None
    money = lambda v: round(v, 2)
    return {
        "id": t.id, "direction": t.direction, "kind": t.kind, "status": "CLOSED" if t.closed_at else ("PARTIAL" if taken else "OPEN"),
        "openedAt": utc(t.opened_at).isoformat(), "openedAtTsi": tsi(t.opened_at), "closedAt": utc(t.closed_at).isoformat() if t.closed_at else None, "closedAtTsi": tsi(t.closed_at),
        "durationHours": round((ended - utc(t.opened_at)).total_seconds() / 3600, 1),
        "entry": t.entry, "leverage": t.leverage, "stop": t.stop, "stopPercent": t.plan["stop_percent"], "stopNow": t.stop_now, "stopAtEntry": t.stop_now == t.entry,
        "steps": t.plan["steps"], "fib": t.plan["fib"], "unitsLeft": t.units_left,
        "marginUsd": money(t.margin_usd), "marginPercent": round(100 * t.margin_usd / t.balance_before, 2), "notionalUsd": money(t.notional_usd),
        "balanceBefore": money(t.balance_before), "balanceAfter": money(t.balance_after) if t.balance_after is not None else None,
        "takeProfits": [{"zone": e.kind, "price": e.price, "units": e.units, "atTsi": tsi(e.at), "pnlUsd": money(e.pnl_usd)} for e in taken],
        "stopped": {"zone": stopped.kind, "price": stopped.price, "units": stopped.units, "atTsi": tsi(stopped.at), "pnlUsd": money(stopped.pnl_usd)} if stopped else None,
        "exit": t.exit_price, "exitReason": t.exit_reason, "pnlUsd": money(t.pnl_usd), "roiPercent": round(100 * t.pnl_usd / t.margin_usd, 1) if t.margin_usd else None, "resultR": t.result_r,
        "openPnlUsd": money(floating), "lastPrice": t.last_price,
        "maxProfit": {"price": t.best_price, "percent": round(away(t.best_price), 2), "roiPercent": round(away(t.best_price) * t.leverage, 1), "usd": money(t.notional_usd * away(t.best_price) / 100)},
        "maxLoss": {"price": t.worst_price, "percent": round(away(t.worst_price), 2), "roiPercent": round(away(t.worst_price) * t.leverage, 1)},
        "score": t.plan["score"], "triggerFrame": t.plan["trigger_frame"], "trigger": t.plan["trigger"], "categories": t.plan["categories"], "confirmations": t.plan["confirmations"],
        "evidence": t.plan["evidence"], "source": "FORWARD",
    }


def account_out(db: Session) -> dict:
    """The paper account now: realised balance, open result, how many trades were won and lost."""
    a = db.get(VirtualAccount, ACCOUNT)
    start, balance, iq = (a.start_balance, a.balance, a.iq_score) if a else (ACCOUNT_START, ACCOUNT_START, ACCOUNT_IQ)
    opened = open_trades(db)
    closed = list(db.scalars(select(VirtualTrade).where(VirtualTrade.closed_at.is_not(None))))
    floating = sum(record(t, [])["openPnlUsd"] for t in opened)
    return {"iqScore": iq, "startBalance": start, "balance": round(balance, 2), "openPnlUsd": round(floating, 2), "equity": round(balance + floating, 2),
            "percent": round(100 * ((balance + floating) / start - 1), 2), "openTrades": len(opened), "marginInUse": round(sum(t.margin_usd * t.units_left / 100 for t in opened), 2),
            "won": sum(t.pnl_usd > 0 for t in closed), "lost": sum(t.pnl_usd <= 0 for t in closed), "closedTrades": len(closed),
            "missed": len(list(db.scalars(select(VirtualMissedTrade.id))))}


def performance(trades: list[VirtualTrade]) -> dict:
    """Closed trades only, oldest first."""
    done = sorted((t for t in trades if t.result_r is not None), key=lambda t: utc(t.closed_at))
    total, peak, worst, streak, longest, best_streak, longest_best = 0.0, 0.0, 0.0, 0, 0, 0, 0
    for t in done:
        total += t.result_r
        peak = max(peak, total)
        worst = max(worst, peak - total)
        streak, best_streak = (streak + 1, 0) if t.result_r <= 0 else (0, best_streak + 1)
        longest, longest_best = max(longest, streak), max(longest_best, best_streak)
    n = len(done)
    win, loss = [t for t in done if t.result_r > 0], [t for t in done if t.result_r <= 0]
    mean = lambda v: round(sum(v) / len(v), 3) if v else None
    lost_usd = -sum(t.pnl_usd for t in loss)
    return {"n": n, "won": len(win), "lost": len(loss), "winRate": round(len(win) / n, 3) if n else None, "averageR": mean([t.result_r for t in done]),
            "averageWinR": mean([t.result_r for t in win]), "averageLossR": mean([t.result_r for t in loss]), "totalUsd": round(sum(t.pnl_usd for t in done), 2),
            "profitFactor": round(sum(t.pnl_usd for t in win) / lost_usd, 2) if lost_usd > 0 else None,
            "best": max((t.result_r for t in done), default=None), "worst": min((t.result_r for t in done), default=None),
            "maxDrawdownR": round(worst, 2) if n else None, "longestLosingStreak": longest if n else None, "longestWinningStreak": longest_best if n else None,
            "averageHours": mean([(utc(t.closed_at) - utc(t.opened_at)).total_seconds() / 3600 for t in done]),
            "byKind": _groups(done, lambda t: [t.kind]), "byDirection": _groups(done, lambda t: [t.direction]), "byExit": _groups(done, lambda t: [t.exit_reason]),
            "byCategory": _groups(done, lambda t: list(t.plan["categories"])), "byRule": _groups(done, lambda t: sorted({c["rule"] for c in t.plan["categories"].values()}))}


def _groups(trades: list[VirtualTrade], keys) -> dict[str, dict]:
    """Won / lost and the average result per key: which kind, exit or confirmation went wrong."""
    groups: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        for k in keys(t):
            groups[k].append(t.result_r)
    return {k: {"n": len(v), "won": sum(x > 0 for x in v), "lost": sum(x <= 0 for x in v), "averageR": round(sum(v) / len(v), 3)} for k, v in sorted(groups.items(), key=lambda g: -len(g[1]))}
