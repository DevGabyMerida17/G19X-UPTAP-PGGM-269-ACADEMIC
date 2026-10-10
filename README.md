# Plataforma de Onboarding Interactivo Guiado por Agentes Inteligentes

Proyecto de estadía para **PluriOne S.A. de C.V. (Develop Talent & Technology)**. Es una plataforma web que automatiza y personaliza la incorporación de nuevos colaboradores.

## Tecnologías

| Componente | Tecnología | Dónde está |
|---|---|---|
| Frontend web | React.js (Vite) | `frontend/src` |
| API backend | Python + FastAPI, con WebSocket para el chat | `backend/app/main.py`, `backend/app/routers` |
| Capa de agentes | LangGraph + LangChain | `backend/app/agente.py`, `backend/app/rag.py` |
| Modelos de lenguaje | Azure OpenAI Service | `backend/app/ia.py` |
| Base de datos | PostgreSQL (SQLAlchemy) | `backend/app/models.py` |
| Caché / estado | Redis: sesiones, enlaces de un solo uso, historial del chat, límite de peticiones y pub/sub | `backend/app/cache.py` |
| Autenticación | Microsoft Entra ID (MSAL) y correo con contraseña | `backend/app/seguridad.py`, `frontend/src/paginas/Acceso.jsx` |
| Correo | SMTP (Microsoft 365 u otro); Mailpit para pruebas | `backend/app/correo.py` |
| CI/CD | GitHub Actions | `.github/workflows/ci.yml` |
| Contenedores | Docker + Docker Compose | `docker-compose.yml`, `*/Dockerfile` |
| Metodología | Scrum | — |

## Cuentas y acceso

- **Nadie se registra solo.** Recursos Humanos da de alta a cada persona en **Personal → Dar de alta**: colaboradores, supervisores (responsables) y otras cuentas de RH.
- Al darla de alta, la persona recibe un **correo de invitación** para crear su contraseña. El enlace vence en 72 horas y RH puede reenviarlo.
- **¿Olvidaste tu contraseña?:** desde la pantalla de inicio llega un correo con un enlace que vence en 30 minutos y sirve una sola vez. Al cambiar la contraseña se cierran las sesiones abiertas.
- **Bajas:** RH puede dar de baja (y reactivar) a cualquier persona. Una cuenta dada de baja no puede entrar y ve el aviso "Tu cuenta fue dada de baja y está inactiva". Si tenía la sesión abierta, el aviso aparece en su siguiente acción.
- **Responsables:** cada colaborador tiene un supervisor responsable que RH asigna o cambia. Cada supervisor ve solo a las personas que tiene asignadas.
- **Primera cuenta de RH:** se crea al arrancar con `ADMIN_CORREO` del archivo `.env`. Si no pones `ADMIN_PASSWORD`, le llega el correo de invitación.

## Cómo funciona el Tutor IA

El Tutor usa **Azure OpenAI de verdad**: cada pregunta se envía al modelo. No hay respuestas escritas en el código. Funciona como un grafo de **LangGraph**:

1. **clasificar**: el modelo decide qué tipo de pregunta es.
2. **Dudas de la empresa** (vacaciones, nómina, políticas): busca en la base de conocimiento que administra RH y responde **solo** con esos documentos, citando la fuente, para no inventar reglas ni fechas.
3. **Dudas de aprendizaje** ("¿qué es Docker?", "explícame Scrum con un ejemplo", "¿cómo reconozco un phishing?"): el modelo explica con su propio conocimiento, adaptado al puesto y avance del colaborador. Si hay documentos de PluriOne relacionados, también los usa y los cita.
4. **¿Qué hago ahora?**: revisa el avance real del colaborador (documentos, módulos, evaluaciones y tareas) y le dice su siguiente paso.

Para que responda, el backend necesita los datos de Azure OpenAI (ver abajo). Sin ellos, el chat avisa que falta la clave.

## Ejecutar con Docker (recomendado)

1. Abre Docker Desktop.
2. Copia `backend/.env.example` como `backend/.env` y llena:
   - `ADMIN_CORREO` (y opcionalmente `ADMIN_NOMBRE` y `ADMIN_PASSWORD`).
   - Los datos de Azure OpenAI.
   - Para pruebas de correo: `SMTP_HOST=mailpit`, `SMTP_PORT=1025` y `SMTP_STARTTLS=false`.
3. En la carpeta del proyecto ejecuta:

```bash
docker compose up --build
```

4. Abre http://localhost:8080. Los correos de prueba (invitaciones y cambio de contraseña) se ven en http://localhost:8025.

La primera vez se crean las tablas y los datos iniciales: programas, módulos, preguntas, tareas, la cuenta de RH y algunos colaboradores y responsables de ejemplo. Los de ejemplo no tienen contraseña. Para no cargarlos, pon `CARGAR_DATOS_DEMO=false`.

## Ejecutar sin Docker (desarrollo)

Necesitas Python 3.12 y Node.js 24. En `backend/.env` puedes usar `DATABASE_URL=sqlite:///dev.db` y `REDIS_URL=memory://` para probar sin PostgreSQL ni Redis. Si dejas `SMTP_HOST` vacío, los correos se guardan como archivos `.eml` en `backend/correos_enviados`.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

En otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173

## Configurar Azure OpenAI (necesario para el Tutor IA)

1. En el [portal de Azure](https://portal.azure.com) crea un recurso **Azure OpenAI**. Si eres estudiante, puedes usar los créditos de **Azure for Students**.
2. En **Azure AI Foundry**, crea una implementación (deployment) de un modelo de chat, por ejemplo `gpt-4o-mini`.
3. En el recurso, abre **Claves y punto de conexión** y copia en `backend/.env`:
   - `AZURE_OPENAI_ENDPOINT`: el punto de conexión.
   - `AZURE_OPENAI_API_KEY`: una de las claves.
   - `AZURE_OPENAI_DEPLOYMENT`: el nombre de tu implementación.
4. Comprueba la conexión desde la carpeta `backend`:

```bash
python -m app.probar_ia
```

Si muestra "Azure OpenAI respondió: …", el Tutor ya funciona. Si hay un error, el mensaje dice qué dato revisar.

## Configurar el correo (SMTP)

Con Microsoft 365 usa `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587` y `SMTP_STARTTLS=true`. En `SMTP_USER` y `SMTP_PASSWORD` va una cuenta que tenga habilitado "SMTP AUTH". `APP_URL` debe ser la dirección pública de la página para que los enlaces de los correos funcionen.

## Configurar Microsoft Entra ID

El botón **Continuar con Microsoft** siempre aparece, pero solo funciona cuando se configura:

1. En el portal de Azure ve a **Microsoft Entra ID → Registros de aplicaciones → Nuevo registro**.
2. En **Autenticación** agrega la plataforma **Aplicación de página única (SPA)** con el URI de redirección `http://localhost:8080` (y `http://localhost:5173` para desarrollo).
3. Copia el **Id. de directorio (inquilino)** en `ENTRA_TENANT_ID` y el **Id. de aplicación (cliente)** en `ENTRA_CLIENT_ID`.

Solo pueden entrar con Microsoft las personas que RH ya dio de alta con ese mismo correo.

## Pruebas

```bash
cd backend
pytest
```

Las pruebas usan SQLite, un Redis simulado y un modelo falso para el agente, así que no gastan créditos de Azure. Cubren el alta por RH con invitación, olvidé mi contraseña, bajas, responsables, capacitación, documentos, permisos y las rutas del Tutor. GitHub Actions corre estas pruebas, compila el frontend y construye las imágenes de Docker en cada cambio.

## Pendientes antes de producción

- **Contenido de ejemplo:** el documento "Beneficios y nómina" es de ejemplo y hay que reemplazarlo con la información oficial de RH.
- **Integración con HRIS:** la sincronización con el sistema de RH de la empresa todavía no está implementada.
- **Migraciones:** las tablas se crean al arrancar. Si ya tenías una base de datos de una versión anterior, bórrala o agrega Alembic para migrarla.
