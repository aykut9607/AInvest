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
