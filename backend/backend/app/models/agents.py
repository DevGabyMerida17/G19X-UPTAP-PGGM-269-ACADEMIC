"""Catálogo de agentes y el historial de chat — schema.sql §9 y §10."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class AIAgent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "ai_agents"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # orquestador | tutor | preguntas | evaluador | recomendador | documentos | seguimiento
    agent_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")


class AgentConversation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "agent_conversations"

    process_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_processes.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_agents.id"))
    title: Mapped[str | None] = mapped_column(String(200))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="activa")

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False
    )
    sender: Mapped[str] = mapped_column(String(20), nullable=False)  # usuario | agente
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int | None] = mapped_column(Integer)

    conversation: Mapped["AgentConversation"] = relationship(back_populates="messages")
