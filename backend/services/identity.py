from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.pg_models import Company, CompanyProviderXref
from models.market_data import CompanyIdentity

_OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"


async def resolve_identity(
    ticker: str,
    provider: str,
    session: AsyncSession,
    exchange_hint: str | None = None,
) -> CompanyIdentity:
    """
    Return a canonical CompanyIdentity for the given provider ticker.
    Checks the xref table first; falls back to OpenFIGI; falls back to a stub entry.
    """
    # 1. Check xref for an existing mapping
    result = await session.execute(
        select(Company)
        .join(CompanyProviderXref, Company.canonical_id == CompanyProviderXref.canonical_id)
        .where(
            CompanyProviderXref.provider == provider,
            CompanyProviderXref.provider_ticker == ticker,
        )
    )
    company_row = result.scalars().first()
    if company_row:
        return CompanyIdentity(
            canonical_id=str(company_row.canonical_id),
            isin=company_row.isin,
            figi=company_row.figi,
            name=company_row.name,
            exchange=company_row.exchange,
            currency=company_row.currency,
        )

    # 2. Try OpenFIGI
    identity = await _lookup_openfigi(ticker, exchange_hint)

    # 3. Fall back to a stub if OpenFIGI returns nothing
    if identity is None:
        identity = CompanyIdentity(name=ticker)

    # 4. Upsert into companies + xref
    await _upsert_company(identity, ticker, provider, session)
    await session.commit()
    return identity


async def _lookup_openfigi(ticker: str, exchange_code: str | None) -> CompanyIdentity | None:
    payload: list[dict] = [{"idType": "TICKER", "idValue": ticker}]
    if exchange_code:
        payload[0]["exchCode"] = exchange_code

    headers = {"Content-Type": "application/json"}
    if settings.openfigi_api_key:
        headers["X-OPENFIGI-APIKEY"] = settings.openfigi_api_key

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(_OPENFIGI_URL, json=payload, headers=headers)
            if not response.is_success:
                return None
            data = response.json()
            if not data or not data[0].get("data"):
                return None

            entry = data[0]["data"][0]
            return CompanyIdentity(
                figi=entry.get("figi"),
                name=entry.get("name") or ticker,
                exchange=entry.get("exchCode"),
                currency=entry.get("marketSector"),  # OpenFIGI doesn't return currency directly
            )
    except Exception:
        return None


async def _upsert_company(
    identity: CompanyIdentity,
    provider_ticker: str,
    provider: str,
    session: AsyncSession,
) -> str:
    """Upsert into companies and company_provider_xref. Returns canonical_id."""
    # Upsert company — match on ISIN or FIGI if available, else always insert
    canonical_id = str(uuid.uuid4())

    company_stmt = insert(Company).values(
        canonical_id=canonical_id,
        isin=identity.isin,
        figi=identity.figi,
        name=identity.name,
        exchange=identity.exchange,
        currency=identity.currency,
    )

    if identity.isin:
        company_stmt = company_stmt.on_conflict_do_update(
            index_elements=["isin"],
            set_={"name": identity.name, "figi": identity.figi, "exchange": identity.exchange},
        ).returning(Company.canonical_id)
    elif identity.figi:
        company_stmt = company_stmt.on_conflict_do_update(
            index_elements=["figi"],
            set_={"name": identity.name, "isin": identity.isin, "exchange": identity.exchange},
        ).returning(Company.canonical_id)
    else:
        company_stmt = company_stmt.on_conflict_do_nothing().returning(Company.canonical_id)

    result = await session.execute(company_stmt)
    row = result.fetchone()
    if row:
        canonical_id = str(row[0])

    # Upsert xref
    xref_stmt = insert(CompanyProviderXref).values(
        canonical_id=canonical_id,
        provider=provider,
        provider_ticker=provider_ticker,
    ).on_conflict_do_update(
        index_elements=["provider", "provider_ticker"],
        set_={"canonical_id": canonical_id},
    )
    await session.execute(xref_stmt)

    identity.canonical_id = canonical_id
    return canonical_id
