"""4.4 for the screen. /api/portfolio/market/... is the same for everyone (gateway: any valid token); the sizes of /api/portfolio/{userId}/market-plan
depend on the user's own score."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from adapters.upstream import MissingData, UpstreamError
from api.deps import current_user_id
from api.routers.portfolio import Data, Db, Owner, failure
from db.models import MarketScan, VirtualTrade
from schemas.envelope import Envelope
from services import market
from signals.live import plan as planning
from signals.live.score import tables

router = APIRouter(prefix="/api/portfolio", tags=["market"])

DISCLAIMER = "Sanal işlem; gerçek emir gönderilmez. Yatırım tavsiyesi değildir."
NAMES = {"BTCUSDT": "BTC", "XAU": "GOLD", "SPX": "SPX"}
Caller = Annotated[str, Depends(current_user_id)]


def trade_out(t: VirtualTrade) -> dict:
    return {"id": t.id, "asset": NAMES.get(t.asset, t.asset), "direction": t.direction, "kind": t.kind, "source": "FORWARD", "openedAt": market.utc(t.opened_at).isoformat(),
            "entry": t.entry, "stop": t.stop, "target": t.target, "score": t.plan["score"], "triggerFrame": t.plan["trigger_frame"], "categories": t.plan["categories"],
            "evidence": t.plan["evidence"], "closedAt": market.utc(t.closed_at).isoformat() if t.closed_at else None, "exit": t.exit_price, "exitReason": t.exit_reason, "resultR": t.result_r}


@router.get("/market/view", response_model=Envelope[dict])
def view(caller: Caller, db: Db):
    """Per asset: the newest scan, the open virtual trade, the limits and what the score was worth in the past."""
    items = []
    for asset, table in tables().items():
        scan = db.get(MarketScan, asset)
        opened = [trade_out(t) for t in market.open_trades(db, asset)]
        items.append({"asset": NAMES.get(asset, asset), "status": "CONFIRMED" if opened else "NO_VIEW", "scan": scan.payload if scan else None,
                      "scannedAt": market.utc(scan.scanned_at).isoformat() if scan else None, "openTrades": opened, "weights": table["weights"], "limits": table["limits"],
                      "evidence": table["evidence"], "base": table["base"]})
    return Envelope[dict].ok({"items": items, "disclaimer": DISCLAIMER}, "Market view loaded.")


@router.get("/market/trades", response_model=Envelope[dict])
def trades(caller: Caller, db: Db, asset: str | None = None, limit: int = 100):
    query = select(VirtualTrade).order_by(VirtualTrade.opened_at.desc()).limit(max(1, min(500, limit)))
    if asset:
        query = query.where(VirtualTrade.asset == next((k for k, v in NAMES.items() if v == asset), asset))
    return Envelope[dict].ok({"items": [trade_out(t) for t in db.scalars(query)], "disclaimer": DISCLAIMER}, "Trades loaded.")


@router.get("/market/performance", response_model=Envelope[dict])
def performance(caller: Caller, db: Db):
    return Envelope[dict].ok({"source": "FORWARD", **market.performance(list(db.scalars(select(VirtualTrade))))}, "Performance loaded.")


@router.get("/{user_id}/market-plan", response_model=Envelope[dict])
def market_plan(user_id: Owner, upstream: Data, db: Db):
    """The open virtual trades with this user's size: 1-10 % of the cash by the score, leverage so that a stop costs at most 1 % of the account."""
    try:
        iq = upstream.iq(user_id)
    except (MissingData, UpstreamError) as error:
        return failure(error)
    items = []
    for asset in tables():
        for t in market.open_trades(db, asset):
            s = planning.size(iq.score, t.plan["stop_percent"])
            items.append(trade_out(t) | {"size": {"marginPercent": s.margin_percent, "leverage": s.leverage, "riskPercent": s.risk_percent}})
    return Envelope[dict].ok({"iqScore": iq.score, "items": items, "disclaimer": DISCLAIMER}, "Plan loaded.")
