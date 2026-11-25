"""From a score to a conditional plan: direction, entry, stop, targets, leverage and how much cash. Virtual trades only, no order is ever sent.

Size (Aykut, 25 November 2026): the Financial IQ gives 1-10 % of the cash at 10x, i.e. a position of 10-100 % of the account. The position also
never loses more than 1 % of the account at the stop (RK-01). The closer the stop, the higher the leverage (at most 25x, a swing at most 10x) and
the smaller the cash put in: 10 USD at 10x and 4 USD at 25x are the same position. Everything is a percentage of the CURRENT balance, so it compounds.

Exit: half of the position at +50 % on the cash put in and the stop goes to the entry; the rest leaves in steps of 10 % at the fib targets
(scalp: scalp fib, scalp with swing potential and swing: trend fib). A trade has no time limit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import floor

from signals.live import fibs

RISK_PER_TRADE = 1.0                                          # % of the account lost if the stop is hit
REFERENCE_LEVERAGE = 10                                       # the leverage the 1-10 % of cash is meant for
LEVERAGE_CAP = {"SCALP": 25, "SCALP_SWING": 25, "SWING": 10}
STOP_TO_LIQUIDATION = 0.75                                    # at the stop at most this part of the cash put in is gone (25x up to a stop of 3 %)
MIN_REWARD = 1.5                                              # the last target against the stop (RK-03)
FEE_PERCENT = 0.1                                             # of the position, opening and closing together
MIN_STOP = 0.15                                               # %: a closer stop is inside the spread and the fee
MIN_TARGET = 0.2                                              # %: a closer target only pays the fee
ENTRY_HALF = 0.5                                              # of the scalp fib: only its cheaper half is entered (long: the lower one)
HALF_PROFIT = 50.0                                            # % on the cash put in: half of the position is closed there
HALF_UNITS, STEP_UNITS = 50.0, 10.0                           # of 100 units
NEAR_HALF = 0.25                                              # the half is moved to the scalp TP when it is within a quarter of that distance
KINDS = ("SCALP", "SCALP_SWING", "SWING")


@dataclass(frozen=True)
class Size:
    margin_percent: float          # of the account's cash
    leverage: int
    notional_percent: float        # margin x leverage
    risk_percent: float            # of the account, if the stop is hit


def margin_percent(iq_score: int) -> float:
    """Cash at 10x: 1 % at IQ 0 ... 10 % at IQ 100."""
    return round(1 + 9 * max(0, min(100, iq_score)) / 100, 1)


def leverage_of(stop_percent: float, kind: str) -> int:
    return max(1, min(LEVERAGE_CAP[kind], floor(100 * STOP_TO_LIQUIDATION / stop_percent + 1e-9)))


def size(iq_score: int, stop_percent: float, kind: str = "SCALP") -> Size:
    if stop_percent <= 0:
        raise ValueError("The stop must be away from the entry.")
    notional = min(margin_percent(iq_score) * REFERENCE_LEVERAGE, 100 * RISK_PER_TRADE / stop_percent)
    leverage = leverage_of(stop_percent, kind)
    return Size(round(notional / leverage, 2), leverage, round(notional, 2), round(notional * stop_percent / 100, 2))


def kind_of(score: float, limits: dict[str, float]) -> str | None:
    """The kind of trade a score allows, or None. `limits`: {kind: lowest score}; a kind without a limit does not exist for the asset."""
    allowed = [k for k in KINDS if k in limits and score >= limits[k]]
    return allowed[-1] if allowed else None


@dataclass(frozen=True)
class Step:
    zone: str                      # HALF, SCALP_TP, TP1 ... MARKET_SELL, TREND_1.272 ...
    price: float
    units: float                   # of the 100 the trade starts with
    moves_stop: bool               # the stop goes to the entry after this one


def ladder(kind: str, side: int, entry: float, leverage: int, fib: fibs.Fib) -> list[Step]:
    """Where the position is closed, nearest first; the units add up to 100. Empty when no target is left."""
    away = lambda p: 100 * side * (p - entry) / entry
    scalp_tp = fib.scalp(dict(fibs.SCALP)["SCALP_TP"])
    targets = [(n, fib.scalp(r)) for n, r in fibs.SCALP] if kind == "SCALP" else [(n, fib.trend(r)) for n, r in fibs.TREND]
    targets = [(n, p) for n, p in targets if away(p) >= MIN_TARGET]
    if not targets:
        return []
    half = HALF_PROFIT / leverage          # % of price that is +50 % on the cash
    at, label = entry * (1 + side * half / 100), "HALF"
    if away(scalp_tp) >= MIN_TARGET and abs(away(scalp_tp) - half) <= NEAR_HALF * half:
        at, label = scalp_tp, "HALF_AT_SCALP_TP"
        targets = [t for t in targets if t[0] != "SCALP_TP"]
    elif half > away(targets[-1][1]):          # +50 % lies beyond the whole plan: the first fib target takes its place
        at, label = targets[0][1], f"HALF_AT_{targets[0][0]}"
        targets = targets[1:]
    steps = [Step(n, round(p, 2), STEP_UNITS, False) for n, p in targets] + [Step(label, round(at, 2), HALF_UNITS, True)]
    steps.sort(key=lambda s: side * s.price)
    last = steps[-1]
    return steps[:-1] + [Step(last.zone, last.price, 100 - sum(s.units for s in steps[:-1]), last.moves_stop)]


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
    leverage: int
    steps: list[dict]
    fib: dict
    trigger_frame: str
    trigger: list[str]
    categories: dict[str, dict]           # what the score counted: category -> {frame, rule, points}
    confirmations: dict[str, list]        # everything that was found: timeframe -> rules
    evidence: dict                        # how this score did in the past

    @property
    def final_target(self) -> float:
        return self.steps[-1]["price"]

    def as_dict(self) -> dict:
        return asdict(self)


def make(asset: str, side: int, kind: str, time: float, score: float, entry: float, atr_stop: float, fib: fibs.Fib, frame: str, categories: dict, evidence: dict,
         trigger: tuple[str, ...] = (), confirmations: dict | None = None) -> Plan | None:
    """None when the plan is not worth opening: entry in the dear half of the fib, no target left, or the last target pays less than 1.5 x the stop."""
    stop = side * min(side * atr_stop, side * fib.scalp(fibs.STOP))          # the farther one: room for a sweep of the low
    if (stop - entry) * side >= 0:
        raise ValueError("The stop is on the wrong side.")
    if side * (entry - fib.scalp(ENTRY_HALF)) > 0:
        return None
    stop_percent = round(100 * abs(stop - entry) / entry, 3)
    leverage = leverage_of(stop_percent, kind)
    steps = ladder(kind, side, entry, leverage, fib)
    if not steps or side * (steps[-1].price - entry) < MIN_REWARD * abs(stop - entry):
        return None
    return Plan(asset, "SHORT" if side == -1 else "LONG", kind, time, round(score, 1), entry, round(stop, 2), stop_percent, leverage, [asdict(s) for s in steps], fib.as_dict(),
                frame, list(trigger), categories, confirmations or {}, evidence)
