"""Módulos de capacitación, su material y el avance por proceso — schema.sql §6."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class TrainingModule(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "training_modules"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")

    materials: Mapped[list["ModuleMaterial"]] = relationship(
        back_populates="module", cascade="all, delete-orphan"
    )


class ModuleMaterial(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Diapositivas, PDFs, imágenes de un módulo. Varios por módulo.
    Solo admin_rh sube/edita (permiso materials.manage) — ver decisión
    en Definicion_MVP_Onboarding.docx §4.2."""
    __tablename__ = "module_materials"

    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    file_type: Mapped[str | None] = mapped_column(String(50))
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Foto del rol al momento de subir — no depende del rol actual de uploaded_by.
    uploaded_by_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    module: Mapped["TrainingModule"] = relationship(back_populates="materials")


class TrainingProgress(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "training_progress"
    __table_args__ = (UniqueConstraint("process_id", "module_id"),)

    process_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_processes.id", ondelete="CASCADE"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_modules.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="bloqueado")
    progress_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
