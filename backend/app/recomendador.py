"""Agente Recomendador: analiza el progreso y sugiere qué hacer para avanzar o reforzar.

Tiene dos vistas:
- Para el colaborador: hasta 3 recomendaciones personalizadas (repasar un módulo, presentar o repetir una
  evaluación, revisar un documento de la empresa, preguntarle algo al Tutor, completar sus documentos).
- Para el supervisor: una recomendación de cómo dar seguimiento a ese colaborador.
"""
from typing import Literal, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from . import nombres_agentes
from .agente import linea_nombre, resumen_progreso
from .validaciones import nombre_para_mostrar

AGENTE_RECOMENDADOR = nombres_agentes.RECOMENDADOR  # se cambia en nombres_agentes.py


class Recomendacion(BaseModel):
    titulo: str = Field(description="Acción concreta y breve, por ejemplo 'Repasa la sección de Phishing'.")
    motivo: str = Field(description="Por qué se lo recomiendas, basado en su avance o resultados (1 oración).")
    tipo: Literal["modulo", "evaluacion", "documentos", "material", "tutor"] = Field(
        description="modulo: leer o repasar un módulo; evaluacion: presentar o repetir una evaluación; "
                    "documentos: subir o corregir documentos; material: revisar un documento de la base de "
                    "conocimiento; tutor: preguntarle algo al Tutor IA."
    )
    modulo_id: Optional[int] = Field(default=None, description="Id del módulo relacionado, si aplica.")
    pregunta_sugerida: Optional[str] = Field(default=None, description="Si tipo es tutor, la pregunta que podría hacerle.")


class Recomendaciones(BaseModel):
    recomendaciones: list[Recomendacion] = Field(description="De 1 a 3 recomendaciones, de la más a la menos importante.")


def recomendar_colaborador(llm: BaseChatModel, nombre: str | None, progreso: dict, modulos: list[dict],
                           materiales: list[str], temas_debiles: list[str]) -> dict:
    sistema = (
        f"Eres el {AGENTE_RECOMENDADOR} de la plataforma de bienvenida de PluriOne. Analizas el progreso de un "
        "colaborador de nuevo ingreso y le das de 1 a 3 recomendaciones personalizadas para avanzar o reforzar "
        "lo que se le dificulta. Prioriza: 1) evaluaciones reprobadas y temas débiles, 2) documentos rechazados "
        "o pendientes, 3) el módulo en curso, 4) materiales útiles para su puesto. Usa solo los módulos y "
        "materiales de las listas (con su id cuando sea un módulo). Si ya terminó todo, felicítalo y sugiere "
        "repasar o preguntarle algo al Tutor sobre su puesto. Español de México, en segunda persona, breve."
    )
    datos = (
        f"{linea_nombre(nombre)}\n{resumen_progreso(progreso)}\n\n"
        "Módulos disponibles (id: título — estado):\n"
        + "\n".join(f"  {m['id']}: {m['titulo']} — {m['estado']}" for m in modulos)
        + "\n\nMateriales de la base de conocimiento:\n" + ("\n".join(f"  - {t}" for t in materiales) or "  (ninguno)")
        + "\n\nTemas que el Agente Evaluador le pidió reforzar:\n" + ("\n".join(f"  - {t}" for t in temas_debiles) or "  (ninguno)")
    )
    r = llm.with_structured_output(Recomendaciones, method="function_calling").invoke(
        [SystemMessage(content=sistema), HumanMessage(content=datos)]
    )
    ids = {m["id"] for m in modulos}
    recs = []
    for rec in r.recomendaciones[:3]:
        d = rec.model_dump()
        if d["modulo_id"] not in ids:
            d["modulo_id"] = None
        recs.append(d)
    return {"agente": AGENTE_RECOMENDADOR, "recomendaciones": recs}


async def recomendar_seguimiento(llm: BaseChatModel, ficha: dict, progreso: dict) -> str:
    """Recomendación para el supervisor sobre cómo apoyar a un colaborador."""
    sistema = (
        f"Eres el {AGENTE_RECOMENDADOR} de PluriOne. Con base en el avance de onboarding de un colaborador, "
        "escribe UNA recomendación concreta para su supervisor (máximo 2 oraciones). Si alguna evaluación está "
        "por debajo del mínimo o se le acabaron los intentos, menciona el módulo y la calificación. Si va "
        "retrasado, sugiere una acción. Si va bien, sugiere reconocer su avance. No inventes datos."
    )
    datos = (
        f"Colaborador: {nombre_para_mostrar(ficha['nombre'], ficha.get('correo', ''))} ({ficha['puesto']}, {ficha['area']})\n"
        f"Ingreso: {ficha['fecha_ingreso']} · Estado: {ficha['estado']}\n"
        f"{resumen_progreso(progreso)}"
    )
    r = await llm.ainvoke([SystemMessage(content=sistema), HumanMessage(content=datos)])
    return r.content.strip()
