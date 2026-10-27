"""Seguimiento del supervisor: solo ve a los colaboradores que RH le asignó."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import cache, ia
from ..db import get_db
from ..models import Comentario, Modulo, ProgresoModulo, Usuario
from ..seguridad import requiere_rol
from ..servicios import estado_modulos, evaluaciones_de, ficha, intentos, progreso_para_tutor

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])
supervisor = requiere_rol("supervisor")

TIPOS = ("comentario", "solicitud", "apoyo", "seguimiento")


@router.post("/colaboradores/{uid}/modulos/{mid}/intento-extra")
def conceder_intento(uid: int, mid: int, quien: Usuario = Depends(requiere_rol("supervisor", "rh")),
                     db: Session = Depends(get_db)):
    """El responsable (de sus colaboradores) o RH (de cualquiera) concede un intento más en una evaluación."""
    u = db.get(Usuario, uid)
    if not u or u.rol != "colaborador" or (quien.rol == "supervisor" and u.supervisor_id != quien.id):
        raise HTTPException(404, "Ese colaborador no está asignado a ti.")
    m = db.get(Modulo, mid)
    if not m or not m.preguntas:
        raise HTTPException(404, "Ese módulo no tiene evaluación.")
    it = intentos(db, u, m)
    if it["aprobada"]:
        raise HTTPException(400, "Ya aprobó esta evaluación.")
    if not it["agotados"]:
        raise HTTPException(400, f"Todavía le quedan {it['restantes']} intento(s).")
    p = db.scalar(select(ProgresoModulo).where(ProgresoModulo.usuario_id == u.id, ProgresoModulo.modulo_id == m.id))
    if not p:
        p = ProgresoModulo(usuario_id=u.id, modulo_id=m.id, secciones_leidas=len(m.secciones or []))
        db.add(p)
    p.intentos_extra = (p.intentos_extra or 0) + 1
    db.add(Comentario(colaborador_id=u.id, autor_id=quien.id, tipo="seguimiento",
                      texto=f"Te concedí un intento más en la evaluación de {m.titulo}. ¡Tú puedes!"))
    db.commit()
    cache.publicar("avance", id=u.id)
    return intentos(db, u, m)


def _de_mi_equipo(db: Session, sup: Usuario, uid: int) -> Usuario:
    u = db.get(Usuario, uid)
    if not u or u.rol != "colaborador" or u.supervisor_id != sup.id:
        raise HTTPException(404, "Ese colaborador no está asignado a ti.")
    return u


@router.get("/equipo")
def equipo(sup: Usuario = Depends(supervisor), db: Session = Depends(get_db)):
    miembros = db.scalars(select(Usuario).where(Usuario.rol == "colaborador", Usuario.supervisor_id == sup.id, Usuario.activo)
                          .order_by(Usuario.fecha_ingreso.desc()))
    salida = []
    for u in miembros:
        n = db.scalar(select(func.count()).select_from(Comentario).where(Comentario.colaborador_id == u.id)) or 0
        # Escalamiento: evaluaciones donde ya agotó sus intentos sin aprobar y necesita al responsable.
        escalados = [{"modulo_id": e["modulo_id"], "modulo": e["modulo"]} for e in evaluaciones_de(db, u) if e["intentos_agotados"]]
        salida.append({**ficha(db, u), "comentarios": n, "escalados": escalados})
    salida.sort(key=lambda c: not c["escalados"])  # primero a quien requiere intervención
    return {"area": sup.area, "colaboradores": salida}


@router.get("/colaboradores/{uid}")
def detalle(uid: int, sup: Usuario = Depends(supervisor), db: Session = Depends(get_db)):
    u = _de_mi_equipo(db, sup, uid)
    comentarios = db.scalars(select(Comentario).where(Comentario.colaborador_id == u.id).order_by(Comentario.fecha.desc()))
    return {
        **ficha(db, u),
        "modulos": estado_modulos(db, u),
        "evaluaciones": evaluaciones_de(db, u),
        "comentarios": [{"id": c.id, "tipo": c.tipo, "texto": c.texto, "autor": c.autor.nombre,
                         "fecha": c.fecha.isoformat()} for c in comentarios],
    }


class NuevoComentario(BaseModel):
    texto: str = Field(min_length=2, max_length=1000)
    tipo: str = "comentario"


@router.post("/colaboradores/{uid}/comentarios")
def comentar(uid: int, datos: NuevoComentario, sup: Usuario = Depends(supervisor), db: Session = Depends(get_db)):
    u = _de_mi_equipo(db, sup, uid)
    if datos.tipo not in TIPOS:
        raise HTTPException(400, "Tipo de comentario no válido.")
    db.add(Comentario(colaborador_id=u.id, autor_id=sup.id, tipo=datos.tipo, texto=datos.texto.strip()))
    db.commit()
    cache.publicar("comentario", id=u.id)
    return {"ok": True}


@router.get("/colaboradores/{uid}/recomendacion")
async def recomendacion(uid: int, sup: Usuario = Depends(supervisor), db: Session = Depends(get_db)):
    """Recomendación generada por el modelo de IA; se guarda en Redis mientras el avance no cambie."""
    u = _de_mi_equipo(db, sup, uid)
    f, progreso = ficha(db, u), progreso_para_tutor(db, u)
    huella = hashlib.sha1(json.dumps(progreso, sort_keys=True, default=str).encode()).hexdigest()[:16]
    clave = f"recomendacion:{u.id}:{huella}"
    guardada = cache.r().get(clave)
    if guardada:
        return {"recomendacion": guardada}
    try:
        texto = await ia.recomendar_seguimiento(f, progreso)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"El servicio de IA no respondió ({type(e).__name__}).") from e
    cache.r().set(clave, texto, ex=3600)
    return {"recomendacion": texto}
