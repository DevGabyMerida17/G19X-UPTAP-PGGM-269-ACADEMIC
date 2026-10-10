"""
Conexión a PostgreSQL con SQLAlchemy 2.0 (estilo async).

Uso típico en un endpoint:

    @router.get("/example")
    async def example(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User).where(User.id == user_id))
        ...
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# El driver async de PostgreSQL es asyncpg; psycopg (sync) se usa solo en Alembic.
_ASYNC_DATABASE_URL = str(settings.DATABASE_URL).replace(
    "postgresql://", "postgresql+asyncpg://", 1
)

engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # evita usar conexiones muertas tras inactividad
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Clase base para todos los modelos — ver app/models/."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency de FastAPI: una sesión por request, cerrada al final."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
