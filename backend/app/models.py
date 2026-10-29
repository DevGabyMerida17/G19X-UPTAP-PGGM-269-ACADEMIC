"""Tablas de la base de datos (PostgreSQL)."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

AREAS = ("Desarrollo", "Consultoría", "Capacitación", "Recursos Humanos")


def ahora() -> datetime:
    return datetime.now(timezone.utc)


class Programa(Base):
    __tablename__ = "programas"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120), unique=True)
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    modulos: Mapped[list["Modulo"]] = relationship(back_populates="programa", order_by="Modulo.orden")


class Rol(Base):
    """Catálogo de roles. Qué puede hacer cada uno se define con datos en rol_permisos, no en el código."""
    __tablename__ = "roles"
    clave: Mapped[str] = mapped_column(String(20), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    permisos: Mapped[list["Permiso"]] = relationship(secondary="rol_permisos", order_by="Permiso.clave")


class Permiso(Base):
    __tablename__ = "permisos"
    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    descripcion: Mapped[str] = mapped_column(String(200), default="")


class RolPermiso(Base):
    __tablename__ = "rol_permisos"
    rol_clave: Mapped[str] = mapped_column(ForeignKey("roles.clave"), primary_key=True)
    permiso_clave: Mapped[str] = mapped_column(ForeignKey("permisos.clave"), primary_key=True)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    entra_oid: Mapped[str | None] = mapped_column(String(64), unique=True)
    rol: Mapped[str] = mapped_column(ForeignKey("roles.clave"), default="colaborador")
    puesto: Mapped[str] = mapped_column(String(120), default="")
    area: Mapped[str] = mapped_column(String(60), default="Desarrollo")
    fecha_ingreso: Mapped[date] = mapped_column(Date, default=date.today)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    programa_id: Mapped[int | None] = mapped_column(ForeignKey("programas.id"))
    # Responsable (supervisor) que da seguimiento a este colaborador; lo asigna RH.
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    programa: Mapped[Programa | None] = relationship()
    # True mientras use la contraseña temporal que le dio RH: debe crear una propia al entrar.
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=False)
    supervisor: Mapped["Usuario | None"] = relationship(remote_side="Usuario.id")
    foto_ruta: Mapped[str] = mapped_column(String(400), default="")  # foto de perfil que sube la persona

    @property
    def tiene_foto(self) -> bool:
        return bool(self.foto_ruta)

    @property
    def pendiente_activacion(self) -> bool:
        """Aún no crea su propia contraseña (no tiene ninguna o sigue con la temporal)."""
        return self.debe_cambiar_password or (not self.password_hash and not self.entra_oid)


class Modulo(Base):
    __tablename__ = "modulos"
    id: Mapped[int] = mapped_column(primary_key=True)
    programa_id: Mapped[int] = mapped_column(ForeignKey("programas.id"))
    titulo: Mapped[str] = mapped_column(String(160))
    minutos: Mapped[int] = mapped_column(Integer, default=10)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Lista de {"titulo": str, "contenido": str}
    secciones: Mapped[list] = mapped_column(JSON, default=list)
    puntuacion_minima: Mapped[int] = mapped_column(Integer, default=70)
    # Cuántas veces se puede presentar la evaluación (RH lo cambia por módulo).
    intentos_maximos: Mapped[int] = mapped_column(Integer, default=3)
    programa: Mapped[Programa] = relationship(back_populates="modulos")
    preguntas: Mapped[list["Pregunta"]] = relationship(back_populates="modulo", order_by="Pregunta.id")


class Pregunta(Base):
    __tablename__ = "preguntas"
    id: Mapped[int] = mapped_column(primary_key=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("modulos.id"))
    texto: Mapped[str] = mapped_column(Text)
    opciones: Mapped[list] = mapped_column(JSON)
    correcta: Mapped[int] = mapped_column(Integer)
    retroalimentacion: Mapped[str] = mapped_column(Text, default="")
    modulo: Mapped[Modulo] = relationship(back_populates="preguntas")


class ProgresoModulo(Base):
    __tablename__ = "progreso_modulos"
    __table_args__ = (UniqueConstraint("usuario_id", "modulo_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("modulos.id"))
    secciones_leidas: Mapped[int] = mapped_column(Integer, default=0)
    completado: Mapped[bool] = mapped_column(Boolean, default=False)
    completado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Intentos adicionales que el responsable o RH le concedió en la evaluación de este módulo.
    intentos_extra: Mapped[int] = mapped_column(Integer, default=0)


class Evaluacion(Base):
    __tablename__ = "evaluaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("modulos.id"))
    calificacion: Mapped[int] = mapped_column(Integer)
    aprobada: Mapped[bool] = mapped_column(Boolean)
    respuestas: Mapped[list] = mapped_column(JSON)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    # Retroalimentación del Agente Evaluador (se genera una vez y se guarda).
    retro_ia: Mapped[dict | None] = mapped_column(JSON)
    modulo: Mapped[Modulo] = relationship()


class Tarea(Base):
    __tablename__ = "tareas"
    id: Mapped[int] = mapped_column(primary_key=True)
    etapa: Mapped[str] = mapped_column(String(30))  # Día 1, Semana 1, Mes 1
    titulo: Mapped[str] = mapped_column(String(200))
    orden: Mapped[int] = mapped_column(Integer, default=0)


class TareaColaborador(Base):
    __tablename__ = "tareas_colaborador"
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), primary_key=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"), primary_key=True)
    hecha: Mapped[bool] = mapped_column(Boolean, default=False)


class TipoDocumento(Base):
    __tablename__ = "tipos_documento"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(160))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    orden: Mapped[int] = mapped_column(Integer, default=0)


class DocumentoColaborador(Base):
    __tablename__ = "documentos_colaborador"
    __table_args__ = (UniqueConstraint("usuario_id", "tipo_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tipo_id: Mapped[int] = mapped_column(ForeignKey("tipos_documento.id"))
    estado: Mapped[str] = mapped_column(String(20), default="revision")  # revision, validado, rechazado
    nota: Mapped[str] = mapped_column(String(300), default="")
    archivo_nombre: Mapped[str] = mapped_column(String(200), default="")
    archivo_ruta: Mapped[str] = mapped_column(String(400), default="")
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    tipo: Mapped[TipoDocumento] = relationship()
    usuario: Mapped[Usuario] = relationship()


class DocumentoConocimiento(Base):
    """Documentos de la empresa que usa el Tutor IA para responder (RAG)."""
    __tablename__ = "documentos_conocimiento"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(160))
    tema: Mapped[str] = mapped_column(String(60), default="")
    contenido: Mapped[str] = mapped_column(Text)
    modulo_id: Mapped[int | None] = mapped_column(ForeignKey("modulos.id"))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora, onupdate=ahora)


class Comentario(Base):
    __tablename__ = "comentarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    colaborador_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    # Queda vacío si se eliminó a quien lo escribió: el comentario se conserva en el historial del colaborador.
    autor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(20), default="comentario")  # comentario, solicitud, apoyo, seguimiento
    texto: Mapped[str] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
    autor: Mapped[Usuario | None] = relationship(foreign_keys=[autor_id])

    @property
    def autor_nombre(self) -> str:
        return self.autor.nombre if self.autor else "Usuario eliminado"


class ConsultaTutor(Base):
    """Registro de preguntas al Tutor, para las métricas de RH."""
    __tablename__ = "consultas_tutor"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    pregunta: Mapped[str] = mapped_column(Text)
    intencion: Mapped[str] = mapped_column(String(30), default="")
    tema: Mapped[str | None] = mapped_column(String(60))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora)
