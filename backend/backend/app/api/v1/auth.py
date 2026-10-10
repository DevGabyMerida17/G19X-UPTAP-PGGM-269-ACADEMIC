"""
Intercambio del token OIDC de Microsoft Entra ID por la sesión propia de
la API (ver Documento_Arquitectura_Onboarding.docx §8.1).

El frontend nunca ve ni maneja contraseñas: hace el login contra Entra ID
directamente (MSAL.js u otra librería del lado del cliente), obtiene un
id_token, y se lo manda a este endpoint. Aquí se valida la firma de ese
token contra el JWKS público de Entra ID — nunca se confía en el token
tal cual llega, siempre se verifica.
"""
import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_session_token
from app.models.users import User

router = APIRouter(prefix="/auth", tags=["auth"])

_jwks_client = jwt.PyJWKClient(settings.ENTRA_JWKS_URL) if settings.ENTRA_JWKS_URL else None


class EntraCallbackRequest(BaseModel):
    id_token: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/callback", response_model=SessionResponse)
async def entra_callback(
    payload: EntraCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    if _jwks_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ENTRA_JWKS_URL no configurado — ver .env.example",
        )

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(payload.id_token)
        claims = jwt.decode(
            payload.id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.ENTRA_CLIENT_ID,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Entra ID inválido",
        ) from exc

    entra_id: str = claims["oid"]  # object id, estable, es lo que se guarda en users.entra_id
    email: str = claims.get("preferred_username") or claims["email"]

    result = await db.execute(select(User).where(User.entra_id == entra_id))
    user = result.scalar_one_or_none()

    if user is None:
        # Política a decidir: ¿se auto-provisiona aquí, o el login falla si
        # RH no dio de alta al colaborador primero? Ahora mismo falla —
        # es la opción más segura por defecto, pero afecta el flujo de
        # "Autenticación y alta de colaborador" del PRD §6.1.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe un colaborador registrado con esta cuenta. Contacta a RH.",
        )

    if user.status != "activo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta desactivada")

    token = create_session_token(user.id)
    return SessionResponse(access_token=token)
