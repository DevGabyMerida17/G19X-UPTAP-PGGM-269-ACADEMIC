# Plataforma de Onboarding Interactivo Guiado por Agentes Inteligentes

Proyecto de estadía para **PluriOne S.A. de C.V. (Develop Talent & Technology)**. Es una plataforma web que automatiza y personaliza la incorporación de nuevos colaboradores.

## Tecnologías

| Componente | Tecnología | Dónde está |
|---|---|---|
| Frontend web | React.js (Vite) | `frontend/src` |
| API backend | Python + FastAPI, con WebSocket para el chat | `backend/app/main.py`, `backend/app/routers` |
| Capa de agentes | LangGraph + LangChain | `backend/app/agente.py`, `backend/app/rag.py` |
| Modelos de lenguaje | Azure OpenAI Service (principal) y Google Gemini (alternativa, la que se usa ahora) | `backend/app/ia.py` |
| Base de datos | PostgreSQL (SQLAlchemy) con migraciones de Alembic | `backend/app/models.py`, `backend/migraciones/` |
| Caché / estado | Redis: sesiones, enlaces de un solo uso, historial del chat, límite de peticiones y pub/sub | `backend/app/cache.py` |
| Autenticación | Correo con contraseña y Microsoft Entra ID (MSAL, listo para activarse) | `backend/app/seguridad.py`, `frontend/src/paginas/Acceso.jsx` |
| Correo | SMTP (Microsoft 365 u otro); Mailpit para pruebas | `backend/app/correo.py` |
| CI/CD | GitHub Actions | `.github/workflows/ci.yml` |
| Contenedores | Docker + Docker Compose | `docker-compose.yml`, `*/Dockerfile` |
| Metodología | Scrum | — |

## Estado de Azure OpenAI y Microsoft Entra ID

Las dos integraciones con Microsoft están **programadas y probadas**, pero necesitan datos que solo entrega una cuenta de Azure de la organización. No fue posible obtenerlos con una cuenta personal ni de estudiante: Azure for Students rechazó la cuenta ("No tiene acceso") y Entra ID exige un directorio organizacional para registrar aplicaciones.

| Integración | Estado | Qué falta para activarla |
|---|---|---|
| **Azure OpenAI** | Programada (`AzureChatOpenAI`). Mientras tanto, los agentes funcionan con **Google Gemini**. | Poner `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` y `AZURE_OPENAI_DEPLOYMENT` en `backend/.env`. Si están, se usa Azure en lugar de Gemini, sin cambiar código. |
| **Microsoft Entra ID** (botón "Continuar con Microsoft") | Programado: MSAL en el navegador, validación del token en el backend y prueba automática. Mientras no se configure, el botón avisa que todavía no está habilitado. | Que TI de PluriOne registre la aplicación y entregue `ENTRA_TENANT_ID` y `ENTRA_CLIENT_ID` (ver [Configurar Microsoft Entra ID](#configurar-microsoft-entra-id)). |

Como la capa de agentes usa LangChain, cambiar de proveedor de IA no toca a los agentes: solo cambia la conexión en `backend/app/ia.py`. Mientras no se activen estas integraciones, la plataforma funciona completa con correo y contraseña y con Gemini.

## Cuentas y acceso

- **Nadie se registra solo.** Recursos Humanos da de alta a cada persona en **Personal → Dar de alta**: colaboradores, supervisores (responsables) y otras cuentas de RH.
- Al darla de alta, el sistema genera una **contraseña temporal**: RH la ve en pantalla y también se le envía a la persona por correo. En su primer inicio de sesión la plataforma le pide crear su propia contraseña. RH puede generar una nueva contraseña temporal cuando haga falta.
- **¿Olvidaste tu contraseña?:** desde la pantalla de inicio llega un correo con un enlace que vence en 30 minutos y sirve una sola vez. Al cambiar la contraseña se cierran las sesiones abiertas.
- **Bajas:** RH puede dar de baja (y reactivar) a cualquier persona. Una cuenta dada de baja no puede entrar y ve el aviso "Tu cuenta fue dada de baja y está inactiva". Si tenía la sesión abierta, el aviso aparece en su siguiente acción.
- **Roles y permisos:** los roles (colaborador, supervisor, RH) y lo que puede hacer cada uno están en las tablas `roles`, `permisos` y `rol_permisos`, no en el código. Cada ruta pide un permiso (lista en `backend/app/permisos.py`); para dar o quitar uno a un rol se agrega o borra su fila en `rol_permisos`. `GET /api/rh/roles` muestra el catálogo.
- **Responsables:** cada colaborador tiene un supervisor responsable que RH asigna o cambia. Cada supervisor ve solo a las personas que tiene asignadas.
- **Escalamiento:** si un colaborador agota sus intentos en una evaluación, aparece primero en "Mi equipo" de su responsable con la etiqueta "Agotó intentos", y el responsable puede concederle un intento más.
- **Primera cuenta de RH:** se crea al arrancar con `ADMIN_CORREO` del archivo `.env`. Si no pones `ADMIN_PASSWORD`, le llega el correo de invitación.

## Agentes de IA

La plataforma tiene **5 agentes**. Todos usan un modelo de lenguaje real (Azure OpenAI o un servicio compatible); no hay respuestas escritas en el código.

| Agente | Dónde trabaja | Qué hace | Archivo |
|---|---|---|---|
| **Agente de Conocimiento General** | Chat del Tutor IA | Responde preguntas generales, explica conceptos y resuelve dudas de cualquier tema con el conocimiento del modelo, **sin** consultar documentos internos. | `backend/app/agente.py` |
| **Tutor de Onboarding** | Chat del Tutor IA | Guía al colaborador en su incorporación, explica cómo usar la plataforma, revisa su avance y le dice qué sigue. Para políticas y procedimientos responde **solo** con la documentación oficial que sube RH (RAG) y cita la fuente. | `backend/app/agente.py` |
| **Agente Evaluador** | Al terminar una evaluación | La calificación la calcula el sistema; el agente explica cada error, dice qué temas reforzar y orienta según los intentos que quedan. Cada evaluación tiene **3 intentos** (RH lo cambia por módulo; el responsable o RH pueden conceder uno más). | `backend/app/evaluador.py` |
| **Agente Recomendador** | Inicio del colaborador y "Mi equipo" del supervisor | Analiza el progreso y los temas débiles y recomienda módulos, materiales y actividades. Al supervisor le sugiere cómo dar seguimiento. | `backend/app/recomendador.py` |
| **Asistente de RH** | Panel de RH → "Asistente de RH" | Responde preguntas de RH con los datos reales de la plataforma ("¿quién va retrasado?", "¿cuántos documentos faltan por revisar?"). | `backend/app/asistente_rh.py` |

En el chat, un **orquestador** hecho con **LangGraph** decide si la pregunta la atiende el Agente de Conocimiento General o el Tutor de Onboarding.

**Cambiar los nombres de los agentes:** edítalos en `backend/app/nombres_agentes.py` y reinicia el backend. El nombre nuevo aparece en el chat, las evaluaciones, las recomendaciones y el panel de RH, y también en las instrucciones de cada agente.

Para que respondan, el backend necesita los datos de un modelo de IA en `backend/.env` (ver abajo). Sin ellos, cada agente avisa que la IA no está configurada.

## Uso de IA

### En la plataforma

- **Proveedor:** Azure OpenAI Service es el principal; mientras no haya suscripción se usa Google Gemini (ver [Estado de Azure OpenAI y Microsoft Entra ID](#estado-de-azure-openai-y-microsoft-entra-id)). La conexión está en `backend/app/ia.py`.
- **Qué datos recibe el modelo:**
  - Tutor y Conocimiento General: la pregunta, los últimos mensajes del chat, el nombre de pila y el resumen del avance (puesto, área, estado de módulos, documentos, evaluaciones y tareas pendientes).
  - Tutor de Onboarding: además, los fragmentos de la base de conocimiento que encontró la búsqueda.
  - Agente Evaluador: el contenido del módulo, las preguntas y las respuestas elegidas.
  - Agente Recomendador: el avance y los temas débiles.
  - Asistente de RH: un resumen del personal (nombre, puesto, área, avance, evaluaciones y estado de documentos).
- **Qué no recibe:** contraseñas, tokens ni los archivos que suben los colaboradores.
- **Las decisiones las toma el sistema o una persona, no la IA:** la calificación la calcula el backend, el desbloqueo de módulos y el límite de intentos son reglas del código, y el intento extra lo concede el responsable o RH. Los agentes explican, orientan y recomiendan.
- **Para evitar respuestas inventadas:** el Tutor responde sobre PluriOne solo con la base de conocimiento y cita la fuente; el Asistente de RH responde solo con los datos de la plataforma; el Recomendador descarta módulos que no existen.
- **Costos y límites:** máximo de mensajes por minuto en el Tutor y el Asistente de RH (`TUTOR_LIMITE_POR_MINUTO`), historial acotado, y la retroalimentación y las recomendaciones se guardan para no generarlas dos veces.
- **Si la IA falla o no está configurada,** la plataforma sigue funcionando y cada agente avisa que no está disponible.
- **Pruebas:** `backend/tests/` usa un modelo falso, así que no se envían datos a ningún proveedor al correr `pytest`.

### En el desarrollo

Durante el desarrollo se usó un asistente de programación con IA (Claude Code, de Anthropic) para escribir y revisar código, pruebas y documentación. Los requisitos, las decisiones de diseño y la revisión de cada cambio, con las pruebas automáticas y probando la plataforma, estuvieron a cargo de quien desarrolla el proyecto.

## Ejecutar con Docker (recomendado)

1. Abre Docker Desktop.
2. Copia `backend/.env.example` como `backend/.env` y llena:
   - `ADMIN_CORREO` (y opcionalmente `ADMIN_NOMBRE` y `ADMIN_PASSWORD`).
   - Los datos de la IA: Gemini o Azure OpenAI (ver [Configurar la IA](#configurar-la-ia)).
   - Para pruebas de correo: `SMTP_HOST=mailpit`, `SMTP_PORT=1025` y `SMTP_STARTTLS=false`.
3. En la carpeta del proyecto ejecuta:

```bash
docker compose up --build
```

4. Abre http://localhost:8080. Los correos de prueba (invitaciones y cambio de contraseña) se ven en http://localhost:8025.

La primera vez se crean las tablas y los datos iniciales: programas, módulos, preguntas, tareas, la cuenta de RH y algunos colaboradores y responsables de ejemplo. Los de ejemplo no tienen contraseña. Para no cargarlos, pon `CARGAR_DATOS_DEMO=false`.

Los módulos y la base del Tutor salen de los documentos de ejemplo de `backend/conocimiento/` (Markdown con su bloque `titulo:`/`tema:` y secciones `##`). Para usar la información oficial de RH, reemplaza esos archivos o edita los documentos desde **Base del Tutor IA**.

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

## Configurar la IA

Los agentes necesitan un modelo de lenguaje. El backend usa **Azure OpenAI** si sus datos están en `backend/.env`; si no, usa el servicio compatible con OpenAI de `IA_BASE_URL` (Gemini).

### Google Gemini (lo que se usa ahora; gratis)

1. Entra a https://aistudio.google.com con una cuenta de Google y crea una clave (**Get API key**).
2. En `backend/.env` pon:

```
IA_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
IA_API_KEY=tu-clave
IA_MODELO=gemini-3.5-flash-lite
```

La versión gratis tiene un límite de peticiones por día y puede tardar algunos segundos en responder.

### Azure OpenAI (proveedor principal, para producción)

1. En el [portal de Azure](https://portal.azure.com) de la organización crea un recurso **Azure OpenAI** (o un proyecto en **Azure AI Foundry**, https://ai.azure.com).
2. Crea una implementación (deployment) de un modelo de chat, por ejemplo `gpt-4o-mini`. Si la región no lo tiene disponible, prueba East US o Sweden Central.
3. En el recurso, abre **Claves y punto de conexión** y copia en `backend/.env`:
   - `AZURE_OPENAI_ENDPOINT`: el punto de conexión.
   - `AZURE_OPENAI_API_KEY`: una de las claves.
   - `AZURE_OPENAI_DEPLOYMENT`: el nombre de tu implementación.

### Comprobar la conexión

Desde la carpeta `backend`:

```bash
python -m app.probar_ia
```

Muestra qué proveedor respondió. Si hay un error, el mensaje dice qué dato revisar. Reinicia el backend después de cambiar `.env`.

## Configurar el correo (SMTP)

Con Microsoft 365 usa `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587` y `SMTP_STARTTLS=true`. En `SMTP_USER` y `SMTP_PASSWORD` va una cuenta que tenga habilitado "SMTP AUTH". `APP_URL` debe ser la dirección pública de la página para que los enlaces de los correos funcionen.

## Configurar Microsoft Entra ID

El botón **Continuar con Microsoft** ya está programado. Para que funcione solo faltan dos datos en `backend/.env`:

```
ENTRA_TENANT_ID=
ENTRA_CLIENT_ID=
```

Esos datos salen de registrar la aplicación en el Entra ID **de la organización** (PluriOne). Con una cuenta personal (Outlook, Hotmail o Gmail) no se puede, porque Microsoft exige un directorio organizacional. Lo hace alguien de TI con permisos de administrador:

1. Entra a https://entra.microsoft.com → **Aplicaciones → Registros de aplicaciones → Nuevo registro**.
2. **Nombre:** `Onboarding PluriOne`. **Tipos de cuenta compatibles:** "Solo las cuentas de este directorio organizativo".
3. **URI de redirección:** "Aplicación de página única (SPA)" con `http://localhost:5173`. Después, en **Autenticación**, agrega también `http://localhost:8080` (Docker) y la dirección pública de la plataforma cuando exista.
4. En **Información general** copia el **Id. de directorio (inquilino)** en `ENTRA_TENANT_ID` y el **Id. de aplicación (cliente)** en `ENTRA_CLIENT_ID`. No son secretos.
5. Reinicia el backend.

Quién puede entrar con Microsoft:

- Solo cuentas de Microsoft de la organización (por ejemplo `nombre@plurione.com.mx`).
- Solo si RH ya dio de alta a la persona en la plataforma **con ese mismo correo**. Si no, el botón le dice que su cuenta no está registrada.
- Si el nombre que registró RH no es válido (por ejemplo, solo números), se toma el nombre de su cuenta de Microsoft.

Mientras no estén los dos datos, el botón aparece normal y, al darle clic, avisa: "El inicio de sesión con Microsoft todavía no está habilitado. Usa tu correo y contraseña."

## Correr el proyecto en otra computadora

Lo que está en GitHub es todo el código. Solo **no** está `backend/.env`, que lleva las claves.

1. Instala **Git** y **Docker Desktop**.
2. Descarga el proyecto:

```bash
git clone https://github.com/DevGabyMerida17/G19X-UPTAP-PGGM-269-ACADEMIC
```

3. Copia `backend/.env.example` como `backend/.env` y llena tu `ADMIN_CORREO` y `ADMIN_PASSWORD` (será la primera cuenta de RH) y tu clave de Gemini (ver [Configurar la IA](#configurar-la-ia)). Cada persona usa su propia clave; no compartas la tuya.
4. Abre Docker Desktop y, en la carpeta del proyecto, ejecuta:

```bash
docker compose up --build
```

5. Abre http://localhost:8080 e inicia sesión con la cuenta de RH.

## Migraciones de la base de datos

El esquema se versiona con **Alembic** en `backend/migraciones/versions/`. Al arrancar, el backend aplica solo las migraciones que falten (`migrar()` en `backend/app/seed.py`); si encuentra una base creada antes de usar migraciones, la marca en la versión que ya tiene en lugar de recrear las tablas.

Después de cambiar `backend/app/models.py`, desde la carpeta `backend`:

```bash
alembic revision --autogenerate -m "describe el cambio"
alembic upgrade head
```

Revisa el archivo generado antes de subirlo. `alembic check` confirma que los modelos y las migraciones coinciden.

## Pruebas

```bash
cd backend
pytest
```

Las pruebas usan SQLite, un Redis simulado y un modelo falso para el agente, así que no gastan créditos de Azure. Cubren el alta por RH con contraseña temporal, olvidé mi contraseña, bajas, responsables, capacitación, documentos, permisos, el límite de intentos y su escalamiento en "Mi equipo", el inicio de sesión con Microsoft, los 5 agentes y las rutas del Tutor. GitHub Actions corre estas pruebas, compila el frontend y construye las imágenes de Docker en cada cambio.

## Pendientes antes de producción

- **Azure OpenAI y Microsoft Entra ID:** activarlos con la cuenta de Azure de PluriOne (ver [Estado de Azure OpenAI y Microsoft Entra ID](#estado-de-azure-openai-y-microsoft-entra-id)).
- **Contenido de ejemplo:** los documentos de `backend/conocimiento/` son de ejemplo y hay que reemplazarlos con la información oficial de RH.
- **Integración con HRIS:** la sincronización con el sistema de RH de la empresa todavía no está implementada.
