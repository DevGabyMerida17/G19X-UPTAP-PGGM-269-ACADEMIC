from fastapi import APIRouter

from app.api.v1 import auth, health, onboarding, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(onboarding.router)

# Siguientes routers a agregar aquí, siguiendo el mismo patrón que
# users.py / onboarding.py (get_current_user o require_permission según
# el caso): documents, training, quizzes, quiz_exception_cases,
# agent conversations (probablemente WebSocket, no REST), supervisor
# followups.
