from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Ensure the backend/ root is on the path so db.pg_models can be imported
backend_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_root))

# Load .env so DATABASE_URL_UNPOOLED is available
load_dotenv(backend_root / ".env")

from db.pg_models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# asyncpg rejects libpq-style query params — strip them and pass ssl via connect_args
_STRIP_PARAMS = {"sslmode", "channel_binding", "connect_timeout"}


def _migration_url() -> str:
    url = os.environ.get("DATABASE_URL_UNPOOLED", os.environ.get("DATABASE_URL", ""))
    url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    filtered = {k: v[0] for k, v in parse_qs(parsed.query).items() if k not in _STRIP_PARAMS}
    return urlunparse(parsed._replace(query=urlencode(filtered)))


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        _migration_url(),
        poolclass=pool.NullPool,
        connect_args={"ssl": True},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
