"""Catálogo organizacional — schema.sql §1."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class Department(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # FK a users, ver models/users.py
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")

    positions: Mapped[list["Position"]] = relationship(back_populates="department")


class Position(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "positions"

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")

    department: Mapped["Department"] = relationship(back_populates="positions")
