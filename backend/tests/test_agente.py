"""Prueba el flujo de LangGraph con un modelo simulado (no llama a Azure)."""
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from app.agente import FUENTE_GENERAL, Clasificacion, RespuestaConFuentes, crear_agente


class ModeloFalso:
    def __init__(self, intencion):
        self.intencion = intencion
        self.prompts = []

    def with_structured_output(self, esquema, method=None):
        modelo = self

        class Estructurado:
            def invoke(self, mensajes):
                modelo.prompts.append(mensajes)
                if esquema is Clasificacion:
                    return Clasificacion(intencion=modelo.intencion)
                return RespuestaConFuentes(respuesta="Se piden con 15 días de anticipación.", fuentes_usadas=[1])
        return Estructurado()

    def invoke(self, mensajes):
        self.prompts.append(mensajes)
        return AIMessage(content="Sube tu Formato de datos bancarios.")


def buscar(_pregunta):
    return [Document(page_content="Vacaciones\nSe solicitan con 15 días.",
                     metadata={"fuente": "Políticas internas · Vacaciones", "tema": "Políticas"})]


def test_ruta_politicas_usa_rag():
    agente = crear_agente(ModeloFalso("politicas"), buscar)
    r = agente.invoke({"pregunta": "¿Cómo pido vacaciones?", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["intencion"] == "politicas"
    assert r["fuentes"] == ["Políticas internas · Vacaciones"]
    assert r["tema"] == "Políticas"


def test_ruta_siguiente_paso_usa_progreso():
    modelo = ModeloFalso("siguiente_paso")
    agente = crear_agente(modelo, buscar)
    progreso = {"avance": 20, "documentos": [{"titulo": "Formato de datos bancarios", "estado": "rechazado"}]}
    r = agente.invoke({"pregunta": "¿Qué hago ahora?", "nombre": "Ana", "historial": [], "progreso": progreso})
    assert r["intencion"] == "siguiente_paso"
    assert "Formato de datos bancarios: rechazado" in modelo.prompts[-1][0].content
    assert r["respuesta"].startswith("Sube")


def test_ruta_tema_explica_con_conocimiento_general():
    """Dudas de aprendizaje (p. ej. '¿qué es Docker?') se responden aunque no haya documentos de RH."""
    modelo = ModeloFalso("tema")
    agente = crear_agente(modelo, lambda _p: [])
    r = agente.invoke({"pregunta": "¿Qué es Docker?", "nombre": "Ana", "historial": [], "progreso": {"puesto": "QA"}})
    assert r["intencion"] == "tema"
    assert r["fuentes"] == [FUENTE_GENERAL]
    assert "No necesitas documentos" in modelo.prompts[-1][0].content


def test_ruta_tema_cita_documentos_si_existen():
    agente = crear_agente(ModeloFalso("tema"), buscar)
    r = agente.invoke({"pregunta": "Explícame las vacaciones", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["fuentes"] == ["Políticas internas · Vacaciones"]


def test_ruta_plataforma_explica_como_usarla():
    """'¿Cómo veo mis avances?' se responde con la guía de la plataforma, sin documentos de RH."""
    from app.agente import FUENTE_PLATAFORMA
    modelo = ModeloFalso("plataforma")
    agente = crear_agente(modelo, lambda _p: [])
    r = agente.invoke({"pregunta": "¿Cómo puedo ver mis avances?", "nombre": "Ana", "historial": [], "progreso": {"avance": 30}})
    assert r["intencion"] == "plataforma"
    assert r["fuentes"] == [FUENTE_PLATAFORMA]
    assert "Mi avance" in modelo.prompts[-1][0].content


def test_ruta_general_responde_sin_redirigir():
    modelo = ModeloFalso("general")
    agente = crear_agente(modelo, lambda _p: [])
    r = agente.invoke({"pregunta": "¿Me recomiendas un libro?", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["intencion"] == "general" and r["respuesta"]
    assert "Responde de forma natural" in modelo.prompts[-1][0].content


def test_politicas_sin_documentos_no_se_queda_sin_respuesta():
    agente = crear_agente(ModeloFalso("politicas"), lambda _p: [])
    r = agente.invoke({"pregunta": "¿Hay bono de puntualidad?", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["respuesta"] and r["fuentes"] == [FUENTE_GENERAL]
