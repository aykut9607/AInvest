"""Runs a few sample IQ results through the real model and prints what the user would see.

    cd services/ai-rag-service
    venv/Scripts/python -m scripts.try_model            # default model (gemma3:4b)
    venv/Scripts/python -m scripts.try_model mistral:7b
"""

import sys
import time

from adapters.llm import OllamaChatModel
from core.config import get_settings
from schemas.explain import ExplainRequest
from services.explainer import explain

# scoring v2 (5 factors, 25/25/25/15/10); the first one is the weak example profile of CLAUDE.md section 6.7 (score 8)
SAMPLES = {
    "LOW, overspending": {
        "segment": "LOW",
        "factorBreakdown": {
            "version": "v2",
            "factors": {"CashReserveMonths": 0, "DebtToIncomeRatio": 8, "SavingsRate": 0,
                        "ExpenseRatio": 0, "Impatience": 0},
            "warnings": ["Low cash reserve", "Negative savings rate", "Overspending relative to income",
                         "High impatience"],
            "appliedRule": None,
        },
    },
    "MEDIUM, thin reserve": {
        "segment": "MEDIUM",
        "factorBreakdown": {
            "version": "v2",
            "factors": {"CashReserveMonths": 8, "DebtToIncomeRatio": 15, "SavingsRate": 15,
                        "ExpenseRatio": 9, "Impatience": 8},
            "warnings": ["Low cash reserve"],
            "appliedRule": None,
        },
    },
    "HIGH, impatient": {
        "segment": "HIGH",
        "factorBreakdown": {
            "version": "v2",
            "factors": {"CashReserveMonths": 25, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                        "ExpenseRatio": 15, "Impatience": 2},
            "warnings": ["High impatience"],
            "appliedRule": None,
        },
    },
    "rule: very high wealth": {
        "segment": "HIGH",
        "factorBreakdown": {
            "version": "v2",
            "factors": {"CashReserveMonths": 25, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                        "ExpenseRatio": 15, "Impatience": 10},
            "warnings": [],
            "appliedRule": "VERY_HIGH_WEALTH",
        },
    },
    "rule: extreme debt": {
        "segment": "LOW",
        "factorBreakdown": {
            "version": "v2",
            "factors": {"CashReserveMonths": 0, "DebtToIncomeRatio": 0, "SavingsRate": 0,
                        "ExpenseRatio": 0, "Impatience": 0},
            "warnings": ["Extreme total debt"],
            "appliedRule": "EXTREME_DEBT",
        },
    },
}


def main() -> None:
    settings = get_settings()
    model_name = sys.argv[1] if len(sys.argv) > 1 else settings.ollama_model
    model = OllamaChatModel(settings.ollama_base_url, model_name, settings.llm_timeout_seconds)

    for name, body in SAMPLES.items():
        # keep the samples honest: score = sum of factors, as the IQ service guarantees
        body["score"] = int(sum(body["factorBreakdown"]["factors"].values()))
        request = ExplainRequest.model_validate(body)

        started = time.perf_counter()
        response = explain(request, model)
        seconds = time.perf_counter() - started

        status = "TEMPLATE (" + str(response.fallback_reason) + ")" if response.fallback_used else "MODEL OK"
        print(f"\n=== {name} | score {request.score} | {model_name} | {status} | {seconds:.1f}s")
        print(response.explanation)


if __name__ == "__main__":
    main()
