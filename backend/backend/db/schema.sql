-- ============================================================================
-- PLATAFORMA DE ONBOARDING INTERACTIVO GUIADO POR AGENTES INTELIGENTES
-- PostgreSQL 15+
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- Función de utilidad: mantiene updated_at al día en cada UPDATE.
-- Se aplica a las tablas que declaran esa columna (ver sección 18).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- 0. ROLES Y PERMISOS (configurable)
-- Antes, el rol de un usuario era un VARCHAR con CHECK fijo a tres valores.
-- Aquí es un catálogo de datos: agregar un rol nuevo (o cambiar qué puede
-- hacer uno existente) es un INSERT/UPDATE, no una migración de esquema ni
-- un cambio de código. Los permisos se resuelven así:
--   SELECT p.code FROM users u
--   JOIN role_permissions rp ON rp.role_id = u.role_id
--   JOIN permissions p ON p.id = rp.permission_id
--   WHERE u.id = :user_id
-- La aplicación verifica "¿tiene el permiso materials.manage?", nunca
-- "¿su rol se llama admin_rh?" — así el código no le importa quién,
-- organizacionalmente, hace ese trabajo hoy.
-- ============================================================================

CREATE TABLE roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(60) NOT NULL UNIQUE,
    description     VARCHAR(300),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(80) NOT NULL UNIQUE,   -- p. ej. 'materials.manage'
    description     VARCHAR(300),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);


-- ============================================================================
-- 1. USUARIOS Y ORGANIZACIÓN
-- ============================================================================

CREATE TABLE departments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(120) NOT NULL UNIQUE,
    description     VARCHAR(300),
    manager_id      UUID,
    status          VARCHAR(20) NOT NULL DEFAULT 'activo'
                    CHECK (status IN ('activo', 'inactivo')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE positions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id   UUID REFERENCES departments(id),
    name            VARCHAR(120) NOT NULL,
    description     VARCHAR(300),
    status          VARCHAR(20) NOT NULL DEFAULT 'activo'
                    CHECK (status IN ('activo', 'inactivo')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- FIX: se eliminaron las columnas position / department (VARCHAR) que
-- coexistían con position_id / department_id. Con las tablas normalizadas
-- ya creadas arriba, esas columnas de texto eran una segunda fuente de
-- verdad para el mismo dato y podían desincronizarse.
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    full_name       VARCHAR(200) NOT NULL,
    email           VARCHAR(200) NOT NULL UNIQUE,

    -- Microsoft Entra ID
    entra_id        VARCHAR(200) UNIQUE,

    role_id         UUID NOT NULL REFERENCES roles(id),

    manager_id      UUID REFERENCES users(id),

    position_id     UUID REFERENCES positions(id),
    department_id   UUID REFERENCES departments(id),

    contract_type   VARCHAR(40),
    work_mode       VARCHAR(20),

    status          VARCHAR(20) NOT NULL DEFAULT 'activo'
                    CHECK (status IN ('activo', 'inactivo')),

    hire_date       DATE,

    last_login      TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


ALTER TABLE departments
ADD CONSTRAINT fk_department_manager
FOREIGN KEY (manager_id)
REFERENCES users(id);


CREATE TABLE user_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id)
                        ON DELETE CASCADE,

    phone               VARCHAR(30),
    profile_photo       VARCHAR(500),
    emergency_contact   VARCHAR(200),
    emergency_phone     VARCHAR(30),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_users_manager_id
ON users(manager_id);

CREATE INDEX idx_users_role_id
ON users(role_id);

CREATE INDEX idx_users_department_id
ON users(department_id);

CREATE INDEX idx_users_position_id
ON users(position_id);


-- ============================================================================
-- 2. PLANTILLAS DE ONBOARDING
-- ============================================================================

CREATE TABLE onboarding_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name            VARCHAR(150) NOT NULL,
    description     VARCHAR(300),

    position_id     UUID REFERENCES positions(id),
    department_id   UUID REFERENCES departments(id),

    duration_days   INT,

    status          VARCHAR(20) NOT NULL DEFAULT 'activo'
                    CHECK (status IN ('activo', 'inactivo')),

    created_by      UUID REFERENCES users(id),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE template_checklist_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    template_id     UUID NOT NULL
                    REFERENCES onboarding_templates(id)
                    ON DELETE CASCADE,

    item_type       VARCHAR(30) NOT NULL
                    CHECK (
                        item_type IN (
                            'task',
                            'document',
                            'training',
                            'evaluation'
                        )
                    ),

    subtype         VARCHAR(60),

    title           VARCHAR(200) NOT NULL,
    description     VARCHAR(500),

    required        BOOLEAN NOT NULL DEFAULT true,

    sort_order      INT NOT NULL DEFAULT 0
);


CREATE INDEX idx_template_items_template_id
ON template_checklist_items(template_id);


-- ============================================================================
-- 3. PROCESOS DE ONBOARDING
-- ============================================================================

CREATE TABLE onboarding_processes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id         UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    template_id     UUID REFERENCES onboarding_templates(id),

    start_date      DATE NOT NULL,
    expected_end_date DATE,

    status          VARCHAR(20) NOT NULL DEFAULT 'en_curso'
                    CHECK (
                        status IN (
                            'en_curso',
                            'retrasado',
                            'completado',
                            'cancelado'
                        )
                    ),

    progress_percentage NUMERIC(5,2) NOT NULL DEFAULT 0
                        CHECK (
                            progress_percentage >= 0
                            AND progress_percentage <= 100
                        ),

    completed_at    TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_processes_user_id
ON onboarding_processes(user_id);

CREATE INDEX idx_processes_status
ON onboarding_processes(status);


-- ============================================================================
-- 4. ACTIVIDADES / TASKS
-- ============================================================================

CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    process_id      UUID NOT NULL
                    REFERENCES onboarding_processes(id)
                    ON DELETE CASCADE,

    type            VARCHAR(60) NOT NULL,

    title           VARCHAR(200) NOT NULL,
    description     VARCHAR(500),

    status          VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                    CHECK (
                        status IN (
                            'pendiente',
                            'en_curso',
                            'completada'
                        )
                    ),

    due_date        DATE,

    completed_at    TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_tasks_process_id
ON tasks(process_id);


-- ============================================================================
-- 5. DOCUMENTOS
-- ============================================================================

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    process_id      UUID NOT NULL
                    REFERENCES onboarding_processes(id)
                    ON DELETE CASCADE,

    doc_type        VARCHAR(80) NOT NULL,

    title           VARCHAR(200),

    description     VARCHAR(500),

    status          VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                    CHECK (
                        status IN (
                            'pendiente',
                            'en_revision',
                            'validado',
                            'rechazado'
                        )
                    ),

    file_url        VARCHAR(500),

    file_type       VARCHAR(50),
    file_size       BIGINT,

    version         INT NOT NULL DEFAULT 1,

    uploaded_at     TIMESTAMPTZ,

    reviewed_by     UUID REFERENCES users(id),

    reviewed_at     TIMESTAMPTZ,

    rejection_reason VARCHAR(300),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_documents_process_id
ON documents(process_id);

CREATE INDEX idx_documents_status
ON documents(status);


-- ============================================================================
-- 6. CAPACITACIÓN
-- ============================================================================

CREATE TABLE training_modules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    title           VARCHAR(200) NOT NULL,

    description     VARCHAR(500),

    duration_minutes INT NOT NULL DEFAULT 0,

    sort_order      INT NOT NULL DEFAULT 0,

    department_id   UUID REFERENCES departments(id),

    is_required     BOOLEAN NOT NULL DEFAULT true,

    status          VARCHAR(20) NOT NULL DEFAULT 'activo'
                    CHECK (
                        status IN (
                            'activo',
                            'inactivo'
                        )
                    ),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Material de un módulo: diapositivas, PDFs, imágenes. Varios por módulo,
-- cada uno editable/reemplazable/eliminable de forma independiente.
-- La aplicación exige el permiso 'materials.manage' para subir/editar —
-- hoy solo lo tiene admin_rh, pero eso vive en role_permissions, no aquí.
-- uploaded_by_role_id es una FOTO del rol al momento de subir: si esa
-- persona cambia de puesto después, este registro sigue diciendo qué rol
-- tenía cuando lo hizo, sin depender de su rol actual.
CREATE TABLE module_materials (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    module_id           UUID NOT NULL
                        REFERENCES training_modules(id)
                        ON DELETE CASCADE,

    title               VARCHAR(200),

    file_type           VARCHAR(50),          -- 'pdf', 'pptx', 'image', etc.
    file_url            VARCHAR(500) NOT NULL,
    file_size           BIGINT,

    uploaded_by         UUID NOT NULL REFERENCES users(id),
    uploaded_by_role_id UUID REFERENCES roles(id),

    sort_order          INT NOT NULL DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_module_materials_module_id ON module_materials(module_id);
CREATE INDEX idx_module_materials_uploaded_by ON module_materials(uploaded_by);


CREATE TABLE training_progress (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    process_id      UUID NOT NULL
                    REFERENCES onboarding_processes(id)
                    ON DELETE CASCADE,

    module_id       UUID NOT NULL
                    REFERENCES training_modules(id),

    status          VARCHAR(20) NOT NULL DEFAULT 'bloqueado'
                    CHECK (
                        status IN (
                            'bloqueado',
                            'en_curso',
                            'completado'
                        )
                    ),

    progress_percentage NUMERIC(5,2) NOT NULL DEFAULT 0,

    started_at      TIMESTAMPTZ,

    last_accessed_at TIMESTAMPTZ,

    completed_at    TIMESTAMPTZ,

    UNIQUE (process_id, module_id)
);


CREATE INDEX idx_training_progress_process_id
ON training_progress(process_id);


-- ============================================================================
-- 6.1 CUESTIONARIOS DE FIN DE MÓDULO (MVP)
-- Reemplaza, para el MVP, al motor de evaluaciones de la sección 7: en vez de
-- "actividades" configurables de cualquier tipo, es específicamente un
-- cuestionario por módulo. Reglas de negocio acordadas:
--   - Máximo 3 intentos "regulares" por colaborador y cuestionario.
--   - Aprobar es obligatorio: el módulo solo pasa a 'completado' (y desbloquea
--     el siguiente) si existe un intento con passed = true.
--   - Si se agotan los 3 intentos sin aprobar: ver quiz_exception_cases abajo.
--     Un 4o intento SOLO es válido si cuelga de un caso en estado
--     'en_recuperacion' — nunca como un intento regular más. Eso se valida
--     en la aplicación, no con max_attempts (que se queda en 3).
-- ============================================================================

CREATE TABLE module_quizzes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id       UUID NOT NULL UNIQUE
                    REFERENCES training_modules(id)
                    ON DELETE CASCADE,
    title           VARCHAR(200),
    passing_score   NUMERIC(5,2) NOT NULL DEFAULT 70,
    max_attempts    INT NOT NULL DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE quiz_questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id         UUID NOT NULL
                    REFERENCES module_quizzes(id)
                    ON DELETE CASCADE,
    question_text   TEXT NOT NULL,
    topic           VARCHAR(100),   -- p. ej. 'Contraseñas', 'Phishing' — para detectar dificultades
    sort_order      INT NOT NULL DEFAULT 0
);


CREATE TABLE quiz_options (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL
                    REFERENCES quiz_questions(id)
                    ON DELETE CASCADE,
    option_text     VARCHAR(500) NOT NULL,
    is_correct      BOOLEAN NOT NULL DEFAULT false
);


-- Un renglón por intento. attempt_number se calcula en la aplicación
-- (COUNT + 1) y se valida ahí mismo contra module_quizzes.max_attempts
-- antes de insertar — no hay forma simple de expresar ese límite como
-- CHECK porque depende de otra tabla.
CREATE TABLE quiz_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id      UUID NOT NULL
                    REFERENCES onboarding_processes(id)
                    ON DELETE CASCADE,
    quiz_id         UUID NOT NULL
                    REFERENCES module_quizzes(id),
    attempt_number  INT NOT NULL DEFAULT 1,
    score           NUMERIC(5,2),
    passed          BOOLEAN NOT NULL DEFAULT false,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (process_id, quiz_id, attempt_number)
);


-- Respuesta seleccionada por pregunta en un intento — permite mostrarle al
-- colaborador qué falló, y a RH auditar el cuestionario si hace falta.
CREATE TABLE quiz_attempt_answers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id          UUID NOT NULL
                        REFERENCES quiz_attempts(id)
                        ON DELETE CASCADE,
    question_id         UUID NOT NULL
                        REFERENCES quiz_questions(id),
    selected_option_id  UUID REFERENCES quiz_options(id),
    is_correct          BOOLEAN NOT NULL DEFAULT false
);


-- Caso de excepción: se abre automáticamente al reprobar el 3er intento.
-- "Principales dificultades" y "mejor resultado" se calculan así:
--   SELECT qq.topic, COUNT(*) AS fallos
--   FROM quiz_attempt_answers qaa
--   JOIN quiz_attempts qa ON qa.id = qaa.attempt_id
--   JOIN quiz_questions qq ON qq.id = qaa.question_id
--   WHERE qa.process_id = :process_id AND qa.quiz_id = :quiz_id AND qaa.is_correct = false
--   GROUP BY qq.topic ORDER BY fallos DESC;
-- El checklist "Acciones realizadas" NO se guarda aparte — se deriva:
--   Curso inicial          -> training_progress.status = 'completado'
--   Refuerzo automático    -> reinforcement_completed_at IS NOT NULL
--   Evaluación recuperación-> recovery_attempt_id IS NOT NULL
CREATE TABLE quiz_exception_cases (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    process_id              UUID NOT NULL
                            REFERENCES onboarding_processes(id)
                            ON DELETE CASCADE,

    quiz_id                 UUID NOT NULL REFERENCES module_quizzes(id),

    triggering_attempt_id   UUID NOT NULL REFERENCES quiz_attempts(id),

    status                  VARCHAR(20) NOT NULL DEFAULT 'abierto'
                            CHECK (
                                status IN (
                                    'abierto',
                                    'en_refuerzo',
                                    'en_recuperacion',
                                    'escalado',
                                    'resuelto'
                                )
                            ),

    best_score              NUMERIC(5,2),   -- cacheado; MAX(score) entre los intentos del caso

    -- Generado por el agente Recomendador tras el análisis del Evaluador
    reinforcement_strategy      TEXT,
    reinforcement_conversation_id UUID REFERENCES agent_conversations(id),
    reinforcement_completed_at  TIMESTAMPTZ,

    recovery_attempt_id     UUID REFERENCES quiz_attempts(id),

    escalated_to            UUID REFERENCES users(id),   -- supervisor o admin_rh
    escalation_recommendation TEXT,                       -- p. ej. "Realizar acompañamiento humano"
    escalated_at             TIMESTAMPTZ,

    resolved_by              UUID REFERENCES users(id),
    resolution_notes         TEXT,
    resolved_at               TIMESTAMPTZ,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_quiz_exception_cases_process_id ON quiz_exception_cases(process_id);
CREATE INDEX idx_quiz_exception_cases_status ON quiz_exception_cases(status);
CREATE INDEX idx_quiz_exception_cases_escalated_to ON quiz_exception_cases(escalated_to);


CREATE INDEX idx_quiz_questions_quiz_id ON quiz_questions(quiz_id);
CREATE INDEX idx_quiz_options_question_id ON quiz_options(question_id);
CREATE INDEX idx_quiz_attempts_process_id ON quiz_attempts(process_id);
CREATE INDEX idx_quiz_attempts_quiz_id ON quiz_attempts(quiz_id);
CREATE INDEX idx_quiz_attempt_answers_attempt_id ON quiz_attempt_answers(attempt_id);


-- ============================================================================
-- 7. ACTIVIDADES DE EVALUACIÓN — FASE 2 (revisar si sigue haciendo falta)
-- Motor genérico de actividades (tareas, documentos, capacitación,
-- evaluación) para más de un tipo de actividad por módulo, con calificación
-- AI/humana y evidencias. Con los cuestionarios de fin de módulo (6.1) ya
-- cubriendo el requisito de evaluación del MVP, confirmar tras el
-- lanzamiento si este motor más amplio sigue siendo necesario o si
-- los cuestionarios son suficientes para todo el ciclo de vida.
-- ============================================================================

CREATE TABLE activities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    module_id       UUID NOT NULL
                    REFERENCES training_modules(id)
                    ON DELETE CASCADE,

    title           VARCHAR(200) NOT NULL,

    description     VARCHAR(500),

    activity_type   VARCHAR(50) NOT NULL,

    instructions    TEXT,

    passing_score   NUMERIC(5,2) DEFAULT 70,

    max_attempts    INT DEFAULT 3,

    is_required     BOOLEAN NOT NULL DEFAULT true,

    order_number    INT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE questions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    activity_id     UUID NOT NULL
                    REFERENCES activities(id)
                    ON DELETE CASCADE,

    question_text   TEXT NOT NULL,

    question_type   VARCHAR(40) NOT NULL,

    points          NUMERIC(6,2) NOT NULL DEFAULT 1,

    order_number    INT NOT NULL DEFAULT 0
);


CREATE TABLE question_options (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    question_id     UUID NOT NULL
                    REFERENCES questions(id)
                    ON DELETE CASCADE,

    option_text     VARCHAR(500) NOT NULL,

    is_correct      BOOLEAN NOT NULL DEFAULT false
);


-- ============================================================================
-- 8. EVALUACIONES
-- ============================================================================

CREATE TABLE evaluations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    activity_id         UUID NOT NULL
                        REFERENCES activities(id)
                        ON DELETE CASCADE,

    user_id             UUID NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

    attempt_number      INT NOT NULL DEFAULT 1,

    score               NUMERIC(5,2),

    status              VARCHAR(30) NOT NULL DEFAULT 'en_proceso'
                        CHECK (
                            status IN (
                                'en_proceso',
                                'aprobada',
                                'no_aprobada'
                            )
                        ),

    feedback            TEXT,

    evaluation_method   VARCHAR(20) NOT NULL DEFAULT 'AI'
                        CHECK (
                            evaluation_method IN (
                                'AI',
                                'HUMANA'
                            )
                        ),

    evaluated_by_user_id UUID REFERENCES users(id),

    -- FIX: faltaba la referencia a ai_agents(id); era inconsistente con
    -- evaluated_by_user_id, que sí la tenía.
    evaluated_by_agent_id UUID REFERENCES ai_agents(id),

    started_at          TIMESTAMPTZ,

    completed_at        TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE TABLE user_answers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    evaluation_id       UUID NOT NULL
                        REFERENCES evaluations(id)
                        ON DELETE CASCADE,

    user_id             UUID NOT NULL
                        REFERENCES users(id)
                        ON DELETE CASCADE,

    question_id         UUID NOT NULL
                        REFERENCES questions(id)
                        ON DELETE CASCADE,

    answer_text         TEXT,

    selected_option_id  UUID REFERENCES question_options(id),

    is_correct          BOOLEAN,

    points_obtained     NUMERIC(6,2),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- 9. AGENTES DE INTELIGENCIA ARTIFICIAL
-- ============================================================================

-- FIX: se agregó 'preguntas' al catálogo. Con solo 'tutor' se había perdido,
-- respecto al diseño original, el agente de FAQ que responde dudas sobre
-- políticas internas vía RAG — confirmar si 'tutor' lo reemplaza a propósito
-- o si ambos deben coexistir (tutor = guía de capacitación, preguntas = FAQ).
CREATE TABLE ai_agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name            VARCHAR(100) NOT NULL,

    agent_type      VARCHAR(40) NOT NULL
                    CHECK (
                        agent_type IN (
                            'orquestador',
                            'tutor',
                            'preguntas',
                            'evaluador',
                            'recomendador',
                            'documentos',
                            'seguimiento'
                        )
                    ),

    description     VARCHAR(500),

    model           VARCHAR(100),

    status          VARCHAR(20) NOT NULL DEFAULT 'activo'
                    CHECK (
                        status IN (
                            'activo',
                            'inactivo'
                        )
                    ),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- 10. CONVERSACIONES CON AGENTES
-- ============================================================================

-- FIX: se eliminó agent_conversations.user_id. Era redundante con
-- process_id -> onboarding_processes.user_id y podía desincronizarse si
-- alguna vez un proceso cambiara de dueño. Para consultar por usuario:
--   SELECT c.* FROM agent_conversations c
--   JOIN onboarding_processes p ON p.id = c.process_id
--   WHERE p.user_id = :user_id
CREATE TABLE agent_conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    process_id      UUID NOT NULL
                    REFERENCES onboarding_processes(id)
                    ON DELETE CASCADE,

    agent_id        UUID REFERENCES ai_agents(id),

    title           VARCHAR(200),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    ended_at        TIMESTAMPTZ,

    status          VARCHAR(20) NOT NULL DEFAULT 'activa'
                    CHECK (
                        status IN (
                            'activa',
                            'cerrada'
                        )
                    )
);


CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    conversation_id UUID NOT NULL
                    REFERENCES agent_conversations(id)
                    ON DELETE CASCADE,

    sender          VARCHAR(20) NOT NULL
                    CHECK (
                        sender IN (
                            'usuario',
                            'agente'
                        )
                    ),

    content         TEXT NOT NULL,

    tokens_used     INT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_conversations_process_id
ON agent_conversations(process_id);

CREATE INDEX idx_messages_conversation_id
ON messages(conversation_id);


-- ============================================================================
-- 11. RECOMENDACIONES DE IA
-- ============================================================================

CREATE TABLE recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id         UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    process_id      UUID REFERENCES onboarding_processes(id)
                    ON DELETE CASCADE,

    agent_id        UUID REFERENCES ai_agents(id),

    module_id       UUID REFERENCES training_modules(id),

    recommendation  TEXT NOT NULL,

    reason          TEXT,

    priority        VARCHAR(20)
                    CHECK (
                        priority IN (
                            'baja',
                            'media',
                            'alta'
                        )
                    ),

    status          VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                    CHECK (
                        status IN (
                            'pendiente',
                            'aceptada',
                            'completada',
                            'descartada'
                        )
                    ),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    completed_at    TIMESTAMPTZ
);


-- ============================================================================
-- 12. FEEDBACK GENERADO POR IA
-- ============================================================================

CREATE TABLE ai_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id         UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    evaluation_id   UUID REFERENCES evaluations(id)
                    ON DELETE CASCADE,

    agent_id        UUID REFERENCES ai_agents(id),

    feedback        TEXT NOT NULL,

    strengths      TEXT,

    weaknesses     TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================================
-- 13. SEGUIMIENTO DEL SUPERVISOR
-- ============================================================================
-- NOTA (sin resolver, no es un bug puntual): esta tabla le da al supervisor
-- capacidad de escritura (comment, action) sobre su equipo. Choca con la
-- decisión previa de que el supervisor es de solo lectura. Pendiente de
-- decidir junto con el resto de las tablas fuera del alcance original.

CREATE TABLE supervisor_followups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    supervisor_id   UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    collaborator_id UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    type            VARCHAR(50),

    comment         TEXT,

    action          VARCHAR(300),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_followups_supervisor
ON supervisor_followups(supervisor_id);

CREATE INDEX idx_followups_collaborator
ON supervisor_followups(collaborator_id);


-- ============================================================================
-- 14. NOTIFICACIONES
-- ============================================================================
-- Informativas, orientadas al usuario final: llevan estado leído/no leído
-- (read_at) y no requieren resolución. Ej.: "tu documento fue validado".

CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    recipient_id    UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    type            VARCHAR(60) NOT NULL,

    title           VARCHAR(200),

    message         TEXT,

    payload         JSONB,

    read_at         TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_notifications_recipient_id
ON notifications(recipient_id, read_at);


-- ============================================================================
-- 15. ALERTAS
-- ============================================================================
-- Condiciones operativas que requieren atención y seguimiento explícito:
-- llevan severidad y se resuelven (resolved_at), no solo se leen.
-- Ej.: "proceso de onboarding retrasado más de 5 días".

CREATE TABLE alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id         UUID NOT NULL
                    REFERENCES users(id)
                    ON DELETE CASCADE,

    type            VARCHAR(60) NOT NULL,

    message         TEXT NOT NULL,

    severity        VARCHAR(20)
                    CHECK (
                        severity IN (
                            'baja',
                            'media',
                            'alta',
                            'critica'
                        )
                    ),

    status          VARCHAR(20) NOT NULL DEFAULT 'activa'
                    CHECK (
                        status IN (
                            'activa',
                            'resuelta'
                        )
                    ),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    resolved_at     TIMESTAMPTZ
);


-- ============================================================================
-- 16. AUDITORÍA Y SEGURIDAD
-- ============================================================================

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    actor_id        UUID REFERENCES users(id),
    actor_role_id   UUID REFERENCES roles(id),  -- foto del rol al momento de la acción

    agent_id        UUID REFERENCES ai_agents(id),

    agent_type      VARCHAR(40),

    action          VARCHAR(80) NOT NULL,

    entity_type     VARCHAR(60) NOT NULL,

    entity_id       UUID NOT NULL,

    metadata        JSONB,

    ip_address      INET,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


CREATE INDEX idx_audit_log_entity
ON audit_log(entity_type, entity_id);

CREATE INDEX idx_audit_log_actor
ON audit_log(actor_id);

CREATE INDEX idx_audit_log_created_at
ON audit_log(created_at);


-- ============================================================================
-- 17. ÍNDICES ADICIONALES
-- ============================================================================

CREATE INDEX idx_evaluations_user_id
ON evaluations(user_id);

CREATE INDEX idx_evaluations_activity_id
ON evaluations(activity_id);

CREATE INDEX idx_recommendations_user_id
ON recommendations(user_id);

CREATE INDEX idx_recommendations_process_id
ON recommendations(process_id);

CREATE INDEX idx_alerts_user_id
ON alerts(user_id);

CREATE INDEX idx_training_modules_department
ON training_modules(department_id);


-- ============================================================================
-- 18. TRIGGERS DE ACTUALIZACIÓN (updated_at)
-- ============================================================================
-- FIX: antes updated_at solo tenía DEFAULT now(), por lo que se quedaba
-- congelado en la fecha de creación salvo que la aplicación lo actualizara
-- manualmente en cada UPDATE. Estos triggers lo hacen automático a nivel
-- de base de datos para las cuatro tablas que declaran la columna.

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_user_profiles_updated_at
BEFORE UPDATE ON user_profiles
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_onboarding_templates_updated_at
BEFORE UPDATE ON onboarding_templates
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_onboarding_processes_updated_at
BEFORE UPDATE ON onboarding_processes
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================================
-- 19. DATOS SEMILLA — roles y permisos iniciales
-- Esto es DATA, no esquema. Agregar un rol nuevo en el futuro (por un
-- cambio organizacional) es repetir el patrón de estos INSERT, no editar
-- esta tabla ni desplegar código nuevo.
-- ============================================================================

INSERT INTO roles (id, name, description) VALUES
    (gen_random_uuid(), 'nuevo_colaborador', 'Persona en proceso de onboarding'),
    (gen_random_uuid(), 'supervisor', 'Da seguimiento a su equipo directo'),
    (gen_random_uuid(), 'admin_rh', 'Administra el proceso de onboarding a nivel empresa');

INSERT INTO permissions (code, description) VALUES
    ('profile.view_own', 'Ver el propio perfil'),
    ('onboarding.view_own', 'Ver el propio roadmap de onboarding'),
    ('documents.upload_own', 'Subir los propios documentos requeridos'),
    ('training.view_own', 'Consultar y avanzar en los propios módulos'),
    ('chat.use', 'Conversar con los agentes'),
    ('quiz.take', 'Contestar el cuestionario de un módulo'),
    ('users.manage', 'Registrar, editar y activar/desactivar colaboradores'),
    ('templates.manage', 'Crear y editar plantillas de onboarding'),
    ('modules.manage', 'Crear, editar y ordenar módulos de capacitación'),
    ('materials.manage', 'Subir, reemplazar y eliminar material de un módulo'),
    ('documents.validate', 'Validar o rechazar documentos de un colaborador'),
    ('quiz.manage', 'Crear preguntas y definir la calificación mínima de un cuestionario'),
    ('processes.view_all', 'Ver el avance de todos los procesos de onboarding'),
    ('team.view', 'Ver únicamente a los colaboradores del propio equipo'),
    ('team.progress.view', 'Ver el avance del propio equipo'),
    ('followups.create', 'Agregar comentarios y observaciones de seguimiento'),
    ('quiz.results.view_team', 'Ver las calificaciones de cuestionarios del propio equipo'),
    ('cases.view', 'Ver casos de excepción escalados'),
    ('cases.resolve', 'Cerrar un caso de excepción con intervención humana');

-- nuevo_colaborador
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'nuevo_colaborador'
AND p.code IN ('profile.view_own', 'onboarding.view_own', 'documents.upload_own',
               'training.view_own', 'chat.use', 'quiz.take');

-- admin_rh
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'admin_rh'
AND p.code IN ('users.manage', 'templates.manage', 'modules.manage', 'materials.manage',
               'documents.validate', 'quiz.manage', 'processes.view_all',
               'cases.view', 'cases.resolve');

-- supervisor
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'supervisor'
AND p.code IN ('team.view', 'team.progress.view', 'followups.create', 'quiz.results.view_team',
               'cases.view', 'cases.resolve');


-- ============================================================================
-- FIN DEL ESQUEMA
-- ============================================================================
