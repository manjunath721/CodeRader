"""
Central application configuration.

All secrets/config come from environment variables (see /.env.example).
Nothing here is hard-coded to a real credential — this satisfies the
"no hard-coded API keys" requirement (master spec §35).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    # App
    APP_NAME: str = "CodeRadar"
    API_V1_PREFIX: str = "/api"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://coderesilience:coderesilience@localhost:5432/coderesilience"

    # GitHub
    GITHUB_TOKEN: str | None = None

    # LLM provider abstraction (see app/ai/provider.py)
    LLM_PROVIDER: str = "none"  # "none" | "anthropic" | "openai" | ...
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None

    # Repository ingestion safety limits (§35, perf-hardening pass)
    CLONE_TIMEOUT_SECONDS: int = 300
    MAX_REPO_SIZE_MB: int = 500
    MAX_REPO_FILE_COUNT: int = 50_000
    MAX_COMMITS_PER_RUN: int = 50_000  # hard ceiling even for Full Historical Scan
    ALLOWED_REPO_SCHEMES: tuple[str, ...] = ("https", "git")
    ALLOW_PRIVATE_NETWORK_REPOS: bool = False  # set true for trusted on-prem Git/GitHub Enterprise
    GIT_COMMAND_TIMEOUT_SECONDS: float = 120

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
