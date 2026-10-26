import argparse
import getpass
import json
from pathlib import Path
from sqlalchemy import inspect, select
from app.core.config import get_settings
from app.core.database import build_database
from app.integrations.infrastructure import Infrastructure
from app.services.bootstrap import seed_admin
from app.services.identity import IdentityService
from app.services.knowledge import KnowledgeService
from app.models.entities import User


def main():
    parser = argparse.ArgumentParser(description='知识库后端管理工具')
    parser.add_argument('command', choices=['inspect-db', 'seed-admin', 'init-infrastructure', 'load-samples'])
    args = parser.parse_args()
    settings = get_settings()
    engine, factory = build_database(settings.database_url)
    if args.command == 'inspect-db':
        print(json.dumps(inspect(engine).get_table_names(), ensure_ascii=False, indent=2))
    elif args.command == 'seed-admin':
        password = getpass.getpass('初始管理员密码（至少12位，不回显）：')
        if password != getpass.getpass('再次输入：'):
            raise SystemExit('两次密码不一致')
        with factory.begin() as db:
            seed_admin(db, password)
        print('已创建 admin 账号及三种初始角色，没有默认弱密码。')
    elif args.command == 'init-infrastructure':
        infra = Infrastructure.from_settings(settings)
        infra.storage.ensure()
        infra.vectors.ensure()
        infra.cache.ready()
        print('MinIO 存储桶、Milvus 集合、Redis 已验证。没有删除已有集合或数据。')
    elif args.command == 'load-samples':
        samples = Path(__file__).resolve().parents[1]/'samples'
        with factory.begin() as db:
            user = db.scalar(select(User).where(User.username == 'admin', User.status == 'active'))
            if not user:
                raise SystemExit('请先初始化管理员')
            actor = IdentityService(db, settings).identity(user)
            for path in samples.glob('*.md'):
                KnowledgeService(db, settings).save(actor, dict(title=path.stem, content=path.read_text(encoding='utf-8'),
                    category='示例', status='published', acl=[{'type': 'global'}]))
        print('已加载明确全局授权的示例文档；请启动 Worker 完成向量索引。')


if __name__ == '__main__':
    main()
