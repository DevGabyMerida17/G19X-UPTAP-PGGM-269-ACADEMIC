"""Agente Tutor orquestado con LangGraph. Usa un modelo de lenguaje real (Azure OpenAI u otro compatible).

Flujo:
                ┌─> recuperar ─┬─> responder_politicas ─┐
                │              └─> explicar_tema ───────┤
    clasificar ─┼─> ayudar_plataforma ──────────────────┤
                ├─> guiar ──────────────────────────────┼─> FIN
                └─> conversar ──────────────────────────┘

Cada ruta es un agente especializado:
- politicas: reglas o datos de PluriOne. Responde SOLO con los documentos oficiales que sube RH
  (RAG), para no inventar fechas, montos ni prestaciones.
- tema: cualquier pregunta de conocimiento (definiciones, explicaciones, ejemplos, cómo se hace algo).
  Responde con el conocimiento del modelo; si hay documentos de PluriOne relacionados, también los usa.
- plataforma: cómo se usa esta plataforma ("¿dónde veo mi avance?", "¿cómo subo un documento?").
- siguiente_paso: revisa el avance real del colaborador y le dice qué sigue.
- general: saludos y cualquier otra plática; responde de forma natural.
"""
from typing import Callable, Literal, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

FUENTE_GENERAL = "Conocimiento general del Tutor IA (no es una política oficial)"
FUENTE_PLATAFORMA = "Guía de uso de la plataforma"

# Lo que el agente de ayuda sabe de la plataforma (menú del colaborador).
GUIA_PLATAFORMA = """Secciones del menú lateral del colaborador:
- Inicio: saludo, tu puesto, área y fecha de ingreso; "Continúa donde lo dejaste" con el módulo en curso;
  "Tu ruta" con las tareas de Día 1, Semana 1 y Mes 1 (se marcan con la casilla); tu responsable y los
  mensajes que te deja.
- Documentos: lista de documentos que pide RH (identificación, comprobante de domicilio, datos bancarios,
  estudios). Se suben con el botón "Subir archivo" o arrastrando el archivo encima. Solo PDF, JPG o PNG de
  máximo 5 MB. Estados: Sin subir, En revisión, Validado o Rechazado (si se rechaza, aparece el motivo y el
  botón "Volver a subir").
- Capacitación: módulos en orden; se desbloquean al terminar el anterior. Dentro de cada módulo se marca
  cada sección como leída y al final se completa el módulo.
- Evaluaciones: se habilitan al terminar de leer el módulo que las tiene. Muestran la calificación y la
  retroalimentación de cada respuesta; si no se alcanza el mínimo, se puede presentar de nuevo.
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
    documentos: list
    respuesta: str
    fuentes: list[str]
    tema: Optional[str]


class Clasificacion(BaseModel):
    intencion: Literal["politicas", "tema", "plataforma", "siguiente_paso", "general"] = Field(
        description=(
            "politicas: reglas o datos propios de la empresa PluriOne (sus políticas, vacaciones, "
            "beneficios, nómina, horario, dirección, procesos internos). "
            "tema: cualquier pregunta de conocimiento: definiciones ('¿qué es...?'), explicaciones, "
            "conceptos técnicos o de cualquier materia, ejemplos, cómo se hace algo, consejos. "
            "plataforma: cómo usar esta plataforma o dónde encontrar algo en ella (ver avances, subir "
            "documentos, presentar evaluaciones, cambiar contraseña, modo oscuro). "
            "siguiente_paso: qué le toca hacer ahora, qué le falta o cómo va su propio avance. "
            "general: saludos, agradecimientos o cualquier otra plática."
        )
    )


class RespuestaConFuentes(BaseModel):
    respuesta: str = Field(description="Respuesta en español, clara y bien organizada.")
    fuentes_usadas: list[int] = Field(
        default_factory=list,
        description="Números [n] de los fragmentos de documentos que usaste. Vacío si no usaste ninguno.",
    )


PERSONA = (
    "Eres el Tutor de PluriOne (Develop Talent & Technology), una empresa mexicana de consultoría, "
    "desarrollo de software y capacitación en TI. Acompañas a colaboradores de nuevo ingreso: resuelves "
    "sus dudas, les explicas lo que no entienden y los orientas en su proceso. Hablas en español de "
    "México, con un tono amable, cercano y directo. Te diriges al colaborador por su nombre de pila "
    "cuando es natural."
)


def _historial(estado: Estado) -> list:
    msgs = []
    for m in estado.get("historial", [])[-8:]:
        cls = HumanMessage if m.get("rol") == "usuario" else AIMessage
        msgs.append(cls(content=m.get("texto", "")))
    return msgs


def _resumen_progreso(p: dict) -> str:
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
        lineas.append(f"Evaluación {e['modulo']}: {e['calificacion']}% (mínimo {e['minimo']}%)")
    if p.get("tareas_pendientes"):
        lineas.append("Tareas pendientes de su ruta:")
        lineas += [f"  - {t}" for t in p["tareas_pendientes"]]
    return "\n".join(lineas)


def _contexto(docs: list[Document]) -> str:
    return "\n\n".join(f"[{i + 1}] ({d.metadata['fuente']})\n{d.page_content}" for i, d in enumerate(docs))


def _fuentes(docs: list[Document], numeros: list[int]) -> tuple[list[Document], list[str]]:
    usados = [docs[n - 1] for n in numeros if 1 <= n <= len(docs)]
    return usados, list(dict.fromkeys(d.metadata["fuente"] for d in usados))


def crear_agente(llm: BaseChatModel, buscar: Callable[[str], list[Document]]):
    clasificador = llm.with_structured_output(Clasificacion, method="function_calling")
    redactor = llm.with_structured_output(RespuestaConFuentes, method="function_calling")

    def mensajes(estado: Estado, sistema: str) -> list:
        return [SystemMessage(content=sistema), *_historial(estado), HumanMessage(content=estado["pregunta"])]

    def clasificar(estado: Estado) -> Estado:
        r = clasificador.invoke([
            SystemMessage(content="Clasifica la última pregunta del colaborador según su intención."),
            *_historial(estado),
            HumanMessage(content=estado["pregunta"]),
        ])
        return {"intencion": r.intencion}

    def recuperar(estado: Estado) -> Estado:
        return {"documentos": buscar(estado["pregunta"])}

    def responder_politicas(estado: Estado) -> Estado:
        docs = estado.get("documentos", [])
        sistema = (
            f"{PERSONA}\n\n"
            "La pregunta es sobre reglas o datos propios de PluriOne. Responde SOLO con la información de "
            "los fragmentos de documentos oficiales. Si los fragmentos no la contienen, dilo con honestidad, "
            "explica en general cómo suele funcionar ese tema en las empresas en México aclarando que no es "
            "la regla oficial de PluriOne, y sugiere confirmarlo con Recursos Humanos o su responsable. "
            "Nunca inventes reglas, cifras, fechas ni prestaciones de PluriOne. Máximo 6 oraciones.\n\n"
            f"Colaborador: {estado.get('nombre') or 'colaborador'}\n\n"
            f"Fragmentos:\n{_contexto(docs) or '(no hay documentos oficiales sobre este tema)'}"
        )
        r = redactor.invoke(mensajes(estado, sistema))
        usados, fuentes = _fuentes(docs, r.fuentes_usadas)
        tema = next((d.metadata.get("tema") for d in usados if d.metadata.get("tema")), None)
        return {"respuesta": r.respuesta, "fuentes": fuentes or [FUENTE_GENERAL], "tema": tema}

    def explicar_tema(estado: Estado) -> Estado:
        docs = estado.get("documentos", [])
        sistema = (
            f"{PERSONA}\n\n"
            "El colaborador hizo una pregunta de conocimiento. Respóndela completa con tu propio "
            "conocimiento, sea del tema que sea: primero la idea principal en palabras sencillas, luego un "
            "ejemplo práctico (de preferencia relacionado con su trabajo) y, si ayuda, pasos o una lista "
            "corta. No necesitas documentos para responder. Si alguno de los fragmentos de PluriOne es "
            "relevante, úsalo y cítalo; si no, ignóralos. Adapta el nivel a alguien que está aprendiendo. "
            "Unas 200 palabras como máximo, salvo que pida más detalle.\n\n"
            f"Colaborador: {estado.get('nombre') or 'colaborador'}\n"
            f"Su situación:\n{_resumen_progreso(estado.get('progreso', {}))}\n\n"
            f"Fragmentos de documentos de PluriOne:\n{_contexto(docs) or '(ninguno relacionado)'}"
        )
        r = redactor.invoke(mensajes(estado, sistema))
        usados, fuentes = _fuentes(docs, r.fuentes_usadas)
        tema = next((d.metadata.get("tema") for d in usados if d.metadata.get("tema")), None) or "Capacitación"
        return {"respuesta": r.respuesta, "fuentes": fuentes or [FUENTE_GENERAL], "tema": tema}

    def ayudar_plataforma(estado: Estado) -> Estado:
        sistema = (
            f"{PERSONA}\n\n"
            "El colaborador pregunta cómo usar esta plataforma. Explícale paso a paso dónde encontrar lo que "
            "busca, usando los nombres exactos de las secciones y botones. Si su avance ayuda a la respuesta, "
            "menciónalo. Si lo que pide no existe en la plataforma, dilo y sugiere contactar a RH. "
            "Máximo 5 oraciones o una lista corta.\n\n"
            f"Guía de la plataforma:\n{GUIA_PLATAFORMA}\n\n"
            f"Colaborador: {estado.get('nombre') or 'colaborador'}\n"
            f"Su avance:\n{_resumen_progreso(estado.get('progreso', {}))}"
        )
        r = llm.invoke(mensajes(estado, sistema))
        return {"respuesta": r.content, "fuentes": [FUENTE_PLATAFORMA], "tema": "Uso de la plataforma"}

    def guiar(estado: Estado) -> Estado:
        sistema = (
            f"{PERSONA}\n\n"
            "El colaborador quiere saber qué hacer ahora o cómo va. Con base en su avance, "
            "dile cuál es el paso más importante a seguir y por qué, en orden de prioridad: "
            "1) documentos rechazados o sin subir, 2) el módulo en curso o una evaluación reprobada, "
            "3) tareas pendientes de su ruta. Dile en qué sección de la plataforma hacerlo. "
            "Sé concreto y motivador, máximo 4 oraciones.\n\n"
            f"Guía de la plataforma:\n{GUIA_PLATAFORMA}\n\n"
            f"Colaborador: {estado.get('nombre') or 'colaborador'}\n"
            f"Avance actual:\n{_resumen_progreso(estado.get('progreso', {}))}"
        )
        r = llm.invoke(mensajes(estado, sistema))
        return {"respuesta": r.content, "fuentes": ["Tu ruta de onboarding"], "tema": None}

    def conversar(estado: Estado) -> Estado:
        sistema = (
            f"{PERSONA}\n\n"
            "Responde de forma natural y útil a lo que te diga o pregunte, sea del tema que sea. "
            "Solo rechaza con amabilidad lo que sea dañino, ilegal o inapropiado para el trabajo."
        )
        r = llm.invoke(mensajes(estado, sistema))
        return {"respuesta": r.content, "fuentes": [], "tema": None}

    g = StateGraph(Estado)
    g.add_node("clasificar", clasificar)
    g.add_node("recuperar", recuperar)
    g.add_node("responder_politicas", responder_politicas)
    g.add_node("explicar_tema", explicar_tema)
    g.add_node("ayudar_plataforma", ayudar_plataforma)
    g.add_node("guiar", guiar)
    g.add_node("conversar", conversar)

    g.add_edge(START, "clasificar")
    g.add_conditional_edges(
        "clasificar",
        lambda e: e["intencion"],
        {"politicas": "recuperar", "tema": "recuperar", "plataforma": "ayudar_plataforma",
         "siguiente_paso": "guiar", "general": "conversar"},
    )
    g.add_conditional_edges(
        "recuperar",
        lambda e: e["intencion"],
        {"politicas": "responder_politicas", "tema": "explicar_tema"},
    )
    for nodo in ("responder_politicas", "explicar_tema", "ayudar_plataforma", "guiar", "conversar"):
        g.add_edge(nodo, END)
    return g.compile()
