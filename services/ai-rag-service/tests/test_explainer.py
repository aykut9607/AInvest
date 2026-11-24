from schemas.explain import ExplainRequest
from services.explainer import explain
from tests.conftest import FakeModel

GOOD_TEXT = (
    "Finansal IQ skorun 100 üzerinden 55 ve ORTA segmentte. Borç ve tasarruf tarafında dengen yerinde, "
    "ancak nakit rezervin en zayıf alanın. Önceliğin acil durumlar için birikimini artırmak olmalı."
)


def test_verified_model_text_is_returned(medium_request):
    response = explain(medium_request, FakeModel(GOOD_TEXT))
    assert response.explanation == GOOD_TEXT
    assert response.model == "fake-model"
    assert response.numbers_verified and not response.fallback_used


def test_invented_number_falls_back_to_template(medium_request):
    response = explain(medium_request, FakeModel("Skorun 55; tasarruf oranını %30 yaparsan 80 olur."))
    assert response.fallback_used and response.fallback_reason == "UNVERIFIED_NUMBERS"
    assert response.model is None
    assert "%30" not in response.explanation


def test_answer_in_another_script_falls_back_to_template(medium_request):
    # its only number is the score, so the number check alone would have let it through
    response = explain(medium_request, FakeModel("你的财务IQ得分为55分，表明你的财务状况稳定。"))
    assert response.fallback_reason == "WRONG_LANGUAGE"
    assert "财务" not in response.explanation


def test_unreachable_model_falls_back_to_template(medium_request):
    response = explain(medium_request, FakeModel(error=True))
    assert response.fallback_reason == "LLM_UNAVAILABLE"
    assert "55" in response.explanation


def test_empty_answer_falls_back_to_template(medium_request):
    assert explain(medium_request, FakeModel("   ")).fallback_reason == "EMPTY_OUTPUT"


def test_disabled_model_uses_template(medium_request):
    assert explain(medium_request, None).fallback_reason == "LLM_UNAVAILABLE"


def test_request_without_breakdown_never_calls_the_model():
    model = FakeModel(GOOD_TEXT)
    response = explain(ExplainRequest(score=80, segment="HIGH"), model)
    assert response.fallback_reason == "NO_BREAKDOWN"
    assert model.calls == []


def test_empty_breakdown_counts_as_no_breakdown():
    # the IQ service returns {} for a breakdown it cannot read
    model = FakeModel(GOOD_TEXT)
    request = ExplainRequest.model_validate({"score": 80, "segment": "HIGH", "factorBreakdown": {}})
    assert explain(request, model).fallback_reason == "NO_BREAKDOWN"
    assert model.calls == []


def test_template_names_the_weakest_factors_and_warnings(medium_request):
    text = explain(medium_request, None).explanation
    assert "Nakit rezervi (25 üzerinden 8)" in text
    assert "nakit rezervi düşük" in text


def test_prompt_contains_only_labels_from_our_tables(medium_request):
    model = FakeModel(GOOD_TEXT)
    explain(medium_request, model)
    _, user = model.calls[0]
    assert user.startswith("<veri>")
    assert "Nakit rezervi: zayıf" in user
    assert "Gider/gelir oranı: orta" in user
    assert "Sabır (acele etmeden bekleyebilme; zayıf ise kullanıcı sabırsızdır): güçlü" in user
    assert "25" not in user  # labels only, no factor points
    assert "Uyarılar: Nakit rezervi düşük" in user and "Low cash reserve" not in user
    assert "risk" not in user.lower()  # scoring v2 has no self-reported risk


def test_rule_decided_score_is_explained_by_the_rule_not_the_factors(wealth_request):
    model = FakeModel("Finansal IQ skorun 100; net servetin çok yüksek olduğu için skorun doğrudan belirlendi.")
    response = explain(wealth_request, model)
    assert not response.fallback_used
    _, user = model.calls[0]
    assert "Özel kural: skor bu kuralla doğrudan belirlendi; net servet" in user
    # the factors are all at their maximum only because of the rule; showing them would mislead
    assert "Faktörler" not in user and "Nakit rezervi" not in user


def test_template_for_a_rule_explains_the_rule(wealth_request):
    text = explain(wealth_request, None).explanation
    assert "Skorun özel bir kuralla belirlendi: net servet" in text
    assert "puan kaybettiğin" not in text


def test_worked_examples_are_in_the_prompt_and_use_made_up_numbers(medium_request):
    # the example's score (47) is not this user's: copying it would be caught by the number check
    model = FakeModel("Finansal IQ skorun 100 üzerinden 47.")
    response = explain(medium_request, model)
    system, _ = model.calls[0]
    assert "<örnek>" in system and "Finansal IQ skoru: 47 / 100" in system
    assert response.fallback_reason == "UNVERIFIED_NUMBERS"


def test_long_coach_answer_keeps_the_first_sentences_and_the_closing_advice(medium_request):
    sentences = [f"Cümle {w}." for w in ("bir", "iki", "üç", "dört", "beş", "altı", "yedi")]
    text = " ".join(sentences[:-1] + ["Son olarak nakit rezervini büyütmelisin."])
    response = explain(medium_request, FakeModel(text))
    assert not response.fallback_used
    assert response.explanation == "Cümle bir. Cümle iki. Cümle üç. Cümle dört. Cümle beş. " \
                                   "Son olarak nakit rezervini büyütmelisin."


def test_numbers_with_dots_and_commas_are_not_sentence_ends():
    from services.checked import cap_sentences
    text = "Ayda 1.740 TL ayrılıyor. Fonun 1,4 ay yetiyor. Üç. Dört. Beş. Altı."
    assert cap_sentences(text, 6) == text


def test_trace_shows_what_the_model_wrote_and_which_numbers_were_rejected(medium_request):
    from services.checked import trace_checks
    with trace_checks() as records:
        response = explain(medium_request, FakeModel("Skorun 55; tasarruf oranını %30 yaparsan 80 olur."))
    assert response.fallback_reason == "UNVERIFIED_NUMBERS"
    [record] = records
    assert record.model == "fake-model" and record.reason == "UNVERIFIED_NUMBERS"
    assert "%30" in record.text and set(record.unknown_numbers) >= {"%30", "80"}
    assert record.data.startswith("<veri>")


def test_no_trace_outside_the_block(medium_request):
    from services.checked import trace_checks
    explain(medium_request, FakeModel(GOOD_TEXT))  # must not fail without a trace
    with trace_checks() as records:
        pass
    assert records == []
