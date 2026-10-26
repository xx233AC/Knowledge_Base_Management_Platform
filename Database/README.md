# 数据库设计 v2：PostgreSQL + Milvus

本目录替换此前 PostgreSQL+pgvector 的 28 表设计。当前共22张 PostgreSQL业务表，向量使用独立 Milvus 集合；不需要 vector 扩展。

- `001_schema.sql`：完整 PostgreSQL DDL，包含外键、CHECK、唯一约束和索引。
- `DATA-DICTIONARY.md`：字段字典。
- `../Back/migrations`：正式版本迁移；推荐在 Back 运行 `python -m alembic upgrade head`，不要同时手工运行DDL再重复执行迁移。
- `../Back/docs/milvus-schema.md`：Milvus 字段、索引、版本与一致性设计。
- `../Back/README.md`：初始化、PyCharm、SSH隧道、服务接入与验收步骤。

原始旧设计和旧 Docker 文件已备份后从项目中移除。没有在服务器上执行 DROP、TRUNCATE 或删除容器数据。迁移要求连接目标库具备权限且不存在同名旧业务表；若已手工创建旧表，先备份并比较结构，禁止直接 stamp 跳过迁移。
