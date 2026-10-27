"""Contraseñas, sesiones (en Redis) y validación de tokens de Microsoft Entra ID."""
import secrets
from functools import lru_cache

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import cache, config
from .db import get_db
from .models import RolPermiso, Usuario


_ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"  # sin 0/O ni 1/l/I para evitar confusiones


def password_temporal() -> str:
    """Ej. 'Kx7m-Qp4t-Zr9w': al azar, fácil de dictar y con letras y números."""
    while True:
        p = "-".join("".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(3))
        if any(c.isdigit() for c in p) and any(c.isalpha() for c in p):
            return p


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


MENSAJE_BAJA = ("Tu cuenta fue dada de baja y está inactiva, por eso no puedes entrar a la plataforma. "
                "Si crees que es un error, comunícate con Recursos Humanos.")


def error_cuenta_inactiva() -> HTTPException:
    return HTTPException(403, {"codigo": "cuenta_inactiva", "mensaje": MENSAJE_BAJA})


# ---------- Sesiones ----------
# sesion:<token> -> id del usuario; sesiones_de:<id> -> tokens de ese usuario (para cerrarlas todas).
def crear_sesion(usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    ttl = config.SESION_HORAS * 3600
    pipe = cache.r().pipeline()
    pipe.set(f"sesion:{token}", usuario_id, ex=ttl)
    pipe.sadd(f"sesiones_de:{usuario_id}", token)
    pipe.expire(f"sesiones_de:{usuario_id}", ttl)
    pipe.execute()
    return token


def cerrar_sesion(token: str) -> None:
    uid = cache.r().get(f"sesion:{token}")
    cache.r().delete(f"sesion:{token}")
    if uid:
        cache.r().srem(f"sesiones_de:{uid}", token)


def cerrar_todas_las_sesiones(usuario_id: int) -> None:
    """Se usa al dar de baja a alguien o al cambiar su contraseña."""
    tokens = cache.r().smembers(f"sesiones_de:{usuario_id}")
    if tokens:
        cache.r().delete(*[f"sesion:{t}" for t in tokens])
    cache.r().delete(f"sesiones_de:{usuario_id}")


def usuario_de_token(db: Session, token: str | None, incluir_inactivos: bool = False) -> Usuario | None:
    if not token:
        return None
    uid = cache.r().get(f"sesion:{token}")
    if not uid:
        return None
    u = db.get(Usuario, int(uid))
    if not u or (not u.activo and not incluir_inactivos):
        return None
    return u


# ---------- Enlaces de un solo uso (activar cuenta / restablecer contraseña) ----------
def crear_enlace(tipo: str, usuario_id: int, segundos: int) -> str:
    token = secrets.token_urlsafe(32)
    cache.r().set(f"enlace:{tipo}:{token}", usuario_id, ex=segundos)
    return token


def leer_enlace(token: str) -> tuple[str, int] | None:
    for tipo in ("activar", "restablecer"):
        uid = cache.r().get(f"enlace:{tipo}:{token}")
        if uid:
            return tipo, int(uid)
    return None


def usar_enlace(token: str) -> tuple[str, int] | None:
    """Lee y borra el enlace para que no se pueda usar dos veces."""
    for tipo in ("activar", "restablecer"):
        uid = cache.r().getdel(f"enlace:{tipo}:{token}")
        if uid:
            return tipo, int(uid)
    return None


def _token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


# Rutas que se pueden usar mientras la persona sigue con su contraseña temporal
RUTAS_CON_PASSWORD_TEMPORAL = {"/api/auth/yo", "/api/auth/cambiar-password", "/api/auth/salir"}


def usuario_actual(request: Request, authorization: str | None = Header(None), db: Session = Depends(get_db)) -> Usuario:
    u = usuario_de_token(db, _token(authorization), incluir_inactivos=True)
    if not u:
        raise HTTPException(401, "Tu sesión expiró. Vuelve a iniciar sesión.")
    if not u.activo:
        cerrar_todas_las_sesiones(u.id)
        raise error_cuenta_inactiva()
    if u.debe_cambiar_password and request.url.path not in RUTAS_CON_PASSWORD_TEMPORAL:
        raise HTTPException(403, {"codigo": "cambio_obligatorio",
                                  "mensaje": "Antes de continuar, crea tu propia contraseña."})
    return u


def tiene_permiso(db: Session, u: Usuario, permiso: str) -> bool:
    """Consulta en rol_permisos si el rol de la persona tiene ese permiso (ver app/permisos.py)."""
    return db.scalar(select(RolPermiso.rol_clave).where(
        RolPermiso.rol_clave == u.rol, RolPermiso.permiso_clave == permiso)) is not None


def requiere_permiso(permiso: str):
    def dep(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)) -> Usuario:
        if not tiene_permiso(db, u, permiso):
            raise HTTPException(403, "No tienes permiso para esta sección.")
        return u
    return dep


# ---------- Microsoft Entra ID ----------
@lru_cache
def _jwks() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://login.microsoftonline.com/{config.ENTRA_TENANT_ID}/discovery/v2.0/keys")


def validar_token_entra(id_token: str) -> dict:
    """Valida la firma, audiencia y emisor del id_token que entrega MSAL en el navegador."""
    if not config.entra_configurado():
        raise HTTPException(503, "Microsoft Entra ID no está configurado.")
    try:
        clave = _jwks().get_signing_key_from_jwt(id_token)
        return jwt.decode(
            id_token,
            clave.key,
            algorithms=["RS256"],
            audience=config.ENTRA_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{config.ENTRA_TENANT_ID}/v2.0",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(401, "El token de Microsoft no es válido.") from e
