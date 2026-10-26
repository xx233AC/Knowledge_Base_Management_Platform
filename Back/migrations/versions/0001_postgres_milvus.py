"""Initial relational schema; intentionally independent of pgvector and historical v1 files."""
from pathlib import Path
from alembic import op, context

revision = '0001_pg_milvus'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema = Path(__file__).resolve().parents[2] / 'sql' / '001_schema.sql'
    sql = schema.read_text(encoding='utf-8')
    if context.is_offline_mode():
        op.execute(sql)
    else:
        op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError('禁止自动删除业务数据；如需重建，请先人工备份并审核专用 SQL。')
