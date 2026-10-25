"""Chat del Tutor: orquestador (LangGraph) y los dos agentes que atienden las preguntas del colaborador.

La plataforma tiene 5 agentes de IA:
  1. Conocimiento General  -> este archivo (chat)
  2. Tutor de Onboarding    -> este archivo (chat)
  3. Evaluador              -> evaluador.py (al terminar una evaluación)
  4. Recomendador           -> recomendador.py (inicio del colaborador y "Mi equipo" del supervisor)
  5. Asistente de RH        -> asistente_rh.py (panel de Recursos Humanos)

Flujo del chat:
                  ┌─> conocimiento_general ──────────────┐
    orquestador ──┤                                      ├─> FIN
                  └─> recuperar ─> tutor_onboarding ─────┘

- El orquestador decide qué agente atiende la pregunta.
- Conocimiento General: responde cualquier pregunta con el conocimiento del modelo, SIN consultar
  documentos internos de PluriOne.
- Tutor de Onboarding: guía al colaborador en su proceso, explica la plataforma, revisa su avance
  y le dice qué sigue. Para políticas y procedimientos responde SOLO con la documentación oficial
  que sube RH (RAG), para no inventar reglas, fechas ni prestaciones.
"""
from typing import Callable, Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from . import nombres_agentes

# Los nombres se cambian en nombres_agentes.py
AGENTE_CONOCIMIENTO = nombres_agentes.CONOCIMIENTO_GENERAL
AGENTE_TUTOR = nombres_agentes.TUTOR_ONBOARDING
FUENTE_GENERAL = "Conocimiento general del modelo (no es una política oficial)"
FUENTE_PLATAFORMA = "Guía de uso de la plataforma"

# Lo que el Tutor sabe de la plataforma (menú del colaborador).
GUIA_PLATAFORMA = """Secciones del menú lateral del colaborador:
- Inicio: saludo, tu puesto, área y fecha de ingreso; "Continúa donde lo dejaste" con el módulo en curso;
  "Recomendaciones para ti" del Agente Recomendador; "Tu ruta" con las tareas de Día 1, Semana 1 y Mes 1
  (se marcan con la casilla); tu responsable y los mensajes que te deja.
- Documentos: lista de documentos que pide RH (identificación, comprobante de domicilio, datos bancarios,
  estudios). Se suben con el botón "Subir archivo" o arrastrando el archivo encima. Solo PDF, JPG o PNG de
  máximo 5 MB. Estados: Sin subir, En revisión, Validado o Rechazado (si se rechaza, aparece el motivo y el
  botón "Volver a subir").
- Capacitación: módulos en orden; se desbloquean al terminar el anterior. Dentro de cada módulo se marca
  cada sección como leída y al final se completa el módulo.
- Evaluaciones: se habilitan al terminar de leer el módulo que las tiene. Cada evaluación tiene un número
  limitado de intentos (normalmente 3). Al terminar, el Agente Evaluador explica los errores y qué temas
  reforzar. Si se acaban los intentos, el responsable o RH pueden conceder uno más.
- Tutor IA: este chat.
- Mi avance: porcentaje general, módulos completados y pendientes, calificaciones y próximas actividades.
Además, en el menú lateral está el "Progreso general" con un círculo por etapa (Bienvenida, Documentos,
Capacitación, Cierre) que se va llenando; al terminar una etapa muestra una palomita.
En la barra de arriba: botón de luna/sol para modo oscuro o claro, y "Salir".
Contraseña: en la pantalla de inicio está "¿Olvidaste tu contraseña?", que manda un enlace al correo.
Las cuentas las crea Recursos Humanos; si algo no funciona, el colaborador puede contactar a RH."""


class Estado(TypedDict, total=False):
    pregunta: str
    nombre: str
    historial: list[dict]
    progreso: dict
    intencion: str
    agente: str
    documentos: list
    respuesta: str
    fuentes: list[str]
    tema: Optional[str]


class Clasificacion(BaseModel):
    intencion: Literal["conocimiento", "onboarding"] = Field(
        description=(
            "onboarding: cualquier cosa sobre su incorporación a PluriOne: políticas o reglas de la empresa "
            "(vacaciones, nómina, horario, beneficios, procesos internos), cómo usar esta plataforma (ver "
            "avances, subir documentos, evaluaciones, contraseña), su avance o qué le toca hacer, sus "
            "módulos, documentos o evaluaciones. "
            "conocimiento: preguntas generales que no dependen de PluriOne: definiciones ('¿qué es...?'), "
            "explicaciones de conceptos de cualquier tema, ejemplos, consejos, saludos o plática."
        )
    )


class RespuestaConFuentes(BaseModel):
    respuesta: str = Field(description="Respuesta en español, clara y bien organizada.")
    fuentes_usadas: list[int] = Field(
        default_factory=list,
        description="Números [n] de los fragmentos de documentos oficiales que usaste. Vacío si no usaste ninguno.",
    )


PERSONA = (
    "Trabajas en la plataforma de bienvenida de PluriOne (Develop Talent & Technology), una empresa "
    "mexicana de consultoría, desarrollo de software y capacitación en TI, que acompaña a colaboradores "
    "de nuevo ingreso. Hablas en español de México, con un tono amable, cercano y directo. Te diriges "
    "al colaborador por su nombre de pila cuando es natural. Nunca te refieras a nadie por números, "
    "identificadores ni correos; si no tienes su nombre, háblale sin usar ninguno."
)


def linea_nombre(nombre: str | None) -> str:
    """Cómo se le presenta el nombre del colaborador a un agente."""
    return f"Nombre del colaborador: {nombre}" if nombre else "El colaborador no tiene un nombre registrado: no uses ningún nombre."


def _historial(estado: Estado) -> list:
    msgs = []
    for m in estado.get("historial", [])[-8:]:
        cls = HumanMessage if m.get("rol") == "usuario" else AIMessage
        msgs.append(cls(content=m.get("texto", "")))
    return msgs


def resumen_progreso(p: dict) -> str:
    if not p:
        return "Sin información de avance."
    lineas = [f"Avance general: {p.get('avance', '?')}%"]
    if p.get("puesto"):
        lineas.append(f"Puesto: {p['puesto']} ({p.get('area', '')})")
    for clave, titulo in (("documentos", "Documentos"), ("modulos", "Módulos de capacitación")):
        if p.get(clave):
            lineas.append(f"{titulo}:")
            lineas += [f"  - {x.get('titulo')}: {x.get('estado')}" for x in p[clave]]
    for e in p.get("evaluaciones", []):
        extra = ""
        if "intentos_usados" in e:
            extra = f", intentos {e['intentos_usados']} de {e['intentos_permitidos']}"
        lineas.append(f"Evaluación {e['modulo']}: {e['calificacion']}% (mínimo {e['minimo']}%{extra})")
    if p.get("tareas_pendientes"):
        lineas.append("Tareas pendientes de su ruta:")
        lineas += [f"  - {t}" for t in p["tareas_pendientes"]]
    return "\n".join(lineas)


# Se conserva el nombre anterior para no romper importaciones existentes.
_resumen_progreso = resumen_progreso


def _contexto(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i + 1}] ({d.metadata['fuente']})\n{d.page_content}" for i, d in enumerate(docs))


def crear_agente(llm: BaseChatModel, buscar: Callable[[str], list[Document]]):
    clasificador = llm.with_structured_output(Clasificacion, method="function_calling")
    redactor = llm.with_structured_output(RespuestaConFuentes, method="function_calling")

    def mensajes(estado: Estado, sistema: str) -> list:
        return [SystemMessage(content=sistema), *_historial(estado), HumanMessage(content=estado["pregunta"])]

    def orquestador(estado: Estado) -> Estado:
        r = clasificador.invoke([
            SystemMessage(content="Decide qué agente debe atender la última pregunta del colaborador."),
            *_historial(estado),
            HumanMessage(content=estado["pregunta"]),
        ])
        return {"intencion": r.intencion}

    def conocimiento_general(estado: Estado) -> Estado:
        sistema = (
            f"Eres el {AGENTE_CONOCIMIENTO}. {PERSONA}\n\n"
            "Responde cualquier pregunta con tu propio conocimiento, sea del tema que sea: explica conceptos, "
            "resuelve dudas y da información clara y comprensible. Cuando ayude, primero la idea principal en "
            "palabras sencillas, luego un ejemplo práctico y, si hace falta, pasos o una lista corta. Si es un "
            "saludo o plática, responde de forma natural y breve. No uses ni menciones documentos internos de "
            "PluriOne; si te preguntan una regla específica de la empresa, sugiere preguntarle al Tutor de "
            "Onboarding o a RH. Rechaza con amabilidad solo lo dañino, ilegal o inapropiado para el trabajo. "
            "Unas 200 palabras como máximo, salvo que pida más detalle.\n\n"
            f"{linea_nombre(estado.get('nombre'))}"
            + (f" ({estado['progreso']['puesto']})" if estado.get("progreso", {}).get("puesto") else "")
        )
        r = llm.invoke(mensajes(estado, sistema))
        return {"respuesta": r.content, "fuentes": [FUENTE_GENERAL], "tema": "Conocimiento general",
                "agente": AGENTE_CONOCIMIENTO}

    def recuperar(estado: Estado) -> Estado:
        return {"documentos": buscar(estado["pregunta"])}

    def tutor_onboarding(estado: Estado) -> Estado:
        docs = estado.get("documentos", [])
        sistema = (
            f"Eres el {AGENTE_TUTOR}. {PERSONA}\n\n"
            "Guías al colaborador durante su incorporación. Según lo que pregunte:\n"
            "- Políticas o procedimientos de PluriOne: responde SOLO con los fragmentos de documentos oficiales "
            "y cita los que usaste. Si no contienen la respuesta, dilo con honestidad, explica en general cómo "
            "suele funcionar en México aclarando que no es la regla oficial de PluriOne, y sugiere confirmarlo "
            "con RH o su responsable. Nunca inventes reglas, cifras, fechas ni prestaciones.\n"
            "- Cómo usar la plataforma: explica paso a paso con los nombres exactos de secciones y botones de "
            "la guía.\n"
            "- Su avance o qué le toca hacer: con base en su avance, dile el paso más importante y en qué "
            "sección hacerlo, en este orden: 1) documentos rechazados o sin subir, 2) evaluación reprobada o "
            "módulo en curso, 3) tareas pendientes de su ruta. Sé motivador.\n"
            "Sé concreto: máximo 6 oraciones o una lista corta.\n\n"
            f"Guía de la plataforma:\n{GUIA_PLATAFORMA}\n\n"
            f"{linea_nombre(estado.get('nombre'))}\n"
            f"Su avance:\n{resumen_progreso(estado.get('progreso', {}))}\n\n"
            f"Fragmentos de documentos oficiales:\n{_contexto(docs) or '(no hay documentos relacionados)'}"
        )
        r = redactor.invoke(mensajes(estado, sistema))
        usados = [docs[n - 1] for n in r.fuentes_usadas if 1 <= n <= len(docs)]
        fuentes = list(dict.fromkeys(d.metadata["fuente"] for d in usados)) or [FUENTE_PLATAFORMA]
        tema = next((d.metadata.get("tema") for d in usados if d.metadata.get("tema")), None) or "Onboarding"
        return {"respuesta": r.respuesta, "fuentes": fuentes, "tema": tema, "agente": AGENTE_TUTOR}

    g = StateGraph(Estado)
    g.add_node("orquestador", orquestador)
    g.add_node("conocimiento_general", conocimiento_general)
    g.add_node("recuperar", recuperar)
    g.add_node("tutor_onboarding", tutor_onboarding)

    g.add_edge(START, "orquestador")
    g.add_conditional_edges(
        "orquestador",
        lambda e: e["intencion"],
        {"conocimiento": "conocimiento_general", "onboarding": "recuperar"},
    )
    g.add_edge("recuperar", "tutor_onboarding")
    g.add_edge("conocimiento_general", END)
    g.add_edge("tutor_onboarding", END)
    return g.compile()
