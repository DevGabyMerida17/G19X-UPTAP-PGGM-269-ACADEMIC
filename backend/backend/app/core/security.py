"""
Autenticación y autorización.

Dos capas, que no hay que confundir:
1. Autenticación: ¿quién eres? — valida el JWT de la sesión (emitido por
   esta API tras validar el token OIDC de Microsoft Entra ID).
2. Autorización: ¿puedes hacer esto? — SIEMPRE por permiso, nunca por
   nombre de rol. Ver Definicion_MVP_Onboarding.docx §4 y schema.sql §0.

   MAL:  if current_user.role.name == "admin_rh": ...
   BIEN: require_permission("materials.manage")

La diferencia importa: si mañana un rol nuevo también necesita subir
material, se le asigna el permiso con un INSERT en role_permissions —
esta capa de código no cambia.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.rbac import Permission, RolePermission
from app.models.users import User

bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Emisión y validación del JWT de sesión (propio de esta API)
# ---------------------------------------------------------------------------

def create_session_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_session_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency base: resuelve el usuario autenticado a partir del JWT.
    No verifica permisos — para eso, componer con require_permission()."""
    user_id = decode_session_token(credentials.credentials)

    result = await db.execute(
        select(User).where(User.id == user_id).options(selectinload(User.role))
    )
    user = result.scalar_one_or_none()

    if user is None or user.status != "activo":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no válido o inactivo")

    return user


# ---------------------------------------------------------------------------
# Autorización por permiso — el corazón del RBAC configurable
# ---------------------------------------------------------------------------

async def _user_has_permission(db: AsyncSession, user: User, permission_code: str) -> bool:
    result = await db.execute(
        select(Permission.id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == user.role_id, Permission.code == permission_code)
    )
    return result.scalar_one_or_none() is not None


def require_permission(permission_code: str):
    """
    Factory de dependency de FastAPI. Uso en un router:

        @router.post("/modules/{id}/materials")
        async def upload_material(
            current_user: User = Depends(require_permission("materials.manage")),
        ):
            ...

    Si el usuario no tiene el permiso, corta con 403 antes de que el
    endpoint corra ni una línea de lógica de negocio.
    """
    async def _dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if not await _user_has_permission(db, current_user, permission_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes el permiso requerido: {permission_code}",
            )
        return current_user

    return _dependency
