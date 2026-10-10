"""Reglas de negocio del onboarding: avance, desbloqueo de módulos y retrasos."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    DocumentoColaborador, Evaluacion, Modulo, ProgresoModulo, Tarea, TareaColaborador, TipoDocumento, Usuario,
)


def modulos_de(db: Session, u: Usuario) -> list[Modulo]:
    if not u.programa_id:
        return []
    return list(db.scalars(
        select(Modulo).where(Modulo.programa_id == u.programa_id, Modulo.activo).order_by(Modulo.orden, Modulo.id)
    ))


def estado_modulos(db: Session, u: Usuario) -> list[dict]:
    """Los módulos se desbloquean en orden: el primero sin completar queda 'en_curso'."""
    progreso = {p.modulo_id: p for p in db.scalars(select(ProgresoModulo).where(ProgresoModulo.usuario_id == u.id))}
    salida, desbloqueado = [], True
    for m in modulos_de(db, u):
        p = progreso.get(m.id)
        if p and p.completado:
            estado = "completado"
        elif desbloqueado:
            estado, desbloqueado = "en_curso", False
        else:
            estado = "bloqueado"
        total = len(m.secciones or [])
        salida.append({
            "id": m.id, "titulo": m.titulo, "minutos": m.minutos, "estado": estado,
            "leidas": total if estado == "completado" else (p.secciones_leidas if p else 0),
            "total": total, "tiene_evaluacion": bool(m.preguntas), "puntuacion_minima": m.puntuacion_minima,
        })
    return salida


def tareas_de(db: Session, u: Usuario) -> list[dict]:
    hechas = {t.tarea_id for t in db.scalars(
        select(TareaColaborador).where(TareaColaborador.usuario_id == u.id, TareaColaborador.hecha))}
    return [{"id": t.id, "etapa": t.etapa, "titulo": t.titulo, "hecha": t.id in hechas}
            for t in db.scalars(select(Tarea).order_by(Tarea.orden))]


def documentos_de(db: Session, u: Usuario) -> list[dict]:
    subidos = {d.tipo_id: d for d in db.scalars(select(DocumentoColaborador).where(DocumentoColaborador.usuario_id == u.id))}
    salida = []
    for t in db.scalars(select(TipoDocumento).order_by(TipoDocumento.orden)):
        d = subidos.get(t.id)
        salida.append({
            "tipo_id": t.id, "titulo": t.titulo, "descripcion": t.descripcion,
            "id": d.id if d else None,
            "estado": d.estado if d else "pendiente",
            "nota": d.nota if d else "",
            "archivo": d.archivo_nombre if d else "",
            "fecha": d.actualizado_en.isoformat() if d else None,
        })
    return salida


def evaluaciones_de(db: Session, u: Usuario) -> list[dict]:
    """La mejor calificación de cada módulo."""
    mejores: dict[int, Evaluacion] = {}
    for e in db.scalars(select(Evaluacion).where(Evaluacion.usuario_id == u.id)):
        if e.modulo_id not in mejores or e.calificacion > mejores[e.modulo_id].calificacion:
            mejores[e.modulo_id] = e
    return [{"modulo_id": e.modulo_id, "modulo": e.modulo.titulo, "calificacion": e.calificacion,
             "minimo": e.modulo.puntuacion_minima, "aprobada": e.aprobada} for e in mejores.values()]


def avance(db: Session, u: Usuario) -> int:
    tareas = tareas_de(db, u)
    mods = estado_modulos(db, u)
    docs = documentos_de(db, u)
    total = len(tareas) + len(mods) + len(docs)
    if not total:
        return 0
    hechos = (sum(t["hecha"] for t in tareas) + sum(m["estado"] == "completado" for m in mods)
              + sum(d["estado"] == "validado" for d in docs))
    return round(hechos / total * 100)


def estado_onboarding(u: Usuario, porcentaje: int) -> str:
    """Retrasado: más de 14 días con menos de 50%, o más de 30 días sin terminar."""
    if not u.activo:
        return "inactivo"
    if porcentaje >= 100:
        return "completado"
    dias = (date.today() - u.fecha_ingreso).days
    if (dias > 14 and porcentaje < 50) or dias > 30:
        return "retrasado"
    return "en_curso"


def ficha(db: Session, u: Usuario) -> dict:
    p = avance(db, u)
    return {
        "id": u.id, "nombre": u.nombre, "correo": u.correo, "puesto": u.puesto, "area": u.area,
        "fecha_ingreso": u.fecha_ingreso.isoformat(), "activo": u.activo, "programa_id": u.programa_id,
        "programa": u.programa.titulo if u.programa else None, "avance": p, "estado": estado_onboarding(u, p),
        "supervisor_id": u.supervisor_id, "supervisor": u.supervisor.nombre if u.supervisor else None,
        "pendiente_activacion": u.pendiente_activacion,
    }


def progreso_para_tutor(db: Session, u: Usuario) -> dict:
    """Resumen del avance que el Tutor IA usa para orientar al colaborador."""
    return {
        "avance": avance(db, u),
        "puesto": u.puesto,
        "area": u.area,
        "documentos": [{"titulo": d["titulo"], "estado": d["estado"] + (f" ({d['nota']})" if d["nota"] else "")}
                       for d in documentos_de(db, u)],
        "modulos": [{"titulo": m["titulo"], "estado": m["estado"]} for m in estado_modulos(db, u)],
        "evaluaciones": evaluaciones_de(db, u),
        "tareas_pendientes": [f"{t['etapa']}: {t['titulo']}" for t in tareas_de(db, u) if not t["hecha"]],
    }
