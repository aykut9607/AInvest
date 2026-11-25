from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration from environment variables or the git-ignored .env file (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PORTFOLIO_", extra="ignore")

    # no default on purpose: without the real connection string the service must not start
    # (a default with a password in the code would end up in git)
    database_url: str = Field(min_length=1)

    # server to server, like Finance -> IQ: these ports are not reachable for browsers through the gateway
    finance_base_url: str = "http://localhost:5293"
    iq_base_url: str = "http://localhost:5109"


@lru_cache
def get_settings() -> Settings:
    return Settings()
