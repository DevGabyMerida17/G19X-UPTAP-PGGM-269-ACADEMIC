"""Esquema inicial: las tablas de la primera versión de la plataforma.

Revisión: 0001
Fecha: 2026-10-26
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('programas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=120), nullable=False),
    sa.Column('descripcion', sa.String(length=300), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('titulo')
    )
    op.create_table('tareas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('etapa', sa.String(length=30), nullable=False),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('tipos_documento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=160), nullable=False),
    sa.Column('descripcion', sa.String(length=300), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('modulos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('programa_id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=160), nullable=False),
    sa.Column('minutos', sa.Integer(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('secciones', sa.JSON(), nullable=False),
    sa.Column('puntuacion_minima', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['programa_id'], ['programas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.Column('correo', sa.String(length=200), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=True),
    sa.Column('entra_oid', sa.String(length=64), nullable=True),
    sa.Column('rol', sa.String(length=20), nullable=False),
    sa.Column('puesto', sa.String(length=120), nullable=False),
    sa.Column('area', sa.String(length=60), nullable=False),
    sa.Column('fecha_ingreso', sa.Date(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('programa_id', sa.Integer(), nullable=True),
    sa.Column('supervisor_id', sa.Integer(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
    sa.Column('debe_cambiar_password', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['programa_id'], ['programas.id'], ),
    sa.ForeignKeyConstraint(['supervisor_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entra_oid')
    )
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuarios_correo'), ['correo'], unique=True)
        batch_op.create_index(batch_op.f('ix_usuarios_supervisor_id'), ['supervisor_id'], unique=False)

    op.create_table('comentarios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('colaborador_id', sa.Integer(), nullable=False),
    sa.Column('autor_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['colaborador_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comentarios', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comentarios_colaborador_id'), ['colaborador_id'], unique=False)

    op.create_table('consultas_tutor',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('pregunta', sa.Text(), nullable=False),
    sa.Column('intencion', sa.String(length=30), nullable=False),
    sa.Column('tema', sa.String(length=60), nullable=True),
    sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('documentos_colaborador',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tipo_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.String(length=20), nullable=False),
    sa.Column('nota', sa.String(length=300), nullable=False),
    sa.Column('archivo_nombre', sa.String(length=200), nullable=False),
    sa.Column('archivo_ruta', sa.String(length=400), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['tipo_id'], ['tipos_documento.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'tipo_id')
    )
    with op.batch_alter_table('documentos_colaborador', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_documentos_colaborador_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('documentos_conocimiento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=160), nullable=False),
    sa.Column('tema', sa.String(length=60), nullable=False),
    sa.Column('contenido', sa.Text(), nullable=False),
    sa.Column('modulo_id', sa.Integer(), nullable=True),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['modulo_id'], ['modulos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('evaluaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('modulo_id', sa.Integer(), nullable=False),
    sa.Column('calificacion', sa.Integer(), nullable=False),
    sa.Column('aprobada', sa.Boolean(), nullable=False),
    sa.Column('respuestas', sa.JSON(), nullable=False),
    sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['modulo_id'], ['modulos.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('evaluaciones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_evaluaciones_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('preguntas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('modulo_id', sa.Integer(), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('opciones', sa.JSON(), nullable=False),
    sa.Column('correcta', sa.Integer(), nullable=False),
    sa.Column('retroalimentacion', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['modulo_id'], ['modulos.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('progreso_modulos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('modulo_id', sa.Integer(), nullable=False),
    sa.Column('secciones_leidas', sa.Integer(), nullable=False),
    sa.Column('completado', sa.Boolean(), nullable=False),
    sa.Column('completado_en', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['modulo_id'], ['modulos.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'modulo_id')
    )
    with op.batch_alter_table('progreso_modulos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_progreso_modulos_usuario_id'), ['usuario_id'], unique=False)

    op.create_table('tareas_colaborador',
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('tarea_id', sa.Integer(), nullable=False),
    sa.Column('hecha', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['tarea_id'], ['tareas.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('usuario_id', 'tarea_id')
    )


def downgrade() -> None:
    op.drop_table('tareas_colaborador')
    with op.batch_alter_table('progreso_modulos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_progreso_modulos_usuario_id'))

    op.drop_table('progreso_modulos')
    op.drop_table('preguntas')
    with op.batch_alter_table('evaluaciones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_evaluaciones_usuario_id'))

    op.drop_table('evaluaciones')
    op.drop_table('documentos_conocimiento')
    with op.batch_alter_table('documentos_colaborador', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_documentos_colaborador_usuario_id'))

    op.drop_table('documentos_colaborador')
    op.drop_table('consultas_tutor')
    with op.batch_alter_table('comentarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comentarios_colaborador_id'))

    op.drop_table('comentarios')
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuarios_supervisor_id'))
        batch_op.drop_index(batch_op.f('ix_usuarios_correo'))

    op.drop_table('usuarios')
    op.drop_table('modulos')
    op.drop_table('tipos_documento')
    op.drop_table('tareas')
    op.drop_table('programas')
