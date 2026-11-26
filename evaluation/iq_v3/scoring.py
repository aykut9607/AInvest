"""Financial IQ scoring v3 prototype (variants v3a and v3b), the reference for the C# port.

Every number is a decimal.Decimal so the arithmetic matches C# `decimal` (28 significant digits). Points are
rounded in two steps, first to 6 decimals and then to an integer, both half-up (C#: MidpointRounding.AwayFromZero;
every rounded value is >= 0). The first step absorbs the last-digit noise of a division, so a value that is exactly
x.5 on paper rounds up in Python and in C# alike.

Design (evaluation/IQ_V3_PROPOSAL.md has the reasoning and the porting spec):
  - every factor is a piecewise-linear "share" (0..1) of its maximum, read from an anchor table; the anchors sit on
    a fixed ladder: ideal benchmark -> 100 %, adequate -> 60 %, fragile -> 20 %, collapse -> 0 %
  - liquid assets = cash + 50 % of investments, used everywhere (reserve, debt offset, runway)
  - liquid assets first fill the emergency target (6 months of outflow); only the excess offsets the debt
  - debt service is at least the interest the uncovered debt accrues (3.5 % a month)
  - no TL thresholds: a continuous solvency cap scales every factor down from 5 to 15 years of income in net debt,
    and a wealth runway (liquid net worth in years of expenses, 25 years = the 4 % rule) can lift the cash-flow factors
  - a factor below 60 % of its maximum always carries a warning; the points of the factors add up to the score
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

D = Decimal
ZERO, ONE = D(0), D(1)

VERSION = "v3"

# --- constants -------------------------------------------------------------------------------------------------------
INVESTMENT_LIQUID_SHARE = D("0.5")    # Basel LCR level-2B haircut: half of the investments counts as liquid
EXPENSE_FLOOR_SHARE = D("0.10")       # expenses below 10 % of income are treated as 10 % in the savings rate (and flagged)
# data-quality floor (TL) for the reserve / runway denominator only. 26 Nov: the 10 % income floor used to sit there
# too, so a higher income raised the denominator and LOWERED the score when expenses < 10 % of income
EXPENSE_FLOOR_TL = D(2000)
RESERVE_TARGET_MONTHS = D(6)          # emergency target; liquid assets above it offset debt
DEFAULT_MONTHLY_INTEREST = D("0.035") # same assumption as DebtPayoffRules in the IQ service
WARNING_SHARE = D("0.6")              # a factor below 60 % of its maximum carries a warning
# the WEALTH_RUNWAY label needs at least this many years of expenses in liquid net worth (lambda >= 0.2); below it a
# few months of cash can still lift a factor by a rounded point, but "the wealth covers expenses for years" is false.
# Label only: the runway lift itself starts at 0 years, so the scores do not depend on this constant
WEALTH_RUNWAY_LABEL_MIN_YEARS = D(5)

# severe-warning lines (the v2 texts keep their v2 meaning and threshold)
SEVERE_INSTALLMENT_RATIO = D("0.36")  # "High debt burden"
SEVERE_NET_DEBT_YEARS = D(3)          # "High total debt"
SEVERE_SAVINGS_RATE = ZERO            # "Negative savings rate" (strictly below)
SEVERE_EXPENSE_RATIO = D("0.80")      # "Overspending relative to income"


def _table(*pairs: tuple[str, str]) -> tuple[tuple[Decimal, Decimal], ...]:
    return tuple((D(x), D(s)) for x, s in pairs)


# anchor tables: (measure value, share of the factor maximum), ascending by value. Below the first anchor the first
# share applies, above the last anchor the last share applies, in between linear interpolation.
RESERVE_MONTHS = _table(("0", "0"), ("3", "0.6"), ("6", "1"))
INSTALLMENT_RATIO = _table(("0.10", "1"), ("0.20", "0.6"), ("0.36", "0.2"), ("0.50", "0"))
NET_DEBT_YEARS = _table(("0.5", "1"), ("1", "0.6"), ("3", "0.2"), ("5", "0"))
SAVINGS_RATE = _table(("-0.10", "0"), ("0", "0.2"), ("0.10", "0.6"), ("0.20", "1"))
EXPENSE_RATIO = _table(("0.40", "1"), ("0.60", "0.6"), ("0.80", "0.2"), ("1.00", "0"))
IMPATIENCE = _table(("1", "1"), ("2", "0.8"), ("3", "0.6"), ("4", "0.2"), ("5", "0"))
SOLVENCY_CAP = _table(("5", "1"), ("15", "0"))
RUNWAY_YEARS = _table(("0", "0"), ("25", "1"))

# warning texts (stable identifiers; v2 texts reused where the meaning did not change)
W_LOW_RESERVE = "Low cash reserve"
W_HIGH_DEBT_BURDEN = "High debt burden"
W_ELEVATED_DEBT_BURDEN = "Elevated debt burden"
W_HIGH_TOTAL_DEBT = "High total debt"
W_ELEVATED_TOTAL_DEBT = "Elevated total debt"
W_NEGATIVE_SAVINGS = "Negative savings rate"
W_LOW_SAVINGS = "Low savings rate"
W_OVERSPENDING = "Overspending relative to income"
W_HIGH_EXPENSE_RATIO = "High expense ratio"
W_HIGH_IMPATIENCE = "High impatience"
W_EXTREME_DEBT = "Extreme total debt"
W_BELOW_INTEREST = "Installment below interest"
W_EXPENSES_TOO_LOW = "Expenses look too low"
W_INSTALLMENT_NO_DEBT = "Installment without debt"
W_INSTALLMENT_OVER_DEBT = "Installment exceeds total debt"

FACTOR_WARNINGS = [W_LOW_RESERVE, W_HIGH_DEBT_BURDEN, W_ELEVATED_DEBT_BURDEN, W_HIGH_TOTAL_DEBT, W_ELEVATED_TOTAL_DEBT,
                   W_NEGATIVE_SAVINGS, W_LOW_SAVINGS, W_OVERSPENDING, W_HIGH_EXPENSE_RATIO, W_HIGH_IMPATIENCE]
OTHER_WARNINGS = [W_EXTREME_DEBT, W_BELOW_INTEREST, W_EXPENSES_TOO_LOW, W_INSTALLMENT_NO_DEBT, W_INSTALLMENT_OVER_DEBT]
DATA_QUALITY_WARNINGS = [W_EXPENSES_TOO_LOW, W_INSTALLMENT_NO_DEBT, W_INSTALLMENT_OVER_DEBT]

RULE_SOLVENCY_CAP = "SOLVENCY_CAP"
RULE_WEALTH_RUNWAY = "WEALTH_RUNWAY"


@dataclass(frozen=True)
class Variant:
    name: str
    layout: str               # "a": 5 v2 factor names, "b": ExpenseRatio dropped, debt split in two
    maxima: dict[str, int]    # factor -> maximum points, in display order (sum 100)


VARIANTS: dict[str, Variant] = {
    "v3a": Variant("v3a", "a", {"CashReserveMonths": 25, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                                "ExpenseRatio": 15, "Impatience": 10}),
    "v3b": Variant("v3b", "b", {"CashReserveMonths": 25, "InstallmentToIncome": 20, "NetDebtToIncome": 20,
                                "SavingsRate": 25, "Impatience": 10}),
    # impatience weight 5 instead of 10; the 5 points go to the best-grounded factor (3-month reserve benchmark)
    "v3a-i5": Variant("v3a-i5", "a", {"CashReserveMonths": 30, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                                      "ExpenseRatio": 15, "Impatience": 5}),
    "v3b-i5": Variant("v3b-i5", "b", {"CashReserveMonths": 30, "InstallmentToIncome": 20, "NetDebtToIncome": 20,
                                      "SavingsRate": 25, "Impatience": 5}),
    # v3b layout with weights that follow the strength of the threshold evidence: the reserve (3-month benchmark)
    # and the savings rate (10 % / 20 %) get 30, the installment (10 % / 20 % / 36 %) 20, the net debt (no source for
    # 0.5 / 1 / 3 years; under the interest floor it rarely binds) 10
    "v3c": Variant("v3c", "b", {"CashReserveMonths": 30, "InstallmentToIncome": 20, "NetDebtToIncome": 10,
                                "SavingsRate": 30, "Impatience": 10}),
    "v3c-i5": Variant("v3c-i5", "b", {"CashReserveMonths": 30, "InstallmentToIncome": 25, "NetDebtToIncome": 10,
                                      "SavingsRate": 30, "Impatience": 5}),
}
for _v in VARIANTS.values():
    assert sum(_v.maxima.values()) == 100, _v.name


# --- helpers ---------------------------------------------------------------------------------------------------------
def dec(value) -> Decimal:
    """Exact decimal of an input (str() first, so 0.1 stays 0.1 and not the binary float)."""
    return value if isinstance(value, Decimal) else D(str(value))


def round_points(value: Decimal) -> int:
    """Two-step half-up rounding: 6 decimals, then integer. value is never negative."""
    six = value.quantize(D("0.000001"), rounding=ROUND_HALF_UP)
    return int(six.quantize(ONE, rounding=ROUND_HALF_UP))


def interpolate(x: Decimal, table) -> Decimal:
    """Share for measure x: clamp at both ends, linear in between: s0 + (x - x0) * (s1 - s0) / (x1 - x0)."""
    if x <= table[0][0]:
        return table[0][1]
    for (x0, s0), (x1, s1) in zip(table, table[1:]):
        if x <= x1:
            return s0 + (x - x0) * (s1 - s0) / (x1 - x0)
    return table[-1][1]


@dataclass(frozen=True)
class Measures:
    income: Decimal
    expenses: Decimal
    payment: Decimal
    debt: Decimal
    cash: Decimal
    investments: Decimal
    impatience: int
    liquid: Decimal            # L = cash + 0.5 * investments
    expenses_eff: Decimal      # max(expenses, 0.10 * income), savings rate only
    expenses_reserve: Decimal  # max(expenses, 2000 TL), reserve and runway
    outflow: Decimal           # expenses_reserve + payment
    reserve_months: Decimal    # L / outflow
    excess_liquid: Decimal     # max(0, L - 6 * outflow)
    net_debt: Decimal          # max(0, debt - excess_liquid)
    net_debt_years: Decimal    # net_debt / (12 * income)
    payment_eff: Decimal       # max(payment, 0.035 * net_debt)
    installment_ratio: Decimal # payment_eff / income
    savings_rate: Decimal      # (income - expenses_eff - payment_eff) / income
    expense_ratio: Decimal     # expenses_eff / income
    liquid_net_worth: Decimal  # L - debt
    runway_years: Decimal      # liquid_net_worth / (12 * expenses_reserve), 0 when liquid_net_worth <= 0
    runway_share: Decimal      # lambda
    solvency_cap: Decimal      # kappa


def measures(p: dict) -> Measures:
    income = dec(p["monthlyIncome"])
    if income <= 0:
        raise ValueError("monthly income must be greater than zero (same precondition as v2)")
    expenses, payment = dec(p["monthlyExpenses"]), dec(p["monthlyDebtPayment"])
    debt, cash, investments = dec(p.get("totalDebt", 0)), dec(p["cashReserve"]), dec(p.get("investmentAmount", 0))
    impatience = int(p.get("impatienceLevel", 3))

    liquid = cash + investments * INVESTMENT_LIQUID_SHARE
    expenses_eff = max(expenses, income * EXPENSE_FLOOR_SHARE)
    expenses_reserve = max(expenses, EXPENSE_FLOOR_TL)
    outflow = expenses_reserve + payment
    reserve_months = liquid / outflow
    excess_liquid = max(ZERO, liquid - outflow * RESERVE_TARGET_MONTHS)
    net_debt = max(ZERO, debt - excess_liquid)
    net_debt_years = net_debt / (income * 12)
    payment_eff = max(payment, net_debt * DEFAULT_MONTHLY_INTEREST)
    installment_ratio = payment_eff / income
    savings_rate = (income - expenses_eff - payment_eff) / income
    expense_ratio = expenses_eff / income
    liquid_net_worth = liquid - debt
    runway_years = liquid_net_worth / (expenses_reserve * 12) if liquid_net_worth > 0 else ZERO
    return Measures(income, expenses, payment, debt, cash, investments, impatience, liquid, expenses_eff, expenses_reserve, outflow,
                    reserve_months, excess_liquid, net_debt, net_debt_years, payment_eff, installment_ratio,
                    savings_rate, expense_ratio, liquid_net_worth, runway_years,
                    interpolate(runway_years, RUNWAY_YEARS), interpolate(net_debt_years, SOLVENCY_CAP))


def _shares(m: Measures, layout: str, lam: Decimal) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """(factor shares, sub-part shares used for warnings). lam lifts the three cash-flow measures."""
    own = {
        "reserve": interpolate(m.reserve_months, RESERVE_MONTHS),
        "installment": max(interpolate(m.installment_ratio, INSTALLMENT_RATIO), lam),
        "netDebt": interpolate(m.net_debt_years, NET_DEBT_YEARS),
        "savings": max(interpolate(m.savings_rate, SAVINGS_RATE), lam),
        "expense": max(interpolate(m.expense_ratio, EXPENSE_RATIO), lam),
        "impatience": interpolate(D(m.impatience), IMPATIENCE),
    }
    if layout == "a":
        factors = {"CashReserveMonths": own["reserve"], "DebtToIncomeRatio": min(own["installment"], own["netDebt"]),
                   "SavingsRate": own["savings"], "ExpenseRatio": own["expense"], "Impatience": own["impatience"]}
    else:
        factors = {"CashReserveMonths": own["reserve"], "InstallmentToIncome": own["installment"],
                   "NetDebtToIncome": own["netDebt"], "SavingsRate": own["savings"], "Impatience": own["impatience"]}
    return factors, own


def _points(factors: dict[str, Decimal], maxima: dict[str, int], kappa: Decimal) -> dict[str, int]:
    # raw = maximum * share, then * kappa, then rounded
    return {f: round_points(D(maxima[f]) * factors[f] * kappa) for f in maxima}


def _below(points: int, maximum: int) -> bool:
    return D(points) < D(maximum) * WARNING_SHARE


def segment(score: int) -> str:
    return "HIGH" if score >= 71 else "MEDIUM" if score >= 41 else "LOW"


def score(p: dict, variant: str = "v3a") -> dict:
    """Same shape as the BatchScorer output: {userId, score, segment, factorBreakdown}."""
    v = VARIANTS[variant]
    m = measures(p)
    factors, own = _shares(m, v.layout, m.runway_share)
    points = _points(factors, v.maxima, m.solvency_cap)
    total = sum(points.values())

    # warnings: factor ones from the points before the cap (the cap has its own warning), fixed order
    warnings: list[str] = []
    pre = _points(factors, v.maxima, ONE)
    reserve_max = v.maxima["CashReserveMonths"]
    debt_max = v.maxima.get("DebtToIncomeRatio") or v.maxima["InstallmentToIncome"]
    net_debt_max = v.maxima.get("DebtToIncomeRatio") or v.maxima["NetDebtToIncome"]
    if _below(pre["CashReserveMonths"], reserve_max):
        warnings.append(W_LOW_RESERVE)
    if _below(round_points(D(debt_max) * own["installment"]), debt_max):
        warnings.append(W_HIGH_DEBT_BURDEN if m.installment_ratio > SEVERE_INSTALLMENT_RATIO else W_ELEVATED_DEBT_BURDEN)
    if _below(round_points(D(net_debt_max) * own["netDebt"]), net_debt_max):
        warnings.append(W_HIGH_TOTAL_DEBT if m.net_debt_years > SEVERE_NET_DEBT_YEARS else W_ELEVATED_TOTAL_DEBT)
    if _below(pre["SavingsRate"], v.maxima["SavingsRate"]):
        warnings.append(W_NEGATIVE_SAVINGS if m.savings_rate < SEVERE_SAVINGS_RATE else W_LOW_SAVINGS)
    if "ExpenseRatio" in v.maxima and _below(pre["ExpenseRatio"], v.maxima["ExpenseRatio"]):
        warnings.append(W_OVERSPENDING if m.expense_ratio > SEVERE_EXPENSE_RATIO else W_HIGH_EXPENSE_RATIO)
    if _below(pre["Impatience"], v.maxima["Impatience"]):
        warnings.append(W_HIGH_IMPATIENCE)
    if m.solvency_cap < ONE:
        warnings.append(W_EXTREME_DEBT)
    if m.net_debt > 0 and m.payment < m.net_debt * DEFAULT_MONTHLY_INTEREST:
        warnings.append(W_BELOW_INTEREST)
    if m.expenses < m.income * EXPENSE_FLOOR_SHARE:
        warnings.append(W_EXPENSES_TOO_LOW)
    if m.payment > 0 and m.debt == 0:
        warnings.append(W_INSTALLMENT_NO_DEBT)
    if m.debt > 0 and m.payment > m.debt:
        warnings.append(W_INSTALLMENT_OVER_DEBT)

    # label only; the score is always the sum of the factor points
    applied_rule = None
    if m.solvency_cap < ONE:
        applied_rule = RULE_SOLVENCY_CAP
    elif m.runway_years >= WEALTH_RUNWAY_LABEL_MIN_YEARS:
        unlifted, _ = _shares(m, v.layout, ZERO)
        if total > sum(_points(unlifted, v.maxima, m.solvency_cap).values()):
            applied_rule = RULE_WEALTH_RUNWAY

    return {
        "userId": p.get("userId"),
        "score": total,
        "segment": segment(total),
        "factorBreakdown": {
            "version": VERSION,
            "factors": points,
            "factorMaximums": dict(v.maxima),
            "warnings": warnings,
            "appliedRule": applied_rule,
        },
    }


def intermediates(p: dict) -> dict[str, str]:
    """The measures rounded to 6 decimals, for the golden table (helps debugging the port)."""
    m = measures(p)
    q = D("0.000001")
    keys = ["liquid", "expenses_eff", "expenses_reserve", "outflow", "reserve_months", "excess_liquid", "net_debt", "net_debt_years",
            "payment_eff", "installment_ratio", "savings_rate", "expense_ratio", "liquid_net_worth", "runway_years",
            "runway_share", "solvency_cap"]
    return {k: str(getattr(m, k).quantize(q, rounding=ROUND_HALF_UP)) for k in keys}
