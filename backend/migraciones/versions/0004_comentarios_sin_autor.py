"""Los comentarios pueden quedar sin autor: al eliminar a una persona se conserva lo que escribió
sobre otros colaboradores, mostrado como "Usuario eliminado".

Revisión: 0004
Anterior: 0003
Fecha: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("comentarios") as t:
        t.alter_column("autor_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM comentarios WHERE autor_id IS NULL")
    with op.batch_alter_table("comentarios") as t:
        t.alter_column("autor_id", existing_type=sa.Integer(), nullable=False)
