"""Regenerate the initial DDL only before first deployment; later changes require new migrations."""
from pathlib import Path
import sys
from sqlalchemy import create_mock_engine
from sqlalchemy.schema import CreateTable, CreateIndex, AddConstraint
from sqlalchemy.dialects import postgresql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.models.entities import Base  # noqa: E402


def export():
    statements = []
    def emit(sql, *args, **kwargs):
        statements.append(str(sql.compile(dialect=postgresql.dialect())).strip()+';')
    engine = create_mock_engine('postgresql+psycopg://', emit)
    Base.metadata.create_all(engine, checkfirst=False)
    text = '-- PostgreSQL 17 / schema v2: vectors are stored in Milvus, not PostgreSQL.\n'
    text += '-- No DROP/TRUNCATE; run via alembic upgrade head against the intended database.\n\n'
    text += '\n\n'.join(statements)+'\n'
    for path in [ROOT/'sql'/'001_schema.sql', ROOT.parent/'Database'/'001_schema.sql']:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    print(f'Exported {len(Base.metadata.tables)} tables and their constraints/indexes')
    dictionary = ['# PostgreSQL 数据字典 v2', '', '权威定义：Back/app/models/entities.py；迁移后请用 Alembic 新 revision 维护。',
                  '', '所有 id 为 UUID，时间为 timestamptz，JSON 使用 JSONB；向量只存 Milvus。', '']
    for table in Base.metadata.sorted_tables:
        dictionary += [f'## {table.name}', '', '| 字段 | PostgreSQL 类型 | 可空 |', '|---|---|---|']
        for c in table.columns:
            dictionary.append(f'| {c.name} | {c.type.compile(dialect=postgresql.dialect())} | {"是" if c.nullable else "否"} |')
        dictionary += ['', '约束：'+', '.join(sorted(c.name or type(c).__name__ for c in table.constraints)), '']
    content = '\n'.join(dictionary)
    (ROOT/'docs'/'data-dictionary.md').write_text(content, encoding='utf-8')
    (ROOT.parent/'Database'/'DATA-DICTIONARY.md').write_text(content, encoding='utf-8')


if __name__ == '__main__':
    export()
