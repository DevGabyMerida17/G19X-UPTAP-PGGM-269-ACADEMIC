"""
Configuración centralizada de la aplicación.

Todo lo que cambia entre entornos (dev / staging / producción) vive aquí,
leído de variables de entorno — nunca hardcodeado en el código. Ver
.env.example para la lista completa de variables esperadas.
"""
from functools import lru_cache

from pydantic import PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Aplicación ---
    APP_NAME: str = "Onboarding Platform API"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # --- Base de datos ---
    DATABASE_URL: PostgresDsn

    # --- Redis (sesiones, rate limiting, estado de conversación) ---
    REDIS_URL: RedisDsn

    # --- Autenticación (Microsoft Entra ID) ---
    ENTRA_TENANT_ID: str = ""
    ENTRA_CLIENT_ID: str = ""
    # JWKS de Entra ID para validar la firma de los tokens entrantes
    ENTRA_JWKS_URL: str = ""

    # --- JWT propio (para la sesión de la app, tras validar el token de Entra ID) ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # --- Azure OpenAI (agentes) ---
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # --- Límites de agentes (control de costo, ver Documento de Arquitectura §8.4) ---
    AGENT_MAX_TOKENS_PER_CONVERSATION: int = 8000
    AGENT_TIMEOUT_SECONDS: int = 30


@lru_cache
def get_settings() -> Settings:
    """Cachea la instancia: las variables de entorno se leen una sola vez."""
    return Settings()


settings = get_settings()
