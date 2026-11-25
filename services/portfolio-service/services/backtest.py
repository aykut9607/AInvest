"""The stored one-year rehearsal of 4.4 (signals/live/year.json, written by `python -m signals.live.replay year`) in the shape of the live ledger."""

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from services.market import tsi

FILE = Path(__file__).resolve().parents[1] / "signals" / "live" / "year.json"


@lru_cache
def load() -> dict | None:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else None


def _at(seconds: int) -> str | None:
    return tsi(datetime.fromtimestamp(seconds, timezone.utc))


def record(r: dict, n: int, names: list[str], asset_names: dict[str, str]) -> dict:
    """One rehearsed trade with the field names of market.record."""
    taken = [f for f in r["fills"] if f["zone"] not in ("STOP", "ENTRY_STOP")]
    stopped = next((f for f in r["fills"] if f["zone"] in ("STOP", "ENTRY_STOP")), None)
    end = r["fills"][-1]["time"] if r["fills"] else r["time"]
    fill = lambda f: {"zone": f["zone"], "price": f["price"], "units": f["units"], "atTsi": _at(f["time"]), "pnlUsd": f["pnlUsd"]}
    return {"id": f"year-{n}", "asset": asset_names.get(r["asset"], r["asset"]), "direction": r["direction"], "kind": r["kind"], "status": r["status"], "openedAtTsi": _at(r["time"]),
            "closedAtTsi": _at(end) if r["status"] == "CLOSED" else None, "durationHours": round((end - r["time"]) / 3600, 1), "entry": r["entry"], "leverage": r["leverage"], "stop": r["stop"],
            "stopPercent": r["stopPercent"], "stopNow": r["stop"], "steps": r["steps"], "unitsLeft": r["unitsLeft"], "marginUsd": r["marginUsd"], "notionalUsd": r["notionalUsd"], "balanceBefore": r["balanceBefore"],
            "balanceAfter": r["balanceAfter"], "takeProfits": [fill(f) for f in taken], "stopped": fill(stopped) if stopped else None, "exitReason": r["exit"], "pnlUsd": r["pnlUsd"], "roiPercent": r["roiPercent"],
            "resultR": r["resultR"], "openPnlUsd": 0.0, "maxProfit": {"percent": r["maxProfitPercent"], "roiPercent": r["maxProfitRoi"]}, "maxLoss": {"percent": r["maxLossPercent"]}, "score": r["score"],
            "triggerFrame": r["frame"], "trigger": [], "categories": r["categories"], "confirmations": {f: [names[i] for i in v] for f, v in r["confirmations"].items()}, "evidence": {"proven": False}, "source": "REHEARSAL"}
