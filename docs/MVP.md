# MVP — Plataforma de Onboarding Interactivo Guiado por Agentes Inteligentes

**Empresa:** PluriOne S.A. de C.V. (Develop Talent & Technology)
**Versión:** 1.0 · Octubre 2026
**Relacionado:** [`PRD.md`](../PRD.md) (requisitos) · [`README.md`](../README.md) (instalación y configuración)

El MVP es la versión mínima que cubre el ciclo completo de incorporación: **RH da de alta → el colaborador completa su ruta con apoyo de los agentes → el supervisor y RH dan seguimiento.** Todo lo que está en "Entra en el MVP" funciona hoy y tiene pruebas automáticas en `backend/tests/`.

---

## 1. Entra en el MVP

### 1.1 Cuentas y acceso

| Función | Backend | Frontend |
|---|---|---|
| Alta de personas por RH (sin registro público), con contraseña temporal en pantalla y por correo | `POST /api/rh/usuarios` → `crear_usuario` en `backend/app/routers/rh.py`; correo en `backend/app/correo.py` | `frontend/src/paginas/rh/Colaboradores.jsx` |
| Cambio obligatorio de contraseña en el primer inicio | `POST /api/auth/cambiar-password` en `backend/app/routers/auth.py` | `frontend/src/paginas/CambioObligatorio.jsx` |
| Inicio de sesión con correo y contraseña | `POST /api/auth/login` en `backend/app/routers/auth.py` | `frontend/src/paginas/Acceso.jsx` |
| Inicio de sesión con Microsoft Entra ID (listo para configurar) | `POST /api/auth/microsoft`; validación del token en `validar_token_entra` (`backend/app/seguridad.py`) | `Acceso.jsx` (MSAL) |
| ¿Olvidaste tu contraseña? con enlace de un solo uso | `POST /api/auth/olvide` y `POST /api/auth/nueva-password` | `Acceso.jsx`, `frontend/src/paginas/NuevaPassword.jsx` |
| Bajas y reactivación; aviso de cuenta dada de baja | `PATCH /api/rh/usuarios/{uid}`; `error_cuenta_inactiva` en `seguridad.py` | `Colaboradores.jsx` |
| Nueva contraseña temporal y corrección de nombre | `POST /api/rh/usuarios/{uid}/password-temporal`, `PATCH /api/rh/usuarios/{uid}` | `Colaboradores.jsx` |
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
| Activar Azure OpenAI y Microsoft Entra ID con la cuenta de PluriOne | Requieren una suscripción de Azure de la organización; el código ya está listo (ver README) |
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
