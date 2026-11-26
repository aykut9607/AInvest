"""4.1-4.3: how much may be invested and in what. Pure functions, no database, no HTTP, no LLM: the same input always gives the same output."""

from dataclasses import dataclass, field

from services.baskets import (
    ASSETS,
    FOCUS_SHARE,
    INSTITUTION_BASKETS,
    INSTITUTION_SOURCES,
    MEASURED_VOLATILITY,
    RISK_LEVELS,
    RISKY_ASSETS,
    RISKY_SHARE,
    SAFE_ASSETS,
)

FULL_SCORE_RULES = ("VERY_HIGH_INCOME", "VERY_HIGH_WEALTH")
FLOORS = ("WEALTH_FLOOR", "INCOME_FLOOR")          # IQ v2.1: the score was raised by the wealth or the income itself
RESERVE_MONTHS = 3
INVESTMENT_IN_RESERVE = 0.5


class AllocationError(ValueError):
    """The choice itself is not possible (HTTP 400)."""


@dataclass(frozen=True)
class Profile:
    monthly_income: float
    monthly_expenses: float
    monthly_debt_payment: float
    total_debt: float
    cash_reserve: float
    investment_amount: float
    impatience_level: int = 3          # 1 patient ... 5 very impatient (the user's own answer)


@dataclass(frozen=True)
class Investable:
    share_percent: float
    monthly_amount: float
    one_time_amount: float
    reasons: tuple[str, ...]


@dataclass
class Basket:
    weights: dict[str, float]
    reasons: list[str] = field(default_factory=list)
    source: dict | None = None


def basis(p: Profile) -> dict[str, float]:
    """The inputs of investable(), for the screen: where the two amounts come from."""
    fund = RESERVE_MONTHS * p.monthly_expenses
    return {"monthly_income": p.monthly_income, "monthly_expenses": p.monthly_expenses, "monthly_debt_payment": p.monthly_debt_payment,
            "monthly_surplus": p.monthly_income - p.monthly_expenses - p.monthly_debt_payment, "cash_reserve": p.cash_reserve,
            "investment_amount": p.investment_amount, "reserve": p.cash_reserve + p.investment_amount * INVESTMENT_IN_RESERVE,
            "emergency_fund": fund, "free_cash": max(0.0, p.cash_reserve - fund), "reserve_months": RESERVE_MONTHS}


def investable(iq_score: int, applied_rule: str | None, p: Profile, adjustment: str | None = None) -> Investable:
    """share = clamp(IQ - 30, 0, 70) %, on the monthly surplus and on the cash above a 3-month fund; 0 while that fund is missing."""
    share = float(min(70, max(0, iq_score - 30)))
    reasons = []
    emergency_fund = RESERVE_MONTHS * p.monthly_expenses
    reserve = p.cash_reserve + p.investment_amount * INVESTMENT_IN_RESERVE          # the score counts the reserve the same way
    if reserve < emergency_fund and applied_rule not in FULL_SCORE_RULES and adjustment not in FLOORS:
        share = 0.0
        reasons.append("RESERVE_FIRST")
    surplus = max(0.0, p.monthly_income - p.monthly_expenses - p.monthly_debt_payment)
    if surplus == 0:
        reasons.append("NO_MONTHLY_SURPLUS")
    if p.total_debt > p.cash_reserve + p.investment_amount:          # a warning, never a lock (22 Nov: no silly limits)
        reasons.append("DEBT_FIRST")
    return Investable(share, round(surplus * share / 100, 2), round(max(0.0, p.cash_reserve - emergency_fund) * share / 100, 2), tuple(reasons))


# Gates of the risk ceiling (advisor, 22 Oct: the risk level is not asked, it is read from the data, crossing them). The IQ is a sum: a strong
# saving rate can hide a missing emergency fund. So the ceiling is the IQ segment, lowered by the weakest link. Every limit is one the IQ
# itself already uses (ScoringRules): 3 months of reserve, installment 36 % of income, net debt 3 years of income.
INSTALLMENT_LIMIT = 0.36
NET_DEBT_YEARS = 3
IMPATIENT = 4


def risk_ceiling(segment: str, applied_rule: str | None, p: Profile, adjustment: str | None = None) -> tuple[str, tuple[str, ...]]:
    """(the highest risk level the user may choose, why it is lower than the segment)."""
    level, reasons = RISK_LEVELS.index(segment), []

    def lower_to(top: str, reason: str) -> None:
        nonlocal level
        if level > RISK_LEVELS.index(top):
            level = RISK_LEVELS.index(top)
            reasons.append(reason)

    # 1,000,000 a month, 10,000,000 net worth, or (v2.1) a score raised by the wealth or income itself: the IQ already says the reserve
    # and the monthly surplus are not the problem (a retiree living from 6,000,000 has no salary, but no risk from it either)
    full = applied_rule in FULL_SCORE_RULES or adjustment in FLOORS
    reserve = p.cash_reserve + p.investment_amount * INVESTMENT_IN_RESERVE
    if not full and reserve < RESERVE_MONTHS * p.monthly_expenses:
        lower_to("LOW", "CEILING_RESERVE")
    if not full and p.monthly_income - p.monthly_expenses - p.monthly_debt_payment <= 0:
        lower_to("LOW", "CEILING_NO_SURPLUS")
    yearly = 12 * p.monthly_income
    net_debt = p.total_debt - p.cash_reserve - p.investment_amount
    if (p.monthly_income > 0 and p.monthly_debt_payment / p.monthly_income > INSTALLMENT_LIMIT) or (net_debt > 0 and net_debt > NET_DEBT_YEARS * yearly):
        lower_to("MEDIUM", "CEILING_DEBT")
    if p.impatience_level >= IMPATIENT and level > 0:
        level -= 1
        reasons.append("CEILING_IMPATIENCE")
    return RISK_LEVELS[level], tuple(reasons)


def check_risk(chosen: str, ceiling: str) -> None:
    if chosen not in RISK_LEVELS:
        raise AllocationError(f"Unknown risk level: {chosen}.")
    if RISK_LEVELS.index(chosen) > RISK_LEVELS.index(ceiling):
        raise AllocationError(f"Risk level {chosen} is above the allowed maximum ({ceiling}).")


def institution(style: str | None, risk: str) -> Basket:
    """4.1: the allocation the institution published for this risk level."""
    if style not in INSTITUTION_BASKETS:
        raise AllocationError("institutionStyle is required for INSTITUTION.")
    source = INSTITUTION_SOURCES[style]
    url = source.get("urls", {}).get(risk, source["url"])          # Ziraat: one fund, one page per risk level
    return Basket(dict(INSTITUTION_BASKETS[style][risk]), [f"PUBLISHED_ALLOCATION:{style}:{source['period']}"],
                  {"name": source["name"], "period": source["period"], "url": url})


def standard(risk: str, excluded: tuple[str, ...] = ()) -> Basket:
    """4.3: safe part in equal parts, risky part by inverse volatility; an excluded asset's share stays inside its own part."""
    _check_assets(excluded)
    safe = [a for a in SAFE_ASSETS if a not in excluded]
    risky = {a: 1 / v for a, v in MEASURED_VOLATILITY.items() if a not in excluded}
    if not safe:
        raise AllocationError("At least one safe asset must stay in the basket.")
    risky_share = RISKY_SHARE[risk] if risky else 0
    reasons = []
    for a in excluded:
        if a in SAFE_ASSETS:
            reasons += [f"EXCLUDED_ASSET_REPLACED:{a}->{b}" for b in safe]
        elif a in MEASURED_VOLATILITY:
            reasons += [f"EXCLUDED_ASSET_REPLACED:{a}->{b}" for b in risky or safe]
    weights = {a: (100 - risky_share) / len(safe) for a in safe}
    weights |= {a: risky_share * w / sum(risky.values()) for a, w in risky.items()}
    return Basket(weights, reasons)


def custom(risk: str, focus: tuple[str, ...], excluded: tuple[str, ...] = ()) -> Basket:
    """4.2: the chosen assets take the largest part, the rest is the standard basket; risky assets never exceed the level's share."""
    _check_assets(focus)
    if not focus:
        raise AllocationError("focusAssets is required for CUSTOM.")
    if set(focus) & set(excluded):
        raise AllocationError("An asset cannot be both chosen and excluded.")
    rest = standard(risk, tuple(dict.fromkeys(excluded)))
    others = {a: w for a, w in rest.weights.items() if a not in focus}
    focus_share = FOCUS_SHARE if others else 100
    weights = {a: focus_share / len(focus) for a in focus}
    weights |= {a: (100 - focus_share) * w / sum(others.values()) for a, w in others.items()}
    reasons = [*(f"FOCUS:{a}" for a in focus), *rest.reasons]

    risky_total = sum(w for a, w in weights.items() if a in RISKY_ASSETS)
    ceiling = RISKY_SHARE[risk]
    if risky_total > ceiling + 1e-9:
        safe = {a: w for a, w in weights.items() if a in SAFE_ASSETS} or {a: 1.0 for a in SAFE_ASSETS if a not in excluded}
        chosen = {a: w for a, w in weights.items() if a in RISKY_ASSETS and a in focus}          # the chosen assets fill the ceiling first
        rest_risky = {a: w for a, w in weights.items() if a in RISKY_ASSETS and a not in focus}
        own = min(sum(chosen.values()), ceiling)
        weights = {a: own * w / sum(chosen.values()) for a, w in chosen.items()}
        if ceiling - own > 1e-9:
            weights |= {a: (ceiling - own) * w / sum(rest_risky.values()) for a, w in rest_risky.items()}
        weights |= {a: (100 - ceiling) * w / sum(safe.values()) for a, w in safe.items()}
        reasons.append("RISK_CEILING_REACHED")
    return Basket(weights, reasons)


def _split(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Whole units in proportion to the weights, adding up to exactly `total` (largest remainder)."""
    full = sum(weights.values())
    exact = {a: total * w / full for a, w in weights.items()}
    out = {a: int(v + 1e-9) for a, v in exact.items()}
    for a in sorted(exact, key=lambda a: exact[a] - out[a], reverse=True)[: total - sum(out.values())]:
        out[a] += 1
    return out


def percentages(weights: dict[str, float]) -> dict[str, float]:
    """Two decimals, exactly 100 in total, biggest first."""
    parts = _split(10000, {a: w for a, w in weights.items() if w > 0})
    return {a: c / 100 for a, c in sorted(parts.items(), key=lambda x: (-x[1], x[0]))}


def amounts(weights: dict[str, float], total: float) -> dict[str, float]:
    """`total` split in kurus, the parts add up to it exactly."""
    return {a: c / 100 for a, c in _split(round(total * 100), weights).items()}


def _check_assets(names: tuple[str, ...]) -> None:
    unknown = [a for a in names if a not in ASSETS]
    if unknown:
        raise AllocationError(f"Unknown asset: {', '.join(unknown)}.")
