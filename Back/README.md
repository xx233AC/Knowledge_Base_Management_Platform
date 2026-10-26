# 知识库管理平台 · 后端

FastAPI + PostgreSQL 17 + Milvus 2.5 + Redis 7 + MinIO，本地 bge-m3 生成 1024 维向量。
PDF / 旧版 Word 由 MinerU v4 云端解析；云端大模型只保留配置字段，未配置时问答明确报错。

## 目录

| 路径 | 职责 |
|---|---|
| `app/routers` | HTTP 接口、入参校验、登录与操作权限依赖 |
| `app/services` | 组织、知识、导入、ACL、检索、问答、统计、沉淀业务 |
| `app/repositories` | SQLAlchemy 查询与持久化 |
| `app/models/entities.py` | 22 张关系表 ORM |
| `app/integrations` | MinIO / Redis / Milvus / bge-m3 / LLM / MinerU 适配 |
| `app/worker.py` | 自动后台处理进程：导入、索引、定时挖掘 |
| `app/core/worker_runtime.py` | 随后端启动并监管 Worker，热重载/关闭时清理子进程 |
| `app/workflows/ingestion.py` | LangGraph 节点、State 和条件分支：文档导入图、向量索引图 |
| `migrations`、`sql` | Alembic 迁移与初始 DDL（不含 pgvector） |
| `docs` | 数据字典、Milvus 集合设计、实施计划 |

## 首次启动

以下命令都在 `D:\Knowledge_Base_Management_Platform\Back` 下执行。

### 1. 建立 SSH 隧道

在 PowerShell 中执行，保持窗口打开：

```powershell
ssh -N -L 127.0.0.1:15432:127.0.0.1:5432 -L 127.0.0.1:6379:127.0.0.1:6379 -L 127.0.0.1:19530:127.0.0.1:19530 -L 127.0.0.1:9000:127.0.0.1:9002 -L 127.0.0.1:9091:127.0.0.1:9091 root@192.168.100.233
```

连接的是服务器 root，输入的是 SSH 密码（不是数据库密码）。端口含义：

| 本机 | 服务器 | 服务 |
|---|---|---|
| 15432 | 5432 | PostgreSQL |
| 6379 | 6379 | Redis |
| 19530 | 19530 | Milvus |
| 9000 | 9002 | MinIO（Milvus 配套实例；也可改为独立实例的 9000） |
| 9091 | 9091 | Milvus 健康检查 |

### 2. 安装依赖

`.venv` 尚不存在时才执行第一行（重复执行会重建环境，已装依赖会丢失）。下面两种写法等价，任选其一：

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r pyproject.toml --extra dev --extra embedding
```

```bash
uv sync --extra dev --extra embedding
```

`dev` 提供 pytest/ruff，`embedding` 提供 torch/transformers。只跑接口不跑本地向量模型时可以省略 `--extra embedding`，但导入任务会因缺少模型失败。

torch 的来源在 `pyproject.toml` 的 `[[tool.uv.index]]` 里指向 CUDA 12.6 轮子（`download.pytorch.org/whl/cu126`），适配本机 RTX 3060。换到没有 NVIDIA GPU 的机器时，把该 index 的 url 改回 `https://download.pytorch.org/whl/cpu`，再执行：

```bash
uv sync --extra dev --extra embedding
```

**注意：直接执行 `uv sync` 会卸载这两个 extra 里的全部包**（因为它们在 `pyproject.toml` 中是 `[project.optional-dependencies]`）。如果发现 pytest 或 torch 突然缺失，重跑带 `--extra` 的命令即可。

### 3. 生成并填写配置

```bash
.venv\Scripts\python.exe scripts\init_env.py
```

脚本会生成 `.env` 和独立的 JWT / 加密密钥，**已存在则不会覆盖**。随后手工填写：

- `DATABASE_URL`：`postgresql+psycopg://kb_admin:<POSTGRES_PASSWORD>@127.0.0.1:15432/knowledge_base`
- `REDIS_URL`：`redis://:<REDIS_PASSWORD>@127.0.0.1:6379/0`
- `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`：MinIO 的凭据

密码在服务器的 `/opt/.env` 和 `/opt/redis/redis.conf` 中，不要写进代码或提交到仓库。

### 4. 建表

```bash
.venv\Scripts\python.exe -m alembic upgrade head
```

迁移只执行 `sql/001_schema.sql`，不含任何 DROP/TRUNCATE；降级被刻意禁用，重建前请先人工备份。已有数据库不会自动改动。

### 5. 初始化数据

```bash
.venv\Scripts\python.exe -m app.cli seed-admin
.venv\Scripts\python.exe -m app.cli init-infrastructure
.venv\Scripts\python.exe -m app.cli load-samples
```

- `seed-admin`：交互式设置管理员密码（至少 12 位，无默认弱密码），创建三种初始角色
- `init-infrastructure`：创建 MinIO 存储桶、Milvus 集合，验证 Redis；不删除已有集合或数据
- `load-samples`：导入 `samples/团队知识使用说明.md`，授权为全局，需 Worker 跑完才有向量

### 6. 启动服务

启动后端（PyCharm 运行 `run.py` 也可以）：

```bash
.venv\Scripts\python.exe run.py
```

默认 `WORKER_AUTO_START=true`，后端会自动启动并监管后台 Worker。前端上传成功后，任务自动进入 LangGraph 流程，无需再开一个终端。Worker 意外退出会自动重启；后端退出或热重载会先请求停止 Worker，超时则终止子进程。

仅当部署时需要独立扩容 Worker，才设置 `WORKER_AUTO_START=false`，并单独运行：

```bash
.venv\Scripts\python.exe -m app.worker
```

LangGraph 使用节点和 `TypedDict` State 编排以下两个阶段：

```text
导入图：load_document → parse_document → analyze_images → persist_document
         读取与鉴权       MinerU/本地解析    DeepSeek 图片分析    图片入 MinIO、正文和切片入 PostgreSQL
                                              ↓ 创建持久化索引任务
索引图：load_chunks → embed_chunks → write_vectors → finish_index
         校验版本       本地 bge-m3       Milvus          更新完成状态
```

删除索引走 `load_chunks → write_vectors → finish_index`；取消、过期租约和旧版本任务通过条件边提前结束。State 只在本次执行中流转，不包含数据库连接或 API Key；正文/图片属于瞬时解析结果。持久化边界由现有 `import_jobs`、`index_tasks` 和数据库事务保证，本次未启用 LangGraph Checkpointer，不承诺从任意节点精确续跑。进程中途终止时，任务在租约过期后重新领取，可能重新调用 MinerU；索引重试不会重复创建已保存的知识单元。

DeepSeek 使用官方示例中的 OpenAI Python SDK，`base_url=https://api.deepseek.com`，默认模型 `deepseek-flash`。`KB_LLM_API_KEY` 只写在后端 `.env` 或系统配置的加密密钥中，不写入前端。这里的变量名刻意加了 `KB_` 前缀：桌面环境里常有其他工具导出的 `LLM_API_KEY`，若沿用同名会被它覆盖而报鉴权失败。`LLM_ENABLED=true` 启用知识问答，`LLM_VISION_ENABLED=true` 启用 MinerU 提取插图的分析，两者共用地址与密钥；可用 `LLM_VISION_MODEL` 指定图片模型。`.env` 变更需要重启后端，数据库中已保存的系统配置优先于 `.env`。

图片使用官方 `user.content=[text, image_url]` 格式，将后端取得的图片以 Base64 data URL 提交，避免把本地 MinIO/SSH 隧道地址发给云端下载。BMP/TIFF 等格式在提交前转换为 PNG；原图继续存 MinIO。每张图片的分析附在正文的对应图片下，标注为 AI 生成，随后进入切片、bge-m3 向量化与 Milvus 检索。单张分析失败会使本次导入失败并显示原因，不会静默生成不完整知识；已上传原文件保留，可重试。取消任务后在下一检查点停止后续图片请求。已导入的历史文档不会自动补分析，需要重新导入。

默认关闭思考模式以保证回答速度（`LLM_THINKING_ENABLED=false`，对应官方 `thinking.type=disabled`、`reasoning_effort=none`）；启用后通过 `LLM_REASONING_EFFORT` 选择 `low/high/max`。回答保留 SSE、Token 用量和引用，`reasoning_content` 不输出到用户回答；没有正常结束或被输出上限截断的结果不会标为完成。图片分析默认每份文档最多 100 张（`LLM_VISION_MAX_IMAGES`），超限会明确报错。

回答阶段还会从命中的切片里提取相关原图，最多 `LLM_ANSWER_MAX_IMAGES`（默认 3）张、单张不超过 `LLM_ANSWER_IMAGE_MAX_BYTES`（默认 5 MB），随问题一起以 Base64 发送给视觉模型；只有在 `LLM_VISION_ENABLED=true` 时生效，设为 0 可完全关闭。图片附件仍按知识授权过滤，未授权单元里的图片不会被发送。回答结束后，这些图片会以 Markdown 形式追加到回答末尾（签名地址），便于对照原文。

问候语（`你好`、`谢谢`、`再见` 等）在检索前就会被识别，直接返回引导语，不查询知识库，也不生成知识缺口——因为 bge-m3 对短问候语的相似度可能和真实问题一样高，单靠分数阈值无法区分。

官方调用参考：https://api-docs.deepseek.com/zh-cn/ ，图片格式参考：https://api-docs.deepseek.com/zh-cn/guides/vision/ 。

开发时使用一个 Uvicorn 应用进程。多应用进程/多实例部署建议关闭自动 Worker，集中部署独立 Worker，避免重复加载本地向量模型。两种模式都保留数据库租约和领取代次校验。

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health
- 依赖检查：http://127.0.0.1:8000/ready （逐项返回 postgresql/redis/minio/milvus 状态，任一不可用返回 503）

### 7. 接通前端

```bash
cd D:\Knowledge_Base_Management_Platform\Front
npm install
```

新建 `Front/.env`：

```
VITE_DATA_MODE=api
VITE_API_BASE_URL=/api
```

```bash
npm run dev
```

Vite 已配置把 `/api` 代理到 `127.0.0.1:8000`。默认的 `demo` 模式走本地假数据，不会访问后端。

## 配置项

| 分组 | 关键项 | 说明 |
|---|---|---|
| 数据库 | `DATABASE_URL` | 走隧道时是 `127.0.0.1:15432` |
| 缓存 | `REDIS_URL` | FAQ 缓存、限流；带密码 |
| 向量 | `MILVUS_URI`、`MILVUS_COLLECTION` | 集合名带模型版本，换模型要换集合 |
| 嵌入 | `EMBEDDING_MODEL_PATH`、`EMBEDDING_DIMENSION`、`EMBEDDING_DEVICE` | 本地 bge-m3，固定 1024 维；GPU 机器把 `EMBEDDING_DEVICE` 设为 `cuda` |
| 大模型 | `LLM_ENABLED`、`LLM_BASE_URL`、`KB_LLM_API_KEY`、`LLM_MODEL` | OpenAI 兼容接口；`LLM_ENABLED=false` 时问答明确失败，不做模拟生成 |
| MinerU | `MINERU_ENABLED`、`MINERU_BASE_URL`、`MINERU_API_KEY`、`MINERU_MODEL_VERSION`、`MINERU_ENABLE_OCR`、`MINERU_LANGUAGE`、`MINERU_POLL_SECONDS`、`MINERU_TIMEOUT_SECONDS` | v4 云端解析：申请上传地址 → PUT 文件 → 轮询批次 → 解压 `full.md`。未启用返回 503，额度用完返回 429 |

## 文档图片

MinerU 返回的压缩包里除 `full.md` 外还有抽取出的图片。导入时：

1. 图片按 `images/<unit_id>/<uuid>-<name>` 存入 MinIO 的 `kb-documents` 桶；
2. 每张图在 `attachments` 表里有一条记录，`unit_id` 指向所属知识单元，`mime_type` 为图片类型；
3. `full.md` 里的相对链接 `![](images/x.png)` 被改写成签名地址 `/api/knowledge/assets/<attachment_id>?sig=<hmac>`，正文与切片保存的都是改写后的地址；
4. 切片阶段会跳过“只有图片链接、没有文字”的片段，避免向量噪声；图片仍随正文正常渲染。

访问控制：`sig` 是用 `ENCRYPTION_KEY`（为空时回退 `JWT_SECRET`）对附件 ID 计算的 HMAC。`<img>` 无法携带 Authorization 头，所以这里用签名能力地址而不是登录态。**轮换这两个密钥会使历史图片地址全部失效。**

限制：bge-m3 是纯文本向量模型，图片只能通过周围的文字、图注被检索到，不能按图片内容做相似检索；按图搜图需要另外接入 CLIP 一类的多模态向量模型。

## 验证

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check app tests
```

测试用内存适配器隔离 PostgreSQL/Milvus/Redis/MinIO 与大模型，覆盖：默认拒绝、撤权立即生效、批量操作回滚、部门环、上传路径穿越、旧索引版本、后台任务重试与取消、SSE 中断不记成功、FAQ 缓存撤权。

## 常见问题

| 现象 | 处理 |
|---|---|
| `503 数据库不可用` | 隧道是否断开、`.env` 凭据是否正确、迁移是否执行 |
| `/ready` 中某项为 false | 看对应服务的隧道端口与服务器容器状态 |
| PDF 上传返回 503 | MinerU 未启用、Token 无效或已过期；查导入任务里的具体报错 |
| PDF 上传返回 429 | MinerU 当日解析额度已用完，次日恢复或调整 `MINERU_MODEL_VERSION` |
| 导入后检索不到 | 检查后端自动 Worker 日志、索引任务状态及知识单元授权 |
| 导入任务一直「处理中」，约 2 分钟后自动失败 | 检查后端自动 Worker 启动日志、SSH 隧道和 `WORKER_AUTO_START`；恢复后重新提交或调用任务重试接口 |
| Worker 正在处理别的文件，新任务在排队 | 正常现象，任务不会被判超时（以 Worker 心跳判断） |
| 前端仍是假数据 | 没有 `Front/.env` 或 `VITE_DATA_MODE` 不是 `api` |

## 服务器侧说明

基础设施部署、卷路径、备份位置和 Docker 旧代理问题见服务器上的 `/opt/README-infrastructure.md`。当前虚拟机 4 GB 内存，低于 Milvus 官方建议的 8 GB，正式使用前需要扩容。
