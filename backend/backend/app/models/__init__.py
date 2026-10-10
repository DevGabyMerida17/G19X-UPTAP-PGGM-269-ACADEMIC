"""
Importa todos los modelos en un solo lugar. Alembic (env.py) importa este
módulo para que Base.metadata conozca todas las tablas al generar una
migración automática — un modelo que no se importe aquí, Alembic no lo ve.
"""
from app.models.agents import AgentConversation, AIAgent, Message
from app.models.audit import AuditLog, SupervisorFollowup
from app.models.onboarding import Document, OnboardingProcess, OnboardingTemplate, Task, TemplateChecklistItem
from app.models.org import Department, Position
from app.models.quiz import (
    ModuleQuiz,
    QuizAttempt,
    QuizAttemptAnswer,
    QuizExceptionCase,
    QuizOption,
    QuizQuestion,
)
from app.models.rbac import Permission, Role, RolePermission
from app.models.training import ModuleMaterial, TrainingModule, TrainingProgress
from app.models.users import User, UserProfile

__all__ = [
    "AgentConversation", "AIAgent", "Message",
    "AuditLog", "SupervisorFollowup",
    "Document", "OnboardingProcess", "OnboardingTemplate", "Task", "TemplateChecklistItem",
    "Department", "Position",
    "ModuleQuiz", "QuizAttempt", "QuizAttemptAnswer", "QuizExceptionCase", "QuizOption", "QuizQuestion",
    "Permission", "Role", "RolePermission",
    "ModuleMaterial", "TrainingModule", "TrainingProgress",
    "User", "UserProfile",
]
