from __future__ import annotations

import base64

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Provider priority — comma-separated env var, e.g. QUOTE_PROVIDERS=twelvedata,fmp,finnhub,yfinance
    quote_providers: list[str] = ["twelvedata", "yfinance", "fmp", "finnhub"]
    financials_providers: list[str] = ["yfinance", "fmp"]
    profile_providers: list[str] = ["yfinance", "fmp"]
    price_history_providers: list[str] = ["twelvedata", "yfinance"]
    logo_providers: list[str] = ["fmp", "yfinance"]
    leadership_providers: list[str] = ["yfinance"]
    market_intelligence_providers: list[str] = ["yfinance"]

    # Cache TTLs in seconds
    quote_ttl_seconds: int = 60
    financials_ttl_seconds: int = 86400
    profile_ttl_seconds: int = 86400

    # Analysis report cache TTL in days
    analysis_report_ttl_days: int = 30

    # Leadership and market intelligence cache TTLs in seconds
    leadership_ttl_seconds: int = 86400  # 24 hours — officers/governance change rarely
    market_intelligence_ttl_seconds: int = 3600  # 1 hour — analyst data changes daily

    # Per-adapter max concurrent requests (rate limiting via semaphore)
    fmp_concurrency: int = 10
    finnhub_concurrency: int = 5
    yfinance_concurrency: int = 2
    twelvedata_concurrency: int = 5
    sec_concurrency: int = 2

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
    groq_api_key: str = ""
    sec_contact_email: str = ""

    # Auth — Clerk publishable key used to derive the JWKS URL automatically.
    # Set CLERK_PUBLISHABLE_KEY in .env (same value as NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY).
    clerk_publishable_key: str = ""

    # CORS — comma-separated list of allowed origins.
    # Defaults to production domains; override in .env for local dev.
    allowed_origins: str = "https://investhub.tech,https://www.investhub.tech"

    # File upload — maximum accepted file size in bytes (default 10 MB)
    upload_max_bytes: int = 10 * 1024 * 1024

    @computed_field  # type: ignore[prop-decorator]
    @property
    def clerk_jwks_url(self) -> str:
        """Derive the Clerk JWKS URL from the publishable key.

        Clerk publishable keys encode the frontend API domain as base64 after
        the ``pk_test_`` / ``pk_live_`` prefix, terminated by a ``$`` sentinel.
        Example: ``pk_test_c2ltcGxl...`` → ``simple-kite-73.clerk.accounts.dev``
        """
        key = self.clerk_publishable_key
        if not key:
            return ""
        for prefix in ("pk_test_", "pk_live_"):
            if key.startswith(prefix):
                encoded = key[len(prefix) :]
                # Add padding if needed then decode
                padding = (4 - len(encoded) % 4) % 4
                domain = base64.b64decode(encoded + "=" * padding).decode().rstrip("$")
                return f"https://{domain}/.well-known/jwks.json"
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @field_validator(
        "quote_providers",
        "financials_providers",
        "profile_providers",
        "price_history_providers",
        "logo_providers",
        "leadership_providers",
        "market_intelligence_providers",
        mode="before",
    )
    @classmethod
    def parse_provider_list(cls, value: str | list) -> list[str]:
        if isinstance(value, str):
            return [p.strip() for p in value.split(",") if p.strip()]
        return value


settings = Settings()
