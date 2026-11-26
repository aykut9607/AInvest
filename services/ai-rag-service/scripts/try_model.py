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

V3_MAXIMA = {"CashReserveMonths": 30, "InstallmentToIncome": 25, "NetDebtToIncome": 10, "SavingsRate": 30,
             "Impatience": 5}

# scoring v2 (5 factors, 25/25/25/15/10); the first one is the weak example profile of CLAUDE.md section 6.7 (score 8).
# The "v3:" samples are scoring v3 (v3c-i5, 30/25/10/30/5) results of demo profiles, from evaluation/out/iq_v3_golden.json
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
    "v3: LOW, overspending (demo low)": {
        "segment": "LOW",
        "factorBreakdown": {
            "version": "v3",
            "factors": {"CashReserveMonths": 2, "InstallmentToIncome": 13, "NetDebtToIncome": 10, "SavingsRate": 2,
                        "Impatience": 0},
            "factorMaximums": V3_MAXIMA,
            "warnings": ["Low cash reserve", "Elevated debt burden", "Negative savings rate", "High impatience"],
            "appliedRule": None,
        },
    },
    "v3: hidden debt, installment below interest (demo highdebt)": {
        "segment": "LOW",
        "factorBreakdown": {
            "version": "v3",
            "factors": {"CashReserveMonths": 17, "InstallmentToIncome": 0, "NetDebtToIncome": 1, "SavingsRate": 0,
                        "Impatience": 4},
            "factorMaximums": V3_MAXIMA,
            "warnings": ["Low cash reserve", "High debt burden", "High total debt", "Negative savings rate",
                         "Installment below interest"],
            "appliedRule": None,
        },
    },
    "v3: label wealth runway (demo richwealth)": {
        "segment": "HIGH",
        "factorBreakdown": {
            "version": "v3",
            "factors": {"CashReserveMonths": 30, "InstallmentToIncome": 25, "NetDebtToIncome": 10, "SavingsRate": 19,
                        "Impatience": 0},
            "factorMaximums": V3_MAXIMA,
            "warnings": ["High impatience"],
            "appliedRule": "WEALTH_RUNWAY",
        },
    },
    "v3: label solvency cap (demo extremedebt)": {
        "segment": "LOW",
        "factorBreakdown": {
            "version": "v3",
            "factors": {"CashReserveMonths": 0, "InstallmentToIncome": 0, "NetDebtToIncome": 0, "SavingsRate": 0,
                        "Impatience": 0},
            "factorMaximums": V3_MAXIMA,
            "warnings": ["High debt burden", "High total debt", "Negative savings rate", "Extreme total debt",
                         "Installment below interest"],
            "appliedRule": "SOLVENCY_CAP",
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
