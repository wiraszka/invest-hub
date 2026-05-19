from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ProviderUnavailableError
from db.pg import get_db_session
from models.market_data import CompanyIdentity, Financials, Quote
from services.market_data_service import MarketDataService
from services.provider_registry import registry

router = APIRouter(prefix="/api/v1", tags=["market-data"])


def get_market_data_service() -> MarketDataService:
    return MarketDataService(registry)


@router.get("/quote/{ticker}", response_model=Quote)
async def get_quote(
    ticker: str,
    exchange: str | None = Query(default=None, description="Exchange hint, e.g. TSX"),
    session: AsyncSession = Depends(get_db_session),
    service: MarketDataService = Depends(get_market_data_service),
) -> Quote:
    try:
        return await service.get_quote(ticker.upper(), session, exchange_hint=exchange)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/financials/{ticker}", response_model=Financials)
async def get_financials(
    ticker: str,
    exchange: str | None = Query(default=None, description="Exchange hint, e.g. TSX"),
    session: AsyncSession = Depends(get_db_session),
    service: MarketDataService = Depends(get_market_data_service),
) -> Financials:
    try:
        return await service.get_financials(ticker.upper(), session, exchange_hint=exchange)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/profile/{ticker}", response_model=CompanyIdentity)
async def get_profile(
    ticker: str,
    exchange: str | None = Query(default=None, description="Exchange hint, e.g. TSX"),
    session: AsyncSession = Depends(get_db_session),
    service: MarketDataService = Depends(get_market_data_service),
) -> CompanyIdentity:
    try:
        return await service.get_profile(ticker.upper(), session, exchange_hint=exchange)
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
