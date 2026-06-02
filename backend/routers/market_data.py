from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ProviderUnavailableError
from db.pg import get_db_session
from models.market_data import CompanyIdentity, Financials, Quote
from services.identity import resolve_identity
from services.market_data_service import MarketDataService
from services.provider_registry import registry

router = APIRouter(prefix="/api/v1", tags=["market-data"])

_TICKER_PATH = Path(..., min_length=1, max_length=10, pattern=r"^[A-Z0-9.\-]+$")


def get_market_data_service() -> MarketDataService:
    return MarketDataService(registry)


@router.get("/quote/{ticker}", response_model=Quote)
async def get_quote(
    ticker: str = _TICKER_PATH,
    exchange: str | None = Query(default=None, description="Exchange hint, e.g. TSX"),
    session: AsyncSession = Depends(get_db_session),
    service: MarketDataService = Depends(get_market_data_service),
) -> Quote:
    try:
        identity = await resolve_identity(ticker.upper(), "fmp", session, exchange)
        return await service.get_quote(
            ticker.upper(), identity.security_id, session, exchange_hint=exchange
        )
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/financials/{ticker}", response_model=Financials)
async def get_financials(
    ticker: str = _TICKER_PATH,
    exchange: str | None = Query(default=None, description="Exchange hint, e.g. TSX"),
    session: AsyncSession = Depends(get_db_session),
    service: MarketDataService = Depends(get_market_data_service),
) -> Financials:
    try:
        identity = await resolve_identity(ticker.upper(), "fmp", session, exchange)
        return await service.get_financials(
            ticker.upper(), identity.security_id, session, exchange_hint=exchange
        )
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/profile/{ticker}", response_model=CompanyIdentity)
async def get_profile(
    ticker: str = _TICKER_PATH,
    exchange: str | None = Query(default=None, description="Exchange hint, e.g. TSX"),
    session: AsyncSession = Depends(get_db_session),
    service: MarketDataService = Depends(get_market_data_service),
) -> CompanyIdentity:
    try:
        identity = await resolve_identity(ticker.upper(), "fmp", session, exchange)
        return await service.get_profile(
            ticker.upper(), identity.security_id, session, exchange_hint=exchange
        )
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
