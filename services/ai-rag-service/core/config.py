import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path = SERVICE_ROOT / ".env") -> None:
    """Reads KEY=value lines from the git-ignored .env next to main.py. Variables already set in the environment win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    # writes the coach explanations and, in router mode, the assistant answers
    ollama_model: str
    llm_timeout_seconds: float
    # false -> never call a model, always use the deterministic templates (no GPU / no Ollama)
    llm_enabled: bool
    # all user data is read through the edge gateway with the user's own token (CLAUDE.md 8.1), never from a database
    gateway_base_url: str
    gateway_timeout_seconds: float
    # "router": code picks the data, the model only phrases it; "tools": the model calls the tools itself
    assistant_mode: str
    # tools mode needs a model with tool calling in Ollama (gemma3 has none; llama3.1, mistral and qwen2.5 do)
    assistant_tools_model: str
    # "sample" until the Portfolio Service exists (example of contracts/schemas/portfolio-proposal.draft.schema.json),
    # then "gateway"
    portfolio_source: str
    # worked examples in the coach and assistant prompts (few-shot); off = the bare rules, for the comparison
    prompt_examples: bool


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        llm_enabled=os.getenv("LLM_ENABLED", "true").lower() == "true",
        gateway_base_url=os.getenv("GATEWAY_BASE_URL", "http://localhost:5000"),
        gateway_timeout_seconds=float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "5")),
        assistant_mode=os.getenv("ASSISTANT_MODE", "router"),
        assistant_tools_model=os.getenv("ASSISTANT_TOOLS_MODEL", "llama3.1:8b"),
        portfolio_source=os.getenv("PORTFOLIO_SOURCE", "sample"),
        prompt_examples=os.getenv("PROMPT_EXAMPLES", "true").lower() == "true",
    )
