"""Roles y permisos como datos: tablas roles, permisos y rol_permisos, con su catálogo inicial.

Desde aquí, qué puede hacer cada rol se cambia agregando o borrando filas en rol_permisos,
sin modificar el código. usuarios.rol pasa a ser una llave foránea a roles.clave.

Revisión: 0003
Anterior: 0002
Fecha: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ROLES = [
    ("colaborador", "Colaborador"),
    ("supervisor", "Supervisor / Responsable"),
    ("rh", "Recursos Humanos"),
]

PERMISOS = [
    ("onboarding.propio", "Su propia ruta: documentos, capacitación, evaluaciones y Tutor IA"),
    ("equipo.seguimiento", "Ver y dar seguimiento a los colaboradores que tiene asignados"),
    ("evaluaciones.intento_extra", "Conceder un intento más en una evaluación"),
    ("eventos.tiempo_real", "Recibir avisos en vivo en los paneles"),
    ("panel.ver", "Ver el panel general de onboarding"),
    ("personal.gestionar", "Altas, bajas, responsables y contraseñas temporales de todo el personal"),
    ("capacitacion.gestionar", "Programas, módulos y preguntas de evaluación"),
    ("documentos.revisar", "Ver, validar y rechazar documentos"),
    ("conocimiento.gestionar", "Base de conocimiento del Tutor IA"),
    ("asistente_rh.usar", "Consultar al Asistente de RH"),
]

ROL_PERMISOS = {
    "colaborador": ["onboarding.propio"],
    "supervisor": ["equipo.seguimiento", "evaluaciones.intento_extra", "eventos.tiempo_real"],
    "rh": ["evaluaciones.intento_extra", "eventos.tiempo_real", "panel.ver", "personal.gestionar",
           "capacitacion.gestionar", "documentos.revisar", "conocimiento.gestionar", "asistente_rh.usar"],
}


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("clave", sa.String(length=20), nullable=False),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        sa.PrimaryKeyConstraint("clave"),
    )
    permisos = op.create_table(
        "permisos",
        sa.Column("clave", sa.String(length=60), nullable=False),
        sa.Column("descripcion", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("clave"),
    )
    rol_permisos = op.create_table(
        "rol_permisos",
        sa.Column("rol_clave", sa.String(length=20), nullable=False),
        sa.Column("permiso_clave", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(["permiso_clave"], ["permisos.clave"]),
        sa.ForeignKeyConstraint(["rol_clave"], ["roles.clave"]),
        sa.PrimaryKeyConstraint("rol_clave", "permiso_clave"),
    )
    op.bulk_insert(roles, [{"clave": c, "nombre": n} for c, n in ROLES])
    op.bulk_insert(permisos, [{"clave": c, "descripcion": d} for c, d in PERMISOS])
    op.bulk_insert(rol_permisos, [{"rol_clave": r, "permiso_clave": p} for r, ps in ROL_PERMISOS.items() for p in ps])

    with op.batch_alter_table("usuarios") as t:
        t.create_foreign_key("fk_usuarios_rol", "roles", ["rol"], ["clave"])


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as t:
        t.drop_constraint("fk_usuarios_rol", type_="foreignkey")
    op.drop_table("rol_permisos")
    op.drop_table("permisos")
    op.drop_table("roles")
