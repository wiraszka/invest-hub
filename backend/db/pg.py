from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# asyncpg rejects libpq-style query params — strip them and use connect_args for SSL
_STRIP_PARAMS = {"sslmode", "channel_binding", "connect_timeout"}

_engine: AsyncEngine | None = None


def _async_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    filtered = {k: v[0] for k, v in parse_qs(parsed.query).items() if k not in _STRIP_PARAMS}
    return urlunparse(parsed._replace(query=urlencode(filtered)))


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # NullPool is required for Vercel serverless — each invocation is stateless
        _engine = create_async_engine(_async_url(), poolclass=NullPool, connect_args={"ssl": True})
    return _engine


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    session_factory = async_sessionmaker(_get_engine(), expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
