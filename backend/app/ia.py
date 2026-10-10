"""Conexión con el modelo de lenguaje: Azure OpenAI Service (principal) o un servicio compatible con OpenAI."""
from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage

from . import config, rag
from .agente import crear_agente

_llm = None
_agente = None


def obtener_llm():
    global _llm
    if not config.ia_configurada():
        raise HTTPException(503, "La IA no está configurada: faltan los datos del modelo de IA en el archivo .env")
    if _llm is None:
        if config.azure_configurado():
            from langchain_openai import AzureChatOpenAI

            _llm = AzureChatOpenAI(
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_key=config.AZURE_OPENAI_API_KEY,
                azure_deployment=config.AZURE_OPENAI_DEPLOYMENT,
                api_version=config.AZURE_OPENAI_API_VERSION,
                temperature=0.3,
                timeout=60,
                max_retries=2,
            )
        else:
            from langchain_openai import ChatOpenAI

            _llm = ChatOpenAI(
                base_url=config.IA_BASE_URL,
                api_key=config.IA_API_KEY or "sin-clave",  # Ollama local no necesita clave
                model=config.IA_MODELO,
                temperature=0.3,
                timeout=120,
                max_retries=2,
            )
    return _llm


def obtener_agente():
    global _agente
    if _agente is None:
        _agente = crear_agente(obtener_llm(), rag.buscar)
    return _agente


async def recomendar_seguimiento(ficha: dict, progreso: dict) -> str:
    """Recomendación para el supervisor sobre cómo apoyar a un colaborador."""
    from .agente import _resumen_progreso

    sistema = (
        "Eres un asistente de Recursos Humanos de PluriOne. Con base en el avance de onboarding "
        "de un colaborador, escribe UNA recomendación concreta para su supervisor (máximo 2 oraciones). "
        "Si alguna evaluación está por debajo del mínimo, menciona el módulo y la calificación. "
        "Si va retrasado, sugiere una acción. Si va bien, sugiere reconocer su avance. No inventes datos."
    )
    datos = (
        f"Colaborador: {ficha['nombre']} ({ficha['puesto']}, {ficha['area']})\n"
        f"Ingreso: {ficha['fecha_ingreso']} · Estado: {ficha['estado']}\n"
        f"{_resumen_progreso(progreso)}"
    )
    r = await obtener_llm().ainvoke([SystemMessage(content=sistema), HumanMessage(content=datos)])
    return r.content.strip()
