"""Stand-in for the Portfolio Service until it exists: the example of contracts/schemas/portfolio-proposal.draft.schema.json.

It belongs to a demo user with IQ 88 (income 20,000, expenses 8,000, installment 2,000, cash 30,000), not to the
caller, so responses built from it say source="sample". Replace with PORTFOLIO_SOURCE=gateway when the service is up.
"""

import copy

_SAMPLE = {
    "proposalId": "7d1f3c2a-1111-4b6e-9a3e-0c8e2f5d9a01",
    "userId": "demo.high",
    "createdAt": "2026-11-26T10:00:00Z",
    "basedOn": {"iqScore": 88, "segment": "HIGH", "appliedRule": None, "iqCalculatedAt": "2026-11-26T09:58:00Z",
                "scoringVersion": "v2"},
    "preferences": {"option": "STANDARD", "riskLevel": "MEDIUM", "focusAssets": [], "excludedAssets": ["BTC"]},
    "risk": {"chosen": "MEDIUM", "maxAllowed": "HIGH"},
    "investable": {"sharePercent": 58, "monthlyAmount": 5800, "oneTimeAmount": 3480},
    "allocations": [
        {"asset": "GOLD", "percent": 30, "amount": 1740},
        {"asset": "TRY_DEPOSIT", "percent": 25, "amount": 1450},
        {"asset": "SPX", "percent": 25, "amount": 1450},
        {"asset": "EUR", "percent": 10, "amount": 580},
        {"asset": "NVDA", "percent": 10, "amount": 580},
    ],
    "reasons": ["EXCLUDED_ASSET_REPLACED:BTC->GOLD"],
    "disclaimer": "This is not investment advice.",
}


def sample_proposal() -> dict:
    return copy.deepcopy(_SAMPLE)
