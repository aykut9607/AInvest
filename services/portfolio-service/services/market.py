"""4.4 on paper: stores the newest scan, opens and closes virtual trades. Nothing here talks to an exchange."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import MarketScan, VirtualTrade
from signals.data.candles import Candle
from signals.live.plan import FEE_PERCENT, HORIZON, Plan

BAR = timedelta(minutes=15)


def utc(value: datetime) -> datetime:
    """SQLite gives naive times back; all times are UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def save_scan(db: Session, asset: str, scanned_at: datetime, payload: dict) -> None:
    db.merge(MarketScan(asset=asset, scanned_at=scanned_at, payload=payload))


def open_trades(db: Session, asset: str) -> list[VirtualTrade]:
    return list(db.scalars(select(VirtualTrade).where(VirtualTrade.asset == asset, VirtualTrade.closed_at.is_(None))))


def open_trade(db: Session, plan: Plan) -> VirtualTrade | None:
    """One open trade per asset and direction; a second signal in the same direction is the same idea."""
    if any(t.direction == plan.direction for t in open_trades(db, plan.asset)):
        return None
    trade = VirtualTrade(id=str(uuid.uuid4()), asset=plan.asset, direction=plan.direction, kind=plan.kind, opened_at=datetime.fromtimestamp(plan.time, timezone.utc),
                         entry=plan.entry, stop=plan.stop, target=plan.first_target, plan=plan.as_dict())
    db.add(trade)
    return trade


def follow(db: Session, asset: str, candles: list[Candle]) -> list[VirtualTrade]:
    """Close what the 15m candles closed. Inside one candle the stop counts first; a trade ends after HORIZON bars."""
    closed = []
    for t in open_trades(db, asset):
        side = 1 if t.direction == "LONG" else -1
        opened = utc(t.opened_at)
        last = opened + HORIZON * BAR
        for c in candles:
            if c.time < opened:
                continue
            end = c.time + BAR
            if side * (c.low if side == 1 else c.high) <= side * t.stop:
                _close(t, end, t.stop, "STOP")
            elif side * (c.high if side == 1 else c.low) >= side * t.target:
                _close(t, end, t.target, "TARGET")
            elif end >= last:
                _close(t, end, c.close, "EXPIRED")
            else:
                continue
            closed.append(t)
            break
    return closed


def _close(t: VirtualTrade, when: datetime, price: float, reason: str) -> None:
    side, risk = (1 if t.direction == "LONG" else -1), abs(t.entry - t.stop)
    t.closed_at, t.exit_price, t.exit_reason = when, price, reason
    t.result_r = round(side * (price - t.entry) / risk - FEE_PERCENT / 100 * t.entry / risk, 3)


def performance(trades: list[VirtualTrade]) -> dict:
    """Closed trades only, oldest first."""
    done = sorted((t for t in trades if t.result_r is not None), key=lambda t: utc(t.closed_at))
    total, peak, worst, streak, longest = 0.0, 0.0, 0.0, 0, 0
    for t in done:
        total += t.result_r
        peak = max(peak, total)
        worst = max(worst, peak - total)
        streak = streak + 1 if t.result_r < 0 else 0
        longest = max(longest, streak)
    n = len(done)
    return {"n": n, "winRate": round(sum(t.result_r > 0 for t in done) / n, 3) if n else None, "averageR": round(total / n, 3) if n else None,
            "maxDrawdownR": round(worst, 2) if n else None, "longestLosingStreak": longest if n else None}
