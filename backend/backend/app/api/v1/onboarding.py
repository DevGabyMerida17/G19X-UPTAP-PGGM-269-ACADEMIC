"""
Procesos de onboarding — incluye el patrón de la vista del supervisor,
que es la consulta más importante de todo el diseño de roles:

    SELECT ... FROM onboarding_processes op
    JOIN users u ON u.id = op.user_id
    WHERE u.manager_id = :supervisor_id

Esto es LO QUE HACE que el supervisor sea de solo lectura y esté
acotado a su equipo — no hay una tabla separada de "equipos", es
users.manager_id resuelto en tiempo de consulta.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_permission
from app.models.onboarding import OnboardingProcess
from app.models.users import User
from app.schemas.onboarding import OnboardingProcessCreate, OnboardingProcessRead, TeamMemberProgress

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/me", response_model=OnboardingProcessRead)
async def read_own_process(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OnboardingProcess:
    result = await db.execute(
        select(OnboardingProcess).where(OnboardingProcess.user_id == current_user.id)
    )
    process = result.scalar_one_or_none()
    if process is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No tienes un proceso de onboarding activo")
    return process


@router.get("/team", response_model=list[TeamMemberProgress])
async def read_team_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("team.progress.view")),
) -> list[TeamMemberProgress]:
    """Vista del supervisor. team.progress.view la tienen supervisor y
    admin_rh (ver semilla en schema.sql) — pero OJO: esto solo verifica
    el PERMISO, no acota el resultado. El WHERE manager_id=... de abajo
    es lo que realmente limita al supervisor a su propio equipo. Un
    admin_rh con este mismo permiso, si se reutiliza este endpoint sin
    cambios, también quedaría acotado a "su equipo" (que normalmente es
    ninguno) — en la práctica, RH usa /onboarding/all (processes.view_all)
    para ver todo, no este endpoint."""
    result = await db.execute(
        select(
            User.id.label("user_id"),
            User.full_name,
            OnboardingProcess.id.label("process_id"),
            OnboardingProcess.status,
            OnboardingProcess.progress_percentage,
        )
        .join(OnboardingProcess, OnboardingProcess.user_id == User.id)
        .where(User.manager_id == current_user.id)
    )
    return [TeamMemberProgress(**row._mapping) for row in result.all()]


@router.get("/all", response_model=list[OnboardingProcessRead])
async def read_all_processes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("processes.view_all")),
) -> list[OnboardingProcess]:
    """Panel de RH: todos los procesos, sin filtrar por equipo."""
    result = await db.execute(select(OnboardingProcess).order_by(OnboardingProcess.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=OnboardingProcessRead, status_code=status.HTTP_201_CREATED)
async def create_process(
    payload: OnboardingProcessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
) -> OnboardingProcess:
    # TODO: al crear el proceso, resolver la plantilla (template_id) y
    # generar automáticamente las filas de tasks/documents/training_progress
    # a partir de template_checklist_items — ver PRD.md §6.1. Ese es
    # justamente el siguiente pedazo de lógica de negocio a construir.
    process = OnboardingProcess(**payload.model_dump())
    db.add(process)
    await db.commit()
    await db.refresh(process)
    return process
