"""
Cuestionarios de fin de módulo y el flujo de excepción cuando se agotan
los intentos — schema.sql §6.1 y §7.1.

Reglas de negocio que vive esta parte del modelo (no están en la base de
datos, van en el servicio que las use):
  - Máximo 3 intentos "regulares" (module_quizzes.max_attempts).
  - Un 4o intento SOLO es válido colgado de un QuizExceptionCase en
    estado 'en_recuperacion' — nunca como intento regular.
  - Aprobar es obligatorio para que TrainingProgress pase a 'completado'.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class ModuleQuiz(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "module_quizzes"

    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_modules.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200))
    passing_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=70)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "quiz_questions"

    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("module_quizzes.id", ondelete="CASCADE"), nullable=False
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(100))  # para "principales dificultades"
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quiz: Mapped["ModuleQuiz"] = relationship(back_populates="questions")
    options: Mapped[list["QuizOption"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QuizOption(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "quiz_options"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False
    )
    option_text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    question: Mapped["QuizQuestion"] = relationship(back_populates="options")


class QuizAttempt(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "quiz_attempts"
    __table_args__ = (UniqueConstraint("process_id", "quiz_id", "attempt_number"),)

    process_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_processes.id", ondelete="CASCADE"), nullable=False
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("module_quizzes.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    answers: Mapped[list["QuizAttemptAnswer"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class QuizAttemptAnswer(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "quiz_attempt_answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_questions.id"), nullable=False)
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_options.id"))
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="answers")


class QuizExceptionCase(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Se abre automáticamente al reprobar el 3er intento. El checklist
    "Acciones realizadas" que ve RH NO se guarda aparte — se deriva de
    training_progress + estas marcas de tiempo (ver comentario en
    schema.sql sobre esta tabla)."""
    __tablename__ = "quiz_exception_cases"

    process_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_processes.id", ondelete="CASCADE"), nullable=False
    )
    quiz_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("module_quizzes.id"), nullable=False)
    triggering_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quiz_attempts.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="abierto")
    best_score: Mapped[float | None] = mapped_column(Numeric(5, 2))

    reinforcement_strategy: Mapped[str | None] = mapped_column(Text)
    reinforcement_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_conversations.id")
    )
    reinforcement_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recovery_attempt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_attempts.id"))

    # TODO de negocio, no técnico: falta la regla de a quién se asigna
    # (¿siempre supervisor primero? ¿siempre RH? ¿depende de si tiene
    # supervisor?). Ver PRD.md §11. Por ahora queda NULL hasta que el
    # servicio de escalamiento decida y lo llene.
    escalated_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    escalation_recommendation: Mapped[str | None] = mapped_column(Text)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
