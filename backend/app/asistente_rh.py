"""Agente Asistente de RH: responde preguntas de Recursos Humanos con los datos reales de la plataforma.

Ejemplos: "¿quién va retrasado?", "¿cuántos documentos faltan por revisar?", "resume el avance del área de
Desarrollo", "¿quién reprobó la evaluación de Seguridad?". El agente solo usa la información que se le pasa
(un resumen generado en ese momento desde la base de datos) y no inventa personas ni cifras.
"""
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import nombres_agentes
from .models import DocumentoColaborador, Usuario
from .servicios import estado_modulos, evaluaciones_de, ficha
from .validaciones import nombre_para_mostrar

AGENTE_RH = nombres_agentes.ASISTENTE_RH  # se cambia en nombres_agentes.py
ESTADOS = {"en_curso": "en curso", "completado": "completado", "retrasado": "retrasado", "inactivo": "dado de baja"}


def datos_plataforma(db: Session) -> str:
    """Resumen en texto del estado actual del onboarding (lo que el agente puede consultar)."""
    lineas = []
    colaboradores = list(db.scalars(select(Usuario).where(Usuario.rol == "colaborador").order_by(Usuario.area, Usuario.nombre)))
    for u in colaboradores:
        f = ficha(db, u)
        mods = estado_modulos(db, u)
        hechos = sum(m["estado"] == "completado" for m in mods)
        evals = "; ".join(
            f"{e['modulo']} {e['calificacion']}% ({'aprobada' if e['aprobada'] else 'no aprobada'}, "
            f"intentos {e['intentos_usados']}/{e['intentos_permitidos']})"
            for e in evaluaciones_de(db, u)
        ) or "sin evaluaciones"
        docs = {d.tipo.titulo: d.estado for d in db.scalars(select(DocumentoColaborador).where(DocumentoColaborador.usuario_id == u.id))}
        docs_txt = ", ".join(f"{t}: {e}" for t, e in docs.items()) or "ninguno subido"
        lineas.append(
            f"- {nombre_para_mostrar(f['nombre'], f['correo'])} | {f['puesto']} | área {f['area']} | ingresó {f['fecha_ingreso']} | "
            f"responsable: {f['supervisor'] or 'sin asignar'} | avance {f['avance']}% | estado {ESTADOS.get(f['estado'], f['estado'])} | "
            f"módulos {hechos}/{len(mods)} | evaluaciones: {evals} | documentos: {docs_txt}"
        )
    if not colaboradores:
        return "No hay colaboradores registrados."
    en_revision = len(list(db.scalars(select(DocumentoColaborador.id).where(DocumentoColaborador.estado == "revision"))))
    return (f"Colaboradores registrados: {len(colaboradores)}. Documentos esperando revisión de RH: {en_revision}.\n"
            + "\n".join(lineas))


def responder(llm: BaseChatModel, pregunta: str, historial: list[dict], datos: str, nombre_rh: str) -> str:
    sistema = (
        f"Eres {AGENTE_RH}, el Asistente de RH de la plataforma de bienvenida de PluriOne. Ayudas al personal de Recursos "
        "Humanos a consultar y analizar el proceso de onboarding. Responde SOLO con los datos de abajo, que "
        "vienen directo de la plataforma en este momento. Si la respuesta no está en los datos, dilo. No "
        "inventes personas, cifras ni fechas. Cuando enlistes personas, usa viñetas con su nombre y el dato "
        "relevante. Si te piden una sugerencia (por ejemplo a quién dar seguimiento), basa tu criterio en los "
        "datos y explícalo en una oración. Español de México, directo y profesional.\n\n"
        f"Persona de RH que pregunta: {nombre_rh}\n\nDatos de la plataforma:\n{datos}"
    )
    msgs = [SystemMessage(content=sistema)]
    for m in historial[-6:]:
        msgs.append((HumanMessage if m.get("rol") == "usuario" else AIMessage)(content=m.get("texto", "")))
    msgs.append(HumanMessage(content=pregunta))
    return llm.invoke(msgs).content.strip()
