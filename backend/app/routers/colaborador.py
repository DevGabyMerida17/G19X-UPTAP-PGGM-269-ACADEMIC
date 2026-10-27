"""Portal del colaborador: su ruta, capacitación, evaluaciones y documentos."""
import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import cache, config, evaluador, ia, recomendador
from ..db import get_db
from ..models import (
    Comentario, DocumentoColaborador, DocumentoConocimiento, Evaluacion, Modulo, ProgresoModulo, Tarea,
    TareaColaborador, TipoDocumento, Usuario, ahora,
)
from ..permisos import ONBOARDING_PROPIO
from ..seguridad import requiere_permiso
from ..validaciones import nombre_de_pila
from ..servicios import (
    documentos_de, estado_modulos, evaluaciones_de, ficha, intentos, progreso_para_tutor, tareas_de,
)

router = APIRouter(prefix="/api/yo", tags=["colaborador"])
colaborador = requiere_permiso(ONBOARDING_PROPIO)

EXTENSIONES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _avisar(u: Usuario):
    cache.publicar("avance", id=u.id)


@router.get("/resumen")
def resumen(u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    supervisor = u.supervisor if u.supervisor and u.supervisor.activo else None
    observaciones = db.scalars(select(Comentario).where(Comentario.colaborador_id == u.id)
                               .order_by(Comentario.fecha.desc()).limit(5))
    return {
        **ficha(db, u),
        "supervisor": {"nombre": supervisor.nombre, "puesto": supervisor.puesto} if supervisor else None,
        "tareas": tareas_de(db, u),
        "modulos": estado_modulos(db, u),
        "documentos": documentos_de(db, u),
        "evaluaciones": evaluaciones_de(db, u),
        "observaciones": [{"texto": c.texto, "tipo": c.tipo, "autor": c.autor.nombre, "fecha": c.fecha.isoformat()}
                          for c in observaciones],
    }


class CambioTarea(BaseModel):
    hecha: bool


@router.put("/tareas/{tarea_id}")
def marcar_tarea(tarea_id: int, datos: CambioTarea, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    if not db.get(Tarea, tarea_id):
        raise HTTPException(404, "Tarea no encontrada.")
    t = db.get(TareaColaborador, (u.id, tarea_id)) or TareaColaborador(usuario_id=u.id, tarea_id=tarea_id)
    t.hecha = datos.hecha
    db.add(t)
    db.commit()
    _avisar(u)
    return {"ok": True}


# ---------- Capacitación ----------
def _modulo_disponible(db: Session, u: Usuario, modulo_id: int) -> tuple[Modulo, dict]:
    estado = next((m for m in estado_modulos(db, u) if m["id"] == modulo_id), None)
    if not estado:
        raise HTTPException(404, "Módulo no encontrado.")
    if estado["estado"] == "bloqueado":
        raise HTTPException(403, "Completa los módulos anteriores para desbloquear este.")
    return db.get(Modulo, modulo_id), estado


def _progreso(db: Session, u: Usuario, modulo_id: int) -> ProgresoModulo:
    p = db.scalar(select(ProgresoModulo).where(ProgresoModulo.usuario_id == u.id, ProgresoModulo.modulo_id == modulo_id))
    if not p:
        p = ProgresoModulo(usuario_id=u.id, modulo_id=modulo_id, secciones_leidas=0)
        db.add(p)
    return p


def _completar(db: Session, u: Usuario, m: Modulo):
    p = _progreso(db, u, m.id)
    p.completado, p.completado_en, p.secciones_leidas = True, ahora(), len(m.secciones)


@router.get("/modulos/{modulo_id}")
def ver_modulo(modulo_id: int, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    m, estado = _modulo_disponible(db, u, modulo_id)
    return {**estado, "secciones": m.secciones}


@router.post("/modulos/{modulo_id}/leer")
def leer_seccion(modulo_id: int, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    m, estado = _modulo_disponible(db, u, modulo_id)
    if estado["estado"] == "completado":
        return {"leidas": len(m.secciones)}
    p = _progreso(db, u, m.id)
    p.secciones_leidas = min((p.secciones_leidas or 0) + 1, len(m.secciones))
    db.commit()
    return {"leidas": p.secciones_leidas}


@router.post("/modulos/{modulo_id}/completar")
def completar_modulo(modulo_id: int, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    m, estado = _modulo_disponible(db, u, modulo_id)
    if m.preguntas:
        raise HTTPException(400, "Este módulo se completa al aprobar su evaluación.")
    if estado["leidas"] < estado["total"]:
        raise HTTPException(400, "Lee todas las secciones antes de completar el módulo.")
    _completar(db, u, m)
    db.commit()
    _avisar(u)
    return {"ok": True}


@router.get("/modulos/{modulo_id}/evaluacion")
def ver_evaluacion(modulo_id: int, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    m, estado = _modulo_disponible(db, u, modulo_id)
    if not m.preguntas:
        raise HTTPException(404, "Este módulo no tiene evaluación.")
    return {
        "modulo": m.titulo, "minimo": m.puntuacion_minima,
        "disponible": estado["leidas"] >= estado["total"],
        "intentos": intentos(db, u, m),
        "preguntas": [{"id": p.id, "texto": p.texto, "opciones": p.opciones} for p in m.preguntas],
    }


class Respuestas(BaseModel):
    respuestas: dict[int, int]  # id de pregunta -> índice de opción


@router.post("/modulos/{modulo_id}/evaluacion")
def contestar_evaluacion(modulo_id: int, datos: Respuestas, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    m, estado = _modulo_disponible(db, u, modulo_id)
    if not m.preguntas:
        raise HTTPException(404, "Este módulo no tiene evaluación.")
    if estado["leidas"] < estado["total"]:
        raise HTTPException(400, "Lee todo el módulo antes de presentar la evaluación.")
    it = intentos(db, u, m)
    if it["aprobada"]:
        raise HTTPException(400, "Ya aprobaste esta evaluación.")
    if it["agotados"]:
        raise HTTPException(403, f"Ya usaste tus {it['permitidos']} intentos de esta evaluación. Tu responsable o "
                                 "Recursos Humanos pueden concederte otro; mientras tanto, repasa el módulo.")
    resultado = []
    for p in m.preguntas:
        elegida = datos.respuestas.get(p.id, -1)
        resultado.append({"pregunta_id": p.id, "elegida": elegida, "correcta": p.correcta,
                          "acierto": elegida == p.correcta,
                          "retroalimentacion": "" if elegida == p.correcta else p.retroalimentacion})
    calificacion = round(sum(r["acierto"] for r in resultado) / len(resultado) * 100)
    aprobada = calificacion >= m.puntuacion_minima
    ev = Evaluacion(usuario_id=u.id, modulo_id=m.id, calificacion=calificacion, aprobada=aprobada, respuestas=resultado)
    db.add(ev)
    if aprobada:
        _completar(db, u, m)
    db.commit()
    _avisar(u)
    return {"evaluacion_id": ev.id, "calificacion": calificacion, "aprobada": aprobada, "minimo": m.puntuacion_minima,
            "resultado": resultado, "intentos": intentos(db, u, m)}


@router.post("/evaluaciones/{evaluacion_id}/retroalimentacion")
def retroalimentacion(evaluacion_id: int, u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    """Agente Evaluador: explica los errores y qué reforzar. Se genera una sola vez y se guarda."""
    ev = db.get(Evaluacion, evaluacion_id)
    if not ev or ev.usuario_id != u.id:
        raise HTTPException(404, "Evaluación no encontrada.")
    if ev.retro_ia:
        return ev.retro_ia
    m = ev.modulo
    por_id = {p.id: p for p in m.preguntas}
    preguntas = []
    for r in ev.respuestas or []:
        p = por_id.get(r["pregunta_id"])
        if p:
            preguntas.append({"texto": p.texto, "opciones": p.opciones, "elegida": r["elegida"],
                              "correcta": p.correcta, "acierto": r["acierto"]})
    contenido = "\n\n".join(f"{s['titulo']}\n{s['contenido']}" for s in m.secciones or [])
    datos = {"modulo": m.titulo, "contenido": contenido, "preguntas": preguntas, "calificacion": ev.calificacion,
             "minimo": m.puntuacion_minima, "aprobada": ev.aprobada,
             "intentos_restantes": intentos(db, u, m)["restantes"], "nombre": nombre_de_pila(u.nombre)}
    try:
        retro = evaluador.evaluar(ia.obtener_llm(), datos)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"El Agente Evaluador no respondió ({type(e).__name__}). Intenta de nuevo.") from e
    ev.retro_ia = retro
    db.commit()
    return retro


@router.get("/recomendaciones")
def recomendaciones(u: Usuario = Depends(colaborador), db: Session = Depends(get_db)):
    """Agente Recomendador para el colaborador. Se guarda en Redis mientras su avance no cambie."""
    progreso = progreso_para_tutor(db, u)
    temas = sorted({t for e in db.scalars(select(Evaluacion).where(Evaluacion.usuario_id == u.id)) if e.retro_ia
                    for t in e.retro_ia.get("temas_a_reforzar", [])})
    huella = hashlib.sha1(json.dumps([progreso, temas], sort_keys=True, default=str).encode()).hexdigest()[:16]
    clave = f"recomendaciones:{u.id}:{huella}"
    guardadas = cache.r().get(clave)
    if guardadas:
        return json.loads(guardadas)
    modulos = [{"id": m["id"], "titulo": m["titulo"], "estado": m["estado"]} for m in estado_modulos(db, u)]
    materiales = [d.titulo for d in db.scalars(select(DocumentoConocimiento).order_by(DocumentoConocimiento.titulo))]
    try:
        r = recomendador.recomendar_colaborador(ia.obtener_llm(), nombre_de_pila(u.nombre), progreso, modulos, materiales, temas)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"El Agente Recomendador no respondió ({type(e).__name__}). Intenta de nuevo.") from e
    cache.r().set(clave, json.dumps(r, ensure_ascii=False), ex=3600)
    return r


# ---------- Documentos ----------
@router.post("/documentos/{tipo_id}")
async def subir_documento(tipo_id: int, archivo: UploadFile = File(...), u: Usuario = Depends(colaborador),
                          db: Session = Depends(get_db)):
    tipo = db.get(TipoDocumento, tipo_id)
    if not tipo:
        raise HTTPException(404, "Tipo de documento no encontrado.")
    nombre = archivo.filename or "archivo"
    ext = ("." + nombre.rsplit(".", 1)[-1].lower()) if "." in nombre else ""
    if ext not in EXTENSIONES:
        raise HTTPException(400, "Solo se aceptan archivos PDF, JPG o PNG.")
    contenido = await archivo.read(config.MAX_ARCHIVO_MB * 1024 * 1024 + 1)
    if len(contenido) > config.MAX_ARCHIVO_MB * 1024 * 1024:
        raise HTTPException(400, f"El archivo supera {config.MAX_ARCHIVO_MB} MB.")

    doc = db.scalar(select(DocumentoColaborador).where(DocumentoColaborador.usuario_id == u.id,
                                                       DocumentoColaborador.tipo_id == tipo_id))
    if doc and doc.estado == "validado":
        raise HTTPException(400, "Este documento ya fue validado por RH.")
    carpeta = config.UPLOADS_DIR / str(u.id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{uuid.uuid4().hex}{ext}"
    ruta.write_bytes(contenido)

    doc = doc or DocumentoColaborador(usuario_id=u.id, tipo_id=tipo_id)
    doc.estado, doc.nota, doc.archivo_nombre, doc.archivo_ruta, doc.actualizado_en = \
        "revision", "", nombre[:200], str(ruta), ahora()
    db.add(doc)
    db.commit()
    cache.publicar("documento", id=u.id)
    return {"ok": True}
