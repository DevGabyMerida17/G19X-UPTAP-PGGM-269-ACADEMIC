"""WebSockets: chat con el Tutor IA y eventos en tiempo real para los paneles."""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from .. import cache, config, ia, nombres_agentes
from ..validaciones import nombre_de_pila
from ..db import SessionLocal
from ..models import ConsultaTutor, Usuario
from ..seguridad import requiere_rol, usuario_de_token
from ..servicios import progreso_para_tutor

router = APIRouter(tags=["tiempo real"])
log = logging.getLogger("tutor")

SALUDO = ("{saludo} Aquí te atienden el " + nombres_agentes.TUTOR_ONBOARDING + ", que te guía en tu proceso, te "
          "explica la plataforma y resuelve dudas sobre las políticas de PluriOne, y el "
          + nombres_agentes.CONOCIMIENTO_GENERAL + ", que responde cualquier otra pregunta o definición.")


def _autenticar(token: str | None, roles: tuple[str, ...]) -> Usuario | None:
    with SessionLocal() as db:
        u = usuario_de_token(db, token)
        return u if u and u.rol in roles and not u.debe_cambiar_password else None


@router.get("/api/tutor/historial")
def historial(u: Usuario = Depends(requiere_rol("colaborador"))):
    mensajes = cache.historial_chat(u.id)
    if not mensajes:
        pila = nombre_de_pila(u.nombre)
        mensajes = [{"rol": "tutor", "texto": SALUDO.format(saludo=f"¡Hola, {pila}!" if pila else "¡Hola!"), "fuentes": []}]
    return {"ia_configurada": config.ia_configurada(), "proveedor": config.proveedor_ia(), "mensajes": mensajes}


async def _responder(u: Usuario, pregunta: str) -> dict:
    with SessionLocal() as db:
        progreso = progreso_para_tutor(db, db.get(Usuario, u.id))
    previos = cache.historial_chat(u.id)
    r = await ia.obtener_agente().ainvoke({
        "pregunta": pregunta,
        "nombre": nombre_de_pila(u.nombre),
        "historial": [{"rol": m["rol"], "texto": m["texto"]} for m in previos],
        "progreso": progreso,
    })
    with SessionLocal() as db:
        db.add(ConsultaTutor(usuario_id=u.id, pregunta=pregunta[:1000], intencion=r.get("intencion", ""), tema=r.get("tema")))
        db.commit()
    if r.get("tema"):
        cache.publicar("consulta", tema=r["tema"])
    return {"rol": "tutor", "texto": r["respuesta"], "fuentes": r.get("fuentes", []), "agente": r.get("agente")}


@router.websocket("/ws/tutor")
async def ws_tutor(ws: WebSocket, token: str | None = None):
    u = _autenticar(token, ("colaborador",))
    if not u:
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            datos = await ws.receive_json()
            pregunta = str(datos.get("pregunta", "")).strip()[:1000]
            if not pregunta:
                continue
            if not _autenticar(token, ("colaborador",)):  # lo dieron de baja con el chat abierto
                await ws.send_json({"tipo": "error", "mensaje": "Tu cuenta fue dada de baja. Comunícate con Recursos Humanos."})
                await ws.close(code=4401)
                return
            if not config.ia_configurada():
                await ws.send_json({"tipo": "error", "mensaje": "La IA no está configurada: faltan los datos del modelo (Azure OpenAI u otro compatible) en el archivo .env del backend."})
                continue
            if cache.limite_excedido(f"tutor:{u.id}", config.TUTOR_LIMITE_POR_MINUTO):
                await ws.send_json({"tipo": "error", "mensaje": "Hiciste muchas preguntas seguidas. Espera un minuto."})
                continue
            cache.guardar_chat(u.id, {"rol": "usuario", "texto": pregunta, "fuentes": []})
            await ws.send_json({"tipo": "escribiendo"})
            try:
                respuesta = await _responder(u, pregunta)
            except HTTPException as e:
                await ws.send_json({"tipo": "error", "mensaje": e.detail})
                continue
            except Exception as e:  # red, credenciales o cuota del servicio de IA
                log.exception("Error del Tutor IA")
                await ws.send_json({"tipo": "error", "mensaje": f"El servicio de IA no respondió ({type(e).__name__}). Intenta de nuevo."})
                continue
            cache.guardar_chat(u.id, respuesta)
            await ws.send_json({"tipo": "respuesta", **respuesta})
    except WebSocketDisconnect:
        pass


@router.websocket("/ws/eventos")
async def ws_eventos(ws: WebSocket, token: str | None = None):
    """Los paneles de RH y supervisor se actualizan solos cuando algo cambia (Redis pub/sub)."""
    if not _autenticar(token, ("rh", "supervisor")):
        await ws.close(code=4401)
        return
    await ws.accept()
    pubsub = cache.ar().pubsub()
    await pubsub.subscribe(cache.CANAL_EVENTOS)

    async def reenviar():
        async for msg in pubsub.listen():
            if msg.get("type") == "message":
                await ws.send_text(msg["data"])

    tarea = asyncio.create_task(reenviar())
    try:
        while True:
            await ws.receive_text()  # mantiene la conexión; el cliente no necesita enviar nada
    except WebSocketDisconnect:
        pass
    finally:
        tarea.cancel()
        await pubsub.unsubscribe(cache.CANAL_EVENTOS)
        await pubsub.aclose()
