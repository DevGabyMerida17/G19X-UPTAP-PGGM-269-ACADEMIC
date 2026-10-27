"""Aplica las migraciones y carga los datos iniciales la primera vez que arranca la API."""
import re
from datetime import date, timedelta

import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from . import config, correo
from .db import engine
from .seguridad import crear_enlace, hash_password
from .models import (
    DocumentoColaborador, DocumentoConocimiento, Evaluacion, Modulo, Pregunta, Programa, ProgresoModulo, Tarea,
    TareaColaborador, TipoDocumento, Usuario,
)

log = logging.getLogger("seed")

TAREAS = [
    ("Día 1", "Iniciar sesión con tu cuenta corporativa"),
    ("Día 1", "Revisar tu perfil y puesto"),
    ("Día 1", "Ver el video de bienvenida"),
    ("Día 1", "Conocer a tu supervisor"),
    ("Semana 1", "Subir tus documentos de ingreso"),
    ("Semana 1", "Completar el módulo de Políticas internas"),
    ("Semana 1", "Configurar tus herramientas de trabajo"),
    ("Mes 1", "Aprobar la evaluación de Seguridad"),
    ("Mes 1", "Completar Herramientas del área"),
    ("Mes 1", "Reunión de cierre con RH"),
]

TIPOS_DOCUMENTO = [
    ("Identificación oficial", "INE o pasaporte vigente"),
    ("Comprobante de domicilio", "No mayor a 3 meses"),
    ("Formato de datos bancarios", "Firmado en todas sus páginas"),
    ("Comprobante de estudios", "Título, cédula o constancia"),
]

# (archivo de conocimiento, minutos)
MODULOS_GENERALES = [("bienvenida.md", 8), ("politicas_internas.md", 20), ("seguridad.md", 15), ("herramientas.md", 25)]

PREGUNTAS_SEGURIDAD = [
    ("¿Qué debes hacer si recibes un correo sospechoso que pide tu contraseña?",
     ["Responder con mis datos", "Reportarlo al área de TI", "Reenviarlo a mis compañeros"], 1,
     "Los correos que piden credenciales suelen ser phishing; siempre se reportan a TI."),
    ("¿Dónde se guarda la información de clientes?",
     ["En una memoria USB", "En mi correo personal", "En los repositorios autorizados"], 2,
     "Solo los repositorios autorizados cumplen con las políticas de seguridad."),
    ("¿Qué ayuda más a proteger tu cuenta corporativa?",
     ["Verificación en dos pasos", "Usar la misma contraseña siempre", "Anotar la contraseña en el escritorio"], 0,
     "La verificación en dos pasos agrega una capa extra aunque alguien conozca tu contraseña."),
    ("¿Puedes compartir tus credenciales con un compañero de confianza?",
     ["Sí, si es de mi equipo", "No, nunca", "Solo por chat interno"], 1,
     "Las credenciales son personales; compartirlas rompe la trazabilidad de los accesos."),
]

# Responsables de ejemplo: nombre, correo, puesto, área
DEMO_SUPERVISORES = [
    ("Mariana López", "mariana.lopez@demo.pluri", "Líder de Desarrollo", "Desarrollo"),
    ("Jorge Castillo", "jorge.castillo@demo.pluri", "Gerente de Consultoría", "Consultoría"),
]

# nombre, correo, puesto, área, días desde ingreso, módulos completados, tareas hechas, docs validados,
# calificación seguridad, correo del responsable
DEMO = [
    ("Luis Ramírez", "luis.ramirez@demo.pluri", "Consultor", "Consultoría", 39, 4, 10, 4, 92, "jorge.castillo@demo.pluri"),
    ("Sofía Méndez", "sofia.mendez@demo.pluri", "Capacitadora", "Capacitación", 46, 1, 3, 1, None, "jorge.castillo@demo.pluri"),
    ("Diego Salas", "diego.salas@demo.pluri", "Desarrollador", "Desarrollo", 2, 0, 2, 0, None, "mariana.lopez@demo.pluri"),
    ("Carlos Ruiz", "carlos.ruiz@demo.pluri", "QA Tester", "Desarrollo", 24, 2, 5, 2, 65, "mariana.lopez@demo.pluri"),
    ("Valeria Núñez", "valeria.nunez@demo.pluri", "Analista de RH", "Recursos Humanos", 10, 1, 4, 1, None, None),
]


def leer_markdown(ruta) -> tuple[dict, str]:
    texto = ruta.read_text(encoding="utf-8")
    meta = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", texto, re.S)
    if m:
        for linea in m.group(1).splitlines():
            if ":" in linea:
                k, v = linea.split(":", 1)
                meta[k.strip()] = v.strip()
        texto = texto[m.end():]
    return meta, texto.strip()


def secciones(contenido: str) -> list[dict]:
    salida = []
    for bloque in re.split(r"^## ", contenido, flags=re.M):
        bloque = bloque.strip()
        if bloque:
            titulo, _, texto = bloque.partition("\n")
            salida.append({"titulo": titulo.strip(), "contenido": texto.strip()})
    return salida


def migrar() -> None:
    """Lleva la base a la última versión con las migraciones de Alembic (backend/migraciones/versions)."""
    cfg = Config(str(config.BASE_DIR / "alembic.ini"))
    with engine.begin() as con:
        cfg.attributes["connection"] = con
        tablas = inspect(con).get_table_names()
        if "usuarios" in tablas and "alembic_version" not in tablas:
            # Base creada antes de usar migraciones: se marca la versión que ya tiene para no recrear tablas.
            columnas = {c["name"] for c in inspect(con).get_columns("modulos")}
            actual = "0002" if "intentos_maximos" in columnas else "0001"
            command.stamp(cfg, actual)
            log.warning("Base existente marcada en la migración %s", actual)
        command.upgrade(cfg, "head")


def inicializar() -> None:
    migrar()
    with Session(engine) as db:
        if not db.scalar(select(Programa).limit(1)):
            _cargar_catalogos(db)
            if config.CARGAR_DATOS_DEMO:
                _cargar_demo(db)
            db.commit()
        _crear_admin(db)


def _crear_admin(db: Session) -> None:
    """Como nadie puede registrarse solo, la primera cuenta de RH sale del archivo .env."""
    if not config.ADMIN_CORREO or db.scalar(select(Usuario).where(Usuario.rol == "rh").limit(1)):
        return
    u = Usuario(nombre=config.ADMIN_NOMBRE, correo=config.ADMIN_CORREO, rol="rh", puesto="Recursos Humanos",
                area="Recursos Humanos",
                password_hash=hash_password(config.ADMIN_PASSWORD) if config.ADMIN_PASSWORD else None)
    db.add(u)
    db.commit()
    if not config.ADMIN_PASSWORD:
        token = crear_enlace("activar", u.id, config.HORAS_ENLACE_ACTIVACION * 3600)
        correo.invitacion(u.nombre, u.correo, token)
        log.warning("Cuenta de RH creada para %s. Se envió el correo para crear su contraseña.", u.correo)


def _cargar_catalogos(db: Session) -> None:
    general = Programa(titulo="Onboarding general", descripcion="Para todo el personal de nuevo ingreso")
    db.add_all([
        general,
        Programa(titulo="Onboarding Desarrollo", descripcion="Herramientas, repositorios y flujo Scrum"),
        Programa(titulo="Onboarding Consultoría", descripcion="Atención a clientes y metodologías"),
    ])
    db.flush()

    usados = set()
    for orden, (archivo, minutos) in enumerate(MODULOS_GENERALES):
        meta, contenido = leer_markdown(config.CONOCIMIENTO_DIR / archivo)
        m = Modulo(programa_id=general.id, titulo=meta["titulo"], minutos=minutos, orden=orden, secciones=secciones(contenido))
        db.add(m)
        db.flush()
        db.add(DocumentoConocimiento(titulo=meta["titulo"], tema=meta.get("tema", ""), contenido=contenido, modulo_id=m.id))
        usados.add(archivo)
        if archivo == "seguridad.md":
            for texto, opciones, correcta, retro in PREGUNTAS_SEGURIDAD:
                db.add(Pregunta(modulo_id=m.id, texto=texto, opciones=opciones, correcta=correcta, retroalimentacion=retro))

    # Documentos de conocimiento que no son módulo (p. ej. beneficios)
    for ruta in sorted(config.CONOCIMIENTO_DIR.glob("*.md")):
        if ruta.name not in usados:
            meta, contenido = leer_markdown(ruta)
            db.add(DocumentoConocimiento(titulo=meta.get("titulo", ruta.stem), tema=meta.get("tema", ""), contenido=contenido))

    db.add_all(Tarea(etapa=e, titulo=t, orden=i) for i, (e, t) in enumerate(TAREAS))
    db.add_all(TipoDocumento(titulo=t, descripcion=d, orden=i) for i, (t, d) in enumerate(TIPOS_DOCUMENTO))
    db.flush()


def _cargar_demo(db: Session) -> None:
    """Colaboradores de ejemplo para que los paneles de RH y supervisor tengan datos.
    No tienen contraseña, así que nadie puede entrar con ellos."""
    general = db.scalar(select(Programa).where(Programa.titulo == "Onboarding general"))
    modulos = list(db.scalars(select(Modulo).where(Modulo.programa_id == general.id).order_by(Modulo.orden)))
    seguridad = next(m for m in modulos if m.preguntas)
    tareas = list(db.scalars(select(Tarea).order_by(Tarea.orden)))
    tipos = list(db.scalars(select(TipoDocumento).order_by(TipoDocumento.orden)))

    sups = {}
    for nombre, correo_, puesto, area in DEMO_SUPERVISORES:
        s = Usuario(nombre=nombre, correo=correo_, puesto=puesto, area=area, rol="supervisor")
        db.add(s)
        db.flush()
        sups[correo_] = s.id

    for nombre, correo_, puesto, area, dias, n_mod, n_tar, n_doc, calif, sup in DEMO:
        u = Usuario(nombre=nombre, correo=correo_, puesto=puesto, area=area, rol="colaborador",
                    fecha_ingreso=date.today() - timedelta(days=dias), programa_id=general.id,
                    supervisor_id=sups.get(sup))
        db.add(u)
        db.flush()
        for m in modulos[:n_mod]:
            db.add(ProgresoModulo(usuario_id=u.id, modulo_id=m.id, secciones_leidas=len(m.secciones), completado=True))
        if calif is not None:
            db.add(Evaluacion(usuario_id=u.id, modulo_id=seguridad.id, calificacion=calif, aprobada=calif >= 70, respuestas=[]))
        for t in tareas[:n_tar]:
            db.add(TareaColaborador(usuario_id=u.id, tarea_id=t.id, hecha=True))
        for t in tipos[:n_doc]:
            db.add(DocumentoColaborador(usuario_id=u.id, tipo_id=t.id, estado="validado", archivo_nombre="ejemplo.pdf"))
