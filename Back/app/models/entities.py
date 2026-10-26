"""Authoritative relational records. Vector payloads live exclusively in Milvus."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, Uuid, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


def new_id():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


J = JSON().with_variant(JSONB, "postgresql")
UID = Uuid(as_uuid=False)


class Record(Base):
    __abstract__ = True
    id: Mapped[str] = mapped_column(UID, primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MutableRecord(Record):
    __abstract__ = True
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Department(MutableRecord):
    __tablename__ = "departments"
    parent_id: Mapped[str | None] = mapped_column(UID, ForeignKey("departments.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(100))
    leader_id: Mapped[str | None] = mapped_column(
        UID, ForeignKey("users.id", name="fk_department_leader", use_alter=True, ondelete="SET NULL")
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_dept_not_self"),)


class User(MutableRecord):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[str | None] = mapped_column(UID, ForeignKey("departments.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="active")
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("status IN ('active','disabled')", name="ck_user_status"),)


class Role(MutableRecord):
    __tablename__ = "roles"
    role_name: Mapped[str] = mapped_column(String(100))
    role_code: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class UserRole(Record):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[str] = mapped_column(UID, ForeignKey("roles.id", ondelete="RESTRICT"), index=True)
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)


class RolePermission(Record):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = mapped_column(UID, ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    permission_code: Mapped[str] = mapped_column(String(80))
    permission_type: Mapped[str] = mapped_column(String(16), default="operation")
    __table_args__ = (UniqueConstraint("role_id", "permission_code", name="uq_role_permission"),)


class AuthSession(Record):
    __tablename__ = "auth_sessions"
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeUnit(MutableRecord):
    __tablename__ = "knowledge_units"
    unit_code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="未分类", index=True)
    tags: Mapped[list] = mapped_column(J, default=list)
    source_file_name: Mapped[str] = mapped_column(String(255), default="")
    file_type: Mapped[str] = mapped_column(String(16), default="md")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    creator_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    acl_version: Mapped[int] = mapped_column(Integer, default=1)
    indexed_version: Mapped[int] = mapped_column(Integer, default=0)
    index_status: Mapped[str] = mapped_column(String(16), default="pending")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        CheckConstraint("status IN ('draft','published')", name="ck_unit_status"),
        CheckConstraint("current_version > 0 AND indexed_version >= 0", name="ck_unit_versions"),
        Index("ix_units_active_status", "status", "deleted_at", "updated_at"),
    )


class UnitPermission(Record):
    __tablename__ = "unit_permissions"
    unit_id: Mapped[str] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target_id: Mapped[str | None] = mapped_column(UID)
    department_id: Mapped[str | None] = mapped_column(UID, ForeignKey("departments.id", ondelete="RESTRICT"))
    role_id: Mapped[str | None] = mapped_column(UID, ForeignKey("roles.id", ondelete="RESTRICT"))
    user_id: Mapped[str | None] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (
        UniqueConstraint("unit_id", "target_type", "target_id", name="uq_unit_target"),
        CheckConstraint(
            "(target_type='global' AND target_id IS NULL AND department_id IS NULL AND role_id IS NULL AND user_id IS NULL) OR "
            "(target_type='department' AND target_id IS NOT NULL AND department_id IS NOT NULL AND target_id=department_id AND role_id IS NULL AND user_id IS NULL) OR "
            "(target_type='role' AND target_id IS NOT NULL AND role_id IS NOT NULL AND target_id=role_id AND department_id IS NULL AND user_id IS NULL) OR "
            "(target_type='user' AND target_id IS NOT NULL AND user_id IS NOT NULL AND target_id=user_id AND department_id IS NULL AND role_id IS NULL)",
            name="ck_acl_reference",
        ),
        Index("uq_acl_global", "unit_id", unique=True,
              postgresql_where=text("target_type='global'"), sqlite_where=text("target_type='global'")),
        Index("ix_acl_target_lookup", "target_type", "target_id", "unit_id"),
    )


class UnitVersion(Record):
    __tablename__ = "knowledge_versions"
    unit_id: Mapped[str] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    editor_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"))
    __table_args__ = (UniqueConstraint("unit_id", "version", name="uq_unit_version"),)


class Attachment(Record):
    __tablename__ = "attachments"
    unit_id: Mapped[str | None] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="SET NULL"), index=True)
    uploader_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"))
    file_name: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(String(600), unique=True)
    bucket: Mapped[str] = mapped_column(String(100))
    mime_type: Mapped[str] = mapped_column(String(150), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)


class Chunk(Record):
    __tablename__ = "knowledge_chunks"
    unit_id: Mapped[str] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    heading: Mapped[str] = mapped_column(String(600), default="")
    page: Mapped[int | None] = mapped_column(Integer)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(100), default="BAAI/bge-m3")
    __table_args__ = (
        UniqueConstraint("unit_id", "version", "ordinal", name="uq_chunk_position"),
        CheckConstraint("ordinal >= 0 AND end_offset > start_offset", name="ck_chunk_offsets"),
        Index("ix_chunk_current", "unit_id", "version"),
    )


class ImportJob(MutableRecord):
    __tablename__ = "import_jobs"
    owner_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    attachment_id: Mapped[str] = mapped_column(UID, ForeignKey("attachments.id", ondelete="RESTRICT"))
    unit_id: Mapped[str | None] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="SET NULL"))
    relative_path: Mapped[str] = mapped_column(String(600))
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)
    phase: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_generation: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (CheckConstraint("status IN ('running','completed','failed','canceled')", name="ck_job_status"),)


class IndexTask(MutableRecord):
    __tablename__ = "index_tasks"
    unit_id: Mapped[str] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(16), default="upsert")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_generation: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint("unit_id", "version", "operation", name="uq_index_task"),)


class ChatSession(MutableRecord):
    __tablename__ = "chat_sessions"
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(Record):
    __tablename__ = "chat_messages"
    session_id: Mapped[str] = mapped_column(UID, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(J, default=list)
    source_versions: Mapped[dict] = mapped_column(J, default=dict)
    denied: Mapped[bool] = mapped_column(Boolean, default=False)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)


class QAAccessLog(Record):
    __tablename__ = "qa_access_logs"
    session_id: Mapped[str] = mapped_column(UID, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(UID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    question: Mapped[str] = mapped_column(Text)
    normalized_question: Mapped[str] = mapped_column(String(2000), index=True)
    answer: Mapped[str] = mapped_column(Text, default="")
    recalled_unit_ids_json: Mapped[list] = mapped_column(J, default=list)
    authorized_unit_ids_json: Mapped[list] = mapped_column(J, default=list)
    unauthorized_unit_ids_json: Mapped[list] = mapped_column(J, default=list)
    source_versions: Mapped[dict] = mapped_column(J, default=dict)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[str] = mapped_column(String(24), default="answered", index=True)
    __table_args__ = (Index("ix_qa_created_user", "created_at", "user_id"),)


class QALogUnit(Record):
    __tablename__ = "qa_log_units"
    log_id: Mapped[str] = mapped_column(UID, ForeignKey("qa_access_logs.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[str] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="RESTRICT"), index=True)
    __table_args__ = (UniqueConstraint("log_id", "unit_id", name="uq_log_unit"),)


class Faq(MutableRecord):
    __tablename__ = "faqs"
    question: Mapped[str] = mapped_column(String(2000))
    question_key: Mapped[str] = mapped_column(String(64), unique=True)
    answer: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="未分类")
    related_unit_id: Mapped[str | None] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="SET NULL"))
    source_type: Mapped[str] = mapped_column(String(16), default="manual")
    status: Mapped[str] = mapped_column(String(24), default="pending_review", index=True)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    hit_count: Mapped[int] = mapped_column(Integer, default=0)
    cache_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reviewer_id: Mapped[str | None] = mapped_column(UID, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('pending_review','published','rejected')", name="ck_faq_status"),)


class FaqSource(Record):
    __tablename__ = "faq_sources"
    faq_id: Mapped[str] = mapped_column(UID, ForeignKey("faqs.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[str] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("faq_id", "unit_id", name="uq_faq_source"),)


class KnowledgeGap(MutableRecord):
    __tablename__ = "knowledge_gaps"
    question_pattern: Mapped[str] = mapped_column(String(2000))
    question_key: Mapped[str] = mapped_column(String(64), unique=True)
    sample_questions_json: Mapped[list] = mapped_column(J, default=list)
    ask_count: Mapped[int] = mapped_column(Integer, default=1)
    last_asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="unresolved", index=True)
    resolved_unit_id: Mapped[str | None] = mapped_column(UID, ForeignKey("knowledge_units.id", ondelete="SET NULL"))
    __table_args__ = (CheckConstraint("status IN ('unresolved','resolved','ignored')", name="ck_gap_status"),)


class IntegrationSetting(MutableRecord):
    __tablename__ = "integration_settings"
    provider: Mapped[str] = mapped_column(String(30), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config_json: Mapped[dict] = mapped_column(J, default=dict)
    secret_ciphertext: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[str | None] = mapped_column(UID, ForeignKey("users.id", ondelete="SET NULL"))


class AuditEvent(Record):
    __tablename__ = "audit_events"
    actor_id: Mapped[str | None] = mapped_column(UID, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    entity_id: Mapped[str | None] = mapped_column(UID)
    detail_json: Mapped[dict] = mapped_column(J, default=dict)
