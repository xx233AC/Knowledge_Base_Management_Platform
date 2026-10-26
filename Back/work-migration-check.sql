BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_pg_milvus

-- PostgreSQL 17 / schema v2: vectors are stored in Milvus, not PostgreSQL.
-- No DROP/TRUNCATE; run via alembic upgrade head against the intended database.

CREATE TABLE departments (
    parent_id UUID, 
    name VARCHAR(100) NOT NULL, 
    leader_id UUID, 
    sort_order INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_dept_not_self CHECK (parent_id IS NULL OR parent_id <> id), 
    FOREIGN KEY(parent_id) REFERENCES departments (id) ON DELETE RESTRICT
);

CREATE TABLE roles (
    role_name VARCHAR(100) NOT NULL, 
    role_code VARCHAR(64) NOT NULL, 
    description TEXT NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (role_code)
);

CREATE TABLE users (
    username VARCHAR(64) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    display_name VARCHAR(100) NOT NULL, 
    department_id UUID, 
    status VARCHAR(16) NOT NULL, 
    token_version INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_status CHECK (status IN ('active','disabled')), 
    UNIQUE (username), 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE RESTRICT
);

CREATE TABLE role_permissions (
    role_id UUID NOT NULL, 
    permission_code VARCHAR(80) NOT NULL, 
    permission_type VARCHAR(16) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_role_permission UNIQUE (role_id, permission_code), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE INDEX ix_role_permissions_role_id ON role_permissions (role_id);

CREATE TABLE user_roles (
    user_id UUID NOT NULL, 
    role_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_user_role UNIQUE (user_id, role_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT
);

CREATE INDEX ix_user_roles_role_id ON user_roles (role_id);

CREATE INDEX ix_user_roles_user_id ON user_roles (user_id);

CREATE TABLE auth_sessions (
    user_id UUID NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    revoked BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at);

CREATE TABLE knowledge_units (
    unit_code VARCHAR(40) NOT NULL, 
    title VARCHAR(300) NOT NULL, 
    content TEXT NOT NULL, 
    summary TEXT NOT NULL, 
    category VARCHAR(100) NOT NULL, 
    tags JSONB NOT NULL, 
    source_file_name VARCHAR(255) NOT NULL, 
    file_type VARCHAR(16) NOT NULL, 
    file_size INTEGER NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    creator_id UUID NOT NULL, 
    current_version INTEGER NOT NULL, 
    acl_version INTEGER NOT NULL, 
    indexed_version INTEGER NOT NULL, 
    index_status VARCHAR(16) NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_unit_status CHECK (status IN ('draft','published')), 
    CONSTRAINT ck_unit_versions CHECK (current_version > 0 AND indexed_version >= 0), 
    UNIQUE (unit_code), 
    FOREIGN KEY(creator_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_knowledge_units_creator_id ON knowledge_units (creator_id);

CREATE INDEX ix_knowledge_units_deleted_at ON knowledge_units (deleted_at);

CREATE INDEX ix_knowledge_units_category ON knowledge_units (category);

CREATE INDEX ix_units_active_status ON knowledge_units (status, deleted_at, updated_at);

CREATE INDEX ix_knowledge_units_status ON knowledge_units (status);

CREATE TABLE chat_sessions (
    user_id UUID NOT NULL, 
    title VARCHAR(150) NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_chat_sessions_user_id ON chat_sessions (user_id);

CREATE TABLE integration_settings (
    provider VARCHAR(30) NOT NULL, 
    enabled BOOLEAN NOT NULL, 
    config_json JSONB NOT NULL, 
    secret_ciphertext TEXT, 
    updated_by UUID, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (provider), 
    FOREIGN KEY(updated_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE audit_events (
    actor_id UUID, 
    action VARCHAR(100) NOT NULL, 
    entity_id UUID, 
    detail_json JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_events_action ON audit_events (action);

CREATE INDEX ix_audit_events_actor_id ON audit_events (actor_id);

CREATE TABLE unit_permissions (
    unit_id UUID NOT NULL, 
    target_type VARCHAR(16) NOT NULL, 
    target_id UUID, 
    department_id UUID, 
    role_id UUID, 
    user_id UUID, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_unit_target UNIQUE (unit_id, target_type, target_id), 
    CONSTRAINT ck_acl_reference CHECK ((target_type='global' AND target_id IS NULL AND department_id IS NULL AND role_id IS NULL AND user_id IS NULL) OR (target_type='department' AND target_id IS NOT NULL AND department_id IS NOT NULL AND target_id=department_id AND role_id IS NULL AND user_id IS NULL) OR (target_type='role' AND target_id IS NOT NULL AND role_id IS NOT NULL AND target_id=role_id AND department_id IS NULL AND user_id IS NULL) OR (target_type='user' AND target_id IS NOT NULL AND user_id IS NOT NULL AND target_id=user_id AND department_id IS NULL AND role_id IS NULL)), 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE CASCADE, 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE RESTRICT, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE RESTRICT, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_acl_target_lookup ON unit_permissions (target_type, target_id, unit_id);

CREATE UNIQUE INDEX uq_acl_global ON unit_permissions (unit_id) WHERE target_type='global';

CREATE INDEX ix_unit_permissions_unit_id ON unit_permissions (unit_id);

CREATE TABLE knowledge_versions (
    unit_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    title VARCHAR(300) NOT NULL, 
    content TEXT NOT NULL, 
    editor_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_unit_version UNIQUE (unit_id, version), 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE CASCADE, 
    FOREIGN KEY(editor_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_knowledge_versions_unit_id ON knowledge_versions (unit_id);

CREATE TABLE attachments (
    unit_id UUID, 
    uploader_id UUID NOT NULL, 
    file_name VARCHAR(255) NOT NULL, 
    object_key VARCHAR(600) NOT NULL, 
    bucket VARCHAR(100) NOT NULL, 
    mime_type VARCHAR(150) NOT NULL, 
    size INTEGER NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE SET NULL, 
    FOREIGN KEY(uploader_id) REFERENCES users (id) ON DELETE RESTRICT, 
    UNIQUE (object_key)
);

CREATE INDEX ix_attachments_unit_id ON attachments (unit_id);

CREATE INDEX ix_attachments_sha256 ON attachments (sha256);

CREATE TABLE knowledge_chunks (
    unit_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    ordinal INTEGER NOT NULL, 
    content TEXT NOT NULL, 
    heading VARCHAR(600) NOT NULL, 
    page INTEGER, 
    start_offset INTEGER NOT NULL, 
    end_offset INTEGER NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    embedding_model VARCHAR(100) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_chunk_position UNIQUE (unit_id, version, ordinal), 
    CONSTRAINT ck_chunk_offsets CHECK (ordinal >= 0 AND end_offset > start_offset), 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE CASCADE
);

CREATE INDEX ix_knowledge_chunks_unit_id ON knowledge_chunks (unit_id);

CREATE INDEX ix_chunk_current ON knowledge_chunks (unit_id, version);

CREATE TABLE index_tasks (
    unit_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    operation VARCHAR(16) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    attempts INTEGER NOT NULL, 
    error TEXT NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_index_task UNIQUE (unit_id, version, operation), 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE CASCADE
);

CREATE INDEX ix_index_tasks_status ON index_tasks (status);

CREATE INDEX ix_index_tasks_lease_until ON index_tasks (lease_until);

CREATE INDEX ix_index_tasks_unit_id ON index_tasks (unit_id);

CREATE TABLE chat_messages (
    session_id UUID NOT NULL, 
    role VARCHAR(16) NOT NULL, 
    content TEXT NOT NULL, 
    citations JSONB NOT NULL, 
    source_versions JSONB NOT NULL, 
    denied BOOLEAN NOT NULL, 
    cached BOOLEAN NOT NULL, 
    interrupted BOOLEAN NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id);

CREATE TABLE qa_access_logs (
    session_id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    question TEXT NOT NULL, 
    normalized_question VARCHAR(2000) NOT NULL, 
    answer TEXT NOT NULL, 
    recalled_unit_ids_json JSONB NOT NULL, 
    authorized_unit_ids_json JSONB NOT NULL, 
    unauthorized_unit_ids_json JSONB NOT NULL, 
    source_versions JSONB NOT NULL, 
    prompt_tokens INTEGER NOT NULL, 
    completion_tokens INTEGER NOT NULL, 
    total_tokens INTEGER NOT NULL, 
    response_time_ms INTEGER NOT NULL, 
    cached BOOLEAN NOT NULL, 
    outcome VARCHAR(24) NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(session_id) REFERENCES chat_sessions (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE INDEX ix_qa_access_logs_session_id ON qa_access_logs (session_id);

CREATE INDEX ix_qa_created_user ON qa_access_logs (created_at, user_id);

CREATE INDEX ix_qa_access_logs_normalized_question ON qa_access_logs (normalized_question);

CREATE INDEX ix_qa_access_logs_user_id ON qa_access_logs (user_id);

CREATE INDEX ix_qa_access_logs_outcome ON qa_access_logs (outcome);

CREATE TABLE faqs (
    question VARCHAR(2000) NOT NULL, 
    question_key VARCHAR(64) NOT NULL, 
    answer TEXT NOT NULL, 
    category VARCHAR(100) NOT NULL, 
    related_unit_id UUID, 
    source_type VARCHAR(16) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    frequency INTEGER NOT NULL, 
    hit_count INTEGER NOT NULL, 
    cache_enabled BOOLEAN NOT NULL, 
    revision INTEGER NOT NULL, 
    reviewer_id UUID, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_faq_status CHECK (status IN ('pending_review','published','rejected')), 
    UNIQUE (question_key), 
    FOREIGN KEY(related_unit_id) REFERENCES knowledge_units (id) ON DELETE SET NULL, 
    FOREIGN KEY(reviewer_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_faqs_status ON faqs (status);

CREATE TABLE knowledge_gaps (
    question_pattern VARCHAR(2000) NOT NULL, 
    question_key VARCHAR(64) NOT NULL, 
    sample_questions_json JSONB NOT NULL, 
    ask_count INTEGER NOT NULL, 
    last_asked_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    resolved_unit_id UUID, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_gap_status CHECK (status IN ('unresolved','resolved','ignored')), 
    UNIQUE (question_key), 
    FOREIGN KEY(resolved_unit_id) REFERENCES knowledge_units (id) ON DELETE SET NULL
);

CREATE INDEX ix_knowledge_gaps_status ON knowledge_gaps (status);

CREATE TABLE import_jobs (
    owner_id UUID NOT NULL, 
    attachment_id UUID NOT NULL, 
    unit_id UUID, 
    relative_path VARCHAR(600) NOT NULL, 
    status VARCHAR(16) NOT NULL, 
    phase INTEGER NOT NULL, 
    error TEXT NOT NULL, 
    cancel_requested BOOLEAN NOT NULL, 
    attempts INTEGER NOT NULL, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_job_status CHECK (status IN ('running','completed','failed','canceled')), 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT, 
    FOREIGN KEY(attachment_id) REFERENCES attachments (id) ON DELETE RESTRICT, 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE SET NULL
);

CREATE INDEX ix_import_jobs_owner_id ON import_jobs (owner_id);

CREATE INDEX ix_import_jobs_status ON import_jobs (status);

CREATE INDEX ix_import_jobs_lease_until ON import_jobs (lease_until);

CREATE TABLE qa_log_units (
    log_id UUID NOT NULL, 
    unit_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_log_unit UNIQUE (log_id, unit_id), 
    FOREIGN KEY(log_id) REFERENCES qa_access_logs (id) ON DELETE CASCADE, 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE RESTRICT
);

CREATE INDEX ix_qa_log_units_unit_id ON qa_log_units (unit_id);

CREATE INDEX ix_qa_log_units_log_id ON qa_log_units (log_id);

CREATE TABLE faq_sources (
    faq_id UUID NOT NULL, 
    unit_id UUID NOT NULL, 
    version INTEGER NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_faq_source UNIQUE (faq_id, unit_id), 
    FOREIGN KEY(faq_id) REFERENCES faqs (id) ON DELETE CASCADE, 
    FOREIGN KEY(unit_id) REFERENCES knowledge_units (id) ON DELETE RESTRICT
);

CREATE INDEX ix_faq_sources_unit_id ON faq_sources (unit_id);

CREATE INDEX ix_faq_sources_faq_id ON faq_sources (faq_id);

ALTER TABLE departments ADD CONSTRAINT fk_department_leader FOREIGN KEY(leader_id) REFERENCES users (id) ON DELETE SET NULL;;

INSERT INTO alembic_version (version_num) VALUES ('0001_pg_milvus') RETURNING alembic_version.version_num;

COMMIT;

