# PostgreSQL 数据字典 v2

权威定义：Back/app/models/entities.py；迁移后请用 Alembic 新 revision 维护。

所有 id 为 UUID，时间为 timestamptz，JSON 使用 JSONB；向量只存 Milvus。

## departments

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| parent_id | UUID | 是 |
| name | VARCHAR(100) | 否 |
| leader_id | UUID | 是 |
| sort_order | INTEGER | 否 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, ck_dept_not_self, fk_department_leader

## roles

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| role_name | VARCHAR(100) | 否 |
| role_code | VARCHAR(64) | 否 |
| description | TEXT | 否 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：PrimaryKeyConstraint, UniqueConstraint

## role_permissions

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| role_id | UUID | 否 |
| permission_code | VARCHAR(80) | 否 |
| permission_type | VARCHAR(16) | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, uq_role_permission

## users

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| username | VARCHAR(64) | 否 |
| password_hash | VARCHAR(255) | 否 |
| display_name | VARCHAR(100) | 否 |
| department_id | UUID | 是 |
| status | VARCHAR(16) | 否 |
| token_version | INTEGER | 否 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint, ck_user_status

## audit_events

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| actor_id | UUID | 是 |
| action | VARCHAR(100) | 否 |
| entity_id | UUID | 是 |
| detail_json | JSONB | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint

## auth_sessions

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| user_id | UUID | 否 |
| expires_at | TIMESTAMP WITH TIME ZONE | 否 |
| revoked | BOOLEAN | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint

## chat_sessions

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| user_id | UUID | 否 |
| title | VARCHAR(150) | 否 |
| deleted_at | TIMESTAMP WITH TIME ZONE | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint

## integration_settings

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| provider | VARCHAR(30) | 否 |
| enabled | BOOLEAN | 否 |
| config_json | JSONB | 否 |
| secret_ciphertext | TEXT | 是 |
| updated_by | UUID | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint

## knowledge_units

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| unit_code | VARCHAR(40) | 否 |
| title | VARCHAR(300) | 否 |
| content | TEXT | 否 |
| summary | TEXT | 否 |
| category | VARCHAR(100) | 否 |
| tags | JSONB | 否 |
| source_file_name | VARCHAR(255) | 否 |
| file_type | VARCHAR(16) | 否 |
| file_size | INTEGER | 否 |
| status | VARCHAR(16) | 否 |
| creator_id | UUID | 否 |
| current_version | INTEGER | 否 |
| acl_version | INTEGER | 否 |
| indexed_version | INTEGER | 否 |
| index_status | VARCHAR(16) | 否 |
| deleted_at | TIMESTAMP WITH TIME ZONE | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint, ck_unit_status, ck_unit_versions

## user_roles

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| user_id | UUID | 否 |
| role_id | UUID | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, uq_user_role

## attachments

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| unit_id | UUID | 是 |
| uploader_id | UUID | 否 |
| file_name | VARCHAR(255) | 否 |
| object_key | VARCHAR(600) | 否 |
| bucket | VARCHAR(100) | 否 |
| mime_type | VARCHAR(150) | 否 |
| size | INTEGER | 否 |
| sha256 | VARCHAR(64) | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint

## chat_messages

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| session_id | UUID | 否 |
| role | VARCHAR(16) | 否 |
| content | TEXT | 否 |
| citations | JSONB | 否 |
| source_versions | JSONB | 否 |
| denied | BOOLEAN | 否 |
| cached | BOOLEAN | 否 |
| interrupted | BOOLEAN | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint

## faqs

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| question | VARCHAR(2000) | 否 |
| question_key | VARCHAR(64) | 否 |
| answer | TEXT | 否 |
| category | VARCHAR(100) | 否 |
| related_unit_id | UUID | 是 |
| source_type | VARCHAR(16) | 否 |
| status | VARCHAR(24) | 否 |
| frequency | INTEGER | 否 |
| hit_count | INTEGER | 否 |
| cache_enabled | BOOLEAN | 否 |
| revision | INTEGER | 否 |
| reviewer_id | UUID | 是 |
| reviewed_at | TIMESTAMP WITH TIME ZONE | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint, ck_faq_status

## index_tasks

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| unit_id | UUID | 否 |
| version | INTEGER | 否 |
| operation | VARCHAR(16) | 否 |
| status | VARCHAR(16) | 否 |
| attempts | INTEGER | 否 |
| lease_generation | INTEGER | 否 |
| error | TEXT | 否 |
| lease_until | TIMESTAMP WITH TIME ZONE | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, uq_index_task

## knowledge_chunks

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| unit_id | UUID | 否 |
| version | INTEGER | 否 |
| ordinal | INTEGER | 否 |
| content | TEXT | 否 |
| heading | VARCHAR(600) | 否 |
| page | INTEGER | 是 |
| start_offset | INTEGER | 否 |
| end_offset | INTEGER | 否 |
| content_hash | VARCHAR(64) | 否 |
| embedding_model | VARCHAR(100) | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, ck_chunk_offsets, uq_chunk_position

## knowledge_gaps

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| question_pattern | VARCHAR(2000) | 否 |
| question_key | VARCHAR(64) | 否 |
| sample_questions_json | JSONB | 否 |
| ask_count | INTEGER | 否 |
| last_asked_at | TIMESTAMP WITH TIME ZONE | 否 |
| status | VARCHAR(16) | 否 |
| resolved_unit_id | UUID | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint, ck_gap_status

## knowledge_versions

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| unit_id | UUID | 否 |
| version | INTEGER | 否 |
| title | VARCHAR(300) | 否 |
| content | TEXT | 否 |
| editor_id | UUID | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, uq_unit_version

## qa_access_logs

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| session_id | UUID | 否 |
| user_id | UUID | 否 |
| question | TEXT | 否 |
| normalized_question | VARCHAR(2000) | 否 |
| answer | TEXT | 否 |
| recalled_unit_ids_json | JSONB | 否 |
| authorized_unit_ids_json | JSONB | 否 |
| unauthorized_unit_ids_json | JSONB | 否 |
| source_versions | JSONB | 否 |
| prompt_tokens | INTEGER | 否 |
| completion_tokens | INTEGER | 否 |
| total_tokens | INTEGER | 否 |
| response_time_ms | INTEGER | 否 |
| cached | BOOLEAN | 否 |
| outcome | VARCHAR(24) | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint

## unit_permissions

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| unit_id | UUID | 否 |
| target_type | VARCHAR(16) | 否 |
| target_id | UUID | 是 |
| department_id | UUID | 是 |
| role_id | UUID | 是 |
| user_id | UUID | 是 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, ck_acl_reference, uq_unit_target

## faq_sources

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| faq_id | UUID | 否 |
| unit_id | UUID | 否 |
| version | INTEGER | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, uq_faq_source

## import_jobs

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| owner_id | UUID | 否 |
| attachment_id | UUID | 否 |
| unit_id | UUID | 是 |
| relative_path | VARCHAR(600) | 否 |
| status | VARCHAR(16) | 否 |
| phase | INTEGER | 否 |
| error | TEXT | 否 |
| cancel_requested | BOOLEAN | 否 |
| attempts | INTEGER | 否 |
| lease_generation | INTEGER | 否 |
| lease_until | TIMESTAMP WITH TIME ZONE | 是 |
| updated_at | TIMESTAMP WITH TIME ZONE | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, ck_job_status

## qa_log_units

| 字段 | PostgreSQL 类型 | 可空 |
|---|---|---|
| log_id | UUID | 否 |
| unit_id | UUID | 否 |
| id | UUID | 否 |
| created_at | TIMESTAMP WITH TIME ZONE | 否 |

约束：ForeignKeyConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, uq_log_unit
