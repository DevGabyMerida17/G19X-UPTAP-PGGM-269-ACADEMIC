import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class OnboardingProcessCreate(BaseModel):
    user_id: uuid.UUID
    template_id: uuid.UUID | None = None
    start_date: date


class OnboardingProcessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    progress_percentage: float
    start_date: date
    created_at: datetime


class TeamMemberProgress(BaseModel):
    """Fila de la vista del supervisor — un colaborador de su equipo con
    su avance. No es 1:1 con una tabla: es el resultado de un JOIN."""
    user_id: uuid.UUID
    full_name: str
    process_id: uuid.UUID
    status: str
    progress_percentage: float
