"""Cliente de Redis.

Usos (según el documento del proyecto):
- Sesiones de usuario            -> sesion:<token>
- Estado de la conversación      -> chat:<usuario_id>
- Límite de peticiones al Tutor  -> limite:tutor:<usuario_id>:<minuto>
- Pub/sub de eventos en vivo     -> canal "eventos"
"""
import json
import time

import redis
import redis.asyncio as aredis

from . import config

CANAL_EVENTOS = "eventos"
_sync = None
_async = None
_servidor_falso = None


def _falso():
    global _servidor_falso
    import fakeredis

    if _servidor_falso is None:
        _servidor_falso = fakeredis.FakeServer()
    return fakeredis


def r() -> redis.Redis:
    global _sync
    if _sync is None:
        if config.REDIS_URL.startswith("memory://"):
            _sync = _falso().FakeRedis(server=_servidor_falso, decode_responses=True)
        else:
            _sync = redis.from_url(config.REDIS_URL, decode_responses=True)
    return _sync


def ar() -> aredis.Redis:
    global _async
    if _async is None:
        if config.REDIS_URL.startswith("memory://"):
            _async = _falso().FakeAsyncRedis(server=_servidor_falso, decode_responses=True)
        else:
            _async = aredis.from_url(config.REDIS_URL, decode_responses=True)
    return _async


def publicar(tipo: str, **datos) -> None:
    """Avisa a los paneles de RH y supervisores que algo cambió."""
    try:
        r().publish(CANAL_EVENTOS, json.dumps({"tipo": tipo, **datos}))
    except redis.RedisError:
        pass


def limite_excedido(clave: str, maximo: int, ventana_seg: int = 60) -> bool:
    k = f"limite:{clave}:{int(time.time() // ventana_seg)}"
    n = r().incr(k)
    if n == 1:
        r().expire(k, ventana_seg)
    return n > maximo


# ---- Historial del chat del Tutor ----
def historial_chat(usuario_id: int) -> list[dict]:
    return [json.loads(x) for x in r().lrange(f"chat:{usuario_id}", 0, -1)]


def guardar_chat(usuario_id: int, *mensajes: dict) -> None:
    k = f"chat:{usuario_id}"
    pipe = r().pipeline()
    for m in mensajes:
        pipe.rpush(k, json.dumps(m, ensure_ascii=False))
    pipe.ltrim(k, -40, -1)
    pipe.expire(k, 60 * 60 * 24 * 14)
    pipe.execute()
