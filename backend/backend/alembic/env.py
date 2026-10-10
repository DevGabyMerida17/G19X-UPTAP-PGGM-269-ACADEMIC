"""
env.py de Alembic, adaptado para el engine async de app/core/database.py.

Dos modos:
- offline: genera el SQL sin conectarse (alembic upgrade --sql)
- online: se conecta de verdad y corre las migraciones (el caso normal)

target_metadata viene de Base.metadata, con TODOS los modelos ya
importados vía app.models — así, después de la migración inicial
(0001, que carga db/schema.sql tal cual), `alembic revision --autogenerate`
sí puede detectar cambios futuros comparando modelos vs. base de datos.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

import app.models  # noqa: F401 — registra todos los modelos en Base.metadata
from app.core.config import settings
from app.core.database import Base

config = context.config

# La URL sale de Settings (.env), no de alembic.ini, para no duplicar config.
_async_url = str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", _async_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
