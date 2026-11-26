"""Scoring v2.1 (26 Nov 2026): factorBreakdown.adjustment, a floor or cap that moves the score away from the factor sum."""

import copy

import pytest
from pydantic import ValidationError

from schemas.explain import ExplainRequest
from services.explainer import explain
from tests.conftest import MEDIUM, FakeModel

# the factors of MEDIUM add up to 55; a net worth of 25+ years of outgoings raised the score to 100
WEALTH_FLOOR = copy.deepcopy(MEDIUM)
WEALTH_FLOOR.update(score=100, segment="HIGH")
WEALTH_FLOOR["factorBreakdown"].update(version="v2.1", adjustment={"rule": "WEALTH_FLOOR", "fromFactors": 55, "score": 100})

# the same factors, but net debt above 3 years of income capped the score at 33
DEBT_CAP = copy.deepcopy(MEDIUM)
DEBT_CAP.update(score=33, segment="LOW")
DEBT_CAP["factorBreakdown"].update(version="v2.1", adjustment={"rule": "DEBT_CAP", "fromFactors": 55, "score": 33})


def test_an_adjusted_score_is_accepted_although_the_factors_do_not_add_up():
    assert ExplainRequest.model_validate(WEALTH_FLOOR).factor_breakdown.adjustment.rule == "WEALTH_FLOOR"
    assert ExplainRequest.model_validate(DEBT_CAP).score == 33


@pytest.mark.parametrize("change", [
    lambda b: b.update(score=90),                                                  # the adjustment says 100
    lambda b: b["factorBreakdown"]["adjustment"].update(fromFactors=60),           # the factors add up to 55
    lambda b: b["factorBreakdown"]["adjustment"].update(rule="SOMETHING_ELSE"),
    lambda b: b["factorBreakdown"].update(appliedRule="VERY_HIGH_WEALTH"),         # a rule and an adjustment together
])
def test_a_tampered_adjustment_is_rejected(change):
    body = copy.deepcopy(WEALTH_FLOOR)
    change(body)
    with pytest.raises(ValidationError):
        ExplainRequest.model_validate(body)


def test_the_prompt_keeps_the_factors_and_says_why_the_score_differs():
    model = FakeModel("Finansal IQ skorun 100; servetin giderlerini uzun yıllar karşıladığı için skorun yüksek.")
    response = explain(ExplainRequest.model_validate(WEALTH_FLOOR), model)
    assert not response.fallback_used
    _, user = model.calls[0]
    # unlike a rule, the factors still describe the user, so they stay in the prompt
    assert "Faktörler:" in user and "Nakit rezervi" in user
    assert "Skor ayarı: net servet" in user
    assert "55" not in user          # the coach may write only the score and 100


def test_the_template_names_the_factor_sum_and_the_reason():
    text = explain(ExplainRequest.model_validate(DEBT_CAP), None).explanation
    assert "100 üzerinden 33" in text
    assert "Faktörlerin toplamı 55; net borç" in text
