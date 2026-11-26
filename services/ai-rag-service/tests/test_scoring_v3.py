"""Scoring v3 (variant v3c-i5) next to v2: the explain contract, the coach, the facts, the alerts, the assistant, the
trend and the portfolio staleness. v2 behaviour itself is covered by the other test files, unchanged."""

import copy
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapters.portfolio_sample import sample_proposal
from api.deps import get_chat_model, get_tools_model, get_user_data
from core.domain import factor_level
from core.number_check import allowed_from, allowed_values, verify_numbers
from main import app
from rag.retriever import search
from schemas.explain import ExplainRequest
from services.alerts import alerts_for
from services.assistant import ask
from services.explainer import explain, template_explanation
from services.facts import Money, debt_lines, reserve_lines
from services.portfolio import explain_portfolio
from services.prompts import iq_lines
from services.trend import explain_trend, trend_lines
from tests.conftest import (
    BALANCED_PROFILE,
    DEFICIT_PROFILE,
    EXTREMEDEBT_PROFILE,
    HIGHDEBT_PROFILE,
    LATEST_IQ,
    MEDIUM,
    NO_EXPENSES_PROFILE,
    RICHWEALTH_PROFILE,
    RISING_HISTORY,
    RUNWAY_DEFICIT_PROFILE,
    V3_CAP,
    V3_HIGHDEBT,
    V3_LOW,
    V3_MAXIMA,
    V3_NO_EXPENSES,
    V3_RUNWAY_DEFICIT,
    V3_WEALTH,
    FakeModel,
    FakeUserData,
    latest,
    v3_result,
)

V3_RESULTS = [V3_LOW, V3_WEALTH, V3_CAP, V3_HIGHDEBT, V3_NO_EXPENSES, V3_RUNWAY_DEFICIT]
GOLDEN = Path(__file__).resolve().parents[3] / "evaluation" / "out" / "iq_v3_golden.json"


@pytest.fixture
def api():
    model = FakeModel("Finansal IQ skorun 100 üzerinden 27.", intents=["IQ_SCORE"])
    app.dependency_overrides[get_chat_model] = lambda: model
    app.dependency_overrides[get_tools_model] = lambda: model
    yield TestClient(app), model
    app.dependency_overrides.clear()


# --- the explain contract: v3 is accepted, v2 still works ---------------------------------------------------------------
@pytest.mark.parametrize("body", V3_RESULTS)
def test_v3_breakdowns_are_accepted_not_422(api, body):
    http, _ = api
    response = http.post("/ai/explain-financial-iq", json=body)
    assert response.status_code == 200
    assert response.json()["persona"] == "coach" and response.json()["numbersVerified"] is True


def test_v3_without_factor_maximums_uses_the_v3_table(api):
    http, _ = api
    assert http.post("/ai/explain-financial-iq", json=v3_result(27, "LOW", [2, 13, 10, 2, 0], [],
                                                                maxima=False)).status_code == 200


def test_v2_breakdown_with_and_without_version_still_works(api):
    http, _ = api
    body = copy.deepcopy(MEDIUM)
    assert http.post("/ai/explain-financial-iq", json=body).status_code == 200
    del body["factorBreakdown"]["version"]          # missing version = v2
    assert http.post("/ai/explain-financial-iq", json=body).status_code == 200


def _set(path, value):
    def change(body):
        target = body["factorBreakdown"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return change


@pytest.mark.parametrize("change", [
    lambda b: b.update(score=30),                                                 # factors add up to 27
    _set(["factors", "CashReserveMonths"], 31),                                   # above the v3 maximum 30
    _set(["factors", "Impatience"], 6),                                           # above the v3 maximum 5
    lambda b: b["factorBreakdown"]["factors"].pop("NetDebtToIncome"),             # missing v3 factor
    _set(["factors", "DebtToIncomeRatio"], 0),                                    # a v2 factor under v3
    _set(["appliedRule"], "EXTREME_DEBT"),                                        # a v2 rule under v3
    _set(["appliedRule"], "SOMETHING_ELSE"),
    _set(["factorMaximums", "Impatience"], 10),                                   # maximums add up to 105
    lambda b: b["factorBreakdown"]["factorMaximums"].pop("Impatience"),           # maximums miss a factor
    _set(["version"], "v4"),                                                      # unknown rules: not guessed
])
def test_invalid_v3_breakdowns_are_rejected(api, change):
    http, model = api
    body = copy.deepcopy(V3_LOW)
    change(body)
    assert http.post("/ai/explain-financial-iq", json=body).status_code == 422
    assert model.calls == []


@pytest.mark.parametrize("change", [
    _set(["appliedRule"], "SOLVENCY_CAP"),                                        # a v3 label under v2
    _set(["version"], "v3"),                                                      # v2 factors labelled v3
    _set(["factorMaximums"], {"CashReserveMonths": 30, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                              "ExpenseRatio": 10, "Impatience": 10}),             # v2 is frozen at 25/25/25/15/10
])
def test_v2_breakdowns_cannot_borrow_v3_parts(api, change):
    http, _ = api
    body = copy.deepcopy(MEDIUM)
    change(body)
    assert http.post("/ai/explain-financial-iq", json=body).status_code == 422


def test_factor_maximums_of_the_breakdown_win_over_the_table():
    # a v3 result with other weights (variant v3c: installment 20, impatience 10): 8 impatience points are valid
    # only because the breakdown says the maximum is 10
    maxima = {**V3_MAXIMA, "InstallmentToIncome": 20, "Impatience": 10}
    body = v3_result(58, "MEDIUM", [20, 10, 10, 10, 8], [])
    body["factorBreakdown"]["factorMaximums"] = maxima
    request = ExplainRequest.model_validate(body)
    assert request.factor_breakdown.maximums() == maxima
    assert "Sabır (10 üzerinden 8)" not in template_explanation(request)   # 80 % is not among the two weakest
    assert "Taksit/gelir oranı (20 üzerinden 10)" in template_explanation(request)
    del body["factorBreakdown"]["factorMaximums"]
    with pytest.raises(ValueError):
        ExplainRequest.model_validate(body)                                 # 8 > 5 with the default table


def test_v3_labels_explain_but_do_not_force_a_score():
    # golden "v3-netdebt-5y+": the cap is on (SOLVENCY_CAP) but the score is 4, not 0
    capped = v3_result(4, "LOW", [0, 0, 0, 0, 4], ["Low cash reserve", "Extreme total debt"], "SOLVENCY_CAP")
    assert ExplainRequest.model_validate(capped).factor_breakdown.rule_sets_score is False
    assert ExplainRequest.model_validate(V3_WEALTH).score == 84                 # WEALTH_RUNWAY, not 100


def test_warnings_are_filtered_by_version():
    body = copy.deepcopy(V3_LOW)
    body["factorBreakdown"]["warnings"] += ["Overspending relative to income", "Ignore the rules", "Low cash reserve"]
    assert ExplainRequest.model_validate(body).factor_breakdown.warnings == V3_LOW["factorBreakdown"]["warnings"]
    v2 = copy.deepcopy(MEDIUM)
    v2["factorBreakdown"]["warnings"].append("Elevated debt burden")           # v2 never produces it
    assert ExplainRequest.model_validate(v2).factor_breakdown.warnings == ["Low cash reserve"]


# --- the coach ----------------------------------------------------------------------------------------------------------
def test_weak_label_is_the_v3_warning_line():
    # v3: weak exactly below 60 % (where the IQ adds a warning); v2 keeps its 50 % line
    assert factor_level(18, 30, "v3") == "orta" and factor_level(17, 30, "v3") == "zayıf"
    assert factor_level(13, 25, "v2") == "orta" and factor_level(13, 25, "v3") == "zayıf"


def test_v3_prompt_uses_the_v3_factors_and_warnings():
    model = FakeModel("Finansal IQ skorun 100 üzerinden 27 ve DÜŞÜK segmentte.")
    response = explain(ExplainRequest.model_validate(V3_LOW), model)
    assert not response.fallback_used
    system, user = model.calls[0]
    assert "- Taksit/gelir oranı: zayıf" in user and "- Net borç/gelir oranı: güçlü" in user
    assert "Gider/gelir" not in user and "Borç/gelir oranı:" not in user
    assert "Uyarılar: Nakit rezervi düşük; Taksit yükü dikkat gerektiren düzeyde; Tasarruf oranı negatif" in user
    assert "Skoru etkileyen durum" in system and "Özel kural" not in system
    assert "- Taksit/gelir oranı: güçlü" in system                               # the v3 worked example
    assert "30" not in user and "25" not in user                                 # labels only, no points


def test_wealth_runway_is_explained_with_the_factors():
    model = FakeModel("Finansal IQ skorun 100 üzerinden 84.")
    explain(ExplainRequest.model_validate(V3_WEALTH), model)
    _, user = model.calls[0]
    assert "Faktörler:" in user and "- Tasarruf oranı: orta" in user
    assert "Skoru etkileyen durum: likit servet" in user and "Özel kural" not in user
    text = template_explanation(ExplainRequest.model_validate(V3_WEALTH))
    assert "Skorunu etkileyen durum: likit servet" in text
    assert "En çok puan kaybettiğin alanlar: Sabır (5 üzerinden 0) ve Tasarruf oranı (30 üzerinden 19)." in text


def test_solvency_cap_template_names_the_cap_and_the_warnings():
    text = template_explanation(ExplainRequest.model_validate(V3_CAP))
    assert "Skorunu etkileyen durum: net borç yıllık gelire göre çok yüksek" in text
    assert "toplam borç aşırı yüksek" in text and "taksit, borcun tahmini faizini karşılamıyor" in text


@pytest.mark.parametrize("body", V3_RESULTS)
def test_number_check_with_v3_data(body):
    request = ExplainRequest.model_validate(body)
    allowed = allowed_values(request.score, 100)
    assert verify_numbers(f"Finansal IQ skorun 100 üzerinden {request.score}.", allowed).verified
    # the coach sees no points: a maximum or a point of the breakdown is a number it was not given
    assert not verify_numbers(f"Sabır {request.factor_breakdown.maximums()['Impatience']} üzerinden.", allowed).verified
    # the template may show points and maximums, never anything that is not in the request
    data = {request.score, 100, *request.factor_breakdown.factors.values(), *request.factor_breakdown.maximums().values()}
    assert verify_numbers(template_explanation(request), allowed_values(*data)).verified


def test_invented_number_in_a_v3_explanation_falls_back():
    response = explain(ExplainRequest.model_validate(V3_LOW), FakeModel("Skorun 27; borcunu kapatırsan 60 olur."))
    assert response.fallback_reason == "UNVERIFIED_NUMBERS" and "60" not in response.explanation


# --- facts (v3 definitions) -----------------------------------------------------------------------------------------------
def test_v3_measures_match_the_golden_intermediates():
    # golden "demo-highdebt" intermediates, rounded to 6 decimals like the golden table
    v = Money.from_profile(HIGHDEBT_PROFILE).v3()
    q = lambda d: str(d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
    assert (q(v.reserve_months), q(v.net_debt), q(v.payment_eff), q(v.savings_rate)) == \
           ("2.777778", "2000000.000000", "70000.000000", "-1.150000")


def test_v3_reserve_counts_the_installment_and_never_disappears():
    # v2: 8,000 / 25,000 expenses = 0,3 months; v3: 8,000 / (25,000 + 7,000) = 0,25 -> 0,3 (same rounding here)
    assert "Acil durum fonu 0,3 aylık gider ve taksiti karşılıyor (önerilen en az 3, ideal 6 ay)" in \
           reserve_lines(Money.from_profile(DEFICIT_PROFILE), "v3")
    # no expenses: v2 had no months at all; v3 counts 10 % of income and says so
    lines = reserve_lines(Money.from_profile(NO_EXPENSES_PROFILE), "v3")
    assert "Acil durum fonu 0 aylık gider ve taksiti karşılıyor (önerilen en az 3, ideal 6 ay)" in lines
    assert "Bildirilen gider gelirin %10'undan az olduğu için hesapta aylık gider 5.000 TL sayıldı" in lines


def test_v3_debt_lines_use_the_v3_net_debt_and_the_interest():
    lines = debt_lines(Money.from_profile(HIGHDEBT_PROFILE), "v3")
    assert "Net borç (toplam borç - 6 aylık acil durum hedefini aşan likit varlık): 2.000.000 TL" in lines
    assert "Borcun tahmini aylık faizi (aylık %3,5 varsayımıyla): 70.000 TL; aylık taksit bunu karşılamıyor" in lines
    # liquid assets above the 6-month target cover the debt: no net debt, a liquid net worth instead
    lines = debt_lines(Money.from_profile(RICHWEALTH_PROFILE), "v3")
    assert "Likit net servet (nakit + yatırımın yarısı - toplam borç): 5.500.000 TL" in lines


# --- alerts per version -----------------------------------------------------------------------------------------------
# IQ v3 warning -> alert codes that report it. A floor of v3 (interest instead of the installment, the 10 % expense
# floor) is reported by its own alert, whose numbers are the user's; a deficit is MONTHLY_DEFICIT.
COVERED_BY = {
    "Low cash reserve": {"LOW_RESERVE"},
    "High debt burden": {"HIGH_INSTALLMENT", "INSTALLMENT_BELOW_INTEREST"},
    "Elevated debt burden": {"ELEVATED_INSTALLMENT", "INSTALLMENT_BELOW_INTEREST"},
    "High total debt": {"HIGH_TOTAL_DEBT", "EXTREME_TOTAL_DEBT"},
    "Elevated total debt": {"ELEVATED_TOTAL_DEBT", "EXTREME_TOTAL_DEBT"},
    "Negative savings rate": {"MONTHLY_DEFICIT", "INSTALLMENT_BELOW_INTEREST", "EXPENSES_TOO_LOW"},
    "Low savings rate": {"LOW_SAVINGS", "INSTALLMENT_BELOW_INTEREST", "EXPENSES_TOO_LOW"},
    "High impatience": {"HIGH_IMPATIENCE"},
    "Extreme total debt": {"EXTREME_TOTAL_DEBT"},
    "Installment below interest": {"INSTALLMENT_BELOW_INTEREST"},
    "Expenses look too low": {"EXPENSES_TOO_LOW"},
    "Installment without debt": {"INSTALLMENT_WITHOUT_DEBT"},
    "Installment exceeds total debt": {"INSTALLMENT_EXCEEDS_DEBT"},
}
# alert code -> the IQ warning it stands for (MONTHLY_DEFICIT is a plain fact and may stand alone)
STANDS_FOR = {code: {w for w, codes in COVERED_BY.items() if code in codes}
              for codes in COVERED_BY.values() for code in codes if code != "MONTHLY_DEFICIT"}


def _assert_alerts_match_the_score(profile: dict, result: dict):
    warnings = set(result["factorBreakdown"]["warnings"])
    codes = {a.code for a in alerts_for(profile, [], latest(result))}
    for warning in warnings:
        assert codes & COVERED_BY[warning], f"{warning} has no alert ({sorted(codes)})"
    for code in codes - {"MONTHLY_DEFICIT"}:
        assert warnings & STANDS_FOR[code], f"{code} without its IQ warning ({sorted(warnings)})"


@pytest.mark.parametrize("profile, result", [
    (DEFICIT_PROFILE, V3_LOW), (RICHWEALTH_PROFILE, V3_WEALTH), (EXTREMEDEBT_PROFILE, V3_CAP),
    (HIGHDEBT_PROFILE, V3_HIGHDEBT), (NO_EXPENSES_PROFILE, V3_NO_EXPENSES), (RUNWAY_DEFICIT_PROFILE, V3_RUNWAY_DEFICIT),
])
def test_v3_alerts_match_the_v3_warnings(profile, result):
    _assert_alerts_match_the_score(profile, result)


@pytest.mark.skipif(not GOLDEN.exists(), reason="evaluation/out/iq_v3_golden.json not in this checkout")
def test_v3_alerts_match_every_golden_case():
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["profiles"]
    assert len(cases) >= 52 and {"L1", "L2"} <= {c["id"] for c in cases}     # incl. the WEALTH_RUNWAY label probes
    for case in cases:
        r = case["v3c-i5"]
        result = v3_result(r["score"], r["segment"], list(r["factors"].values()), r["warnings"], r["appliedRule"])
        _assert_alerts_match_the_score(case["input"], result)
        # the runway is only ever mentioned next to the label
        deficit = [a for a in alerts_for(case["input"], [], latest(result)) if a.code == "MONTHLY_DEFICIT"]
        if deficit and r["appliedRule"] != "WEALTH_RUNWAY":
            assert deficit[0].severity == "CRITICAL" and "yıl karşılar" not in deficit[0].message
        text = template_explanation(ExplainRequest.model_validate(result))
        assert ("en az beş yıl" in text) == (r["appliedRule"] == "WEALTH_RUNWAY")


def test_same_profile_different_version_different_alerts():
    v2 = [a.code for a in alerts_for(DEFICIT_PROFILE, [], LATEST_IQ)]
    v3 = [a.code for a in alerts_for(DEFICIT_PROFILE, [], latest(V3_LOW))]
    assert v2 == ["MONTHLY_DEFICIT", "LOW_RESERVE", "HIGH_IMPATIENCE"]
    # v3: the 23 % installment is "Elevated debt burden" (v2 only warned above 36 %)
    assert v3 == ["MONTHLY_DEFICIT", "LOW_RESERVE", "ELEVATED_INSTALLMENT", "HIGH_IMPATIENCE"]
    assert alerts_for(DEFICIT_PROFILE, []) == alerts_for(DEFICIT_PROFILE, [], LATEST_IQ)   # no result -> v2


def test_no_expenses_reserve_alert_in_both_versions():
    # v2: an empty reserve with no expenses is 0 months for the IQ ("Low cash reserve"); the alert used to be skipped
    assert [a.code for a in alerts_for(NO_EXPENSES_PROFILE, [])] == ["LOW_RESERVE"]
    assert "LOW_RESERVE" not in [a.code for a in alerts_for({**NO_EXPENSES_PROFILE, "cashReserve": 1000}, [])]
    alerts = {a.code: a for a in alerts_for(NO_EXPENSES_PROFILE, [], latest(V3_NO_EXPENSES))}
    assert set(alerts) == {"LOW_RESERVE", "EXPENSES_TOO_LOW"}
    assert "Finansal IQ hesabında gider 5.000 TL sayıldı" in alerts["EXPENSES_TOO_LOW"].message


def test_v2_score_rule_softens_the_deficit_alert():
    # G2 of the audit: income 1,000,000, expenses 2,000,000 -> v2 says 100 (VERY_HIGH_INCOME) and ignores the deficit
    profile = {**BALANCED_PROFILE, "monthlyIncome": 1000000, "monthlyExpenses": 2000000, "monthlyDebtPayment": 0,
               "totalDebt": 0, "cashReserve": 0, "investmentAmount": 0}
    rule = latest({"score": 100, "segment": "HIGH", "factorBreakdown": {
        "version": "v2", "factors": {"CashReserveMonths": 25, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                                     "ExpenseRatio": 15, "Impatience": 10},
        "warnings": [], "appliedRule": "VERY_HIGH_INCOME"}})
    deficit = alerts_for(profile, [], rule)[0]
    assert deficit.code == "MONTHLY_DEFICIT" and deficit.severity == "WARNING"
    assert deficit.message.endswith("Skorun özel bir kuralla belirlendi; bu kural aylık açığı hesaba katmıyor.")
    assert alerts_for(profile, [])[0].severity == "CRITICAL"                    # no rule: still critical


def test_wealth_runway_softens_the_deficit_alert():
    deficit = alerts_for(RUNWAY_DEFICIT_PROFILE, [], latest(V3_RUNWAY_DEFICIT))[0]
    assert deficit.code == "MONTHLY_DEFICIT" and deficit.severity == "WARNING"
    # 20,000,000 / (5,000 * 12) = 333,3 years
    assert "Likit servetin (nakit + yatırımın yarısı - borç) bu açığı yaklaşık 333,3 yıl karşılar." in deficit.message


# golden "L1" / "L2" (WEALTH_RUNWAY only from five years of expenses in liquid net worth)
L1_PROFILE = {"monthlyIncome": 30000, "monthlyExpenses": 20000, "monthlyDebtPayment": 30000, "totalDebt": 0,
              "cashReserve": 100000, "investmentAmount": 0, "impatienceLevel": 3}
V3_L1 = v3_result(26, "LOW", [12, 0, 10, 1, 3], ["Low cash reserve", "High debt burden", "Negative savings rate",
                                                  "Installment without debt"])
L2_PROFILE = {"monthlyIncome": 30000, "monthlyExpenses": 33000, "monthlyDebtPayment": 0, "totalDebt": 0,
              "cashReserve": 11880000, "investmentAmount": 0, "impatienceLevel": 3}
V3_L2 = v3_result(98, "HIGH", [30, 25, 10, 30, 3], [], "WEALTH_RUNWAY")


def test_short_runway_without_the_label_is_a_plain_critical_deficit():
    # L1: 100,000 cash is under half a year of expenses; the lift added a point but the IQ writes no label
    deficit = alerts_for(L1_PROFILE, [], latest(V3_L1))[0]
    assert deficit.code == "MONTHLY_DEFICIT" and deficit.severity == "CRITICAL"
    assert "yıl karşılar" not in deficit.message and "5 ayda tükenir" in deficit.message
    request = ExplainRequest.model_validate(V3_L1)
    lines = iq_lines(request.score, request.segment, request.factor_breakdown)
    assert not any(line.startswith("Skoru etkileyen durum") for line in lines)
    assert "uzun yıllar" not in template_explanation(request) and "beş yıl" not in template_explanation(request)


def test_runway_label_softens_the_deficit_with_the_years():
    # L2: 11,880,000 / (3,000 * 12) = 330 years of the deficit
    deficit = alerts_for(L2_PROFILE, [], latest(V3_L2))[0]
    assert deficit.severity == "WARNING" and "bu açığı yaklaşık 330 yıl karşılar." in deficit.message
    assert "giderleri en az beş yıl karşılıyor" in template_explanation(ExplainRequest.model_validate(V3_L2))


def test_stale_runway_label_does_not_soften_a_deficit_it_no_longer_covers():
    # the label is from an older result; today the same cash covers the deficit for under five years
    deficit = alerts_for(L1_PROFILE, [], latest(V3_L2))[0]
    assert deficit.severity == "CRITICAL" and "yıl karşılar" not in deficit.message


def test_solvency_cap_is_one_critical_debt_alert():
    alerts = alerts_for(EXTREMEDEBT_PROFILE, [], latest(V3_CAP))
    assert [a.code for a in alerts] == ["EXTREME_TOTAL_DEBT", "INSTALLMENT_BELOW_INTEREST"]
    assert all(a.severity == "CRITICAL" for a in alerts)
    assert "5 yıllık gelirin üstündeki borç" in alerts[0].message


def test_installment_below_interest_alert_uses_the_users_amounts():
    alert = {a.code: a for a in alerts_for(HIGHDEBT_PROFILE, [], latest(V3_HIGHDEBT))}["INSTALLMENT_BELOW_INTEREST"]
    assert alert.message.startswith("Aylık taksitin (2.000 TL), borcunun tahmini aylık faizini (70.000 TL, aylık %3,5")


def test_unreadable_v3_breakdown_still_uses_v3_definitions():
    broken = copy.deepcopy(V3_LOW)
    broken["factorBreakdown"]["factors"]["Impatience"] = 99
    codes = [a.code for a in alerts_for(DEFICIT_PROFILE, [], latest(broken))]
    assert "ELEVATED_INSTALLMENT" in codes


def test_score_drop_across_a_rule_change_is_informational():
    history = [{"calculatedAt": "2026-11-20T10:00:00", "score": 100, "segment": "HIGH", "scoringVersion": "v2"},
               {"calculatedAt": "2026-11-26T10:00:00", "score": 53, "segment": "MEDIUM", "scoringVersion": "v3"}]
    drop = alerts_for(None, history)[0]
    assert drop.code == "IQ_DROPPED" and drop.severity == "INFO" and "kurallar" in drop.message


def test_warnings_endpoint_reads_the_version_of_the_latest_result():
    data = FakeUserData(profile=HIGHDEBT_PROFILE, latest_iq=latest(V3_HIGHDEBT))
    app.dependency_overrides[get_user_data] = lambda: data
    try:
        codes = [a["code"] for a in TestClient(app).get("/ai/insights/warnings").json()["alerts"]]
    finally:
        app.dependency_overrides.clear()
    assert codes == ["INSTALLMENT_BELOW_INTEREST", "LOW_RESERVE", "HIGH_TOTAL_DEBT"]


# --- assistant, trend and portfolio with a v3 latest result ------------------------------------------------------------
@pytest.fixture
def v3_user() -> FakeUserData:
    return FakeUserData(profile=HIGHDEBT_PROFILE, latest_iq=latest(V3_HIGHDEBT), history=RISING_HISTORY)


def test_assistant_iq_answer_with_v3_factors(v3_user):
    model = FakeModel("Finansal IQ skorun 22 ve DÜŞÜK segmentte.", intents=["IQ_SCORE"])
    response = ask("Finansal IQ skorum kaç?", "router", v3_user, model, None)
    assert not response.fallback_used
    _, user = model.calls[0]
    assert "- Taksit/gelir oranı: zayıf" in user and "Taksit, borcun tahmini faizini karşılamıyor" in user


def test_assistant_debt_answer_with_v3_numbers_passes_the_number_check(v3_user):
    model = FakeModel("Taksitin 2.000 TL ama borcunun aylık faizi 70.000 TL; bu yüzden borcun büyüyor.",
                      intents=["DEBT"])
    response = ask("Kaç para borcum var?", "router", v3_user, model, None)
    assert not response.fallback_used and response.model == "fake-model"
    computed = FakeModel("Faiz yılda 840.000 TL eder.", intents=["DEBT"])              # 70.000 x 12: computed
    assert ask("Kaç para borcum var?", "router", v3_user, computed, None).fallback_reason == "UNVERIFIED_NUMBERS"


def test_assistant_warnings_are_the_v3_alerts(v3_user):
    model = FakeModel("Taksitin faizi karşılamıyor.", intents=["WARNINGS"])
    ask("Bir risk var mı?", "router", v3_user, model, None)
    assert "Uyarı: Aylık taksitin (2.000 TL), borcunun tahmini aylık faizini" in model.calls[0][1]


def test_tools_mode_iq_tool_with_a_v3_result(v3_user):
    model = FakeModel(script=[{"content": "", "tool_calls": [{"function": {"name": "get_financial_iq",
                                                                            "arguments": {}}}]},
                              {"content": "Finansal IQ skorun 22."}])
    response = ask("Skorum kaç?", "tools", v3_user, None, model)
    assert not response.fallback_used
    assert "- Net borç/gelir oranı: zayıf" in model.message_calls[1][-1]["content"]


def test_faq_answers_follow_the_users_scoring_version():
    v2 = search("Finansal IQ nasıl hesaplanıyor?")[0].answer
    v3 = search("Finansal IQ nasıl hesaplanıyor?", version="v3")[0].answer
    assert "nakit rezervi en fazla 25 puan" in v2 and "nakit rezervi en fazla 30 puan" in v3
    assert "1.000.000 TL" not in search("Skorum neden doğrudan 100 oldu?", version="v3")[0].answer
    model = FakeModel("Skor beş faktörün toplamıdır.", intents=["FAQ"])
    ask("Finansal IQ nasıl hesaplanıyor?", "router",
        FakeUserData(latest_iq=latest(V3_LOW)), model, None)
    assert "taksit/gelir oranı en fazla 25 puan" in model.calls[0][1]


def test_faq_still_answers_when_the_iq_result_cannot_be_read():
    # an FAQ-only question did not need the gateway before; looking up the version must not change that
    response = ask("Verilerim nereye gidiyor?", "router", FakeUserData(raise_unavailable=True), None, None)
    assert response.fallback_reason == "LLM_UNAVAILABLE" and "kendi sunucularında" in response.answer


def test_trend_with_a_v3_latest_result(v3_user):
    model = FakeModel("Skorun 8'den 62'ye yükseldi; taksit tarafın hâlâ zayıf.")
    response = explain_trend(v3_user, model)
    assert not response.fallback_used
    assert "- Taksit/gelir oranı: zayıf" in model.calls[0][1]


def test_trend_says_when_the_scoring_rules_changed():
    history = [{**p, "scoringVersion": v} for p, v in zip(RISING_HISTORY, ["v2", "v2", "v3"])]
    lines = trend_lines(history)
    assert any(line.startswith("Skor hesaplama kuralları bu dönemde güncellendi") for line in lines)
    assert not any("kuralları" in line for line in trend_lines(RISING_HISTORY))       # field absent: nothing said
    # no version names in the data: their digits would become numbers the model may write
    assert not verify_numbers("Skorun 2 kez değişti.", allowed_from(*trend_lines(history))).verified


def test_proposal_from_v2_rules_is_stale_once_the_result_is_v3():
    # same score and an older result date, but the latest result was rescored under v3: the proposal is stale
    proposal = sample_proposal()
    result = latest(v3_result(88, "HIGH", [30, 25, 10, 18, 5], []))
    result["createdAt"] = "2026-11-20T08:00:00"
    response = explain_portfolio(FakeUserData(latest_iq=result, portfolio=proposal, source="service"), FakeModel("x"))
    assert response.stale
    same = {**LATEST_IQ, "score": 88, "createdAt": "2026-11-20T08:00:00"}           # v2, same score, older: fresh
    assert not explain_portfolio(FakeUserData(latest_iq=same, portfolio=proposal, source="service"),
                                 FakeModel("Önerin standart dengeli sepet.")).stale
