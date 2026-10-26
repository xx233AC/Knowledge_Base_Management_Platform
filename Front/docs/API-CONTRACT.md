# 前后端接口契约 v1

本文描述当前前端的实际请求，供后续在 PyCharm 中实现 FastAPI。**本次只开发前端**，下列后端端点尚未实现或联调。权威前端类型为 `src/types/domain.ts`，请求映射为 `src/services/api.ts`；此处明确原需求未指定的返回结构和补充端点。

## 通用约定

- Base URL 默认 `/api`；除登录外使用 `Authorization: Bearer <access_token>`。
- IDs 是字符串，时间使用带时区的 ISO 8601；前端转换为本地显示。
- 领域 JSON 使用 camelCase，与 `domain.ts` 一致。为兼容原需求，登录响应和流式请求的指定字段保留 snake_case。FastAPI 可使用 Pydantic alias 做映射，数据库字段不用随之改变。
- 列表：`GET ?page=1&page_size=100` → `{ "items": [...], "total": 12 }`。当前小团队版适配器分批最多加载 10000 条，页面本地筛选/分页；更大规模应扩展服务端查询参数。
- 部门 API 列表返回扁平 `Department[]`（`parentId` 保留层级），前端构建树，不能直接返回嵌套树替代此契约。
- 错误状态 400/401/403/404/409/422/500，响应 `{ "detail": "可读说明" }`。401 清理登录并返回登录页；403 不应清除整个登录会话。
- 删除 `DELETE <collection>`，body `{ "ids": ["..."] }`，成功 204。保存返回更新后的领域对象。
- 生产中鉴权与数据过滤全部在后端完成。前端隐藏菜单/按钮只改善操作体验，不构成安全防线。身份从 Token 取得，不能信任客户端指定用户身份。

## 认证

| 请求 | 入参 | 返回 |
|---|---|---|
| POST `/auth/login` | `{username,password}` | 见下例 |
| GET `/auth/me`（补充） | — | `Identity`，含 user / roles / permissions / department |
| POST `/auth/logout`（补充） | — | 204；撤销当前令牌 |

```json
{
  "access_token": "server-issued-token",
  "expires_in": 3600,
  "user_info": {"id":"u1","username":"admin","displayName":"林序","departmentId":"d1","roleIds":["r_sys"],"status":"active","createdAt":"2026-10-21T09:00:00+08:00"},
  "roles": [{"id":"r_sys","name":"系统管理员","code":"system_admin","description":"系统管理","permissions":["dashboard.view"]}],
  "permissions": ["dashboard.view"]
}
```

角色权限和账号状态变更应即时影响后续请求。前端切回窗口时刷新 `/auth/me`；后端每次请求均须复核，不能仅依赖登录时的快照。当前未约定 refresh token，过期后重新登录。

## 组织

| 请求 | 用途与入参 |
|---|---|
| GET/POST `/org/users` | 列表/新增 `Partial<User> & {password}`；初始密码最少 8 位 |
| PUT `/org/users/{id}` | 更新姓名、部门、roleIds、active/disabled；用户名唯一 |
| POST `/org/users/{id}/reset-password`（补充） | `{password}` → 204 |
| GET/POST `/org/roles` | 列表/新增 Role；新增时 permissions 必须原子保存 |
| PUT `/org/roles/{id}`（补充） | 更新 name/code/description |
| POST `/org/roles/{id}/permissions` | `{permissions: Permission[]}` → 完整 Role |
| DELETE `/org/roles`（补充） | 已分配用户或被知识授权引用的角色返回 409 |
| GET/POST `/org/departments` | 扁平列表/新增 Department |
| PUT `/org/departments/{id}`（补充） | 名称、parentId、leaderId、sort |
| DELETE `/org/departments`（补充） | 有成员、下级或知识授权的部门返回 409 |

编辑角色先保存资料，再提交独立权限端点；权限保存失败会明确显示，已有角色可重试。后端应确保操作权限集合整体替换而非增量残留。至少保留一位启用且可管理用户及角色的管理员。部门禁止环，负责人应为本部门启用成员；成员调离或停用时，同一事务清理失效负责人关联。

只读目录访问例外：`knowledge.permissions` 可读取最小用户/角色/部门目录用于授权选择；`org.users.manage` 可读角色与部门目录用于分配；`org.departments.manage` 可读用户的姓名、用户名、部门、状态用于成员与负责人管理。均不隐含对应组织写权限或敏感字段访问。纯知识授权目录只需启用用户；部门成员目录须包含停用用户，成员数不能漏计。

## 知识单元与授权

| 请求 | 入参 / 返回 |
|---|---|
| GET `/knowledge/units` | 分页列表 `Unit[]` |
| POST `/knowledge/units`（补充） | 新建知识；默认 acl=[]；返回 Unit |
| GET `/knowledge/units/{id}` | 已授权详情，否则 403 |
| PUT `/knowledge/units/{id}` | 更新知识/标签/附件关联/状态，可含 acl（需独立授权配置权限）；应在事务中保存 |
| POST `/knowledge/units/{id}/permissions` | `{permissions: Grant[]}`，整体替换；返回 Unit 或脱敏 Unit，避免撤销自身权限后额外 GET 导致误报失败 |
| DELETE `/knowledge/units` | `{ids}`，批量删除须先验证整批权限；关联 FAQ 缓存失效，已解决缺口重新打开 |
| POST `/knowledge/check-permissions` | 后端 AI 服务可调用 `{unit_ids}`；从调用身份校验或可信内部身份取得用户。返回 `authorized_unit_ids` / `unauthorized_unit_ids`；当前页面不直接调用此内部检索步骤 |

`Grant`：`{type:'global'}` 或 `{type:'department'|'role'|'user',id:string}`。空数组默认拒绝，四维 OR；部门精确匹配，不隐含子部门继承。系统管理员无自动内容旁路。

无授权列表项的正文、摘要、附件、标签、版本、真实标题必须移除；可返回可配置的 opaque id/code 与 `restricted:true`，title 固定“未授权知识单元”，content/summary 空字符串。非知识管理员也不应收到不必要的受限 metadata。配置授权时需区分“允许管理授权元信息”与“允许读取内容”。

Unit 完整字段包含 id/code/title/content/summary/category/tags/fileType/attachments/status/creatorId/updatedAt/acl/versions。版本 `{version,date,editor,title,content}` 必须由后端生成，不能信任客户端伪造 creator 或版本历史。权限撤销后版本与附件也不可绕过。

附件类型当前为 `{name,size,path?}`，path 只是上传相对路径，不能当作存储路径或下载地址。前端可移除附件关联，暂不提供原始附件下载。后端文件服务就绪后，再补专用鉴权下载端点和按钮，不通过猜测静态文件 URL 下载。

## 导入与处理任务

| 请求 | 入参 / 返回 |
|---|---|
| POST `/knowledge/import` | multipart `files` 文件字段（可重复）、`relative_paths` 对应相对路径 → `{jobs:Job[]}` |
| GET `/knowledge/import/jobs`（补充） | 当前有权管理的任务分页列表 |
| GET `/knowledge/import/jobs/{id}`（补充） | Job，供前端每 800ms 轮询 |
| POST `/knowledge/import/jobs/{id}/cancel`（补充） | 取消未结束任务，204 |

前端当前每请求提交一个文件、有限并发（默认 3，配置 1–6）；端点仍可接受多个文件。默认最多 30 个文件，单文件 50MB，支持 pdf/md/markdown/doc/docx/txt；服务端必须独立验证内容类型、大小、文件名、目录路径、数量和权限。

```json
{"id":"j1","name":"手册.pdf","path":"制度/手册.pdf","size":12345,"phase":2,"status":"running","startedAt":"2026-10-21T10:00:00+08:00"}
```

phase 从 0 到 5：0 上传完成等待解析，1 解析中，2 结构切分中，3 向量化中，4 收尾中，5 完成。status 为 running/completed/failed/canceled。完成带 unitId；失败带 error。后台独立处理，刷新后通过任务列表恢复。单文档是一份 Unit，内部片段继承其 ACL。

取消浏览器上传只停止传输，若服务已收件应依靠任务取消/任务列表核实；生产可扩展幂等请求键，避免超时后重复入库。进度请求失败不等于后台任务失败，前端提示可重新获取。已完成的演示导入默认无授权，要在列表授权后查看。

## AI 会话与 SSE

| 请求 | 入参 / 返回 |
|---|---|
| GET `/ai/sessions`（补充） | 当前用户会话分页列表；含过滤后的 messages |
| DELETE `/ai/sessions`（补充） | `{ids}` 仅删除本人会话 |
| POST `/ai/chat/stream` | `{question,session_id?}` → `text/event-stream` |

消息必须只返回当前仍可读的内容。历史回答的引用来源被撤权、删除或下线后，应脱敏整条依赖回答；不能仅隐藏引用卡片而保留正文。会话按当前 Token 用户隔离，不能由传入 user_id 越权。当前原型与正式前端的 demo 数据互相隔离。

SSE 每条事件以空行终止；data 是 JSON。支持以下事件：

```text
event: session
data: {"sessionId":"s1"}

event: citations
data: {"citations":[{"unitId":"k2","code":"KB-002","title":"差旅报销操作指南","location":"第二章 / 第4页"}]}

event: delta
data: {"text":"需要提交"}

event: denied
data: {"message":"部分相关资料未获授权"}

event: cache
data: {"hit":true}

event: done
data: {"tokens":620,"ms":2400}

event: error
data: {"message":"回答暂不可用，请重试"}
```

一次成功响应必须有 done；error 终止失败；不允许将截断连接作为成功。多行 data 和跨 UTF-8/CRLF 网络分片可解析。前端使用 fetch POST + AbortController；停止应通知后台取消生成，历史记录标记 interrupted。服务不应将拒绝知识的标题、摘要或正文放进任何事件。仅使用已发布且授权的知识；FAQ 缓存必须再次验证其关联知识状态和数据权限。

模型密钥、MinerU 密钥、向量数据库凭证不进入前端。真实回答、Token 与耗时由后端记录，前端 demo 的估算值不用于生产计费。

## 数据看板

下列端点共享参数 `?period=7d|30d|all`，返回同一时间范围的数据；知识总量为当前总量，其他指标按时间过滤。

| 请求 | 返回 |
|---|---|
| GET `/dashboard/metrics` | `{visits,uv,unitCount,tokens,avgMs}` |
| GET `/dashboard/rankings/questions` | `[[question,count],...]`，最多5项 |
| GET `/dashboard/rankings/units` | `[{id,title,count},...]`，最多5项，标题需脱敏 |
| GET `/dashboard/stats/tokens` | `[{date:'2026-10-21',visits:6,tokens:3700},...]` |
| GET `/dashboard/stats/latency`（补充） | `[{label:'< 1 秒',min:0,max:1000,count:2},...]`；无穷上限可为 null |

看板指标、问题榜、知识榜、趋势、耗时分布应来自同一日志源。没有访问时显示 0；日/周聚合前端对同一趋势序列求和。`/dashboard/logs` 是 Service 列表资源预留，当前看板页面不调用它；若后续使用需添加分页和独立权限审计。

## FAQ 与知识缺口

| 请求 | 入参 / 返回 |
|---|---|
| GET `/settlement/faqs`（补充） | 包含 pending_review/published/rejected 的分页 FAQ；前端两页按状态筛选 |
| GET `/settlement/faqs/recommendations` | 原需求的推荐专用入口，可作为上面统一列表的服务端别名或扩展，当前适配器使用统一入口 |
| POST `/settlement/faqs/{id}/review` | `{action:'approve'|'reject',edited_answer}` → 204 |
| PUT `/settlement/faqs/{id}`（补充） | 修改 question/answer/category/status；下线变 pending_review，缓存失效 |
| DELETE `/settlement/faqs`（补充） | `{ids}`，缓存同步失效 |
| GET `/settlement/knowledge-gaps` | 分页 Gap |
| PUT `/settlement/knowledge-gaps/{id}`（补充） | `{status:'ignored'|'unresolved'}` → Gap |

FAQ：`{id,question,answer,unitId,frequency,status,cache,category,hits,reviewerId?,reviewedAt?}`。审核时校验关联知识可访问且已发布，更新状态、审核人和时间，再更新 Redis 缓存。无权限的 FAQ 脱敏问题和答案。FAQ 频次按日志聚合；不在前端自动挖掘真实数据。

Gap：`{id,question,samples,count,lastAskedAt,status,unitId?}`。建档：POST `/knowledge/units` 可带 gapId，知识保存成功后在同一事务关联缺口并标记 resolved；取消页面或保存失败不应提前解决。纯粹的权限拒绝不产生知识缺口。删除关联知识时重新打开缺口。

## 后续联调顺序

认证与 `/auth/me` → 组织与权限 → 知识 CRUD/四维 ACL → 上传/后台任务/MinerU → SSE/会话/引用 → 看板统计 → FAQ 缓存/缺口挖掘。此顺序仅是后端阶段的对接建议，本次未执行后端开发。
