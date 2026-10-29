"""Foto de perfil: cada persona puede subir la suya.

Revisión: 0005
Anterior: 0004
Fecha: 2026-10-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as t:
        t.add_column(sa.Column("foto_ruta", sa.String(length=400), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as t:
        t.drop_column("foto_ruta")
