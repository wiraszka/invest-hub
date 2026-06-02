from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from core.config import settings

# asyncpg rejects libpq-style query params — strip them and use connect_args for SSL
_STRIP_PARAMS = {"sslmode", "channel_binding", "connect_timeout"}

_engine: AsyncEngine | None = None


def _async_url() -> str:
    url = settings.database_url
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    filtered = {
        k: v[0] for k, v in parse_qs(parsed.query).items() if k not in _STRIP_PARAMS
    }
    return urlunparse(parsed._replace(query=urlencode(filtered)))


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # NullPool is required for Vercel serverless — each invocation is stateless
        _engine = create_async_engine(
            _async_url(), poolclass=NullPool, connect_args={"ssl": True}
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a session factory using the correctly-configured async engine.

    Use this in standalone scripts instead of rolling a custom engine, so that
    URL param stripping (channel_binding, sslmode, etc.) is applied consistently.
    """
    return async_sessionmaker(
        _get_engine(), expire_on_commit=False, class_=AsyncSession
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    session_factory = async_sessionmaker(
        _get_engine(), expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as session:
        yield session
