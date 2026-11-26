"""Deterministic facts about the user's money, computed from the Finance Profile.

Every ratio and amount the assistant and the alerts mention is computed here, in code, with the same definitions the
IQ rules use. The definitions depend on the scoring version of the user's latest IQ result:

  v2  reserve = cash + half of the investments, in months of expenses; net debt = debt - cash - investments
  v3  liquid assets = cash + half of the investments; reserve = liquid assets in months of (expenses + installment);
      expenses count as at least 10 % of income; net debt = debt - the liquid assets above a 6-month target;
      debt service is at least 3.5 % of the net debt a month (evaluation/IQ_V3_PROPOSAL.md 8.2)

The model only receives the rendered lines; the number check then allows exactly the numbers in them.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from core.domain import (
    DEFAULT_SCORING_VERSION,
    INVESTMENT_RESERVE_SHARE,
    RESERVE_GOOD_MONTHS,
    RESERVE_MIN_MONTHS,
    V3_EXPENSE_FLOOR_SHARE,
    V3_IMPATIENCE,
    V3_INSTALLMENT_RATIO,
    V3_INVESTMENT_LIQUID_SHARE,
    V3_MONTHLY_INTEREST,
    V3_NET_DEBT_YEARS,
    V3_RESERVE_MONTHS,
    V3_RESERVE_TARGET_MONTHS,
    V3_RUNWAY_YEARS,
    V3_SAVINGS_RATE,
    V3_SOLVENCY_CAP,
    V3_WARNING_SHARE,
)
from core.fmt import num, pct, tl

_ZERO = Decimal(0)


def _dec(value: float) -> Decimal:
    # str() first: 0.1 stays 0.1, not the binary float (the IQ computes in C# decimal)
    return Decimal(str(value))


def interpolate(x: Decimal, table: tuple[tuple[Decimal, Decimal], ...]) -> Decimal:
    """Share for measure x: clamped at both ends, linear in between (IQ_V3_PROPOSAL.md 8.3, same operation order)."""
    if x <= table[0][0]:
        return table[0][1]
    for (x0, s0), (x1, s1) in zip(table, table[1:]):
        if x <= x1:
            return s0 + (x - x0) * (s1 - s0) / (x1 - x0)
    return table[-1][1]


def round_points(value: Decimal) -> int:
    """The IQ's two-step half-up rounding: 6 decimals, then a whole number (value is never negative)."""
    six = value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return int(six.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class V3Measures:
    """The measures of scoring v3, in the order and with the names of IQ_V3_PROPOSAL.md 8.2."""

    liquid: Decimal             # L = cash + 0.5 * investments
    expenses_eff: Decimal       # max(expenses, 0.10 * income)
    outflow: Decimal            # expenses_eff + installment
    reserve_months: Decimal     # L / outflow
    excess_liquid: Decimal      # max(0, L - 6 * outflow)
    net_debt: Decimal           # max(0, debt - excess_liquid)
    net_debt_years: Decimal     # net_debt / (12 * income)
    interest: Decimal           # 0.035 * net_debt, the least the debt costs a month
    payment_eff: Decimal        # max(installment, interest)
    installment_ratio: Decimal  # payment_eff / income
    savings_rate: Decimal       # (income - expenses_eff - payment_eff) / income
    liquid_net_worth: Decimal   # L - debt
    runway_years: Decimal       # liquid_net_worth / (12 * expenses_eff), 0 when there is no net worth
    runway_share: Decimal       # lambda: lifts the installment and savings shares
    solvency_cap: Decimal       # kappa: scales every factor down between 5 and 15 years of income in net debt
    # factor key -> share of its maximum, before the cap (what the warnings are decided on)
    shares: dict[str, Decimal]
    expense_floor_used: bool    # the reported expenses were below 10 % of income
    interest_floor_used: bool   # the installment does not cover the interest, so the interest is counted instead

    def weak(self, factor: str, maximum: int) -> bool:
        """True when the IQ lists a warning for this factor: its points before the cap are below 60 % of the maximum."""
        return Decimal(round_points(Decimal(maximum) * self.shares[factor])) < Decimal(maximum) * V3_WARNING_SHARE


@dataclass(frozen=True)
class Money:
    income: float
    expenses: float
    installment: float
    total_debt: float
    cash: float
    investment: float
    impatience: int

    @classmethod
    def from_profile(cls, p: dict) -> "Money":
        return cls(
            income=float(p.get("monthlyIncome") or 0),
            expenses=float(p.get("monthlyExpenses") or 0),
            installment=float(p.get("monthlyDebtPayment") or 0),
            total_debt=float(p.get("totalDebt") or 0),
            cash=float(p.get("cashReserve") or 0),
            investment=float(p.get("investmentAmount") or 0),
            impatience=int(p.get("impatienceLevel") or 3),
        )

    # monthly income minus expenses minus installments; negative = the user spends more than they earn
    @property
    def balance(self) -> float:
        return self.income - self.expenses - self.installment

    # emergency reserve as the IQ counts it (v2 and v3 alike: cash + half of the investments)
    @property
    def reserve(self) -> float:
        return self.cash + self.investment * INVESTMENT_RESERVE_SHARE

    # v2 definition: months of expenses. With no expenses the IQ counts any reserve as ample and an empty one as
    # 0 months ("Low cash reserve"), so 0 is returned for that case instead of nothing
    @property
    def reserve_months(self) -> float | None:
        if self.expenses > 0:
            return self.reserve / self.expenses
        return 0.0 if self.reserve <= 0 else None

    @property
    def installment_ratio(self) -> float | None:
        return self.installment / self.income if self.income > 0 else None

    @property
    def expense_ratio(self) -> float | None:
        return self.expenses / self.income if self.income > 0 else None

    @property
    def savings_rate(self) -> float | None:
        return self.balance / self.income if self.income > 0 else None

    # v2 definition: what is owed minus what is owned; negative = net worth
    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash - self.investment

    @property
    def net_debt_years(self) -> float | None:
        return self.net_debt / (self.income * 12) if self.income > 0 and self.net_debt > 0 else None

    # months until the cash runs out at the current monthly deficit; None when there is no deficit
    @property
    def runway_months(self) -> float | None:
        return self.cash / -self.balance if self.balance < 0 else None

    def v3(self) -> V3Measures | None:
        """The v3 measures; None without a positive income (the IQ rejects such a profile in both versions)."""
        income = _dec(self.income)
        if income <= 0:
            return None
        expenses, payment, debt = _dec(self.expenses), _dec(self.installment), _dec(self.total_debt)
        liquid = _dec(self.cash) + _dec(self.investment) * V3_INVESTMENT_LIQUID_SHARE
        expenses_eff = max(expenses, income * V3_EXPENSE_FLOOR_SHARE)
        outflow = expenses_eff + payment
        reserve_months = liquid / outflow
        excess_liquid = max(_ZERO, liquid - outflow * V3_RESERVE_TARGET_MONTHS)
        net_debt = max(_ZERO, debt - excess_liquid)
        net_debt_years = net_debt / (income * 12)
        interest = net_debt * V3_MONTHLY_INTEREST
        payment_eff = max(payment, interest)
        installment_ratio = payment_eff / income
        savings_rate = (income - expenses_eff - payment_eff) / income
        liquid_net_worth = liquid - debt
        runway_years = liquid_net_worth / (expenses_eff * 12) if liquid_net_worth > 0 else _ZERO
        lam = interpolate(runway_years, V3_RUNWAY_YEARS)
        shares = {
            "CashReserveMonths": interpolate(reserve_months, V3_RESERVE_MONTHS),
            "InstallmentToIncome": max(interpolate(installment_ratio, V3_INSTALLMENT_RATIO), lam),
            "NetDebtToIncome": interpolate(net_debt_years, V3_NET_DEBT_YEARS),
            "SavingsRate": max(interpolate(savings_rate, V3_SAVINGS_RATE), lam),
            "Impatience": interpolate(Decimal(self.impatience), V3_IMPATIENCE),
        }
        return V3Measures(
            liquid=liquid, expenses_eff=expenses_eff, outflow=outflow, reserve_months=reserve_months,
            excess_liquid=excess_liquid, net_debt=net_debt, net_debt_years=net_debt_years, interest=interest,
            payment_eff=payment_eff, installment_ratio=installment_ratio, savings_rate=savings_rate,
            liquid_net_worth=liquid_net_worth, runway_years=runway_years, runway_share=lam,
            solvency_cap=interpolate(net_debt_years, V3_SOLVENCY_CAP), shares=shares,
            expense_floor_used=expenses < income * V3_EXPENSE_FLOOR_SHARE,
            interest_floor_used=net_debt > 0 and payment < interest,
        )


def interest_rate_text() -> str:
    """"%3,5": pct() rounds to whole percents."""
    return "%" + num(float(V3_MONTHLY_INTEREST) * 100, 1)


def _balance_line(m: Money) -> str:
    if m.balance < 0:
        return f"Aylık açık (gelir - gider - taksit eksi çıkıyor): {tl(-m.balance)}"
    return f"Aylık kalan para (gelir - gider - taksit): {tl(m.balance)}"


# every *_lines function takes the scoring version of the user's latest IQ, so the assistant uses the definitions
# behind the score the user sees; lines that are plain facts (income, balance) are the same in both versions
def income_expense_lines(m: Money, version: str = DEFAULT_SCORING_VERSION) -> list[str]:
    lines = [f"Aylık gelir: {tl(m.income)}", f"Aylık gider: {tl(m.expenses)}", f"Aylık taksit: {tl(m.installment)}",
             _balance_line(m)]
    if m.expense_ratio is not None:
        lines.append(f"Giderin gelire oranı: {pct(m.expense_ratio)}")
    return lines


def debt_lines(m: Money, version: str = DEFAULT_SCORING_VERSION) -> list[str]:
    lines = [f"Toplam borç: {tl(m.total_debt)}", f"Aylık taksit: {tl(m.installment)}"]
    if m.installment_ratio is not None:
        lines.append(f"Taksitin aylık gelire oranı: {pct(m.installment_ratio)}")
    v = m.v3() if version == "v3" else None
    if v is not None:
        if v.net_debt > 0:
            lines.append(f"Net borç (toplam borç - 6 aylık acil durum hedefini aşan likit varlık): {tl(float(v.net_debt))}")
            lines.append(f"Net borç {num(float(v.net_debt_years), 1)} yıllık gelire eşit")
            if v.interest_floor_used:
                lines.append(f"Borcun tahmini aylık faizi (aylık {interest_rate_text()} varsayımıyla): "
                             f"{tl(float(v.interest))}; aylık taksit bunu karşılamıyor")
        else:
            lines.append(f"Likit net servet (nakit + yatırımın yarısı - toplam borç): {tl(float(v.liquid_net_worth))}")
        return lines
    if m.net_debt > 0:
        lines.append(f"Net borç (toplam borç - nakit - yatırım): {tl(m.net_debt)}")
        if m.net_debt_years is not None:
            lines.append(f"Net borç {num(m.net_debt_years, 1)} yıllık gelire eşit")
    else:
        lines.append(f"Net servet (nakit + yatırım - toplam borç): {tl(-m.net_debt)}")
    return lines


def investment_lines(m: Money, version: str = DEFAULT_SCORING_VERSION) -> list[str]:
    return [f"Yatırım tutarı: {tl(m.investment)}",
            f"Yatırımın acil durum fonuna sayılan kısmı (yarısı): {tl(m.investment * INVESTMENT_RESERVE_SHARE)}"]


def _v3_reserve_line(v: V3Measures) -> str:
    return f"Acil durum fonu {num(float(v.reserve_months), 1)} aylık gider ve taksiti karşılıyor"


def _expense_floor_line(v: V3Measures) -> str:
    return (f"Bildirilen gider gelirin %10'undan az olduğu için hesapta aylık gider {tl(float(v.expenses_eff))} "
            f"sayıldı")


def reserve_lines(m: Money, version: str = DEFAULT_SCORING_VERSION) -> list[str]:
    lines = [f"Nakit: {tl(m.cash)}", f"Acil durum fonu (nakit + yatırımın yarısı): {tl(m.reserve)}"]
    v = m.v3() if version == "v3" else None
    if v is not None:
        lines.append(f"{_v3_reserve_line(v)} (önerilen en az {RESERVE_MIN_MONTHS}, ideal {RESERVE_GOOD_MONTHS} ay)")
        if v.expense_floor_used:
            lines.append(_expense_floor_line(v))
        return lines
    if m.reserve_months is not None:
        lines.append(f"Acil durum fonu {num(m.reserve_months, 1)} aylık gideri karşılıyor "
                     f"(önerilen en az {RESERVE_MIN_MONTHS}, ideal {RESERVE_GOOD_MONTHS} ay)")
    return lines


def savings_lines(m: Money, version: str = DEFAULT_SCORING_VERSION) -> list[str]:
    lines = [_balance_line(m)]
    if m.savings_rate is not None:
        lines.append(f"Tasarruf oranı (aylık kalanın gelire oranı): {pct(m.savings_rate)}")
    return lines


def summary_lines(m: Money, version: str = DEFAULT_SCORING_VERSION) -> list[str]:
    lines = [f"Aylık gelir: {tl(m.income)}", f"Aylık gider: {tl(m.expenses)}", f"Aylık taksit: {tl(m.installment)}",
             _balance_line(m), f"Nakit: {tl(m.cash)}", f"Yatırım tutarı: {tl(m.investment)}",
             f"Toplam borç: {tl(m.total_debt)}"]
    v = m.v3() if version == "v3" else None
    if v is not None:
        lines.append(_v3_reserve_line(v))
    elif m.reserve_months is not None:
        lines.append(f"Acil durum fonu {num(m.reserve_months, 1)} aylık gideri karşılıyor")
    lines.append(f"Sabırsızlık düzeyi: {m.impatience} (1 en sabırlı, 5 en sabırsız)")
    return lines
