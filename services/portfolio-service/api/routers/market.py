"""4.4 for the screen. /api/portfolio/market/... is the same for everyone (gateway: any valid token); the sizes of /api/portfolio/{userId}/market-plan
depend on the user's own score."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from adapters.upstream import MissingData, UpstreamError
from api.deps import current_user_id
from api.routers.portfolio import Data, Db, Owner, failure
from db.models import MarketScan, VirtualMissedTrade, VirtualTrade
from schemas.envelope import Envelope
from services import backtest, market, trade_story
from signals.live import plan as planning
from signals.live.score import tables

router = APIRouter(prefix="/api/portfolio", tags=["market"])

DISCLAIMER = "Sanal işlem; gerçek emir gönderilmez. Yatırım tavsiyesi değildir."
NAMES = {"BTCUSDT": "BTC", "XAU": "GOLD", "SPX": "SPX"}
Caller = Annotated[str, Depends(current_user_id)]


def trade_out(db, t: VirtualTrade, full: bool = False) -> dict:
    """One ledger row; the long lists (every confirmation, every event) only in the detail."""
    events = market.events_of(db, t.id)
    out = {"asset": NAMES.get(t.asset, t.asset), **market.record(t, events)}
    if full:
        return out | {"events": [{"at": market.utc(e.at).isoformat(), "atTsi": market.tsi(e.at), "kind": e.kind, "name": trade_story.zone(e.kind), "price": e.price, "units": e.units, "unitsLeft": e.units_left,
                                  "pnlUsd": round(e.pnl_usd, 2), "balanceAfter": round(e.balance_after, 2)} for e in events]}
    return {k: v for k, v in out.items() if k != "confirmations"}


@router.get("/market/view", response_model=Envelope[dict])
def view(caller: Caller, db: Db):
    """Per asset: the newest scan, the open virtual trades, the limits and what the score was worth in the past."""
    items = []
    for asset, table in tables().items():
        scan = db.get(MarketScan, asset)
        opened = [trade_out(db, t) for t in market.open_trades(db, asset)]
        items.append({"asset": NAMES.get(asset, asset), "status": "CONFIRMED" if opened else "NO_VIEW", "scan": scan.payload if scan else None,
                      "scannedAt": market.utc(scan.scanned_at).isoformat() if scan else None, "openTrades": opened, "weights": table["weights"], "limits": table["limits"],
                      "evidence": table["evidence"], "base": table["base"]})
    return Envelope[dict].ok({"items": items, "disclaimer": DISCLAIMER}, "Market view loaded.")


@router.get("/market/trades", response_model=Envelope[dict])
def trades(caller: Caller, db: Db, asset: str | None = None, status: str | None = None, limit: int = 100):
    """The ledger, newest first. status = OPEN (also partly closed) or CLOSED."""
    query = select(VirtualTrade).order_by(VirtualTrade.opened_at.desc()).limit(max(1, min(500, limit)))
    if asset:
        query = query.where(VirtualTrade.asset == next((k for k, v in NAMES.items() if v == asset), asset))
    if status in ("OPEN", "CLOSED"):
        query = query.where(VirtualTrade.closed_at.is_(None) if status == "OPEN" else VirtualTrade.closed_at.is_not(None))
    return Envelope[dict].ok({"items": [trade_out(db, t) for t in db.scalars(query)], "disclaimer": DISCLAIMER}, "Trades loaded.")


@router.get("/market/trades/{trade_id}", response_model=Envelope[dict])
def trade(trade_id: str, caller: Caller, db: Db):
    """One trade with every event and confirmation, and its story for a trader and for everyone (the AI service may rephrase it, not compute)."""
    t = db.get(VirtualTrade, trade_id)
    if t is None:
        raise HTTPException(status_code=404, detail="No such virtual trade.")
    out = trade_out(db, t, full=True)
    story = {"facts": trade_story.facts(out), "trader": trade_story.trader(out), "standard": trade_story.standard(out)}
    return Envelope[dict].ok(out | {"analysis": story, "disclaimer": DISCLAIMER}, "Trade loaded.")


@router.get("/market/missed", response_model=Envelope[dict])
def missed(caller: Caller, db: Db, asset: str | None = None, limit: int = 100):
    """Conditions that were met while the engine was off: no trade, no money, only a note and what would have happened."""
    query = select(VirtualMissedTrade).order_by(VirtualMissedTrade.at.desc()).limit(max(1, min(500, limit)))
    if asset:
        query = query.where(VirtualMissedTrade.asset == next((k for k, v in NAMES.items() if v == asset), asset))
    return Envelope[dict].ok({"items": [{"asset": NAMES.get(m.asset, m.asset), **market.missed_out(m)} for m in db.scalars(query)], "disclaimer": DISCLAIMER}, "Missed trades loaded.")


@router.get("/market/account", response_model=Envelope[dict])
def account(caller: Caller, db: Db):
    return Envelope[dict].ok(market.account_out(db) | {"disclaimer": DISCLAIMER}, "Account loaded.")


@router.get("/market/performance", response_model=Envelope[dict])
def performance(caller: Caller, db: Db):
    return Envelope[dict].ok({"source": "FORWARD", "account": market.account_out(db), **market.performance(list(db.scalars(select(VirtualTrade))))}, "Performance loaded.")


@router.get("/market/backtest", response_model=Envelope[dict])
def rehearsal(caller: Caller):
    """The last year played again with the same rules: every asset alone, all three from one account, and the trades of that common account."""
    d = backtest.load()
    if d is None:
        raise HTTPException(status_code=404, detail="No stored backtest yet.")
    rows = [backtest.record(r, n, d["names"], NAMES) for n, r in enumerate(d["trades"])]
    done = sorted((r for r in d["trades"] if r["status"] == "CLOSED"), key=lambda r: r["fills"][-1]["time"])
    named = lambda part: {NAMES.get(k, k): v for k, v in d[part].items()}
    return Envelope[dict].ok({"from": d["from"], "to": {NAMES.get(k, k): v for k, v in d["to"].items()}, "real": named("real"), "control": named("shuffled"),
                              "curve": [{"time": r["fills"][-1]["time"], "balance": r["balanceAfter"]} for r in done],
                              "trades": [{k: v for k, v in r.items() if k != "confirmations"} for r in reversed(rows)], "disclaimer": DISCLAIMER}, "Backtest loaded.")


@router.get("/market/backtest/{trade_id}", response_model=Envelope[dict])
def rehearsed_trade(trade_id: str, caller: Caller):
    d, number = backtest.load(), trade_id.removeprefix("year-")
    if d is None or not number.isdigit() or int(number) >= len(d["trades"]):
        raise HTTPException(status_code=404, detail="No such rehearsed trade.")
    out = backtest.record(d["trades"][int(number)], int(number), d["names"], NAMES)
    story = {"facts": trade_story.facts(out), "trader": trade_story.trader(out), "standard": trade_story.standard(out)}
    return Envelope[dict].ok(out | {"events": [], "analysis": story, "disclaimer": DISCLAIMER}, "Trade loaded.")


@router.get("/{user_id}/market-plan", response_model=Envelope[dict])
def market_plan(user_id: Owner, upstream: Data, db: Db):
    """The open virtual trades with this user's own size."""
    try:
        iq = upstream.iq(user_id)
    except (MissingData, UpstreamError) as error:
        return failure(error)
    items = []
    for t in market.open_trades(db):
        s = planning.size(iq.score, t.plan["stop_percent"], t.kind)
        items.append(trade_out(db, t) | {"size": {"marginPercent": s.margin_percent, "leverage": s.leverage, "notionalPercent": s.notional_percent, "riskPercent": s.risk_percent}})
    return Envelope[dict].ok({"iqScore": iq.score, "items": items, "disclaimer": DISCLAIMER}, "Plan loaded.")
