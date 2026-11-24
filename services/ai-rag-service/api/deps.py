"""FastAPI dependencies: models and the current user's data. Tests override them with fakes."""

from fastapi import Header, HTTPException

from adapters.gateway import GatewayClient, GatewayUserData, UserData
from adapters.llm import OllamaChatModel
from core.config import get_settings


def get_chat_model() -> OllamaChatModel | None:
    """Coach explanations and router answers (gemma3:4b by default); None = templates only."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    return OllamaChatModel(settings.ollama_base_url, settings.ollama_model, settings.llm_timeout_seconds)


def get_tools_model() -> OllamaChatModel | None:
    """Tools mode needs tool calling, which gemma3 does not have in Ollama (llama3.1:8b by default)."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    return OllamaChatModel(settings.ollama_base_url, settings.assistant_tools_model, settings.llm_timeout_seconds)


def get_user_data(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> UserData:
    """The caller's data, read through the gateway with the caller's own token.

    The gateway validates the token and rewrites X-User-Id from its subject (a client-sent X-User-Id is removed), so
    on the /ai route both headers are trustworthy. The direct port 8001 is for development only (CLAUDE.md 1.4).
    """
    if not authorization or not x_user_id:
        raise HTTPException(status_code=401, detail="Sign in first: this endpoint needs the gateway's token.")
    settings = get_settings()
    client = GatewayClient(settings.gateway_base_url, authorization, settings.gateway_timeout_seconds)
    return GatewayUserData(client, x_user_id, settings.portfolio_source)
