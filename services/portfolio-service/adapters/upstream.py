"""Reads the user's profile (Finance Profile) and latest score (Financial IQ) over HTTP; their databases are never touched."""

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends

from core.config import Settings, get_settings
from services.allocation import Profile

TIMEOUT_SECONDS = 5.0


class UpstreamError(Exception):
    """The other service is down or answered nonsense (HTTP 502)."""


class MissingData(Exception):
    """The user has no profile or no IQ result yet (HTTP 404)."""


@dataclass(frozen=True)
class IqResult:
    score: int
    segment: str
    applied_rule: str | None
    scoring_version: str
    calculated_at: str
    result_version: int | None          # changes whenever the result is recalculated: a proposal built on another value is stale
    adjustment: str | None = None       # v2.1: WEALTH_FLOOR / INCOME_FLOOR / DEBT_CAP when it changed the sum of the factors


class Upstream:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self._settings = settings
        self._transport = transport

    def profile(self, user_id: str) -> Profile:
        d = self._get(f"{self._settings.finance_base_url}/api/Profiles/{user_id}", "Finance Profile", "No financial profile yet.")
        try:
            return Profile(float(d["monthlyIncome"]), float(d["monthlyExpenses"]), float(d["monthlyDebtPayment"]), float(d["totalDebt"]), float(d["cashReserve"]), float(d["investmentAmount"]),
                           int(d.get("impatienceLevel") or 3))
        except (KeyError, TypeError, ValueError) as error:
            raise UpstreamError("Finance Profile returned an unexpected answer.") from error

    def iq(self, user_id: str) -> IqResult:
        d = self._get(f"{self._settings.iq_base_url}/api/financial-iq/{user_id}/latest", "Financial IQ", "No Financial IQ result yet.")
        try:
            breakdown = d["factorBreakdown"] or {}
            return IqResult(int(d["score"]), str(d["segment"]), breakdown.get("appliedRule"), str(breakdown.get("version", "v1")), str(d.get("updatedAt") or d["createdAt"]), d.get("resultVersion"),
                            (breakdown.get("adjustment") or {}).get("rule"))
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise UpstreamError("Financial IQ returned an unexpected answer.") from error

    def _get(self, url: str, service: str, missing: str) -> dict:
        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = client.get(url)
            if response.status_code == 404:
                raise MissingData(missing)
            response.raise_for_status()
            return response.json()["data"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise UpstreamError(f"{service} service is unavailable.") from error


def get_upstream(settings: Annotated[Settings, Depends(get_settings)]) -> Upstream:
    return Upstream(settings)
