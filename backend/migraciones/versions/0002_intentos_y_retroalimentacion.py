"""Límite de intentos por evaluación, intentos extra y retroalimentación del Agente Evaluador.

Revisión: 0002
Anterior: 0001
Fecha: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("modulos") as t:
        t.add_column(sa.Column("intentos_maximos", sa.Integer(), nullable=False, server_default="3"))
    with op.batch_alter_table("progreso_modulos") as t:
        t.add_column(sa.Column("intentos_extra", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("evaluaciones") as t:
        t.add_column(sa.Column("retro_ia", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evaluaciones") as t:
        t.drop_column("retro_ia")
    with op.batch_alter_table("progreso_modulos") as t:
        t.drop_column("intentos_extra")
    with op.batch_alter_table("modulos") as t:
        t.drop_column("intentos_maximos")
