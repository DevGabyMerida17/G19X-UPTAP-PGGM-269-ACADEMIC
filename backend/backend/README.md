# Backend — Plataforma de Onboarding

FastAPI + PostgreSQL + Redis + SQLAlchemy async + Alembic. Ver el PRD y
`Documento_Arquitectura_Onboarding.docx` para el diseño completo; esto es
el esqueleto de arranque, no el sistema terminado.

## Cómo correrlo

```bash
cp .env.example .env
# edita .env: como mínimo, genera un JWT_SECRET_KEY real:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

docker compose up --build
```

Con los contenedores arriba, aplica la migración inicial (crea las 35
tablas + los roles/permisos semilla):

```bash
docker compose exec api alembic upgrade head
```

La API queda en `http://localhost:8000`, con documentación interactiva
en `http://localhost:8000/docs`.

## Estructura

```
app/
├── main.py              # instancia de FastAPI, monta el router de v1
├── core/
│   ├── config.py        # Settings — todo lo que viene de variables de entorno
│   ├── database.py      # engine async, get_db()
│   └── security.py      # JWT + require_permission() — LEE ESTE ARCHIVO PRIMERO
├── models/               # un modelo SQLAlchemy por tabla de schema.sql
├── schemas/              # Pydantic — lo que la API realmente expone
└── api/v1/                # un router por recurso
alembic/                   # migraciones — la 0001 carga db/schema.sql completo
db/schema.sql               # copia versionada del esquema (fuente de verdad)
tests/
```

## El patrón que hay que repetir para cada recurso nuevo

Ya está resuelto una vez en `app/api/v1/onboarding.py` y `users.py` — para
un recurso nuevo, el molde es:

1. Modelo en `app/models/` (probablemente ya existe, ver §2 abajo).
2. Esquema Pydantic en `app/schemas/`.
3. Router en `app/api/v1/`, con `Depends(require_permission("codigo.del.permiso"))`
   en vez de comparar el rol a mano. Los códigos de permiso ya están
   sembrados en la base de datos — ver la sección `role_permissions` al
   final de `db/schema.sql`.
4. Registrar el router en `app/api/v1/router.py`.

## Qué falta (a propósito — esto es el punto de partida, no el final)

- **Documentos, capacitación, cuestionarios, casos de excepción**: los
  modelos ya existen (`app/models/onboarding.py`, `training.py`, `quiz.py`),
  faltan sus routers — replicar el patrón de `onboarding.py`.
- **Agentes**: el chat con LangGraph/LangChain va casi con certeza por
  WebSocket, no REST — no se modeló aquí porque es su propio diseño
  (colas, streaming de tokens, manejo de estado de conversación en
  Redis). Los modelos de datos (`app/models/agents.py`) ya están listos
  para lo que ese router necesite persistir.
- **Generación automática del checklist**: al crear un `OnboardingProcess`,
  falta la lógica que lee `template_checklist_items` y genera las filas
  de `tasks`/`documents`/`training_progress` — está marcado con un TODO
  en `app/api/v1/onboarding.py::create_process`.
- **Regla de escalamiento** (`quiz_exception_cases.escalated_to`): sigue
  sin definirse a quién se asigna un caso — ver PRD.md §11. Bloquea
  construir el router de casos de excepción con criterio real.
- **Rate limiting y caché de permisos en Redis**: `require_permission()`
  hoy hace un JOIN en cada request. Funciona, pero vale la pena cachear
  el resultado por sesión antes de que el número de requests crezca.

## Una honestidad, no una excusa

Las versiones fijadas en `requirements.txt` son las que conocía al momento
de escribir esto — corre `pip list --outdated` después de instalar y
confirma que no haya versiones más nuevas con parches de seguridad antes
de usar esto en algo real.
