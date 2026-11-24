"""Deterministic facts about the user's money, computed from the Finance Profile.

Every ratio and amount the assistant and the alerts mention is computed here, in code, with the same definitions the
IQ rules use (reserve = cash + half of the investments, net debt = debt - cash - investments, ...). The model only
receives the rendered lines; the number check then allows exactly the numbers in them.
"""

from dataclasses import dataclass

from core.domain import INVESTMENT_RESERVE_SHARE, RESERVE_GOOD_MONTHS, RESERVE_MIN_MONTHS
from core.fmt import num, pct, tl


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

    # emergency reserve as the IQ counts it
    @property
    def reserve(self) -> float:
        return self.cash + self.investment * INVESTMENT_RESERVE_SHARE

    @property
    def reserve_months(self) -> float | None:
        return self.reserve / self.expenses if self.expenses > 0 else None

    @property
    def installment_ratio(self) -> float | None:
        return self.installment / self.income if self.income > 0 else None

    @property
    def expense_ratio(self) -> float | None:
        return self.expenses / self.income if self.income > 0 else None

    @property
    def savings_rate(self) -> float | None:
        return self.balance / self.income if self.income > 0 else None

    # what is owed minus what is owned; negative = net worth
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


def _balance_line(m: Money) -> str:
    if m.balance < 0:
        return f"Aylık açık (gelir - gider - taksit eksi çıkıyor): {tl(-m.balance)}"
    return f"Aylık kalan para (gelir - gider - taksit): {tl(m.balance)}"


def income_expense_lines(m: Money) -> list[str]:
    lines = [f"Aylık gelir: {tl(m.income)}", f"Aylık gider: {tl(m.expenses)}", f"Aylık taksit: {tl(m.installment)}",
             _balance_line(m)]
    if m.expense_ratio is not None:
        lines.append(f"Giderin gelire oranı: {pct(m.expense_ratio)}")
    return lines


def debt_lines(m: Money) -> list[str]:
    lines = [f"Toplam borç: {tl(m.total_debt)}", f"Aylık taksit: {tl(m.installment)}"]
    if m.installment_ratio is not None:
        lines.append(f"Taksitin aylık gelire oranı: {pct(m.installment_ratio)}")
    if m.net_debt > 0:
        lines.append(f"Net borç (toplam borç - nakit - yatırım): {tl(m.net_debt)}")
        if m.net_debt_years is not None:
            lines.append(f"Net borç {num(m.net_debt_years, 1)} yıllık gelire eşit")
    else:
        lines.append(f"Net servet (nakit + yatırım - toplam borç): {tl(-m.net_debt)}")
    return lines


def investment_lines(m: Money) -> list[str]:
    return [f"Yatırım tutarı: {tl(m.investment)}",
            f"Yatırımın acil durum fonuna sayılan kısmı (yarısı): {tl(m.investment * INVESTMENT_RESERVE_SHARE)}"]


def reserve_lines(m: Money) -> list[str]:
    lines = [f"Nakit: {tl(m.cash)}", f"Acil durum fonu (nakit + yatırımın yarısı): {tl(m.reserve)}"]
    if m.reserve_months is not None:
        lines.append(f"Acil durum fonu {num(m.reserve_months, 1)} aylık gideri karşılıyor "
                     f"(önerilen en az {RESERVE_MIN_MONTHS}, ideal {RESERVE_GOOD_MONTHS} ay)")
    return lines


def savings_lines(m: Money) -> list[str]:
    lines = [_balance_line(m)]
    if m.savings_rate is not None:
        lines.append(f"Tasarruf oranı (aylık kalanın gelire oranı): {pct(m.savings_rate)}")
    return lines


def summary_lines(m: Money) -> list[str]:
    lines = [f"Aylık gelir: {tl(m.income)}", f"Aylık gider: {tl(m.expenses)}", f"Aylık taksit: {tl(m.installment)}",
             _balance_line(m), f"Nakit: {tl(m.cash)}", f"Yatırım tutarı: {tl(m.investment)}",
             f"Toplam borç: {tl(m.total_debt)}"]
    if m.reserve_months is not None:
        lines.append(f"Acil durum fonu {num(m.reserve_months, 1)} aylık gideri karşılıyor")
    lines.append(f"Sabırsızlık düzeyi: {m.impatience} (1 en sabırlı, 5 en sabırsız)")
    return lines
