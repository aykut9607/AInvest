"""Profiles for the v3 evaluation: a population calibrated to published Turkish shares, stress strata, probes.

Calibration targets are the rows of evaluation/realism_check.py (Findex 2025, TÜİK GYKA / Eurostat, TBB Risk
Merkezi). The core population is drawn so that those proxies land near the Turkish figures; the stress strata
(rich incomes, large wealth, extreme and hidden debt) are kept apart so the rule regions of v2 are exercised
without distorting the calibrated shares. Standard library only, seeded.
"""

import math
import random
from statistics import NormalDist

_N = NormalDist()

# --- calibration parameters (tuned with iq_eval_v3.py --calibrate; see IQ_V3_PROPOSAL.md, "Nüfus") -------------------
MEDIAN_INCOME = 40_000        # TL a month; the level only matters for v2's TL rules (v3 is scale-free)
INCOME_SIGMA = 0.72           # lognormal: bottom 20 % share ~5.9 %, top 20 % ~45 %, S80/S20 ~7.6 (TÜİK: 6.4 / 48 / 7.5)
EXPENSE_MEAN = 0.94           # expenses / income at the median income
EXPENSE_GRADIENT = 0.18       # richer people spend a smaller share (per income z-score)
EXPENSE_SD = 0.16
INSTALLMENT_SHARE = 0.564     # TÜİK GYKA: has a debt or installment payment
INSTALLMENT_MEDIAN = 0.14     # installment / income among payers (lognormal)
INSTALLMENT_SIGMA = 0.6
NO_DEBT_WITH_INSTALLMENT = 0.02   # data-quality case: installment reported, total debt 0
DEBT_WITHOUT_INSTALLMENT = 0.24   # of the non-payers: card / family debt without an installment (Findex: 64.7 % borrowed)
REMAINING_MONTHS_MEDIAN = 32  # remaining term of an installment loan (lognormal), debt = present value of the payments
REMAINING_MONTHS_SIGMA = 0.8
CASH_ZERO_BOTTOM = 0.50       # no cash at all, bottom income quintile
CASH_ZERO_REST = 0.03
CASH_MONTHS_MU = 0.32         # log of the median cash reserve in months of expenses (non-zero part)
CASH_MONTHS_GRADIENT = 0.30   # per income z-score
CASH_MONTHS_SIGMA = 0.42
INVESTOR_BASE, INVESTOR_GRADIENT = 0.15, 0.40   # P(has investments) = base + gradient * income rank
INVESTMENT_MONTHS_MEDIAN, INVESTMENT_MONTHS_SIGMA = 2.0, 1.1  # investments in months of income
IMPATIENCE_WEIGHTS = [0.12, 0.22, 0.32, 0.20, 0.14]           # levels 1..5 (no Turkish data; centred on 3)


def _lognormal(rng: random.Random, median: float, sigma: float) -> float:
    return median * math.exp(sigma * rng.gauss(0, 1))


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def annuity_present_value(payment: float, monthly_rate: float, months: float) -> float:
    return payment * (1 - (1 + monthly_rate) ** -months) / monthly_rate


def annuity_payment(principal: float, monthly_rate: float, months: int) -> float:
    return principal * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def profile(user_id: str, income, expenses, payment=0, debt=0, cash=0, investments=0, impatience=3,
            stratum: str = "probe") -> dict:
    return {"userId": user_id, "stratum": stratum, "monthlyIncome": income, "monthlyExpenses": expenses,
            "monthlyDebtPayment": payment, "totalDebt": debt, "cashReserve": cash,
            "investmentAmount": investments, "impatienceLevel": impatience}


def core(n: int, rng: random.Random) -> list[dict]:
    people = []
    for i in range(n):
        u = rng.random()
        z = _N.inv_cdf(_clip(u, 1e-6, 1 - 1e-6))
        income = max(1_000.0, round(MEDIAN_INCOME * math.exp(INCOME_SIGMA * z), -2))
        e = _clip(rng.gauss(EXPENSE_MEAN - EXPENSE_GRADIENT * z, EXPENSE_SD), 0.25, 1.6)
        expenses = round(income * e, -1)

        payment = 0.0
        debt = 0.0
        if rng.random() < INSTALLMENT_SHARE:
            r = _clip(_lognormal(rng, INSTALLMENT_MEDIAN, INSTALLMENT_SIGMA), 0.01, 0.9)
            payment = round(income * r, -1)
            if rng.random() >= NO_DEBT_WITH_INSTALLMENT:
                rate = rng.uniform(0.02, 0.045)  # consumer loans, cards and mortgages, monthly
                months = _clip(_lognormal(rng, REMAINING_MONTHS_MEDIAN, REMAINING_MONTHS_SIGMA), 1, 120)
                debt = round(annuity_present_value(payment, rate, months), -2)
        elif rng.random() < DEBT_WITHOUT_INSTALLMENT:
            debt = round(income * _clip(_lognormal(rng, 0.8, 1.0), 0.05, 24), -2)

        zero_p = CASH_ZERO_BOTTOM if u < 0.2 else CASH_ZERO_REST
        cash = 0.0
        if rng.random() >= zero_p:
            months = math.exp(CASH_MONTHS_MU + CASH_MONTHS_GRADIENT * z + CASH_MONTHS_SIGMA * rng.gauss(0, 1))
            cash = round(expenses * months, -2)
        investments = 0.0
        if rng.random() < INVESTOR_BASE + INVESTOR_GRADIENT * u:
            investments = round(income * _lognormal(rng, INVESTMENT_MONTHS_MEDIAN, INVESTMENT_MONTHS_SIGMA), -2)
        impatience = rng.choices([1, 2, 3, 4, 5], IMPATIENCE_WEIGHTS)[0]
        people.append(profile(f"core-{i:05d}", income, expenses, payment, debt, cash, investments, impatience,
                              "core"))
    return people


def stress(n: int, rng: random.Random) -> list[dict]:
    """Rich incomes, large wealth, extreme debt and hidden debt (small installment, large balance)."""
    out = []
    kinds = ["rich_income", "wealthy", "extreme_debt", "hidden_debt"]
    for i in range(n):
        kind = kinds[i % len(kinds)]
        if kind == "rich_income":
            income = round(math.exp(rng.uniform(math.log(400_000), math.log(4_000_000))), -3)
            expenses = round(income * rng.uniform(0.3, 1.4), -2)
            payment = round(income * rng.uniform(0, 0.3), -2) if rng.random() < 0.5 else 0.0
            debt = round(annuity_present_value(payment, 0.03, rng.uniform(6, 60)), -2) if payment else 0.0
            cash = round(expenses * rng.uniform(0, 6), -2)
            investments = round(income * rng.uniform(0, 36), -2) if rng.random() < 0.6 else 0.0
        elif kind == "wealthy":
            income = round(_lognormal(rng, MEDIAN_INCOME, 0.6), -2)
            expenses = round(income * rng.uniform(0.5, 1.3), -1)
            payment = 0.0
            cash = round(math.exp(rng.uniform(math.log(300_000), math.log(10_000_000))), -3)
            investments = round(math.exp(rng.uniform(math.log(1_000_000), math.log(50_000_000))), -3)
            debt = round((cash + investments) * rng.uniform(0, 0.3), -3) if rng.random() < 0.4 else 0.0
        elif kind == "extreme_debt":
            income = round(_lognormal(rng, MEDIAN_INCOME, 0.7), -2)
            expenses = round(income * rng.uniform(0.4, 1.0), -1)
            payment = round(income * rng.uniform(0, 0.4), -1)
            debt = round(math.exp(rng.uniform(math.log(5_000_000), math.log(300_000_000))), -3)
            cash = round(expenses * rng.uniform(0, 4), -2)
            investments = round(income * rng.uniform(0, 60), -2) if rng.random() < 0.3 else 0.0
        else:  # hidden_debt
            income = round(_lognormal(rng, MEDIAN_INCOME, 0.7), -2)
            expenses = round(income * rng.uniform(0.3, 0.8), -1)
            payment = round(income * rng.uniform(0.02, 0.15), -1)
            debt = round(income * 12 * rng.uniform(1.5, 10), -3)
            cash = round(expenses * rng.uniform(0, 8), -2)
            investments = round(income * rng.uniform(0, 24), -2) if rng.random() < 0.4 else 0.0
        out.append(profile(f"stress-{kind}-{i:04d}", income, expenses, payment, debt, cash, investments,
                           rng.choices([1, 2, 3, 4, 5], IMPATIENCE_WEIGHTS)[0], kind))
    return out


# --- fixed profiles ----------------------------------------------------------------------------------------------------
def demos() -> list[dict]:
    """infra/seed/seed_demo_users.py and evaluation/playground.py presets (same numbers)."""
    rows = [
        ("demo-low", (30000, 25000, 7000, 90000, 3000, 10000, 5)),
        ("demo-medium", (50000, 30000, 8000, 0, 60000, 0, 3)),
        ("demo-high", (20000, 8000, 2000, 0, 30000, 0, 2)),
        ("demo-highdebt", (40000, 16000, 2000, 2000000, 50000, 0, 2)),
        ("demo-richincome", (1000000, 900000, 0, 0, 0, 0, 5)),
        ("demo-richwealth", (30000, 29000, 0, 1000000, 2000000, 9000000, 5)),
        ("demo-extremedebt", (40000, 16000, 4000, 120000000, 96000, 10000000, 1)),
        ("demo-trend-1", (30000, 25000, 7000, 90000, 3000, 10000, 5)),
        ("demo-trend-2", (30000, 22000, 5000, 70000, 15000, 10000, 4)),
        ("demo-trend-3", (30000, 18000, 4000, 50000, 45000, 15000, 3)),
        ("demo-trend-4", (30000, 15000, 3000, 30000, 90000, 20000, 2)),
    ]
    return [profile(uid, *vals, stratum="demo") for uid, vals in rows]


def regression_probes() -> list[tuple[str, str, dict, dict]]:
    """(id, audit finding, before, after): the audit's examples, each a single small change."""
    def p(uid, *vals):
        return profile(uid, *vals, stratum="regression")
    pairs = [
        ("G1a", "investment +1 crosses VERY_HIGH_WEALTH",
         p("G1a", 30000, 6000000, 1000000, 0, 0, 9999999, 5), p("G1a+", 30000, 6000000, 1000000, 0, 0, 10000000, 5)),
        ("G1b", "income +1 crosses VERY_HIGH_INCOME",
         p("G1b", 999999, 2000000, 500000, 0, 0, 0, 5), p("G1b+", 1000000, 2000000, 500000, 0, 0, 0, 5)),
        ("G1c", "debt +1 crosses EXTREME_DEBT",
         p("G1c", 40000, 16000, 4000, 100095999, 96000, 0, 1), p("G1c+", 40000, 16000, 4000, 100096000, 96000, 0, 1)),
        ("G1d", "income +1 leaves EXTREME_DEBT",
         p("G1d", 999999, 400000, 100000, 1002400000, 2400000, 0, 1),
         p("G1d+", 1000000, 400000, 100000, 1002400000, 2400000, 0, 1)),
        ("G2a", "VERY_HIGH_INCOME ignores a deficit (expenses 2x income)",
         p("G2a", 1000000, 2000000, 0, 0, 0, 0, 3), None),
        ("G2b", "VERY_HIGH_WEALTH ignores 6M/month expenses",
         p("G2b", 30000, 6000000, 0, 0, 10000000, 0, 3), None),
        ("G3", "debt penalty capped at 25 (net debt ~104 years of income)",
         p("G3", 40000, 16000, 4000, 50000000, 96000, 0, 1), None),
        ("G4", "borrow 96k and hold it as cash",
         p("G4", 40000, 16000, 4000, 0, 0, 0, 3), p("G4+", 40000, 16000, 4000, 96000, 96000, 0, 3)),
        ("G5a", "impatience 5 -> 1 (self-report)",
         p("G5a", 50000, 30000, 8000, 0, 60000, 0, 5), p("G5a+", 50000, 30000, 8000, 0, 60000, 0, 1)),
        ("G5b", "expenses 0 and 0.01 cash",
         p("G5b", 50000, 0, 0, 0, 0.01, 0, 1), None),
        ("G6a", "expenses +1 at the 3-month and 40 % steps",
         p("G6a", 10000, 4000, 4000, 0, 24000, 0, 1), p("G6a+", 10000, 4001, 4000, 0, 24000, 0, 1)),
        ("G6b", "installment +1 at the 10 % and 20 % steps",
         p("G6b", 10000, 7000, 1000, 0, 60000, 0, 1), p("G6b+", 10000, 7000, 1001, 0, 60000, 0, 1)),
        ("G8", "installment missing from the reserve denominator",
         p("G8", 20000, 5000, 7000, 0, 30000, 0, 3), None),
        ("G9a", "installment below 3.5 %/month interest",
         p("G9a", 40000, 12000, 1000, 100000, 120000, 0, 2), None),
        ("G9b", "installment with zero debt (demo seed)",
         p("G9b", 50000, 30000, 8000, 0, 60000, 0, 3), None),
        ("G10a", "expenses 0 and cash 0, then cash +1",
         p("G10a", 50000, 0, 0, 0, 0, 0, 3), p("G10a+", 50000, 0, 0, 0, 1, 0, 3)),
        ("G10b", "tiny amounts (income 1)",
         p("G10b", 1, 0.4, 0.1, 0, 2, 0, 1), None),
        # WEALTH_RUNWAY label fix (25 Nov): 2 months of outflow in cash, negative savings, runway 0.42 years. The
        # runway lift still adds a rounded point (v3c-i5: 26 vs 25), but the label needs >= 5 years -> null
        ("L1", "2 months of cash, negative savings: runway lift without the label",
         p("L1", 30000, 20000, 30000, 0, 100000, 0, 3), None),
        ("L2", "30 years of runway, negative savings: WEALTH_RUNWAY",
         p("L2", 30000, 33000, 0, 0, 11880000, 0, 3), None),
    ]
    return pairs


def threshold_probes() -> list[tuple[str, dict, dict]]:
    """(id, at the threshold, 1 TL past it): every v2 step and every v3 kink, one input moved."""
    base = dict(income=40000, expenses=16000, payment=2000, debt=10000, cash=64000, investments=0, impatience=2)

    def p(uid, **changes):
        v = {**base, **changes}
        return profile(uid, v["income"], v["expenses"], v["payment"], v["debt"], v["cash"], v["investments"],
                       v["impatience"], stratum="threshold")

    probes = []

    def pair(uid, field, at, step=1, **others):
        probes.append((uid, p(uid, **{field: at}, **others), p(uid + "+", **{field: at + step}, **others)))

    # v2 reserve months (cash / expenses): 1, 3, 6 months -> cash 16k, 48k, 96k (cash -1 crosses down)
    for months in (1, 3, 6):
        pair(f"v2-reserve-{months}m", "cash", 16000 * months, step=-1)
    # v3 reserve months (liquid / (expenses + installment)): 3 and 6 months of 18k
    for months in (3, 6):
        pair(f"v3-reserve-{months}m", "cash", 18000 * months, step=-1)
    # installment / income: 10 %, 20 %, 36 %, 50 %
    for share in (0.10, 0.20, 0.36, 0.50):
        pair(f"installment-{int(share * 100)}pct", "payment", round(40000 * share), debt=round(40000 * share * 20))
    # v2 net debt years (debt - cash - investments) / yearly income: 0.5, 1, 3; v3 5 and 15 (cap)
    for years in (0.5, 1, 3):
        pair(f"v2-netdebt-{years}y", "debt", round(480000 * years + 64000), payment=12000)
    for years in (5, 15):
        pair(f"v3-netdebt-{years}y", "debt", round(480000 * years), payment=12000, cash=0)
    # savings rate (income - expenses - installment) / income: 20 %, 10 %, 0 %, -10 %
    for s in (0.20, 0.10, 0.0, -0.10):
        pair(f"savings-{int(s * 100)}pct", "expenses", round(40000 * (1 - s) - 2000))
    # expense ratio: 40 %, 60 %, 80 %, 100 %
    for e in (0.40, 0.60, 0.80, 1.00):
        pair(f"expense-{int(e * 100)}pct", "expenses", round(40000 * e))
    # v3 expense floor (10 % of income) and interest floor (installment = 3.5 % of the net debt)
    pair("v3-expense-floor", "expenses", 4000, step=-1)
    pair("v3-interest-floor", "payment", 3500, step=-1, debt=100000, cash=0)
    # v3 wealth runway 25 years: liquid net worth = 25 * 12 * expenses (expenses 16k -> 4.8M)
    pair("v3-runway-25y", "cash", 4800000 + 10000, step=-1, expenses=16000)
    # v2 TL rules
    probes.append(("v2-very-high-income", profile("v2-vhi", 999999, 900000, 0, 0, 0, 0, 5, "threshold"),
                   profile("v2-vhi+", 1000000, 900000, 0, 0, 0, 0, 5, "threshold")))
    probes.append(("v2-very-high-wealth", profile("v2-vhw", 30000, 29000, 0, 1000000, 2000000, 8999999, 5, "threshold"),
                   profile("v2-vhw+", 30000, 29000, 0, 1000000, 2000000, 9000000, 5, "threshold")))
    probes.append(("v2-extreme-debt", profile("v2-xd", 40000, 16000, 4000, 110095999, 96000, 10000000, 1, "threshold"),
                   profile("v2-xd+", 40000, 16000, 4000, 110096000, 96000, 10000000, 1, "threshold")))
    return probes
