"""The user's data, read through the edge gateway with the user's own token (CLAUDE.md 8.1).

The AI service never connects to another service's database. Every request carries the caller's Authorization header,
and the gateway checks that the {userId} in the URL is the token's subject (BOLA): the assistant cannot read anybody
else's data even if a prompt asked it to.
"""

from typing import Any, Protocol

import httpx

from adapters.portfolio_sample import sample_proposal


class GatewayError(Exception):
    pass


class GatewayUnavailable(GatewayError):
    """The gateway or the service behind it did not answer (connection error, timeout, 5xx)."""


class GatewayDenied(GatewayError):
    """401/403: the token is missing, expired or not the owner of the data."""


class UserData(Protocol):
    """What the AI may know about the current user. Each method returns None / [] when the user has no data yet."""

    def profile(self) -> dict | None: ...
    def latest_iq(self) -> dict | None: ...
    def history(self) -> list[dict]: ...
    # (proposal, source) with source "sample" or "service"
    def portfolio(self) -> tuple[dict | None, str]: ...


class GatewayClient:
    def __init__(self, base_url: str, authorization: str, timeout_seconds: float,
                 transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport,
                                    headers={"Authorization": authorization})

    def get_data(self, path: str, params: dict | None = None) -> Any:
        """The `data` of the Result envelope { data, success, message }; None when there is nothing (404)."""
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as error:
            raise GatewayUnavailable(f"{type(error).__name__}: {error}") from error
        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise GatewayDenied(str(response.status_code))
        if response.status_code >= 400:
            raise GatewayUnavailable(f"{path} -> {response.status_code}")
        try:
            body = response.json()
        except ValueError as error:
            raise GatewayUnavailable(f"{path}: not JSON") from error
        if isinstance(body, dict) and "success" in body:
            # success=false means "no data": say "I don't know", never guess
            return body.get("data") if body.get("success") else None
        return body


class GatewayUserData:
    """UserData for one request; each source is fetched at most once."""

    def __init__(self, client: GatewayClient, user_id: str, portfolio_source: str = "sample"):
        self._client = client
        self._user = user_id
        self._portfolio_source = portfolio_source
        self._cache: dict[str, Any] = {}

    def _once(self, key: str, fetch):
        if key not in self._cache:
            self._cache[key] = fetch()
        return self._cache[key]

    def profile(self) -> dict | None:
        return self._once("profile", lambda: self._client.get_data(f"/api/Profiles/{self._user}"))

    def latest_iq(self) -> dict | None:
        return self._once("iq", lambda: self._client.get_data(f"/api/financial-iq/{self._user}/latest"))

    def history(self) -> list[dict]:
        return self._once("history", lambda: self._client.get_data(
            f"/api/financial-iq/{self._user}/history", {"take": 12}) or [])

    def portfolio(self) -> tuple[dict | None, str]:
        if self._portfolio_source == "sample":
            # the Portfolio Service does not exist yet (CLAUDE.md 5.10): work against the example of the draft schema
            return sample_proposal(), "sample"
        return self._once("portfolio", lambda: self._client.get_data(f"/api/portfolio/{self._user}/latest")), "service"
