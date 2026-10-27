"""Configuración de Alembic: usa la misma conexión y los mismos modelos que la API."""
from alembic import context

from app import models  # noqa: F401  (registra las tablas en Base.metadata)
from app.db import Base, engine

metadata = Base.metadata


def correr_sin_conexion() -> None:
    context.configure(url=str(engine.url), target_metadata=metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def correr_con_conexion() -> None:
    conexion = context.config.attributes.get("connection")
    if conexion is not None:  # la API pasa su propia conexión al arrancar
        _migrar(conexion)
        return
    with engine.connect() as conexion:
        _migrar(conexion)


def _migrar(conexion) -> None:
    # render_as_batch permite modificar tablas también en SQLite (desarrollo y pruebas).
    context.configure(connection=conexion, target_metadata=metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    correr_sin_conexion()
else:
    correr_con_conexion()
