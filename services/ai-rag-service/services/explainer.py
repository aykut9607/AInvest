"""Capability 3 of the report: the coach explains why the Financial IQ is what it is (POST /ai/explain-financial-iq)."""

from adapters.llm import ChatModel
from core.domain import DISCLAIMER, RULES, SEGMENT_TR, WARNINGS
from core.fmt import num
from core.number_check import allowed_values
from schemas.explain import ExplainRequest, ExplainResponse
from services.checked import Generated, generate_checked
from services.prompts import coach_prompt, data_block, iq_lines

_SEGMENT_SENTENCE = {
    "HIGH": "finansal temelinin sağlam olduğunu gösteriyor.",
    "MEDIUM": "temel dengenin yerinde olduğunu ama güçlendirilecek alanlar bulunduğunu gösteriyor.",
    "LOW": "finansal durumunda öncelikle ilgilenmen gereken alanlar olduğunu gösteriyor.",
}


def template_explanation(req: ExplainRequest) -> str:
    """The B plan: only numbers from the request, so it never shows the user anything that is not in the data."""
    sentences = [
        f"Finansal IQ skorun 100 üzerinden {req.score}; bu {SEGMENT_TR[req.segment]} segmentte ve "
        + _SEGMENT_SENTENCE[req.segment]
    ]
    b = req.factor_breakdown
    if b is None:
        return " ".join(sentences)

    if b.rule_sets_score:
        # v2: the factor values were filled in by the rule, so they are not shown
        sentences.append(f"Skorun özel bir kuralla belirlendi: {RULES[b.applied_rule][1]}.")
    else:
        if b.applied_rule:
            # v3: a label next to real factor points; it names the mechanism, the factors still explain the score
            sentences.append(f"Skorunu etkileyen durum: {RULES[b.applied_rule][1]}.")
        # the two factors that lost the largest share of their points (maximums of the breakdown's own version)
        weak = sorted(
            ((label, points, maximum) for _, label, points, maximum in b.factor_rows() if points < maximum),
            key=lambda row: row[1] / row[2],
        )[:2]
        if weak:
            parts = [f"{label} ({maximum} üzerinden {num(points, 1)})" for label, points, maximum in weak]
            sentences.append("En çok puan kaybettiğin alanlar: " + " ve ".join(parts) + ".")

    if b.warnings:
        sentences.append("Öne çıkan uyarılar: " + "; ".join(WARNINGS[w].lower() for w in b.warnings) + ".")
    return " ".join(sentences)


def _response(generated: Generated) -> ExplainResponse:
    return ExplainResponse(
        explanation=generated.text,
        disclaimer=DISCLAIMER,
        model=generated.model,
        numbers_verified=True,
        fallback_used=generated.fallback_used,
        fallback_reason=generated.fallback_reason,
    )


def explain(req: ExplainRequest, llm: ChatModel | None) -> ExplainResponse:
    """Model writes the text, code checks it. Any failure ends in the deterministic template, never in an error."""
    if req.factor_breakdown is None:
        # nothing for the model to explain beyond the segment; clients sending only score + segment land here
        return _response(Generated(template_explanation(req), None, "NO_BREAKDOWN"))

    user = data_block(iq_lines(req.score, req.segment, req.factor_breakdown), "Bu sonucu kullanıcıya açıkla.")
    # the coach is shown no factor points, so the score and 100 are the only numbers it may write
    generated = generate_checked(llm, coach_prompt(req.factor_breakdown.scoring_version), user,
                                 allowed_values(req.score, 100),
                                 lambda: template_explanation(req), max_sentences=6)
    return _response(generated)
