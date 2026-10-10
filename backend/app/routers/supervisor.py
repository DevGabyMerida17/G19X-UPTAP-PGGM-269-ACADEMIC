"""Seguimiento del supervisor: solo ve a los colaboradores que RH le asignó."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import cache, ia
from ..db import get_db
from ..models import Comentario, Usuario
from ..seguridad import requiere_rol
from ..servicios import estado_modulos, evaluaciones_de, ficha, progreso_para_tutor

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])
supervisor = requiere_rol("supervisor")

TIPOS = ("comentario", "solicitud", "apoyo", "seguimiento")


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
        salida.append({**ficha(db, u), "comentarios": n})
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
