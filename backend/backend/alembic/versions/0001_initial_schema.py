"""Esquema inicial completo (35 tablas, incluye datos semilla de roles/permisos)

Revision ID: 0001
Revises:
Create Date: 2026-09-24

Esta migración no traduce cada tabla a op.create_table() — ejecuta
db/schema.sql directo. La razón: schema.sql ya es la fuente de verdad
revisada y versionada del modelo de datos (ver PRD.md y
Definicion_MVP_Onboarding.docx); reescribirla en la sintaxis de Alembic
sería una segunda copia que se puede desincronizar de la primera.

A partir de aquí, las migraciones siguientes SÍ deben generarse con
`alembic revision --autogenerate`, comparando los modelos de SQLAlchemy
(app/models/) contra la base de datos — no volver a este patrón de
"ejecutar un .sql a mano" salvo que sea, de nuevo, una carga inicial.
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def upgrade() -> None:
    sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    op.execute(sql)


def downgrade() -> None:
    raise NotImplementedError(
        "No hay downgrade automático para el esquema inicial — 35 tablas "
        "con datos semilla no se revierten con seguridad de forma genérica. "
        "Si necesitas deshacer esto, restaura desde un backup."
    )
