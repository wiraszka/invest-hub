from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.openfigi import OpenFIGIAdapter
from db.pg_models import Security, SecurityProviderXref
from models.market_data import CompanyIdentity

_openfigi = OpenFIGIAdapter()


async def resolve_identity(
    ticker: str,
    provider: str,
    session: AsyncSession,
    exchange_hint: str | None = None,
) -> CompanyIdentity:
    """
    Return a canonical CompanyIdentity for the given provider ticker.

    Always the first step before any data fetch.  Checks the xref table
    first; falls back to OpenFIGI; falls back to a stub entry.

    Returns only identity fields (security_id, isin, figi, name, exchange,
    currency).  Profile enrichment fields are populated by get_profile().
    """
    # 1. Check xref for an existing mapping
    result = await session.execute(
        select(Security)
        .join(
            SecurityProviderXref,
            Security.id == SecurityProviderXref.security_id,
        )
        .where(
            SecurityProviderXref.provider == provider,
            SecurityProviderXref.provider_ticker == ticker,
        )
    )
    security_row = result.scalars().first()
    if security_row:
        return CompanyIdentity(
            security_id=str(security_row.id),
            isin=security_row.isin,
            figi=security_row.figi,
            name=security_row.name,
            exchange=security_row.exchange,
            currency=security_row.currency,
        )

    # 2. Try OpenFIGI
    openfigi_response = await _openfigi.lookup(ticker, exchange_hint)
    identity = openfigi_response.data

    # 3. Fall back to a stub if OpenFIGI returns nothing
    if identity is None:
        identity = CompanyIdentity(name=ticker)

    # 4. Upsert into securities + xref
    await _upsert_security(identity, ticker, provider, session)
    await session.commit()
    return identity


async def _upsert_security(
    identity: CompanyIdentity,
    provider_ticker: str,
    provider: str,
    session: AsyncSession,
) -> str:
    """Upsert into securities and security_provider_xref. Returns security id."""
    security_id = str(uuid.uuid4())

    security_stmt = insert(Security).values(
        id=security_id,
        isin=identity.isin,
        figi=identity.figi,
        name=identity.name,
        exchange=identity.exchange,
        currency=identity.currency,
    )

    if identity.isin:
        security_stmt = security_stmt.on_conflict_do_update(
            index_elements=["isin"],
            set_={
                "name": identity.name,
                "figi": identity.figi,
                "exchange": identity.exchange,
            },
        ).returning(Security.id)
    elif identity.figi:
        security_stmt = security_stmt.on_conflict_do_update(
            index_elements=["figi"],
            set_={
                "name": identity.name,
                "isin": identity.isin,
                "exchange": identity.exchange,
            },
        ).returning(Security.id)
    else:
        security_stmt = security_stmt.on_conflict_do_nothing().returning(Security.id)

    result = await session.execute(security_stmt)
    row = result.fetchone()
    if row:
        security_id = str(row[0])

    # Upsert xref
    xref_stmt = (
        insert(SecurityProviderXref)
        .values(
            security_id=security_id,
            provider=provider,
            provider_ticker=provider_ticker,
        )
        .on_conflict_do_update(
            index_elements=["provider", "provider_ticker"],
            set_={"security_id": security_id},
        )
    )
    await session.execute(xref_stmt)

    identity.security_id = security_id
    return security_id
