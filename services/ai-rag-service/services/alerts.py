"""Capability 2 of the report: an assistant that warns (GET /ai/insights/warnings).

Rule-based on purpose, no language model: an alert must be exactly right every time, and it reuses the IQ thresholds
so it never contradicts the score. What can be warned about is limited to the data the platform has today (monthly
amounts in the Finance Profile and the IQ history). Alerts tied to dates or transactions ("a payment is due in two
days", "you passed your monthly spending limit") need payment dates and transactions, which no service stores yet;
they belong to the Notification Service (Faz 5) and are not invented here.
"""

from core.domain import (
    HIGH_IMPATIENCE_LEVEL,
    HIGH_INSTALLMENT_RATIO,
    HIGH_NET_DEBT_YEARS,
    OVERSPENDING_RATIO,
    RESERVE_MIN_MONTHS,
)
from core.fmt import num, pct, tl
from schemas.insights import Alert
from services.facts import Money

_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def alerts_for(profile: dict | None, history: list[dict]) -> list[Alert]:
    alerts: list[Alert] = []

    if profile:
        m = Money.from_profile(profile)

        if m.balance < 0:
            message = f"Her ay {tl(-m.balance)} açık veriyorsun: giderlerin ve taksitlerin gelirini aşıyor."
            if m.runway_months is not None and m.cash > 0:
                message += f" Bu gidişle nakit birikimin yaklaşık {num(m.runway_months, 1)} ayda tükenir."
            elif m.cash <= 0:
                message += " Bu açığı karşılayacak nakit birikimin yok."
            alerts.append(Alert(code="MONTHLY_DEFICIT", severity="CRITICAL", message=message))

        if m.reserve_months is not None and m.reserve_months < RESERVE_MIN_MONTHS:
            alerts.append(Alert(
                code="LOW_RESERVE", severity="WARNING",
                message=f"Acil durum fonun yalnızca {num(m.reserve_months, 1)} aylık giderini karşılıyor; "
                        f"en az {RESERVE_MIN_MONTHS} ay önerilir.",
            ))

        if m.installment_ratio is not None and m.installment_ratio > HIGH_INSTALLMENT_RATIO:
            alerts.append(Alert(
                code="HIGH_INSTALLMENT", severity="WARNING",
                message=f"Gelirinin {pct(m.installment_ratio)} kadarı taksite gidiyor; "
                        f"{pct(HIGH_INSTALLMENT_RATIO)} üstü yüksek kabul edilir.",
            ))

        if m.net_debt_years is not None and m.net_debt_years > HIGH_NET_DEBT_YEARS:
            alerts.append(Alert(
                code="HIGH_TOTAL_DEBT", severity="WARNING",
                message=f"Net borcun {tl(m.net_debt)}, yani {num(m.net_debt_years, 1)} yıllık gelirine eşit; "
                        f"{HIGH_NET_DEBT_YEARS} yılın üstü yüksek kabul edilir.",
            ))

        if m.expense_ratio is not None and m.expense_ratio > OVERSPENDING_RATIO and m.balance >= 0:
            # with a deficit MONTHLY_DEFICIT already says it, more strongly
            alerts.append(Alert(
                code="OVERSPENDING", severity="WARNING",
                message=f"Giderlerin gelirinin {pct(m.expense_ratio)} kadarı; {pct(OVERSPENDING_RATIO)} üstü "
                        f"birikim yapmayı zorlaştırır.",
            ))

        if m.impatience >= HIGH_IMPATIENCE_LEVEL:
            alerts.append(Alert(
                code="HIGH_IMPATIENCE", severity="INFO",
                message="Sabırsızlık düzeyin yüksek; acele kararlar uzun vadeli birikimi zorlaştırabilir.",
            ))

    if len(history) >= 2:
        last, previous = history[-1], history[-2]
        change = int(last.get("score", 0)) - int(previous.get("score", 0))
        if change < 0:
            alerts.append(Alert(
                code="IQ_DROPPED", severity="WARNING" if change <= -10 else "INFO",
                message=f"Finansal IQ skorun son hesaplamada {-change} puan düştü "
                        f"({previous.get('score')} -> {last.get('score')}).",
            ))

    return sorted(alerts, key=lambda a: _ORDER[a.severity])
