# MVP — Plataforma de Onboarding Interactivo Guiado por Agentes Inteligentes

**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Versión:** 1.1 · 29 de octubre de 2026
**Relacionado:** [`PRD.md`](../PRD.md) (requisitos) · [`README.md`](../README.md) (instalación y configuración)

El MVP es la versión mínima que cubre el ciclo completo de incorporación: **RH da de alta → el colaborador completa su ruta con apoyo de los agentes → el supervisor y RH dan seguimiento.** Todo lo que está en "Entra en el MVP" funciona hoy y tiene pruebas automáticas en `backend/tests/`. Para comprobarlo a mano, sigue el [recorrido de prueba](#4-recorrido-de-prueba).

---

## 1. Entra en el MVP

### 1.1 Cuentas y acceso

| Función | Backend | Frontend |
|---|---|---|
| Alta de personas por RH (sin registro público), con contraseña temporal en pantalla y por correo | `POST /api/rh/usuarios` → `crear_usuario` en `backend/app/routers/rh.py`; correo en `backend/app/correo.py` | `frontend/src/paginas/rh/Colaboradores.jsx` |
| Cambio obligatorio de contraseña en el primer inicio | `POST /api/auth/cambiar-password` en `backend/app/routers/auth.py` | `frontend/src/paginas/CambioObligatorio.jsx` |
| Inicio de sesión con correo y contraseña | `POST /api/auth/login` en `backend/app/routers/auth.py` | `frontend/src/paginas/Acceso.jsx` |
| Inicio de sesión con Microsoft Entra ID: elegir cuenta y contraseña en cada inicio, con respaldo en la misma pestaña si se bloquea la ventana emergente (probado con un directorio propio) | `POST /api/auth/microsoft`; validación del token en `validar_token_entra` (`backend/app/seguridad.py`) | `Acceso.jsx`, `frontend/src/microsoft.js` (MSAL) |
| ¿Olvidaste tu contraseña? con enlace de un solo uso | `POST /api/auth/olvide` y `POST /api/auth/nueva-password` | `Acceso.jsx`, `frontend/src/paginas/NuevaPassword.jsx` |
| Bajas y reactivación; aviso de cuenta dada de baja | `PATCH /api/rh/usuarios/{uid}`; `error_cuenta_inactiva` en `seguridad.py` | `Colaboradores.jsx` |
| Eliminar a una persona con su registro; lo que escribió sobre otros se conserva como «Usuario eliminado» | `DELETE /api/rh/usuarios/{uid}` → `eliminar_usuario` en `rh.py`; migración `0004` | Bote de basura en `Colaboradores.jsx` |
| Nueva contraseña temporal y corrección de nombre | `POST /api/rh/usuarios/{uid}/password-temporal`, `PATCH /api/rh/usuarios/{uid}` | `Colaboradores.jsx` |
| Foto de perfil (JPG o PNG, máx. 2 MB) que cada persona sube desde su avatar | `POST`/`DELETE /api/auth/yo/foto`, `GET /api/usuarios/{uid}/foto` en `auth.py`; migración `0005` | `MiFoto` en `frontend/src/App.jsx`, `Avatar` en `frontend/src/ui.jsx` |
| Validación de correo y nombre | `backend/app/validaciones.py` | `frontend/src/validaciones.js` |
| Sesiones y límite de intentos | `backend/app/seguridad.py`, `backend/app/cache.py` (Redis) | `frontend/src/api.js` |
| Roles y permisos como datos (tablas `roles`, `permisos`, `rol_permisos`) | `requiere_permiso` en `seguridad.py`, catálogo en `backend/app/permisos.py`, datos iniciales en la migración `0003`; `GET /api/rh/roles` | — |

### 1.2 Ruta del colaborador

| Función | Backend | Frontend |
|---|---|---|
| Inicio con avance, tareas por etapa, mensajes del supervisor | `GET /api/yo/resumen`, `PUT /api/yo/tareas/{id}` en `backend/app/routers/colaborador.py` | `frontend/src/paginas/colaborador/Inicio.jsx` |
| Anillos de progreso por etapa | Cálculo de avance en `backend/app/servicios.py` | `etapasDe` y `Anillo` en `frontend/src/App.jsx`; `colaborador/Avance.jsx` |
| Documentos: subir, ver estado y motivo de rechazo | `POST /api/yo/documentos/{tipo_id}` → `subir_documento` | `colaborador/Documentos.jsx` |
| Capacitación secuencial por secciones | `GET /api/yo/modulos/{id}`, `POST .../leer`, `POST .../completar`; `estado_modulos` en `servicios.py` | `colaborador/Capacitacion.jsx` |
| Evaluación con calificación mínima e intentos | `GET` y `POST /api/yo/modulos/{id}/evaluacion` → `contestar_evaluacion`; `intentos` en `servicios.py` | `colaborador/Evaluaciones.jsx` |

### 1.3 Agentes de IA (5)

| Agente | Qué hace | Backend | Frontend |
|---|---|---|---|
| Orquestador | Decide si la pregunta va al Tutor o al agente general | Grafo de LangGraph en `backend/app/agente.py` | — |
| Agente de Conocimiento General | Preguntas generales sin documentos internos | `backend/app/agente.py` | `colaborador/Tutor.jsx` |
| Tutor de Onboarding | Proceso, plataforma y políticas con RAG (BM25) y fuentes | `backend/app/agente.py`, `backend/app/rag.py`; WebSocket `/ws/tutor` en `backend/app/routers/tiempo_real.py` | `colaborador/Tutor.jsx` |
| Agente Evaluador | Explica errores y temas a reforzar en cada evaluación | `backend/app/evaluador.py`; `POST /api/yo/evaluaciones/{id}/retroalimentacion` | `RetroEvaluador` en `colaborador/Evaluaciones.jsx` |
| Agente Recomendador | Siguientes pasos al colaborador; sugerencia al supervisor | `backend/app/recomendador.py`; `GET /api/yo/recomendaciones`, `GET /api/supervisor/colaboradores/{uid}/recomendacion` | `colaborador/Inicio.jsx`, `supervisor/Equipo.jsx` |
| Asistente de RH | Consultas sobre el personal con datos reales | `backend/app/asistente_rh.py`; `POST /api/rh/asistente` | `rh/AsistenteRH.jsx` |

Conexión con el modelo (Azure OpenAI o Gemini): `backend/app/ia.py`. Nombres de los agentes: `backend/app/nombres_agentes.py`.

### 1.4 Intentos y escalamiento

| Función | Backend | Frontend |
|---|---|---|
| Límite de intentos por módulo (3 por defecto, configurable de 1 a 10) | `Modulo.intentos_maximos` en `backend/app/models.py`; `PATCH /api/rh/modulos/{mid}` | `rh/Actividades.jsx` |
| Bloqueo al agotar los intentos | `contestar_evaluacion` (403) en `colaborador.py` | `colaborador/Evaluaciones.jsx` |
| Escalamiento visible en "Mi equipo" | `GET /api/supervisor/equipo` (campo `escalados`) en `backend/app/routers/supervisor.py` | `Lista` en `supervisor/Equipo.jsx` |
| Intento extra concedido por el responsable o RH | `POST /api/supervisor/colaboradores/{uid}/modulos/{mid}/intento-extra` | Detalle en `supervisor/Equipo.jsx` |

### 1.5 Recursos Humanos

| Función | Backend | Frontend |
|---|---|---|
| Panel con avance, retrasos y temas consultados | `GET /api/rh/panel` en `rh.py` | `rh/Panel.jsx` |
| Personal por área con búsqueda y responsable asignado | `GET /api/rh/colaboradores`, `/personal`, `/responsables` | `rh/Colaboradores.jsx` |
| Programas y módulos | `/api/rh/programas`, `/api/rh/modulos` | `rh/Programas.jsx` |
| Preguntas de evaluación | `/api/rh/preguntas` | `rh/Actividades.jsx` |
| Revisión de documentos con vista previa | `/api/rh/documentos`, `.../archivo`, `.../validar`, `.../rechazar` | `rh/Revision.jsx` |
| Base de conocimiento del Tutor | `/api/rh/conocimiento`; carga inicial desde `backend/conocimiento/` en `backend/app/seed.py` | `rh/Conocimiento.jsx` |

### 1.6 Supervisor

| Función | Backend | Frontend |
|---|---|---|
| Ver solo a su equipo | `equipo` y `_de_mi_equipo` en `supervisor.py` | `supervisor/Equipo.jsx` |
| Detalle, comentarios y acciones de seguimiento | `GET /api/supervisor/colaboradores/{uid}`, `POST .../comentarios` | `supervisor/Equipo.jsx` |

### 1.7 Transversal

| Función | Dónde |
|---|---|
| Avisos en tiempo real (WebSocket `/ws/eventos` con pub/sub de Redis) | `backend/app/routers/tiempo_real.py`, `backend/app/cache.py`; `useEventos` en `frontend/src/ui.jsx` |
| Modelo de datos (16 tablas), migraciones y datos iniciales | `backend/app/models.py`, `backend/migraciones/versions/` (Alembic), `backend/app/seed.py` |
| Modo claro y oscuro, interfaz por rol | `frontend/src/estilos.css`, `frontend/src/App.jsx` |
| Pruebas automáticas (sin gastar IA: modelo falso) | `backend/tests/` |
| Contenedores | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |
| Integración continua | `.github/workflows/ci.yml` |

---

## 2. Queda para la Fase 2

| Función | Por qué se pospone |
|---|---|
| Activar Azure OpenAI con la cuenta de PluriOne | Requiere una suscripción de Azure de la organización; el código ya está listo (ver README). Mientras tanto se usa Gemini |
| Registrar Entra ID en el directorio de PluriOne | Ya funciona con un directorio de prueba; para producción, TI de la empresa registra la aplicación y cambia dos datos del `.env` |
| Intento de recuperación automático tras una conversación dirigida con el Tutor | El MVP resuelve el caso con el intento extra que concede el responsable |
| Botón para conceder intentos desde la interfaz de RH | Hoy lo hace el responsable; RH ya puede vía API |
| Historial de versiones de documentos | En el MVP, volver a subir reemplaza el archivo anterior |
| Material multiarchivo en módulos (diapositivas, PDF, imágenes) | El MVP usa contenido por secciones |
| Pantalla para editar roles y permisos, y bitácora de auditoría | Los permisos ya son datos; editarlos desde la interfaz no es necesario para la operación inicial |
| Alertas con severidad y notificaciones persistidas | El MVP avisa en tiempo real y en el panel |
| Sincronización con el sistema de RH (HRIS) | No hay API confirmada; el alta es manual |

---

## 3. Criterios de aceptación del MVP

1. RH da de alta a una persona y esta entra con su contraseña temporal y la cambia.
2. El colaborador completa tareas, sube documentos y RH los valida o rechaza.
3. El colaborador lee los módulos en orden y presenta su evaluación; al reprobar recibe la explicación del Agente Evaluador.
4. Al agotar sus intentos, su responsable lo ve marcado en "Mi equipo" y puede concederle otro.
5. El Tutor responde preguntas sobre PluriOne citando fuentes y también preguntas generales.
6. RH consulta el panel y al Asistente de RH.
7. `pytest` pasa y GitHub Actions compila el frontend y las imágenes de Docker.

---

## 4. Recorrido de prueba

Sirve para revisar el MVP a mano, de principio a fin. Toma unos 20 minutos.

**Antes de empezar**
- Levanta el proyecto como dice el [README](../README.md) (con Docker o sin Docker) y abre http://localhost:5173.
- La única cuenta con contraseña es la de **RH**: su correo y contraseña son `ADMIN_CORREO` y `ADMIN_PASSWORD` de `backend/.env`. Las personas de ejemplo (Mariana López, Luis Ramírez, etc.) **no tienen contraseña**; solo sirven para llenar el panel. Por eso, en este recorrido se crean un supervisor y un colaborador nuevos.
- Para los agentes de IA, `backend/.env` debe tener los datos de Gemini o de Azure OpenAI ("Configurar la IA" en el README). Sin ellos, la plataforma funciona, pero cada agente muestra el aviso "La IA no está configurada".
- **Opcional, entrar con Microsoft:** si `backend/.env` tiene `ENTRA_TENANT_ID` y `ENTRA_CLIENT_ID`, en cualquier paso se puede usar **Continuar con Microsoft** con una cuenta del directorio que RH haya dado de alta con el mismo correo. Microsoft pide elegir la cuenta y la contraseña cada vez.
- Sin SMTP configurado, los correos no se envían: se guardan en `backend/correos_enviados/` y no hacen falta para el recorrido, porque la contraseña temporal también aparece en pantalla.

### Paso 1. RH crea a un supervisor
1. Entra con la cuenta de RH.
2. En **Personal**, da clic en **+ Dar de alta**.
3. Llena el formulario:
   - **Rol:** Supervisor / Responsable.
   - **Nombre completo:** por ejemplo, `Pedro Gómez`.
   - **Correo corporativo:** por ejemplo, `pedro.gomez@prueba.test`.
   - **Puesto:** por ejemplo, `Líder de Desarrollo`.
   - **Área:** Desarrollo.
4. Da clic en **Dar de alta**.
5. Copia la **contraseña temporal** que aparece en la tarjeta. Solo se muestra una vez; si se pierde, **Contraseña temporal** genera otra.

### Paso 2. RH crea a un colaborador
1. Otra vez **+ Dar de alta**, con **Rol:** Colaborador.
2. Nombre, por ejemplo, `Ana Torres`, y correo, por ejemplo, `ana.torres@prueba.test`.
3. **Responsable:** el supervisor del paso 1.
4. Copia su contraseña temporal.

### Paso 3. El colaborador entra y avanza
Cierra la sesión de RH con **Salir**, o usa una ventana de incógnito para tener las dos sesiones abiertas.

1. Entra con el correo del colaborador y su contraseña temporal. La plataforma pide crear una contraseña propia: mínimo 8 caracteres, con letras y al menos un número.
2. **Inicio:** se ven el avance, las tareas por etapa y **Recomendaciones para ti**, del agente **Senda (Agente Recomendador)**.
3. **Documentos:** sube un PDF, JPG o PNG en cualquier tipo de documento. Queda "En revisión" para RH.
4. **Capacitación:** los módulos se abren en orden.
   1. En **Bienvenida a PluriOne**, marca cada sección con **Marcar como leído** y luego da clic en **Completar módulo**.
   2. Repite con **Políticas internas**.
   3. Así se desbloquea **Seguridad de la información**: léelo y complétalo también.

### Paso 4. Provocar el escalamiento
1. En **Evaluaciones**, abre **Seguridad de la información**. Pide 70 % para aprobar y tiene 3 intentos.
2. Contesta mal: por ejemplo, la primera opción de cada pregunta da 25 %. Luego da clic en **Enviar respuestas**.
3. Debajo del resultado aparece **Vera (Agente Evaluador)**, que explica cada error y los **temas a reforzar**.
4. Da clic en **Reintentar** y repite hasta usar los **3 intentos**. La evaluación queda en **Sin intentos**.

### Paso 5. El supervisor ve el escalamiento
1. Entra con el supervisor del paso 1 y crea su contraseña.
2. En **Mi equipo** aparece un aviso rojo con las personas que agotaron sus intentos. En la fila de Ana Torres sale **"Agotó intentos · Seguridad de la información"**.
3. Abre su detalle:
   - **Senda (Agente Recomendador)** sugiere cómo apoyarla.
   - En **Evaluaciones**, el botón **Dar un intento más** le devuelve un intento.
   - En **Comentarios y observaciones** se le puede dejar un mensaje. El colaborador lo ve en su **Inicio**.

### Paso 6. RH revisa
1. Entra otra vez con RH.
2. **Panel:** avance general, retrasos y temas más consultados al Tutor.
3. **Documentos:** valida o rechaza, con motivo, el archivo del paso 3. El colaborador ve el resultado en su sección **Documentos**.
4. **Asistente de RH:** pregunta, por ejemplo, "¿Quién está retrasado?". Responde **Omnia (Asistente de RH)** con los datos reales de la plataforma.

### Dónde se ve cada uno de los 5 agentes
| Agente | Quién lo usa | Dónde |
|---|---|---|
| **Orquestador** | Colaborador | No tiene pantalla propia: en **Tutor IA** decide si cada pregunta la contesta Navi o Nova. Cada respuesta muestra el nombre del agente que contestó. |
| **Navi (Tutor de Onboarding)** | Colaborador | **Tutor IA**. Pregunta algo de PluriOne, por ejemplo "¿Cuál es el horario de trabajo?" o "¿Qué me falta por hacer?". Responde con las fuentes de la base de conocimiento. |
| **Nova (Conocimiento General)** | Colaborador | **Tutor IA**. Pregunta algo general, por ejemplo "¿Qué es una API?". |
| **Vera (Agente Evaluador)** | Colaborador | **Evaluaciones**, debajo del resultado de cada intento (paso 4). |
| **Senda (Agente Recomendador)** | Colaborador y supervisor | **Inicio** del colaborador y detalle del colaborador en **Mi equipo** (pasos 3 y 5). |
| **Omnia (Asistente de RH)** | RH | **Asistente de RH** (paso 6). |

Los nombres de los agentes se cambian en `backend/app/nombres_agentes.py`.

