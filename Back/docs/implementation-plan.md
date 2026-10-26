# FastAPI 后端实施计划（2026-10-22）

目标：实现需求书 2.9 全部后端模块，兼容 Front/src/services/api.ts，使用 PostgreSQL 17、Milvus 2.5.5、MinIO、Redis；不改动现有前端视觉或删除旧数据库设计。

## 结构与边界

- app/routers：HTTP、输入校验、登录与操作权限依赖，输出前端兼容 DTO。
- app/services：组织、知识、导入、ACL、检索、问答、统计、沉淀业务。
- app/repositories：SQLAlchemy 查询及持久化，基础设施适配。
- app/models：数据库 ORM；app/schemas：Pydantic 请求契约。
- app/core：配置、安全、数据库、异常、依赖；app/common：切分、文本规范化等纯工具。
- app/integrations：MinIO、Redis、Milvus、本地 bge-m3、MinerU v4 云端解析、LLM 接入。
- app/worker.py：独立后台工作进程；导入、索引任务持久化在 PostgreSQL，租约、重试、恢复；不依赖 Web 进程内不可恢复的后台任务。
- migrations、sql、docs、scripts、tests：迁移、DDL、字典/接口文档、初始化与验证。

## 任务

- [x] 1. 写核心验收测试并观察失败；创建 Python 3.12 隔离环境与依赖。
- [x] 2. ORM/迁移/初始化：需求书十张表加切片、版本、附件、会话消息、索引任务、配置与登录会话等必需表。UUID 主键；时区时间；约束、索引、软删除；无 pgvector 依赖。
- [x] 3. JWT/RBAC/组织/ACL：即时校验当前用户和数据库权限；登出/重置密码撤销会话；无隐式数据权限超管绕过；检查指定他人身份仅允许管理权限。
- [x] 4. 知识 CRUD、版本、附件、导入：TXT/MD/DOCX 实际解析；PDF/DOC 经 MinerU v4 批量上传解析，未启用、Token 失效或额度不足时明确报错；一文档一知识单元，切片保存出处与顺序。文档更新事务性写索引任务；Milvus 失败可重试，不伪称完成。
- [x] 5. bge-m3/Milvus：本地快照自动解析，离线加载、归一化 dense 1024、COSINE/HNSW；检索只返回 ID/版本/得分，再从 PostgreSQL 鉴权取正文，防陈旧向量/撤权泄漏。
- [x] 6. AI/SSE：会话所属人验证；向量与关键词融合；授权后组装上下文；无权限只返回泛化提示，不泄露标题正文；真实 LLM 未配置不能模拟生成；FAQ 同样重新鉴权并校验来源版本。
- [x] 7. 看板、FAQ 审核/缓存、频次语义聚合、知识缺口：无权限不记缺口，统计只展示被授权的引用，普通用户不能查询别人的会话。
- [x] 8. 完整测试、模型实测、接口契约核对、安全复查；启动/隧道/迁移/示例链路/配置说明见 `README.md`。PostgreSQL DDL 已在离线模式校验，真实库执行仍需隧道与凭据（见下）。

## 完成情况（2026-10-22）

- `pytest`：50 项全部通过；`ruff check app tests` 无告警。
- MinerU v4 已接入并实测：真实账号解析 36 KB DOCX 用时 31.8 秒，成功取回 Markdown；单测覆盖 Token 失效、解析失败、额度耗尽、未启用四条路径。
- 文档图片：MinerU 压缩包中的图片写入 MinIO（`images/<unit_id>/`），`attachments` 建档，正文中的相对链接改写为 HMAC 签名地址 `/api/knowledge/assets/{id}?sig=...`；纯图片切片不参与向量化。
- 导入等待超时：Worker 每 10 秒写 Redis 心跳；未被领取且无心跳超过 `IMPORT_WAIT_TIMEOUT_SECONDS`（默认 120 秒）时任务自动判失败并提示启动 Worker，Worker 存活时排队任务不会被误判。
- 向量模型支持 `EMBEDDING_DEVICE=cuda`，torch 来源切换为 cu126 轮子；新增 `EMBEDDING_DTYPE=float32|float16`。
- 前端 `Front/.env` 已设为 `VITE_DATA_MODE=api`，Vite 的 `/api → 127.0.0.1:8000` 代理已验证可到达后端。
- 本地 bge-m3：从 `snapshots/master` 加载成功，两段中文生成 1024 维、L2 归一化（范数 1.0），相关句余弦 0.809。
- OpenAPI：43 个路径 / 55 个操作，无重复 operationId；与 `Front/docs/API-CONTRACT.md` 逐条核对一致，另增 `settings/integrations`、`ai/search`、`knowledge/units/{id}/reindex`、`knowledge/import/jobs/{id}/retry`、`knowledge/attachments/{id}/download`、`settlement/mine`。

## 需在真实环境完成

1. 按 `README.md` 填写 `Back/.env` 的数据库、Redis、MinIO 凭据（来自服务器 `/opt/.env`、`/opt/redis/redis.conf`）。
2. 建立 SSH 隧道后执行 `alembic upgrade head`，让 DDL 真正落到 PostgreSQL。
3. 依次执行 `seed-admin`、`init-infrastructure`、`load-samples`，并常驻运行 `app.worker`。
4. 前端新建 `Front/.env` 设 `VITE_DATA_MODE=api` 联调。


## 验证重点

无授权默认拒绝；四维 OR；账号停用/密码重置/撤权立即生效；批量变更全有或全无；部门环；权限伪造；FAQ 撤权与旧答案；上传路径穿越；旧索引版本不参与回答；后台失败与取消；SSE 数据不能在未鉴权时泄露；未配置外部服务真实报错。

## 执行记录

本目录尚为空且项目不是 Git 仓库，按用户指定位置直接开发，不创建额外 worktree，不自动初始化/改写远程数据库。先交付迁移和初始化命令，绝不自动 drop 旧表。凭据通过本机 .env 配置，不从截图读取或把服务器密码写进源码。测试注入内存适配器隔离外部服务，生产默认使用真实基础设施。
