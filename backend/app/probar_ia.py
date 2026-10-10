"""Comprueba que el modelo de IA configurado en el archivo .env responde.

Uso (desde la carpeta backend):
    python -m app.probar_ia
"""
import sys

from langchain_core.messages import HumanMessage

from . import config


def main() -> int:
    if not config.ia_configurada():
        print("No hay un modelo de IA configurado en backend/.env. Llena una de estas dos opciones:")
        print("  1) Azure OpenAI: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY y AZURE_OPENAI_DEPLOYMENT")
        print("  2) Servicio compatible con OpenAI: IA_BASE_URL, IA_MODELO (e IA_API_KEY si lo pide)")
        return 1
    from .ia import obtener_llm

    destino = config.AZURE_OPENAI_ENDPOINT if config.azure_configurado() else config.IA_BASE_URL
    print(f"Probando {config.proveedor_ia()} en {destino}…")
    try:
        r = obtener_llm().invoke([HumanMessage(content="Responde solo: 'Conexión correcta'.")])
    except Exception as e:  # mostramos el motivo exacto para corregir el .env
        print(f"Error: {type(e).__name__}: {e}")
        print("Revisa la dirección, la clave y el nombre del modelo en backend/.env.")
        return 1
    print("El modelo respondió:", r.content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
