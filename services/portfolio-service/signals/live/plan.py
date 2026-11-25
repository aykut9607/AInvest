"""From a score to a conditional plan: direction, entry, stop, kind of trade, leverage and how much cash. Virtual trades only, no order is ever sent.

Sizes follow the rules already agreed: risk per trade 1 % of the account (RK-01, the strictest of the conflicting rules), reward at least
1.5 x the risk (RK-03), cash per trade 1-10 % by the Financial IQ (Aykut). Leverage is what makes those three fit together, never more than CAP.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import floor

RISK_PER_TRADE = 1.0          # % of the account lost if the stop is hit
LEVERAGE_CAP = 10
STOP_TO_LIQUIDATION = 0.5     # the stop must be hit before half of the margin is gone
MIN_REWARD = 1.5
FEE_PERCENT = 0.1             # of the position, opening and closing together
HORIZON = 480                 # 15m bars (5 days) after which a trade ends by itself
MIN_STOP = 0.15               # %: a closer stop is inside the spread and the fee
KINDS = ("SCALP", "SCALP_SWING", "SWING")


@dataclass(frozen=True)
class Size:
    margin_percent: float          # of the account's cash
    leverage: int
    risk_percent: float            # of the account, if the stop is hit


def margin_percent(iq_score: int) -> float:
    """1 % at IQ 0 ... 10 % at IQ 100."""
    return round(1 + 9 * max(0, min(100, iq_score)) / 100, 1)


def size(iq_score: int, stop_percent: float) -> Size:
    if stop_percent <= 0:
        raise ValueError("The stop must be away from the entry.")
    margin = margin_percent(iq_score)
    by_risk = RISK_PER_TRADE / (margin / 100 * stop_percent)
    by_liquidation = 100 * STOP_TO_LIQUIDATION / stop_percent
    leverage = max(1, min(LEVERAGE_CAP, floor(by_risk + 1e-9), floor(by_liquidation + 1e-9)))
    return Size(margin, leverage, round(margin * leverage * stop_percent / 100, 2))


def kind_of(score: float, limits: dict[str, float]) -> str | None:
    """The kind of trade a score allows, or None. `limits`: {kind: lowest score}; a kind without a limit does not exist for the asset."""
    allowed = [k for k in KINDS if k in limits and score >= limits[k]]
    return allowed[-1] if allowed else None


@dataclass(frozen=True)
class Plan:
    asset: str
    direction: str                 # LONG / SHORT
    kind: str
    time: float
    score: float
    entry: float
    stop: float
    stop_percent: float
    first_target: float            # 1.5 x the risk; the trend fib targets come later
    trigger_frame: str
    categories: dict[str, dict]    # category -> {frame, rule, points}
    evidence: dict                 # how this score did in the past

    def as_dict(self) -> dict:
        return asdict(self)


def make(asset: str, side: int, kind: str, time: float, score: float, entry: float, stop: float, frame: str, categories: dict, evidence: dict) -> Plan:
    distance = abs(stop - entry)
    if (stop - entry) * side >= 0:
        raise ValueError("The stop is on the wrong side.")
    return Plan(asset, "SHORT" if side == -1 else "LONG", kind, time, round(score, 1), entry, round(stop, 2), round(100 * distance / entry, 3),
                round(entry + side * MIN_REWARD * distance, 2), frame, categories, evidence)
