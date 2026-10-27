"""Configuración leída de variables de entorno o del archivo .env (ver .env.example)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(nombre: str, defecto: str = "") -> str:
    return os.getenv(nombre, defecto).strip()


# Base de datos (PostgreSQL). Para pruebas locales sin Docker se acepta sqlite:///archivo.db
DATABASE_URL = _env("DATABASE_URL", "postgresql+psycopg://onboarding:onboarding@localhost:5432/onboarding")

# Redis: sesiones, historial del chat, límite de peticiones y eventos en tiempo real.
# "memory://" usa un Redis simulado en memoria (solo para pruebas locales).
REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")

SESION_HORAS = int(_env("SESION_HORAS", "8"))
TUTOR_LIMITE_POR_MINUTO = int(_env("TUTOR_LIMITE_POR_MINUTO", "15"))
CARGAR_DATOS_DEMO = _env("CARGAR_DATOS_DEMO", "true").lower() == "true"
CORS_ORIGINS = [o for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o]

UPLOADS_DIR = Path(_env("UPLOADS_DIR", str(BASE_DIR / "uploads")))
# conocimiento/ trae documentos de ejemplo (están en GitHub). La información real de la empresa es
# confidencial: va en conocimiento_privado/, que no se sube, y si existe se usa en lugar de los ejemplos.
CONOCIMIENTO_DIR = BASE_DIR / "conocimiento_privado"
if not any(CONOCIMIENTO_DIR.glob("*.md")):
    CONOCIMIENTO_DIR = BASE_DIR / "conocimiento"
MAX_ARCHIVO_MB = 5

# Azure OpenAI Service
AZURE_OPENAI_ENDPOINT = _env("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = _env("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = _env("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = _env("AZURE_OPENAI_API_VERSION", "2024-10-21")

# Alternativa a Azure: cualquier servicio compatible con la API de OpenAI
# (OpenAI, Groq, OpenRouter, o un modelo local con Ollama). Se usa solo si Azure no está configurado.
IA_BASE_URL = _env("IA_BASE_URL")
IA_API_KEY = _env("IA_API_KEY")
IA_MODELO = _env("IA_MODELO")
# Cuánto "piensa" el modelo antes de responder (low, medium, high). Vacío = lo que use el modelo por defecto.
# Con Gemini, "low" responde unas 8 veces más rápido.
IA_RAZONAMIENTO = _env("IA_RAZONAMIENTO")

# Microsoft Entra ID (SSO)
ENTRA_TENANT_ID = _env("ENTRA_TENANT_ID")
ENTRA_CLIENT_ID = _env("ENTRA_CLIENT_ID")


# Dirección pública de la página (para los enlaces que se mandan por correo)
APP_URL = _env("APP_URL", "http://localhost:5173").rstrip("/")

# Correo saliente (SMTP). Con Microsoft 365: smtp.office365.com, puerto 587.
# Si SMTP_HOST está vacío, los correos se guardan como archivos .eml en CORREOS_DIR (solo para pruebas).
SMTP_HOST = _env("SMTP_HOST")
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USER = _env("SMTP_USER")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
SMTP_FROM = _env("SMTP_FROM", "Onboarding PluriOne <no-responder@develop.com.mx>")
SMTP_STARTTLS = _env("SMTP_STARTTLS", "true").lower() == "true"
CORREOS_DIR = Path(_env("CORREOS_DIR", str(BASE_DIR / "correos_enviados")))

# Vigencia de los enlaces que se envían por correo
HORAS_ENLACE_ACTIVACION = 72
MINUTOS_ENLACE_RESTABLECER = 30

# Primera cuenta de Recursos Humanos (se crea al iniciar si no existe ninguna).
# Si no pones contraseña, se envía un correo de activación.
ADMIN_NOMBRE = _env("ADMIN_NOMBRE", "Administrador RH")
ADMIN_CORREO = _env("ADMIN_CORREO").lower()
ADMIN_PASSWORD = _env("ADMIN_PASSWORD")


def azure_configurado() -> bool:
    return all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT])


def compatible_configurado() -> bool:
    return bool(IA_BASE_URL and IA_MODELO)


def ia_configurada() -> bool:
    return azure_configurado() or compatible_configurado()


def proveedor_ia() -> str:
    if azure_configurado():
        return f"Azure OpenAI ({AZURE_OPENAI_DEPLOYMENT})"
    if compatible_configurado():
        return f"{IA_MODELO}"
    return ""


def entra_configurado() -> bool:
    return bool(ENTRA_TENANT_ID and ENTRA_CLIENT_ID)
