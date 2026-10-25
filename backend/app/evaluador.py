"""Agente Evaluador: revisa una evaluación presentada y da retroalimentación personalizada.

La calificación la calcula el sistema con las respuestas correctas que definió RH (es exacta y no
depende de la IA). El agente se encarga de lo que requiere criterio: explicar cada error con sus
propias palabras, decir qué temas reforzar y orientar según los intentos que le quedan.
"""
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from . import nombres_agentes
from .agente import linea_nombre

AGENTE_EVALUADOR = nombres_agentes.EVALUADOR  # se cambia en nombres_agentes.py


class ExplicacionPregunta(BaseModel):
    numero: int = Field(description="Número de la pregunta (empieza en 1).")
    explicacion: str = Field(description="Por qué la respuesta elegida es incorrecta y por qué la correcta sí lo es, en 2 o 3 oraciones.")


class Retroalimentacion(BaseModel):
    resumen: str = Field(description="Mensaje general de 2 a 3 oraciones sobre su resultado, motivador y honesto.")
    errores: list[ExplicacionPregunta] = Field(default_factory=list, description="Una explicación por cada pregunta incorrecta.")
    temas_a_reforzar: list[str] = Field(default_factory=list, description="De 0 a 3 temas concretos que debe repasar (vacío si sacó 100).")
    siguiente_paso: str = Field(description="Qué debe hacer ahora, en una oración.")


def _texto_evaluacion(datos: dict) -> str:
    lineas = []
    for i, p in enumerate(datos["preguntas"], 1):
        elegida = p["opciones"][p["elegida"]] if 0 <= p["elegida"] < len(p["opciones"]) else "(sin responder)"
        estado = "CORRECTA" if p["acierto"] else "INCORRECTA"
        lineas.append(f"{i}. {p['texto']}\n   Respondió: {elegida} -> {estado}\n   Correcta: {p['opciones'][p['correcta']]}")
    return "\n".join(lineas)


def evaluar(llm: BaseChatModel, datos: dict) -> dict:
    """datos: modulo, contenido (texto del módulo), preguntas (con texto, opciones, elegida, correcta, acierto),
    calificacion, minimo, aprobada, intentos_restantes, nombre."""
    sistema = (
        f"Eres el {AGENTE_EVALUADOR} de la plataforma de bienvenida de PluriOne. Revisas la evaluación que "
        "acaba de presentar un colaborador de nuevo ingreso. La calificación ya está calculada; no la cambies. "
        "Tu trabajo: explicar cada error con claridad usando el contenido del módulo, identificar qué temas "
        "necesita reforzar y orientarlo. Habla en español de México, en segunda persona, con un tono amable y "
        "motivador pero honesto. Si aprobó, felicítalo y menciona qué puede pulir. Si reprobó y le quedan "
        "intentos, anímalo a repasar antes de volver a intentarlo. Si ya no le quedan intentos, dile que su "
        "responsable o RH pueden concederle otro y que mientras tanto repase los temas indicados. "
        "No inventes información que no esté en el contenido del módulo."
    )
    datos_texto = (
        f"{linea_nombre(datos.get('nombre'))}\n"
        f"Módulo: {datos['modulo']}\n"
        f"Calificación: {datos['calificacion']}% (mínimo para aprobar: {datos['minimo']}%) -> "
        f"{'APROBADA' if datos['aprobada'] else 'NO APROBADA'}\n"
        f"Intentos que le quedan: {datos['intentos_restantes']}\n\n"
        f"Respuestas:\n{_texto_evaluacion(datos)}\n\n"
        f"Contenido del módulo:\n{datos.get('contenido') or '(sin contenido)'}"
    )
    r = llm.with_structured_output(Retroalimentacion, method="function_calling").invoke(
        [SystemMessage(content=sistema), HumanMessage(content=datos_texto)]
    )
    total = len(datos["preguntas"])
    return {
        "agente": AGENTE_EVALUADOR,
        "resumen": r.resumen,
        "errores": [e.model_dump() for e in r.errores if 1 <= e.numero <= total],
        "temas_a_reforzar": r.temas_a_reforzar[:3],
        "siguiente_paso": r.siguiente_paso,
    }
