"""Prueba los 5 agentes con un modelo simulado (no llama a ningún servicio de IA)."""
import asyncio

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from app import asistente_rh, evaluador, nombres_agentes, recomendador
from app.agente import (
    AGENTE_CONOCIMIENTO, AGENTE_TUTOR, FUENTE_GENERAL, FUENTE_PLATAFORMA, Clasificacion, RespuestaConFuentes,
    crear_agente,
)


class ModeloFalso:
    """Devuelve respuestas fijas y guarda los mensajes que recibió, para revisar los prompts."""

    def __init__(self, intencion="onboarding", estructurado=None):
        self.intencion = intencion
        self.estructurado = estructurado or {}
        self.prompts = []

    def with_structured_output(self, esquema, method=None):
        modelo = self

        class Estructurado:
            def invoke(self, mensajes):
                modelo.prompts.append(mensajes)
                if esquema is Clasificacion:
                    return Clasificacion(intencion=modelo.intencion)
                if esquema is RespuestaConFuentes:
                    return RespuestaConFuentes(respuesta="Se piden con 15 días de anticipación.", fuentes_usadas=[1])
                return esquema(**modelo.estructurado)
        return Estructurado()

    def invoke(self, mensajes):
        self.prompts.append(mensajes)
        return AIMessage(content="Una API permite que dos sistemas se comuniquen.")

    async def ainvoke(self, mensajes):
        return self.invoke(mensajes)


def buscar(_pregunta):
    return [Document(page_content="Vacaciones\nSe solicitan con 15 días.",
                     metadata={"fuente": "Políticas internas · Vacaciones", "tema": "Políticas"})]


def test_conocimiento_general_no_usa_documentos():
    llamadas = []
    modelo = ModeloFalso("conocimiento")
    agente = crear_agente(modelo, lambda p: llamadas.append(p) or [])
    r = agente.invoke({"pregunta": "¿Qué es una API?", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["agente"] == AGENTE_CONOCIMIENTO
    assert r["fuentes"] == [FUENTE_GENERAL]
    assert llamadas == []  # nunca consulta la base de conocimiento de PluriOne
    assert "No uses ni menciones documentos internos" in modelo.prompts[-1][0].content


def test_tutor_responde_politicas_con_documentos_oficiales():
    agente = crear_agente(ModeloFalso("onboarding"), buscar)
    r = agente.invoke({"pregunta": "¿Cómo pido vacaciones?", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["agente"] == AGENTE_TUTOR
    assert r["fuentes"] == ["Políticas internas · Vacaciones"]
    assert r["tema"] == "Políticas"


def test_tutor_explica_plataforma_y_avance():
    modelo = ModeloFalso("onboarding")
    agente = crear_agente(modelo, lambda _p: [])
    progreso = {"avance": 20, "documentos": [{"titulo": "Formato de datos bancarios", "estado": "rechazado"}]}
    r = agente.invoke({"pregunta": "¿Qué me toca hacer?", "nombre": "Ana", "historial": [], "progreso": progreso})
    sistema = modelo.prompts[-1][0].content
    assert "Mi avance" in sistema and "Formato de datos bancarios: rechazado" in sistema
    # Sin documentos relacionados la fuente es la guía de la plataforma
    assert r["agente"] == AGENTE_TUTOR


def test_tutor_sin_documentos_usa_guia_como_fuente():
    class SinFuentes(ModeloFalso):
        def with_structured_output(self, esquema, method=None):
            if esquema is RespuestaConFuentes:
                class E:
                    def invoke(self, m):
                        return RespuestaConFuentes(respuesta="Ve a Mi avance.", fuentes_usadas=[])
                return E()
            return super().with_structured_output(esquema, method)
    r = crear_agente(SinFuentes("onboarding"), lambda _p: []).invoke(
        {"pregunta": "¿Dónde veo mi avance?", "nombre": "Ana", "historial": [], "progreso": {}})
    assert r["fuentes"] == [FUENTE_PLATAFORMA]


def test_agente_evaluador():
    modelo = ModeloFalso(estructurado={
        "resumen": "Vas bien, repasa phishing.", "temas_a_reforzar": ["Phishing", "Contraseñas", "Datos", "Extra"],
        "siguiente_paso": "Repasa la sección 2.",
        "errores": [{"numero": 1, "explicacion": "El correo pedía tu contraseña."}, {"numero": 9, "explicacion": "no existe"}],
    })
    datos = {"modulo": "Seguridad", "contenido": "Phishing...", "calificacion": 50, "minimo": 70, "aprobada": False,
             "intentos_restantes": 2, "nombre": "Ana",
             "preguntas": [{"texto": "¿Qué haces con un correo raro?", "opciones": ["Responder", "Reportar"],
                            "elegida": 0, "correcta": 1, "acierto": False},
                           {"texto": "¿2FA?", "opciones": ["Sí", "No"], "elegida": 0, "correcta": 0, "acierto": True}]}
    r = evaluador.evaluar(modelo, datos)
    assert r["agente"] == nombres_agentes.EVALUADOR
    assert [e["numero"] for e in r["errores"]] == [1]  # descarta preguntas que no existen
    assert len(r["temas_a_reforzar"]) == 3
    assert "Intentos que le quedan: 2" in modelo.prompts[-1][1].content


def test_agente_recomendador():
    modelo = ModeloFalso(estructurado={"recomendaciones": [
        {"titulo": "Repasa Seguridad", "motivo": "Reprobaste", "tipo": "modulo", "modulo_id": 3},
        {"titulo": "Pregunta al Tutor", "motivo": "Dudas", "tipo": "tutor", "modulo_id": 99, "pregunta_sugerida": "¿Qué es phishing?"},
    ]})
    r = recomendador.recomendar_colaborador(modelo, "Ana", {"avance": 40}, [{"id": 3, "titulo": "Seguridad", "estado": "en_curso"}],
                                            ["Políticas internas"], ["Phishing"])
    assert r["agente"] == nombres_agentes.RECOMENDADOR
    assert r["recomendaciones"][0]["modulo_id"] == 3
    assert r["recomendaciones"][1]["modulo_id"] is None  # id inexistente se descarta
    texto = asyncio.run(recomendador.recomendar_seguimiento(
        modelo, {"nombre": "Ana", "puesto": "QA", "area": "Desarrollo", "fecha_ingreso": "2026-10-01", "estado": "en_curso"}, {}))
    assert texto


def test_asistente_rh_usa_datos_de_la_plataforma():
    modelo = ModeloFalso()
    asistente_rh.responder(modelo, "¿Quién va retrasado?", [], "- Sofía Méndez | retrasado", "Laura")
    sistema = modelo.prompts[-1][0].content
    assert "Sofía Méndez | retrasado" in sistema and "No inventes" in sistema
