"""API del Onboarding PluriOne (Python + FastAPI).

Ejecutar desde la carpeta backend:
    uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, rag, seed
from .db import SessionLocal
from .routers import auth, colaborador, rh, supervisor, tiempo_real

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    seed.inicializar()
    with SessionLocal() as db:
        rag.reconstruir(db)
    yield


app = FastAPI(title="Onboarding PluriOne", lifespan=ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (auth, colaborador, rh, supervisor, tiempo_real):
    app.include_router(r.router)


@app.get("/api/salud")
def salud():
    return {"ok": True, "ia_configurada": config.ia_configurada(), "ia_proveedor": config.proveedor_ia(),
            "entra_configurado": config.entra_configurado()}
