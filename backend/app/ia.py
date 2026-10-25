"""Conexión con el modelo de lenguaje: Azure OpenAI Service (principal) o un servicio compatible con OpenAI."""
from fastapi import HTTPException

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
                **({"reasoning_effort": config.IA_RAZONAMIENTO} if config.IA_RAZONAMIENTO else {}),
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
    """Recomendación para el supervisor (Agente Recomendador)."""
    from .recomendador import recomendar_seguimiento as _recomendar

    return await _recomendar(obtener_llm(), ficha, progreso)
