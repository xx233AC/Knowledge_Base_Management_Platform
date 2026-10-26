# Milvus 集合设计

服务版本兼容 Milvus 2.5.5，Python SDK 限定 2.5.x。本项目不在 PostgreSQL 安装 pgvector。

集合：`kb_chunks_bge_m3_v1`（可通过 MILVUS_COLLECTION 修改）。一个版本的一个切片对应一条向量记录。

| 字段 | 类型 | 用途 |
|---|---|---|
| chunk_id | VARCHAR(36)，主键，不自动生成 | 对应 PostgreSQL knowledge_chunks.id |
| unit_id | VARCHAR(36)，INVERTED 索引 | 对应 knowledge_units.id，按单元删除/维护 |
| version | INT64 | 知识正文版本，用于识别陈旧向量 |
| content_hash | VARCHAR(64) | 切片 SHA-256，用于追踪内容一致性 |
| model_id | VARCHAR(100) | BAAI/bge-m3，标识向量生成模型 |
| dense_vector | FLOAT_VECTOR，1024 维 | 本地模型 CLS 池化并 L2 归一化 |

向量索引：HNSW，COSINE，M=16、efConstruction=200；检索 ef 至少64。使用 Strong 一致性。禁用动态字段，防止把正文/秘密意外写入向量存储。

不把正文、标题、角色授权列表复制进 Milvus。真实正文、切片出处、版本和权限始终从 PostgreSQL 读取。召回命中必须同时匹配 chunk_id、unit_id、version，且知识未删除、已发布、版本仍为当前版本，然后按用户当前部门、角色、个人或全局授权过滤。

初始授权为空。系统管理员的操作权限不构成内容权限。授权修改无需重建向量：下次请求立即从 PostgreSQL 按新规则鉴权，避免复制 ACL 后的同步延迟。

新文档/编辑在同一 PostgreSQL 事务写 knowledge_chunks 和 index_tasks。Worker 重试幂等 upsert。Milvus 写入成功并检查当前版本后才更新 indexed_version。陈旧或软删除单元的向量不会用于回答，物理向量清理由后台任务完成。

模型变更或维度变更应创建新集合并离线重建，核验后修改配置切换。初始化命令会检查已有集合，不自动删集合，也不把历史 Milvus 默认集合中的数据搬入本集合。

本期实现 bge-m3 dense 检索，与 PostgreSQL 关键词候选使用 RRF 融合；未实现 sparse/ColBERT，不额外占用这些索引资源。向量服务异常时接口明确标记 degraded，只有真实关键词命中才可继续；检索故障不能被记作知识缺口。

模型文件位置：`D:\ai_models\modelscope_cache\models\models\BAAI--bge-m3\snapshots\master`。自动从用户提供的缓存父目录定位快照。设置 local_files_only=True，不隐式联网下载另一个模型。
