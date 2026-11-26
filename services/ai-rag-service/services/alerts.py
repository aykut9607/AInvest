"""Capability 2 of the report: an assistant that warns (GET /ai/insights/warnings).

Rule-based on purpose, no language model: an alert must be exactly right every time, and it reuses the IQ thresholds
so it never contradicts the score. What can be warned about is limited to the data the platform has today (monthly
amounts in the Finance Profile and the IQ history). Alerts tied to dates or transactions ("a payment is due in two
days", "you passed your monthly spending limit") need payment dates and transactions, which no service stores yet;
they belong to the Notification Service (Faz 5) and are not invented here.

Which thresholds: those of the scoring version of the user's latest IQ result (v2 when there is none or it is
unknown). The alerts are computed from the current profile with that version's definitions (services/facts.py):

  v2  the step thresholds of ScoringRules.cs (reserve < 3 months of expenses, installment > 36 %, net debt > 3 years,
      expenses > 80 %, impatience >= 4). With no expenses an empty reserve is 0 months, as in the IQ.
  v3  "warning = points": a factor alert fires exactly when the IQ lists that factor's warning (its points before the
      solvency cap below 60 % of the maximum, with the IQ's rounding), plus the four consistency checks of v3.
      There is no expense-ratio alert (v3c-i5 has no such factor). When a floor of v3 changes a measure (the interest
      counted instead of a smaller installment, the 10 % expense floor), the alert about that floor is shown instead
      of a message whose numbers would not match the user's own amounts.

The applied rule of the latest result changes only the monthly-deficit alert, which is a fact either way:
  v2  VERY_HIGH_INCOME / VERY_HIGH_WEALTH set the score to 100 without looking at the cash flow (known v2 gap). The
      deficit is still reported, as WARNING instead of CRITICAL and with a sentence saying the rule ignored it.
  v3  WEALTH_RUNWAY (the IQ writes it from five years of expenses on): WARNING, with how many years the liquid net
      worth covers the deficit, but only when the current profile still covers it for five years (a large
      installment or a profile changed since the result can make the deficit bigger than the expenses); otherwise
      the deficit stays CRITICAL and nothing is said about the runway.
      SOLVENCY_CAP: an EXTREME_TOTAL_DEBT alert (CRITICAL) replaces the total-debt alert, computed from the profile.
"""

from pydantic import ValidationError

from core.domain import (
    FACTORS_V3,
    HIGH_IMPATIENCE_LEVEL,
    HIGH_INSTALLMENT_RATIO,
    HIGH_NET_DEBT_YEARS,
    OVERSPENDING_RATIO,
    RESERVE_MIN_MONTHS,
    V3_EXPENSE_FLOOR_SHARE,
    V3_INSTALLMENT_RATIO,
    V3_NET_DEBT_YEARS,
    V3_SAVINGS_RATE,
    V3_SEVERE_INSTALLMENT_RATIO,
    V3_SEVERE_NET_DEBT_YEARS,
    V3_SOLVENCY_CAP,
    V3_WEALTH_RUNWAY_LABEL_MIN_YEARS,
    anchor_value,
    scoring_version_of,
)
from core.fmt import num, pct, tl
from schemas.explain import FactorBreakdown
from schemas.insights import Alert
from services.facts import Money, V3Measures, interest_rate_text

_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
_V2_SCORE_RULES = {"VERY_HIGH_INCOME", "VERY_HIGH_WEALTH"}


def _latest_breakdown(latest: dict | None) -> tuple[str, FactorBreakdown | None]:
    raw = (latest or {}).get("factorBreakdown")
    version = scoring_version_of(raw)
    try:
        return version, FactorBreakdown.model_validate(raw) if raw else None
    except ValidationError:
        return version, None  # unreadable: the version's own defaults still apply


def _deficit(m: Money, rule: str | None, v3: V3Measures | None) -> Alert | None:
    if m.balance >= 0:
        return None
    deficit = -m.balance
    message = f"Her ay {tl(deficit)} açık veriyorsun: giderlerin ve taksitlerin gelirini aşıyor."
    years = float(v3.liquid_net_worth) / (deficit * 12) if v3 is not None and v3.liquid_net_worth > 0 else 0.0
    if rule == "WEALTH_RUNWAY" and years >= float(V3_WEALTH_RUNWAY_LABEL_MIN_YEARS):
        return Alert(code="MONTHLY_DEFICIT", severity="WARNING",
                     message=message + f" Likit servetin (nakit + yatırımın yarısı - borç) bu açığı yaklaşık "
                                       f"{num(years, 1)} yıl karşılar.")
    if m.runway_months is not None and m.cash > 0:
        message += f" Bu gidişle nakit birikimin yaklaşık {num(m.runway_months, 1)} ayda tükenir."
    elif m.cash <= 0:
        message += " Bu açığı karşılayacak nakit birikimin yok."
    if rule in _V2_SCORE_RULES:
        return Alert(code="MONTHLY_DEFICIT", severity="WARNING",
                     message=message + " Skorun özel bir kuralla belirlendi; bu kural aylık açığı hesaba katmıyor.")
    return Alert(code="MONTHLY_DEFICIT", severity="CRITICAL", message=message)


def _v2_alerts(m: Money) -> list[Alert]:
    alerts: list[Alert] = []
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
    return alerts


def _v3_alerts(m: Money, v: V3Measures, maxima: dict[str, int]) -> list[Alert]:
    alerts: list[Alert] = []
    weak = {factor: v.weak(factor, maximum) for factor, maximum in maxima.items()}
    adequate_installment = float(anchor_value(V3_INSTALLMENT_RATIO, "0.6"))       # 20 %
    adequate_net_debt = float(anchor_value(V3_NET_DEBT_YEARS, "0.6"))             # 1 year
    min_savings, good_savings = (float(anchor_value(V3_SAVINGS_RATE, s)) for s in ("0.6", "1"))   # 10 %, 20 %
    cap_start, cap_end = (float(x) for x, _ in V3_SOLVENCY_CAP)                    # 5, 15 years

    if weak["CashReserveMonths"]:
        # with the expense floor the months are of the floored expenses; EXPENSES_TOO_LOW below names that amount
        alerts.append(Alert(code="LOW_RESERVE", severity="WARNING",
                            message=f"Acil durum fonun (nakit + yatırımın yarısı) yalnızca "
                                    f"{num(float(v.reserve_months), 1)} aylık gider ve taksitini karşılıyor; en az "
                                    f"{RESERVE_MIN_MONTHS} ay önerilir."))

    # with the interest floor the IQ scores the interest, not the user's installment: INSTALLMENT_BELOW_INTEREST
    # below says that, a ratio of the installment would not match the warning
    if weak["InstallmentToIncome"] and not v.interest_floor_used:
        ratio = float(v.installment_ratio)
        if v.installment_ratio > V3_SEVERE_INSTALLMENT_RATIO:
            alerts.append(Alert(code="HIGH_INSTALLMENT", severity="WARNING",
                                message=f"Gelirinin {pct(ratio)} kadarı taksite gidiyor; "
                                        f"{pct(float(V3_SEVERE_INSTALLMENT_RATIO))} üstü yüksek kabul edilir."))
        else:
            alerts.append(Alert(code="ELEVATED_INSTALLMENT", severity="INFO",
                                message=f"Gelirinin {pct(ratio)} kadarı taksite gidiyor; taksitlerin gelirinin en "
                                        f"fazla {pct(adequate_installment)} kadarı olması önerilir."))

    net_debt, years = tl(float(v.net_debt)), num(float(v.net_debt_years), 1)
    if v.solvency_cap < 1:
        alerts.append(Alert(code="EXTREME_TOTAL_DEBT", severity="CRITICAL",
                            message=f"Net borcun {net_debt}, yani {years} yıllık gelirine eşit. "
                                    f"{num(cap_start)} yıllık gelirin üstündeki borç Finansal IQ'nun bütün "
                                    f"faktörlerini aşağı çeker; {num(cap_end)} yıllık gelirde skor 0 olur."))
    elif weak["NetDebtToIncome"]:
        if v.net_debt_years > V3_SEVERE_NET_DEBT_YEARS:
            alerts.append(Alert(code="HIGH_TOTAL_DEBT", severity="WARNING",
                                message=f"Net borcun {net_debt}, yani {years} yıllık gelirine eşit; "
                                        f"{num(float(V3_SEVERE_NET_DEBT_YEARS))} yılın üstü yüksek kabul edilir."))
        else:
            alerts.append(Alert(code="ELEVATED_TOTAL_DEBT", severity="INFO",
                                message=f"Net borcun {net_debt}, yani {years} yıllık gelirine eşit; en fazla "
                                        f"{num(adequate_net_debt)} yıllık gelir kadar net borç önerilir."))

    # a deficit is already MONTHLY_DEFICIT; with a floor the IQ's savings rate is not the user's own (see above)
    if weak["SavingsRate"] and m.balance >= 0 and not v.interest_floor_used and not v.expense_floor_used:
        alerts.append(Alert(code="LOW_SAVINGS", severity="INFO",
                            message=f"Gelirinin yalnızca {pct(float(v.savings_rate))} kadarı her ay artıyor; en az "
                                    f"{pct(min_savings)}, ideal olarak {pct(good_savings)} biriktirmen önerilir."))

    if weak["Impatience"]:
        alerts.append(Alert(code="HIGH_IMPATIENCE", severity="INFO",
                            message="Sabırsızlık düzeyin yüksek; acele kararlar uzun vadeli birikimi "
                                    "zorlaştırabilir."))

    if v.interest_floor_used:
        message = (f"Aylık taksitin ({tl(m.installment)}), borcunun tahmini aylık faizini ({tl(float(v.interest))}, "
                   f"aylık {interest_rate_text()} varsayımıyla) karşılamıyor; bu gidişle borcun büyür. Finansal IQ "
                   f"hesabında taksit yerine bu faiz tutarı sayılır.")
        severe = v.installment_ratio > V3_SEVERE_INSTALLMENT_RATIO
        alerts.append(Alert(code="INSTALLMENT_BELOW_INTEREST", severity="CRITICAL" if severe else "WARNING",
                            message=message))

    if v.expense_floor_used:
        alerts.append(Alert(code="EXPENSES_TOO_LOW", severity="INFO",
                            message=f"Bildirdiğin aylık gider ({tl(m.expenses)}) gelirinin "
                                    f"{pct(float(V3_EXPENSE_FLOOR_SHARE))} kadarından az; gerçekçi görünmüyor. "
                                    f"Finansal IQ hesabında gider {tl(float(v.expenses_eff))} sayıldı."))
    if m.installment > 0 and m.total_debt == 0:
        alerts.append(Alert(code="INSTALLMENT_WITHOUT_DEBT", severity="INFO",
                            message=f"Aylık {tl(m.installment)} taksit bildirmişsin ama toplam borcun 0 görünüyor; "
                                    f"profilindeki borç bilgisini kontrol et."))
    if m.total_debt > 0 and m.installment > m.total_debt:
        alerts.append(Alert(code="INSTALLMENT_EXCEEDS_DEBT", severity="INFO",
                            message=f"Aylık taksitin ({tl(m.installment)}) toplam borcundan ({tl(m.total_debt)}) "
                                    f"büyük; profilindeki borç bilgisini kontrol et."))
    return alerts


def _history_alerts(history: list[dict]) -> list[Alert]:
    if len(history) < 2:
        return []
    last, previous = history[-1], history[-2]
    change = int(last.get("score", 0)) - int(previous.get("score", 0))
    if change >= 0:
        return []
    message = (f"Finansal IQ skorun son hesaplamada {-change} puan düştü "
               f"({previous.get('score')} -> {last.get('score')}).")
    severity = "WARNING" if change <= -10 else "INFO"
    # optional field: when the history says which rules scored each point, a drop across a rule change is not the
    # user's doing
    versions = {previous.get("scoringVersion"), last.get("scoringVersion")}
    if None not in versions and len(versions) == 2:
        message += " Bu hesaplamada skor kuralları güncellendi; düşüşün bir kısmı kural değişikliğinden kaynaklanıyor olabilir."
        severity = "INFO"
    return [Alert(code="IQ_DROPPED", severity=severity, message=message)]


def alerts_for(profile: dict | None, history: list[dict], latest: dict | None = None) -> list[Alert]:
    """Alerts for the user's profile and IQ history. latest = the latest IQ result (GET .../latest data); its
    breakdown decides the scoring version and the rule, see the module docstring. Without it: v2, no rule."""
    version, breakdown = _latest_breakdown(latest)
    rule = breakdown.applied_rule if breakdown else None
    alerts: list[Alert] = []

    if profile:
        m = Money.from_profile(profile)
        v3 = m.v3() if version == "v3" else None
        deficit = _deficit(m, rule, v3)
        if deficit:
            alerts.append(deficit)
        if v3 is not None:
            maxima = breakdown.maximums() if breakdown else {k: mx for k, (_, mx) in FACTORS_V3.items()}
            alerts += _v3_alerts(m, v3, maxima)
        else:
            alerts += _v2_alerts(m)

    alerts += _history_alerts(history)
    return sorted(alerts, key=lambda a: _ORDER[a.severity])
