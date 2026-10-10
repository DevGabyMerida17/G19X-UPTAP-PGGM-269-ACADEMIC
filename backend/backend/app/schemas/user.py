"""Esquemas Pydantic (request/response) para el recurso de usuarios.

Nunca se exponen los modelos de SQLAlchemy directo en la API — siempre
pasan por un esquema, aunque sea 1:1 con la tabla, para no filtrar
columnas internas por accidente (p. ej. entra_id) y para poder validar
la entrada antes de que le llegue a la base de datos.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    role_id: uuid.UUID
    manager_id: uuid.UUID | None
    position_id: uuid.UUID | None
    department_id: uuid.UUID | None
    status: str
    hire_date: date | None
    created_at: datetime


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    role_id: uuid.UUID
    manager_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    contract_type: str | None = None
    work_mode: str | None = None
    hire_date: date | None = None
