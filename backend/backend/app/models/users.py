"""Usuarios (colaboradores, supervisores, RH) — schema.sql §1."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    entra_id: Mapped[str | None] = mapped_column(String(200), unique=True)

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    position_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("positions.id"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))

    contract_type: Mapped[str | None] = mapped_column(String(40))
    work_mode: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    hire_date: Mapped[date | None] = mapped_column(Date)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped["Role"] = relationship(foreign_keys=[role_id])  # noqa: F821

    # Auto-referencia (users.manager_id -> users.id, "supervisa" en el ERD).
    # `manager`: el supervisor directo de este usuario (many-to-one).
    # `direct_reports`: el equipo que supervisa este usuario (one-to-many) —
    # es exactamente el filtro que arma la vista del supervisor.
    manager: Mapped["User | None"] = relationship(
        remote_side="User.id", back_populates="direct_reports"
    )
    direct_reports: Mapped[list["User"]] = relationship(back_populates="manager")


class UserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    phone: Mapped[str | None] = mapped_column(String(30))
    profile_photo: Mapped[str | None] = mapped_column(String(500))
    emergency_contact: Mapped[str | None] = mapped_column(String(200))
    emergency_phone: Mapped[str | None] = mapped_column(String(30))
