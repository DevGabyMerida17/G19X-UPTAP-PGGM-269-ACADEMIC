"""Panel administrativo de Recursos Humanos."""
import re
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from .. import asistente_rh, cache, config, correo, ia, permisos, rag
from ..db import get_db
from ..models import (
    AREAS, Comentario, ConsultaTutor, DocumentoColaborador, DocumentoConocimiento, Evaluacion, Modulo, Pregunta,
    Programa, ProgresoModulo, Rol, TareaColaborador, Usuario,
)
from ..seguridad import (
    cerrar_todas_las_sesiones, hash_password, password_temporal, requiere_permiso, usuario_actual,
)
from ..servicios import ficha
from ..validaciones import validar_correo, validar_nombre

router = APIRouter(prefix="/api/rh", tags=["rh"])  # cada ruta pide su permiso (ver app/permisos.py)


def _colaboradores(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).where(Usuario.rol == "colaborador").order_by(Usuario.fecha_ingreso.desc())))


# ---------- Panel ----------
@router.get("/panel", dependencies=[Depends(requiere_permiso(permisos.PANEL_VER))])
def panel(db: Session = Depends(get_db)):
    fichas = [ficha(db, u) for u in _colaboradores(db)]
    inicio_mes = date.today().replace(day=1)
    completados_mes = db.scalar(
        select(func.count(func.distinct(ProgresoModulo.usuario_id))).where(ProgresoModulo.completado)
        .where(ProgresoModulo.completado_en >= datetime.combine(inicio_mes, datetime.min.time(), timezone.utc))
    ) or 0
    temas = db.execute(
        select(ConsultaTutor.tema, func.count()).where(ConsultaTutor.tema.is_not(None))
        .group_by(ConsultaTutor.tema).order_by(func.count().desc()).limit(8)
    ).all()
    activos = [f for f in fichas if f["activo"]]
    por_modulo = []
    for m in db.scalars(select(Modulo).where(Modulo.activo).order_by(Modulo.programa_id, Modulo.orden)):
        asignados = [f for f in activos if f["programa_id"] == m.programa_id]
        if not asignados:
            continue
        hechos = db.scalar(select(func.count()).select_from(ProgresoModulo)
                           .where(ProgresoModulo.modulo_id == m.id, ProgresoModulo.completado)) or 0
        por_modulo.append({"modulo": m.titulo, "porcentaje": round(hechos / len(asignados) * 100)})
    return {
        "procesos_activos": sum(f["estado"] in ("en_curso", "retrasado") for f in fichas),
        "completados": sum(f["estado"] == "completado" for f in fichas),
        "modulos_completados_mes": completados_mes,
        "documentos_por_revisar": db.scalar(select(func.count()).select_from(DocumentoColaborador)
                                            .where(DocumentoColaborador.estado == "revision")) or 0,
        "alertas_retraso": sum(f["estado"] == "retrasado" for f in fichas),
        "procesos": fichas,
        "temas": [{"tema": t, "consultas": n} for t, n in temas],
        "finalizacion_modulos": por_modulo,
    }


# ---------- Personal: alta, responsables y bajas ----------


class NuevoUsuario(BaseModel):
    nombre: str = Field(max_length=120)
    correo: str
    rol: str = "colaborador"
    puesto: str = Field(min_length=2, max_length=120)
    area: str
    fecha_ingreso: date = Field(default_factory=date.today)
    programa_id: int | None = None
    supervisor_id: int | None = None

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, v: str) -> str:
        return validar_correo(v)

    @field_validator("nombre")
    @classmethod
    def nombre_valido(cls, v: str) -> str:
        return validar_nombre(v)


class CambioUsuario(BaseModel):
    activo: bool | None = None
    programa_id: int | None = None
    puesto: str | None = None
    area: str | None = None
    supervisor_id: int | None = None  # enviar null explícitamente para quitar al responsable
    nombre: str | None = Field(default=None, max_length=120)

    @field_validator("nombre")
    @classmethod
    def nombre_valido(cls, v: str | None) -> str | None:
        return validar_nombre(v) if v is not None else None


def _validar_supervisor(db: Session, sid: int | None) -> None:
    if sid is None:
        return
    s = db.get(Usuario, sid)
    if not s or s.rol != "supervisor" or not s.activo:
        raise HTTPException(400, "El responsable debe ser un supervisor activo.")


def _a_cargo(db: Session, sid: int) -> int:
    return db.scalar(select(func.count()).select_from(Usuario)
                     .where(Usuario.supervisor_id == sid, Usuario.rol == "colaborador", Usuario.activo)) or 0


def _personal_json(db: Session, u: Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "correo": u.correo, "rol": u.rol, "puesto": u.puesto, "area": u.area,
            "activo": u.activo, "pendiente_activacion": u.pendiente_activacion, "tiene_foto": u.tiene_foto,
            "a_cargo": _a_cargo(db, u.id) if u.rol == "supervisor" else None}


def _asignar_temporal(u: Usuario) -> str:
    """Contraseña temporal al azar; la persona debe cambiarla en su primer inicio de sesión."""
    temporal = password_temporal()
    u.password_hash = hash_password(temporal)
    u.debe_cambiar_password = True
    return temporal


@router.get("/colaboradores", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def colaboradores(db: Session = Depends(get_db)):
    return [ficha(db, u) for u in _colaboradores(db)]


@router.get("/personal", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def personal(db: Session = Depends(get_db)):
    """Supervisores y personal de RH."""
    filas = db.scalars(select(Usuario).where(Usuario.rol != "colaborador").order_by(Usuario.rol, Usuario.nombre))
    return [_personal_json(db, u) for u in filas]


@router.get("/roles", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def roles(db: Session = Depends(get_db)):
    """Catálogo de roles con sus permisos, tal como están guardados en la base de datos."""
    return [{"clave": r.clave, "nombre": r.nombre, "permisos": [p.clave for p in r.permisos]}
            for r in db.scalars(select(Rol).order_by(Rol.clave))]


@router.get("/responsables", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def responsables(db: Session = Depends(get_db)):
    filas = db.scalars(select(Usuario).where(Usuario.rol == "supervisor", Usuario.activo).order_by(Usuario.nombre))
    return [{"id": s.id, "nombre": s.nombre, "area": s.area, "a_cargo": _a_cargo(db, s.id)} for s in filas]


@router.post("/usuarios", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def crear_usuario(datos: NuevoUsuario, tareas: BackgroundTasks, db: Session = Depends(get_db)):
    """RH da de alta a la persona. La respuesta trae la contraseña temporal: RH la ve una sola vez
    y se la entrega; al entrar por primera vez la persona crea la suya."""
    if not db.get(Rol, datos.rol):  # los roles válidos son los del catálogo (tabla roles)
        raise HTTPException(400, "Rol no válido.")
    if datos.area not in AREAS:
        raise HTTPException(400, "Área no válida.")
    if db.scalar(select(Usuario).where(Usuario.correo == datos.correo)):
        raise HTTPException(409, "Ya existe un usuario con ese correo.")
    extra = {}
    if datos.rol == "colaborador":
        programa_id = datos.programa_id or db.scalar(select(Programa.id).order_by(Programa.id).limit(1))
        if not db.get(Programa, programa_id):
            raise HTTPException(400, "Programa no válido.")
        _validar_supervisor(db, datos.supervisor_id)
        extra = {"programa_id": programa_id, "supervisor_id": datos.supervisor_id}
    u = Usuario(nombre=datos.nombre, correo=datos.correo, rol=datos.rol, puesto=datos.puesto.strip(),
                area=datos.area, fecha_ingreso=datos.fecha_ingreso, **extra)
    temporal = _asignar_temporal(u)
    db.add(u)
    db.commit()
    cache.publicar("colaborador", id=u.id)
    datos_usuario = ficha(db, u) if u.rol == "colaborador" else _personal_json(db, u)
    # También se le envían sus datos de acceso por correo.
    tareas.add_task(correo.bienvenida, u.nombre, u.correo, temporal, True)
    return {**datos_usuario, "password_temporal": temporal, "correo_configurado": bool(config.SMTP_HOST)}


@router.patch("/usuarios/{uid}", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def editar_usuario(uid: int, datos: CambioUsuario, yo: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado.")
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("activo") is False and u.id == yo.id:
        raise HTTPException(400, "No puedes darte de baja a ti mismo.")
    if "area" in cambios and cambios["area"] not in AREAS:
        raise HTTPException(400, "Área no válida.")
    if cambios.get("programa_id") is not None and not db.get(Programa, cambios["programa_id"]):
        raise HTTPException(400, "Programa no válido.")
    if "supervisor_id" in cambios:
        if u.rol != "colaborador":
            raise HTTPException(400, "Solo los colaboradores tienen responsable.")
        _validar_supervisor(db, cambios["supervisor_id"])
    for k, v in cambios.items():
        if v is not None or k == "supervisor_id":
            setattr(u, k, v)
    if cambios.get("activo") is False:
        # Si tenía la sesión abierta, en su siguiente acción verá el aviso de baja y se le cerrará
        # (lo hace seguridad.usuario_actual).
        if u.rol == "supervisor":  # sus colaboradores quedan sin responsable para reasignarlos
            for c in db.scalars(select(Usuario).where(Usuario.supervisor_id == u.id)):
                c.supervisor_id = None
    db.commit()
    cache.publicar("colaborador", id=u.id)
    return ficha(db, u) if u.rol == "colaborador" else _personal_json(db, u)


@router.post("/usuarios/{uid}/password-temporal", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def nueva_password_temporal(uid: int, tareas: BackgroundTasks, yo: Usuario = Depends(usuario_actual),
                            db: Session = Depends(get_db)):
    """Para quien perdió su contraseña temporal o no tiene acceso a su correo."""
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado.")
    if u.id == yo.id:
        raise HTTPException(400, "Para cambiar tu propia contraseña usa \"¿Olvidaste tu contraseña?\".")
    if not u.activo:
        raise HTTPException(400, "La cuenta está dada de baja. Reactívala primero.")
    temporal = _asignar_temporal(u)
    db.commit()
    cerrar_todas_las_sesiones(u.id)
    tareas.add_task(correo.bienvenida, u.nombre, u.correo, temporal, False)
    return {"password_temporal": temporal, "correo_configurado": bool(config.SMTP_HOST)}



@router.delete("/usuarios/{uid}", dependencies=[Depends(requiere_permiso(permisos.PERSONAL_GESTIONAR))])
def eliminar_usuario(uid: int, yo: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Borra a la persona y todo su registro (avance, evaluaciones, documentos, comentarios y consultas).
    Los comentarios que escribió sobre otros colaboradores se conservan sin autor.
    No se puede deshacer; para conservar el historial está "Dar de baja"."""
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado.")
    if u.id == yo.id:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta.")
    archivos = [Path(d.archivo_ruta) for d in db.scalars(select(DocumentoColaborador).where(DocumentoColaborador.usuario_id == uid))
                if d.archivo_ruta] + ([Path(u.foto_ruta)] if u.foto_ruta else [])
    for c in db.scalars(select(Usuario).where(Usuario.supervisor_id == uid)):  # sus colaboradores quedan sin responsable
        c.supervisor_id = None
    for tabla in (ProgresoModulo, Evaluacion, TareaColaborador, DocumentoColaborador, ConsultaTutor):
        db.execute(delete(tabla).where(tabla.usuario_id == uid))
    db.execute(delete(Comentario).where(Comentario.colaborador_id == uid))
    # Lo que escribió sobre otros colaboradores se conserva, como "Usuario eliminado"
    db.execute(update(Comentario).where(Comentario.autor_id == uid).values(autor_id=None))
    db.delete(u)
    db.commit()
    for a in archivos:
        a.unlink(missing_ok=True)
    cerrar_todas_las_sesiones(uid)
    cache.r().delete(f"chat:{uid}")
    cache.publicar("colaborador", id=uid)
    return {"ok": True}

# ---------- Programas y módulos ----------
class NuevoPrograma(BaseModel):
    titulo: str = Field(min_length=3, max_length=120)
    descripcion: str = Field(default="", max_length=300)


class NuevoModulo(BaseModel):
    programa_id: int
    titulo: str = Field(min_length=3, max_length=160)
    minutos: int = Field(default=10, ge=1, le=600)
    contenido: str = Field(min_length=10, description="Secciones separadas con '## Título'")


class CambioModulo(BaseModel):
    activo: bool | None = None
    titulo: str | None = None
    puntuacion_minima: int | None = Field(default=None, ge=0, le=100)
    intentos_maximos: int | None = Field(default=None, ge=1, le=10)
    programa_id: int | None = None


def _secciones(contenido: str) -> list[dict]:
    salida = []
    for bloque in re.split(r"^## ", contenido.strip(), flags=re.M):
        bloque = bloque.strip()
        if bloque:
            titulo, _, texto = bloque.partition("\n")
            salida.append({"titulo": titulo.strip(), "contenido": texto.strip() or titulo.strip()})
    return salida


def _modulo_json(db: Session, m: Modulo) -> dict:
    return {"id": m.id, "titulo": m.titulo, "programa_id": m.programa_id, "programa": m.programa.titulo,
            "minutos": m.minutos, "orden": m.orden, "activo": m.activo, "secciones": len(m.secciones),
            "preguntas": len(m.preguntas), "puntuacion_minima": m.puntuacion_minima,
            "intentos_maximos": m.intentos_maximos or 3}


@router.get("/programas", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def programas(db: Session = Depends(get_db)):
    salida = []
    for p in db.scalars(select(Programa).order_by(Programa.id)):
        n = db.scalar(select(func.count()).select_from(Usuario).where(Usuario.programa_id == p.id, Usuario.activo))
        salida.append({"id": p.id, "titulo": p.titulo, "descripcion": p.descripcion,
                       "modulos": sum(m.activo for m in p.modulos), "colaboradores": n})
    return salida


@router.post("/programas", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def crear_programa(datos: NuevoPrograma, db: Session = Depends(get_db)):
    if db.scalar(select(Programa).where(Programa.titulo == datos.titulo.strip())):
        raise HTTPException(409, "Ya existe un programa con ese nombre.")
    p = Programa(titulo=datos.titulo.strip(), descripcion=datos.descripcion.strip())
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.get("/modulos", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def modulos(db: Session = Depends(get_db)):
    return [_modulo_json(db, m) for m in db.scalars(select(Modulo).order_by(Modulo.programa_id, Modulo.orden, Modulo.id))]


@router.post("/modulos", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def crear_modulo(datos: NuevoModulo, db: Session = Depends(get_db)):
    if not db.get(Programa, datos.programa_id):
        raise HTTPException(400, "Programa no válido.")
    orden = (db.scalar(select(func.max(Modulo.orden)).where(Modulo.programa_id == datos.programa_id)) or 0) + 1
    m = Modulo(programa_id=datos.programa_id, titulo=datos.titulo.strip(), minutos=datos.minutos, orden=orden,
               secciones=_secciones(datos.contenido))
    db.add(m)
    db.flush()
    # El contenido del módulo también alimenta al Tutor IA.
    db.add(DocumentoConocimiento(titulo=m.titulo, tema="", contenido=datos.contenido, modulo_id=m.id))
    db.commit()
    rag.reconstruir(db)
    return _modulo_json(db, m)


@router.patch("/modulos/{mid}", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def editar_modulo(mid: int, datos: CambioModulo, db: Session = Depends(get_db)):
    m = db.get(Modulo, mid)
    if not m:
        raise HTTPException(404, "Módulo no encontrado.")
    for k, v in datos.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    db.commit()
    return _modulo_json(db, m)


@router.post("/modulos/{mid}/mover/{direccion}", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def mover_modulo(mid: int, direccion: str, db: Session = Depends(get_db)):
    m = db.get(Modulo, mid)
    if not m or direccion not in ("arriba", "abajo"):
        raise HTTPException(404, "Módulo no encontrado.")
    hermanos = list(db.scalars(select(Modulo).where(Modulo.programa_id == m.programa_id).order_by(Modulo.orden, Modulo.id)))
    i = hermanos.index(m)
    j = i - 1 if direccion == "arriba" else i + 1
    if 0 <= j < len(hermanos):
        hermanos[i], hermanos[j] = hermanos[j], hermanos[i]
        for orden, h in enumerate(hermanos):
            h.orden = orden
        db.commit()
    return {"ok": True}


# ---------- Revisión de documentos de colaboradores ----------
class Rechazo(BaseModel):
    nota: str = Field(min_length=3, max_length=300)


@router.get("/documentos", dependencies=[Depends(requiere_permiso(permisos.DOCUMENTOS_REVISAR))])
def documentos_por_revisar(db: Session = Depends(get_db)):
    docs = db.scalars(select(DocumentoColaborador).order_by(DocumentoColaborador.estado != "revision",
                                                           DocumentoColaborador.actualizado_en.desc()).limit(100))
    return [{"id": d.id, "colaborador": d.usuario.nombre, "puesto": d.usuario.puesto, "documento": d.tipo.titulo,
             "estado": d.estado, "nota": d.nota, "archivo": d.archivo_nombre,
             "tiene_archivo": bool(d.archivo_ruta), "fecha": d.actualizado_en.isoformat()} for d in docs]


@router.get("/documentos/{did}/archivo", dependencies=[Depends(requiere_permiso(permisos.DOCUMENTOS_REVISAR))])
def ver_archivo(did: int, db: Session = Depends(get_db)):
    d = db.get(DocumentoColaborador, did)
    if not d or not d.archivo_ruta or not Path(d.archivo_ruta).is_file():
        raise HTTPException(404, "Archivo no encontrado.")
    return FileResponse(d.archivo_ruta, filename=d.archivo_nombre)


def _revisar(db: Session, did: int, estado: str, nota: str) -> dict:
    d = db.get(DocumentoColaborador, did)
    if not d:
        raise HTTPException(404, "Documento no encontrado.")
    d.estado, d.nota = estado, nota
    db.commit()
    cache.publicar("documento", id=d.usuario_id)
    return {"ok": True}


@router.post("/documentos/{did}/validar", dependencies=[Depends(requiere_permiso(permisos.DOCUMENTOS_REVISAR))])
def validar_documento(did: int, db: Session = Depends(get_db)):
    return _revisar(db, did, "validado", "Validado por RH")


@router.post("/documentos/{did}/rechazar", dependencies=[Depends(requiere_permiso(permisos.DOCUMENTOS_REVISAR))])
def rechazar_documento(did: int, datos: Rechazo, db: Session = Depends(get_db)):
    return _revisar(db, did, "rechazado", datos.nota.strip())


# ---------- Asistente de RH (agente de IA con los datos de la plataforma) ----------
class MensajeAsistente(BaseModel):
    rol: str
    texto: str


class PreguntaAsistente(BaseModel):
    pregunta: str = Field(min_length=2, max_length=1000)
    historial: list[MensajeAsistente] = []


@router.post("/asistente", dependencies=[Depends(requiere_permiso(permisos.ASISTENTE_RH_USAR))])
def asistente(datos: PreguntaAsistente, yo: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if cache.limite_excedido(f"asistente_rh:{yo.id}", 15):
        raise HTTPException(429, "Hiciste muchas preguntas seguidas. Espera un minuto.")
    llm = ia.obtener_llm()  # 503 si la IA no está configurada
    try:
        respuesta = asistente_rh.responder(llm, datos.pregunta.strip(), [m.model_dump() for m in datos.historial],
                                           asistente_rh.datos_plataforma(db), yo.nombre)
    except Exception as e:
        raise HTTPException(502, f"El Asistente de RH no respondió ({type(e).__name__}). Intenta de nuevo.") from e
    return {"agente": asistente_rh.AGENTE_RH, "respuesta": respuesta}


# ---------- Base de conocimiento del Tutor IA ----------
class DocConocimiento(BaseModel):
    titulo: str = Field(min_length=3, max_length=160)
    tema: str = Field(default="", max_length=60)
    contenido: str = Field(min_length=10)
    modulo_id: int | None = None


def _doc_json(d: DocumentoConocimiento) -> dict:
    return {"id": d.id, "titulo": d.titulo, "tema": d.tema, "contenido": d.contenido, "modulo_id": d.modulo_id,
            "actualizado_en": d.actualizado_en.isoformat() if d.actualizado_en else None}


@router.get("/conocimiento", dependencies=[Depends(requiere_permiso(permisos.CONOCIMIENTO_GESTIONAR))])
def conocimiento(db: Session = Depends(get_db)):
    return [_doc_json(d) for d in db.scalars(select(DocumentoConocimiento).order_by(DocumentoConocimiento.titulo))]


@router.post("/conocimiento", dependencies=[Depends(requiere_permiso(permisos.CONOCIMIENTO_GESTIONAR))])
def crear_conocimiento(datos: DocConocimiento, db: Session = Depends(get_db)):
    d = DocumentoConocimiento(**datos.model_dump())
    db.add(d)
    db.commit()
    rag.reconstruir(db)
    return _doc_json(d)


@router.put("/conocimiento/{did}", dependencies=[Depends(requiere_permiso(permisos.CONOCIMIENTO_GESTIONAR))])
def editar_conocimiento(did: int, datos: DocConocimiento, db: Session = Depends(get_db)):
    d = db.get(DocumentoConocimiento, did)
    if not d:
        raise HTTPException(404, "Documento no encontrado.")
    for k, v in datos.model_dump().items():
        setattr(d, k, v)
    db.commit()
    rag.reconstruir(db)
    return _doc_json(d)


@router.delete("/conocimiento/{did}", dependencies=[Depends(requiere_permiso(permisos.CONOCIMIENTO_GESTIONAR))])
def eliminar_conocimiento(did: int, db: Session = Depends(get_db)):
    d = db.get(DocumentoConocimiento, did)
    if not d:
        raise HTTPException(404, "Documento no encontrado.")
    db.delete(d)
    db.commit()
    rag.reconstruir(db)
    return {"ok": True}


# ---------- Actividades (preguntas de evaluación) ----------
class NuevaPregunta(BaseModel):
    modulo_id: int
    texto: str = Field(min_length=5)
    opciones: list[str] = Field(min_length=2, max_length=6)
    correcta: int
    retroalimentacion: str = ""

    @field_validator("opciones")
    @classmethod
    def sin_vacias(cls, v: list[str]) -> list[str]:
        v = [o.strip() for o in v]
        if any(not o for o in v):
            raise ValueError("Las opciones no pueden estar vacías.")
        return v


@router.get("/preguntas", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def preguntas(db: Session = Depends(get_db)):
    return [{"id": p.id, "texto": p.texto, "opciones": p.opciones, "correcta": p.correcta,
             "modulo_id": p.modulo_id, "modulo": p.modulo.titulo, "minimo": p.modulo.puntuacion_minima}
            for p in db.scalars(select(Pregunta).order_by(Pregunta.id.desc()))]


@router.post("/preguntas", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def crear_pregunta(datos: NuevaPregunta, db: Session = Depends(get_db)):
    if not db.get(Modulo, datos.modulo_id):
        raise HTTPException(400, "Módulo no válido.")
    if not 0 <= datos.correcta < len(datos.opciones):
        raise HTTPException(400, "La respuesta correcta no corresponde a ninguna opción.")
    p = Pregunta(**datos.model_dump())
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.delete("/preguntas/{pid}", dependencies=[Depends(requiere_permiso(permisos.CAPACITACION_GESTIONAR))])
def eliminar_pregunta(pid: int, db: Session = Depends(get_db)):
    p = db.get(Pregunta, pid)
    if not p:
        raise HTTPException(404, "Pregunta no encontrada.")
    db.delete(p)
    db.commit()
    return {"ok": True}
