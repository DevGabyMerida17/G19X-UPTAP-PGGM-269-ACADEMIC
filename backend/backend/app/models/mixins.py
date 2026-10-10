"""
Mixins reutilizados por (casi) todos los modelos, para no repetir
id/created_at/updated_at en cada tabla — ver schema.sql para el DDL
del que salen estos modelos.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """Para las tablas que además llevan updated_at (ver schema.sql §18,
    los triggers set_updated_at en Postgres son quienes lo mantienen —
    el default de aquí solo cubre el INSERT inicial)."""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
