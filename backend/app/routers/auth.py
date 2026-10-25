"""Inicio de sesión (correo o Microsoft Entra ID), activación de cuenta y cambio de contraseña.

Las cuentas las crea Recursos Humanos; nadie puede registrarse por su cuenta.
"""
import re

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import cache, config, correo, nombres_agentes
from ..db import get_db
from ..models import AREAS, Usuario
from ..validaciones import validar_correo
from ..seguridad import (
    cerrar_sesion, cerrar_todas_las_sesiones, crear_enlace, crear_sesion, error_cuenta_inactiva, hash_password,
    leer_enlace, usar_enlace, usuario_actual, validar_token_entra, verificar_password,
)

router = APIRouter(prefix="/api", tags=["auth"])

MENSAJE_OLVIDE = ("Si el correo está registrado y la cuenta está activa, te enviamos un enlace para cambiar "
                  f"tu contraseña. Revisa tu bandeja de entrada (el enlace vence en {config.MINUTOS_ENLACE_RESTABLECER} minutos).")


def perfil(u: Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "correo": u.correo, "rol": u.rol, "puesto": u.puesto,
            "area": u.area, "fecha_ingreso": u.fecha_ingreso.isoformat(),
            "debe_cambiar_password": u.debe_cambiar_password}


def validar_password(v: str) -> str:
    if any(c.isspace() for c in v):
        raise ValueError("La contraseña no puede tener espacios.")
    if len(v) < 8 or not re.search(r"\d", v) or not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]", v):
        raise ValueError("La contraseña debe tener al menos 8 caracteres, una letra y un número.")
    return v


class Login(BaseModel):
    correo: str = Field(max_length=200)

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, v: str) -> str:
        return validar_correo(v)
    password: str


class LoginMicrosoft(BaseModel):
    id_token: str


class CambioPassword(BaseModel):
    nueva: str = Field(max_length=128)

    @field_validator("nueva")
    @classmethod
    def password_segura(cls, v: str) -> str:
        return validar_password(v)


class Olvide(BaseModel):
    correo: str = Field(max_length=200)

    @field_validator("correo")
    @classmethod
    def correo_valido(cls, v: str) -> str:
        return validar_correo(v)


class NuevaPassword(BaseModel):
    token: str
    password: str = Field(max_length=128)

    @field_validator("password")
    @classmethod
    def password_segura(cls, v: str) -> str:
        return validar_password(v)


@router.get("/config")
def configuracion_publica():
    """Datos que necesita el frontend al arrancar."""
    return {
        "ia_configurada": config.ia_configurada(),
        "entra": {"tenant_id": config.ENTRA_TENANT_ID, "client_id": config.ENTRA_CLIENT_ID} if config.entra_configurado() else None,
        "areas": list(AREAS),
        "agentes": nombres_agentes.todos(),
    }


@router.post("/auth/login")
def login(datos: Login, db: Session = Depends(get_db)):
    correo_ = datos.correo
    if cache.limite_excedido(f"login:{correo_}", 10):
        raise HTTPException(429, "Demasiados intentos. Espera un minuto.")
    u = db.scalar(select(Usuario).where(Usuario.correo == correo_))
    # A quien fue dado de baja se le avisa siempre, aunque escriba mal la contraseña.
    if u and not u.activo:
        raise error_cuenta_inactiva()
    if not u or not verificar_password(datos.password, u.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos. Si eres nuevo, usa la contraseña temporal "
                                 "que te entregó Recursos Humanos.")
    return {"token": crear_sesion(u.id), "usuario": perfil(u)}


@router.post("/auth/microsoft")
def login_microsoft(datos: LoginMicrosoft, db: Session = Depends(get_db)):
    claims = validar_token_entra(datos.id_token)
    oid = claims.get("oid")
    correo_ = (claims.get("preferred_username") or claims.get("email") or "").lower()
    u = db.scalar(select(Usuario).where(Usuario.entra_oid == oid)) or \
        db.scalar(select(Usuario).where(Usuario.correo == correo_))
    if not u:
        raise HTTPException(403, "Tu cuenta de Microsoft no está registrada en la plataforma. "
                                 "Pide a Recursos Humanos que te dé de alta.")
    if not u.activo:
        raise error_cuenta_inactiva()
    u.entra_oid = oid
    db.commit()
    return {"token": crear_sesion(u.id), "usuario": perfil(u)}


@router.post("/auth/olvide")
def olvide_password(datos: Olvide, tareas: BackgroundTasks, db: Session = Depends(get_db)):
    """Siempre responde lo mismo para no revelar qué correos existen."""
    correo_ = datos.correo
    if cache.limite_excedido(f"olvide:{correo_}", 3, ventana_seg=600):
        raise HTTPException(429, "Ya pediste varios enlaces. Espera unos minutos y revisa tu correo.")
    u = db.scalar(select(Usuario).where(Usuario.correo == correo_))
    if u and u.activo:
        token = crear_enlace("restablecer", u.id, config.MINUTOS_ENLACE_RESTABLECER * 60)
        tareas.add_task(correo.restablecer, u.nombre, u.correo, token)
    return {"mensaje": MENSAJE_OLVIDE}


@router.get("/auth/enlace/{token}")
def revisar_enlace(token: str, db: Session = Depends(get_db)):
    """El frontend lo usa para mostrar el formulario correcto (activar o restablecer)."""
    datos = leer_enlace(token)
    u = db.get(Usuario, datos[1]) if datos else None
    if not u:
        raise HTTPException(400, "El enlace no es válido o ya venció. Solicita uno nuevo.")
    if not u.activo:
        raise error_cuenta_inactiva()
    return {"tipo": datos[0], "nombre": u.nombre, "correo": u.correo}


@router.post("/auth/nueva-password")
def guardar_password(datos: NuevaPassword, db: Session = Depends(get_db)):
    enlace = usar_enlace(datos.token)
    u = db.get(Usuario, enlace[1]) if enlace else None
    if not u:
        raise HTTPException(400, "El enlace no es válido o ya venció. Solicita uno nuevo.")
    if not u.activo:
        raise error_cuenta_inactiva()
    u.password_hash = hash_password(datos.password)
    u.debe_cambiar_password = False
    db.commit()
    cerrar_todas_las_sesiones(u.id)  # por seguridad se cierran las sesiones abiertas
    return {"ok": True, "tipo": enlace[0], "correo": u.correo}


@router.post("/auth/cambiar-password")
def cambiar_password(datos: CambioPassword, authorization: str | None = Header(None),
                     u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Primer inicio de sesión con la contraseña temporal de RH (o cambio voluntario)."""
    if verificar_password(datos.nueva, u.password_hash):
        raise HTTPException(400, "La contraseña nueva debe ser distinta a la temporal.")
    u.password_hash = hash_password(datos.nueva)
    u.debe_cambiar_password = False
    db.commit()
    # Se cierran las demás sesiones y se conserva la actual
    actual = authorization[7:].strip() if authorization else ""
    cerrar_todas_las_sesiones(u.id)
    nuevo_token = crear_sesion(u.id)
    if actual:
        cerrar_sesion(actual)
    return {"token": nuevo_token, "usuario": perfil(u)}


@router.get("/auth/yo")
def yo(u: Usuario = Depends(usuario_actual)):
    return perfil(u)


@router.post("/auth/salir")
def salir(authorization: str | None = Header(None)):
    if authorization and authorization.lower().startswith("bearer "):
        cerrar_sesion(authorization[7:].strip())
    return {"ok": True}
