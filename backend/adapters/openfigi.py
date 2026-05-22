from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from core.config import settings
from models.market_data import CompanyIdentity, ProviderResponse

_OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
logger = logging.getLogger(__name__)


class OpenFIGIAdapter:
    name = "openfigi"

    async def lookup(
        self,
        ticker: str,
        exchange_hint: str | None = None,
    ) -> ProviderResponse[CompanyIdentity]:
        payload: list[dict] = [{"idType": "TICKER", "idValue": ticker}]
        if exchange_hint:
            payload[0]["exchCode"] = exchange_hint

        headers = {"Content-Type": "application/json"}
        if settings.openfigi_api_key:
            headers["X-OPENFIGI-APIKEY"] = settings.openfigi_api_key

        fetched_at = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(_OPENFIGI_URL, json=payload, headers=headers)
                if not response.is_success:
                    return ProviderResponse(
                        data=None, raw={}, provider=self.name, fetched_at=fetched_at,
                        error=f"OpenFIGI returned {response.status_code}",
                    )
                raw = response.json()
                if not raw or not raw[0].get("data"):
                    return ProviderResponse(
                        data=None, raw={}, provider=self.name, fetched_at=fetched_at,
                        error=f"No FIGI data for {ticker}",
                    )
                entry = raw[0]["data"][0]
                identity = CompanyIdentity(
                    figi=entry.get("figi"),
                    name=entry.get("name") or ticker,
                    exchange=entry.get("exchCode"),
                    currency=entry.get("marketSector"),
                )
                return ProviderResponse(data=identity, raw=entry, provider=self.name, fetched_at=fetched_at)
        except Exception as exc:
            logger.exception("openfigi lookup error", extra={"ticker": ticker})
            return ProviderResponse(data=None, raw={}, provider=self.name, fetched_at=fetched_at, error=str(exc))
