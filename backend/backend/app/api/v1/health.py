from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Sin auth — para que el balanceador/Docker sepan si el servicio vive."""
    return {"status": "ok"}
