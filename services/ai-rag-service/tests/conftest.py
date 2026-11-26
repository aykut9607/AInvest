import copy

import pytest

from adapters.gateway import GatewayUnavailable
from adapters.llm import LlmUnavailable
from adapters.portfolio_sample import sample_proposal
from schemas.explain import ExplainRequest


class FakeModel:
    """Stands in for Ollama: fixed answers (or an error), and a record of everything it was sent."""

    model = "fake-model"

    def __init__(self, reply: str = "", error: bool = False, intents: list[str] | None = None,
                 script: list[dict] | None = None):
        self.reply = reply
        self.error = error
        self.intents = intents          # what chat_json (router) returns; None = behave as unavailable
        self.script = list(script or [])  # successive chat_messages answers (tools mode)
        self.calls: list[tuple[str, str]] = []
        self.json_calls: list[tuple[str, str]] = []
        self.message_calls: list[list[dict]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.error:
            raise LlmUnavailable("connection refused")
        return self.reply

    def chat_json(self, system: str, user: str, schema: dict) -> dict:
        self.json_calls.append((system, user))
        if self.error or self.intents is None:
            raise LlmUnavailable("connection refused")
        return {"intents": self.intents}

    def chat_messages(self, messages: list[dict], tools: list[dict]) -> dict:
        self.message_calls.append(copy.deepcopy(messages))
        if self.error:
            raise LlmUnavailable("connection refused")
        return self.script.pop(0) if self.script else {"content": self.reply}


class FakeUserData:
    """UserData without a gateway; raise_unavailable simulates the gateway being down."""

    def __init__(self, profile=None, latest_iq=None, history=None, portfolio=None, source="sample",
                 raise_unavailable=False):
        self._profile, self._latest, self._history = profile, latest_iq, history or []
        self._portfolio, self._source = portfolio, source
        self._down = raise_unavailable

    def _check(self):
        if self._down:
            raise GatewayUnavailable("connection refused")

    def profile(self):
        self._check()
        return self._profile

    def latest_iq(self):
        self._check()
        return self._latest

    def history(self):
        self._check()
        return self._history

    def portfolio(self):
        self._check()
        return self._portfolio, self._source


# --- IQ results (scoring v2: 5 factors, 25/25/25/15/10) ---------------------------------------------------------------
# a MEDIUM user with a thin cash reserve; factors add up to 55
MEDIUM = {
    "score": 55,
    "segment": "MEDIUM",
    "factorBreakdown": {
        "version": "v2",
        "factors": {
            "CashReserveMonths": 8,     # 8/25  -> weak
            "DebtToIncomeRatio": 15,    # 15/25 -> medium
            "SavingsRate": 15,          # 15/25 -> medium
            "ExpenseRatio": 9,          # 9/15  -> medium
            "Impatience": 8,            # 8/10  -> strong
        },
        "warnings": ["Low cash reserve"],
        "appliedRule": None,
    },
}

# a very high net worth decided the score: every factor is written at its maximum so the bars add up to 100
WEALTH_RULE = {
    "score": 100,
    "segment": "HIGH",
    "factorBreakdown": {
        "version": "v2",
        "factors": {"CashReserveMonths": 25, "DebtToIncomeRatio": 25, "SavingsRate": 25,
                    "ExpenseRatio": 15, "Impatience": 10},
        "warnings": [],
        "appliedRule": "VERY_HIGH_WEALTH",
    },
}

# --- Finance profiles (GET /api/Profiles/{userId} data) ---------------------------------------------------------------
# CLAUDE.md 6.7 weak example (IQ 8): income 30,000 - expenses 25,000 - installment 7,000 = 2,000 deficit a month;
# cash 3,000 lasts 1.5 months; reserve 3,000 + 10,000 / 2 = 8,000 = 0.32 months of expenses
DEFICIT_PROFILE = {
    "userId": "u-low", "monthlyIncome": 30000, "monthlyExpenses": 25000, "monthlyDebtPayment": 7000,
    "totalDebt": 90000, "cashReserve": 3000, "investmentAmount": 10000, "riskPreference": None, "impatienceLevel": 5,
}
# 30,000 - 18,000 - 4,000 = 8,000 left a month; reserve 20,000 + 10,000 / 2 = 25,000 = 1.39 months; installment 13%;
# net debt 60,000 - 20,000 - 10,000 = 30,000
BALANCED_PROFILE = {
    "userId": "u-mid", "monthlyIncome": 30000, "monthlyExpenses": 18000, "monthlyDebtPayment": 4000,
    "totalDebt": 60000, "cashReserve": 20000, "investmentAmount": 10000, "riskPreference": None, "impatienceLevel": 2,
}

LATEST_IQ = {"id": "x", "userId": "u-mid", "score": 55, "segment": "MEDIUM",
             "factorBreakdown": MEDIUM["factorBreakdown"], "createdAt": "2026-11-20T10:00:00.1234567",
             "updatedAt": "2026-11-20T10:00:00.1234567"}

# the "trend" demo account of CLAUDE.md 1.0: 8 -> 37 -> 62 (oldest first, as fn_IqTrend returns it)
RISING_HISTORY = [
    {"calculatedAt": "2026-11-01T10:00:00", "score": 8, "segment": "LOW", "scoreChange": None, "movingAverage3": 8},
    {"calculatedAt": "2026-11-10T10:00:00.1234567", "score": 37, "segment": "LOW", "scoreChange": 29,
     "movingAverage3": 22.5},
    {"calculatedAt": "2026-11-20T10:00:00Z", "score": 62, "segment": "MEDIUM", "scoreChange": 25,
     "movingAverage3": 35.67},
]


# --- IQ results, scoring v3 (variant v3c-i5: 30/25/10/30/5) -----------------------------------------------------------
# From evaluation/out/iq_v3_golden.json (column "v3c-i5"), produced by the reference evaluation/iq_v3/scoring.py.
# Copied here so the service tests do not depend on the evaluation folder; test_scoring_v3.py also runs every golden
# case when that file is present.
V3_MAXIMA = {"CashReserveMonths": 30, "InstallmentToIncome": 25, "NetDebtToIncome": 10, "SavingsRate": 30,
             "Impatience": 5}


def v3_result(score: int, segment: str, factors: list[int], warnings: list[str], rule: str | None = None,
              maxima: bool = True) -> dict:
    """{score, segment, factorBreakdown} as the v3 IQ service returns it; factors in V3_MAXIMA order."""
    breakdown = {"version": "v3", "factors": dict(zip(V3_MAXIMA, factors)), "warnings": warnings, "appliedRule": rule}
    if maxima:
        breakdown["factorMaximums"] = dict(V3_MAXIMA)
    return {"score": score, "segment": segment, "factorBreakdown": breakdown}


def latest(result: dict, user: str = "u-v3") -> dict:
    """GET /api/financial-iq/{userId}/latest data for an IQ result."""
    return {"id": "y", "userId": user, **result, "createdAt": "2026-11-25T10:00:00", "updatedAt": "2026-11-25T10:00:00"}


# golden "demo-low": the same profile as DEFICIT_PROFILE below (v2: 8)
V3_LOW = v3_result(27, "LOW", [2, 13, 10, 2, 0],
                   ["Low cash reserve", "Elevated debt burden", "Negative savings rate", "High impatience"])
# golden "demo-richwealth" (v2: 100, VERY_HIGH_WEALTH): the runway lifts the savings factor
RICHWEALTH_PROFILE = {"userId": "u-v3", "monthlyIncome": 30000, "monthlyExpenses": 29000, "monthlyDebtPayment": 0,
                      "totalDebt": 1000000, "cashReserve": 2000000, "investmentAmount": 9000000, "impatienceLevel": 5}
V3_WEALTH = v3_result(84, "HIGH", [30, 25, 10, 19, 0], ["High impatience"], "WEALTH_RUNWAY")
# golden "demo-extremedebt" (v2: 0, EXTREME_DEBT): net debt about 240 years of income, the cap takes every point
EXTREMEDEBT_PROFILE = {"userId": "u-v3", "monthlyIncome": 40000, "monthlyExpenses": 16000, "monthlyDebtPayment": 4000,
                       "totalDebt": 120000000, "cashReserve": 96000, "investmentAmount": 10000000, "impatienceLevel": 1}
V3_CAP = v3_result(0, "LOW", [0, 0, 0, 0, 0], ["High debt burden", "High total debt", "Negative savings rate",
                                               "Extreme total debt", "Installment below interest"], "SOLVENCY_CAP")
# golden "demo-highdebt" (v2: 63): 2,000,000 debt against a 2,000 installment, far below the 70,000 interest
HIGHDEBT_PROFILE = {"userId": "u-v3", "monthlyIncome": 40000, "monthlyExpenses": 16000, "monthlyDebtPayment": 2000,
                    "totalDebt": 2000000, "cashReserve": 50000, "investmentAmount": 0, "impatienceLevel": 2}
V3_HIGHDEBT = v3_result(22, "LOW", [17, 0, 1, 0, 4], ["Low cash reserve", "High debt burden", "High total debt",
                                                      "Negative savings rate", "Installment below interest"])
# golden "G10a": no expenses and no cash; v3 counts expenses as 10 % of income, so the reserve is 0 months
NO_EXPENSES_PROFILE = {"userId": "u-v3", "monthlyIncome": 50000, "monthlyExpenses": 0, "monthlyDebtPayment": 0,
                       "totalDebt": 0, "cashReserve": 0, "investmentAmount": 0, "impatienceLevel": 3}
V3_NO_EXPENSES = v3_result(68, "MEDIUM", [0, 25, 10, 30, 3], ["Low cash reserve", "Expenses look too low"])
# not in the golden table, scored with the reference: spends 5,000 more than it earns, but 20,000,000 in cash covers
# 47 years of expenses (lambda = 1), so the savings factor is lifted to its maximum
RUNWAY_DEFICIT_PROFILE = {"userId": "u-v3", "monthlyIncome": 30000, "monthlyExpenses": 35000, "monthlyDebtPayment": 0,
                          "totalDebt": 0, "cashReserve": 20000000, "investmentAmount": 0, "impatienceLevel": 2}
V3_RUNWAY_DEFICIT = v3_result(99, "HIGH", [30, 25, 10, 30, 4], [], "WEALTH_RUNWAY")


@pytest.fixture
def medium_request() -> ExplainRequest:
    return ExplainRequest.model_validate(MEDIUM)


@pytest.fixture
def wealth_request() -> ExplainRequest:
    return ExplainRequest.model_validate(WEALTH_RULE)


@pytest.fixture
def balanced_user() -> FakeUserData:
    return FakeUserData(profile=BALANCED_PROFILE, latest_iq=LATEST_IQ, history=RISING_HISTORY,
                        portfolio=sample_proposal())


@pytest.fixture
def deficit_user() -> FakeUserData:
    return FakeUserData(profile=DEFICIT_PROFILE, history=RISING_HISTORY[:1])
