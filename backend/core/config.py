from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider priority — comma-separated env var, e.g. QUOTE_PROVIDERS=fmp,finnhub,yfinance
    quote_providers: list[str] = ["fmp", "finnhub", "yfinance"]
    financials_providers: list[str] = ["fmp", "yfinance"]
    profile_providers: list[str] = ["fmp", "yfinance"]

    # Cache TTLs in seconds
    quote_ttl_seconds: int = 60
    financials_ttl_seconds: int = 86400
    profile_ttl_seconds: int = 86400

    # Per-adapter max concurrent requests (rate limiting via semaphore)
    fmp_concurrency: int = 10
    finnhub_concurrency: int = 5
    yfinance_concurrency: int = 2

    # Circuit breaker
    circuit_failure_threshold: int = 5
    circuit_cooldown_seconds: float = 60.0

    # API keys
    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    openfigi_api_key: str = ""
    database_url: str = ""
    td_api_key: str = ""
    anthropic_api_key: str = ""
    sec_contact_email: str = ""

    @field_validator("quote_providers", "financials_providers", "profile_providers", mode="before")
    @classmethod
    def parse_provider_list(cls, value: str | list) -> list[str]:
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value


settings = Settings()
