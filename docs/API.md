# API 参考

Polaris 的全部 HTTP 接口。交互式文档（Swagger UI）随服务启动：

```
http://<host>:8000/docs
```

- [English](API.en.md)

---

## 通用约定

**Base URL**：`http://<host>:8000/api`

**认证**：除 `/health`、`/auth/register`、`/auth/login` 外，所有接口都需要 Bearer Token。

```bash
curl -H "Authorization: Bearer <token>" http://<host>:8000/api/tickets
```

**Token 获取**：

```bash
curl -X POST http://<host>:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@company.com","password":"your-password"}'
```

响应中的 `access_token` 即为后续请求所需的令牌。默认有效期 72 小时（由 `TOKEN_TTL_HOURS` 控制）。

**租户隔离**：所有数据按 `company_id` 隔离。携带 A 公司令牌访问 B 公司的资源返回 `404`（不是 `403`，避免泄露资源存在性）。

**错误响应**：

```json
{ "detail": "工单不存在" }
```

| 状态码 | 含义 |
|---|---|
| `400` | 参数不合法（如非法状态流转） |
| `401` | 未认证或令牌无效 |
| `403` | 权限不足（如非管理员修改工作时间表） |
| `404` | 资源不存在，或不属于当前租户 |
| `409` | 冲突（如邮箱已注册） |

---

## 健康检查

### `GET /health`

无需认证。

```bash
curl http://<host>:8000/api/health
```

```json
{
  "status": "ok",
  "app": "Polaris 北极星 · 客服工单管理平台",
  "version": "1.0.0",
  "llm_enabled": false,
  "llm_model": null
}
```

---

## 认证

### `POST /auth/register`

自助注册，同时创建一个独立的企业空间。

```json
{
  "company_name": "Acme 科技",     // 必填，唯一
  "name": "张三",                 // 必填
  "email": "you@company.com",     // 必填，唯一
  "password": "至少 6 位",         // 必填
  "industry": "企业软件"           // 可选
}
```

**响应 `201`**：

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": 1, "name": "张三", "email": "you@company.com", "role": "admin" },
  "company": { "id": 1, "name": "Acme 科技", "plan": "trial", "seats": 10 }
}
```

**错误 `409`**：邮箱已注册，或企业名已被占用。

### `POST /auth/login`

```json
{ "email": "you@company.com", "password": "your-password" }
```

响应同注册。**错误 `401`**：凭据错误。

### `GET /auth/me`

返回当前用户与所属企业。

### `GET /auth/members`

列出本企业的成员（仅管理员）。

### `POST /auth/members`

添加坐席（仅管理员）。

```json
{
  "name": "李四",
  "email": "lisi@company.com",
  "password": "初始密码",
  "role": "agent"        // 可选，默认 agent
}
```

角色：`admin`（可添加成员）/ `agent`（坐席）。

### `GET /auth/overview`

试用状态概览（已用席位数、额度、到期时间）。

---

## 工作时间表

SLA 倒计时按工作时间计算，默认周一至周五 09:00–18:00。

### `GET /settings/work-schedule`

```json
{
  "work_days": [0, 1, 2, 3, 4],
  "work_start_hour": 9,
  "work_end_hour": 18,
  "is_default": true,
  "day_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
}
```

`work_days` 用 `0-6` 表示周一到周日。

### `PUT /settings/work-schedule`

仅管理员。修改后**只影响之后创建的工单**，已有工单的 SLA 截止时间不变。

```json
{
  "work_days": [0, 1, 2, 3, 4, 5],
  "work_start_hour": 9,
  "work_end_hour": 18
}
```

**错误 `400`**：工作日为空、取值越界、下班时间早于上班时间。
**错误 `403`**：非管理员。

---

## 工单

### `POST /tickets`

提交工单。**分类与优先级留空时由本地规则引擎自动判定**。

```json
{
  "title": "所有用户登录时提示「账号或密码错误」",   // 必填
  "content": "今天早上开始全部客户提示...",          // 可选
  "requester_name": "王五",                         // 可选
  "requester_email": "wangwu@customer.com",         // 可选
  "channel": "email",                               // 可选
  "priority": "P2",                                 // 可选，指定则跳过自动判定
  "category": "账号登录"                             // 可选
}
```

**响应 `201`**：

```json
{
  "ticket": {
    "id": 1,
    "code": "TK-0001",
    "title": "...",
    "category": "账号登录",
    "category_source": "auto",
    "priority": "P1",
    "confidence": 0.92,
    "status": "new",
    "sla_response_due": "2026-11-02T17:00:00",
    "sla_resolve_due": "2026-11-03T14:00:00",
    "kb_hit": false,
    "linked_kb_ids": []
  },
  "classification": {
    "category": "账号登录",
    "priority": "P1",
    "confidence": 0.92,
    "reason": "关键词命中：账号/密码/无法登录"
  },
  "suggestions": []
}
```

> SLA 截止时间在创建时按优先级**固化**。后续 `PATCH` 改优先级不会重算历史口径。

### `GET /tickets`

查询参数：

| 参数 | 说明 |
|---|---|
| `status` | 按状态过滤 |
| `priority` | 按优先级过滤 |
| `category` | 按分类过滤 |
| `q` | 关键词（标题 / 描述 / 工单号） |
| `assignee` | 按受理人 ID |
| `limit` | 每页条数，默认 50 |
| `offset` | 偏移量，默认 0 |

```bash
curl -H "Authorization: Bearer $T" \
  "http://<host>:8000/api/tickets?status=in_progress&priority=P1&limit=20"
```

响应：

```json
{ "total": 42, "items": [ /* 工单数组 */ ] }
```

### `GET /tickets/meta`

返回分类、优先级、状态字典。前端据此渲染筛选器。

### `GET /tickets/{ticket_id}`

工单详情 + 完整事件流。

```json
{
  "ticket": { /* 工单对象 */ },
  "events": [
    { "id": 1, "type": "created", "actor": "张三", "note": "..." },
    { "id": 2, "type": "status", "actor": "系统", "note": "AI 自动分类为「账号登录」" }
  ]
}
```

### `PATCH /tickets/{ticket_id}`

人工覆盖分类、优先级、受理人、标签。

```json
{
  "priority": "P2",
  "category": "账号登录",
  "assignee_id": 2,
  "tags": ["vip", "已联系"]
}
```

每次修改都会写入事件流，标注为「人工修改：xxx」。

### `POST /tickets/{ticket_id}/status`

状态流转。**非法流转返回 `400`**。

```json
{ "to_status": "in_progress", "note": "开始排查" }
```

允许的流转（状态机）：

```
new          → triaged | in_progress | pending | resolved | closed
triaged      → in_progress | pending | resolved | closed
in_progress  → pending | resolved | closed
pending      → in_progress | resolved | closed
resolved     → closed | in_progress
closed       → in_progress
```

流转到 `resolved` 时可附带 `resolution_note`，它会成为知识沉淀的素材。

### `POST /tickets/{ticket_id}/comment`

添加备注。

```json
{ "note": "已联系客户，等对方提供日志" }
```

### `POST /tickets/{ticket_id}/suggest`

针对工单内容检索知识库，返回可能相关的条目。

```json
{ "content": "可选，不传则用工单自身内容" }
```

### `POST /tickets/{ticket_id}/promote-to-kb`

把工单沉淀为知识库条目。

```json
{
  "title": "认证服务连接池耗尽导致全量登录失败",
  "summary": "可选，不传则自动生成",
  "content": "可选，不传则取工单处理记录",
  "category": "可选",
  "steps": [ { "title": "检查连接池配置", "detail": "..." } ]
}
```

**响应 `201`**：返回新建的条目，同时工单的 `kb_hit` 置为 `true`、`linked_kb_ids` 追加该条目。

---

## 知识库

### `GET /kb`

查询参数：`q`（全文检索）、`category`、`source`（`manual` / `ticket`）、`limit`、`offset`。

```bash
curl -H "Authorization: Bearer $T" \
  "http://<host>:8000/api/kb?q=502&limit=10"
```

响应：`{ "total": 8, "items": [...] }`

### `POST /kb`

```json
{
  "title": "502 网关错误的排查路径",   // 必填
  "content": "根因、现象、处理方法",
  "summary": "可选",
  "category": "接口API",
  "tags": ["502", "网关"],
  "steps": [ { "title": "第一步", "detail": "..." } ]
}
```

### `GET /kb/categories`

返回已有条目的分类列表及计数。

### `GET /kb/{article_id}` · `PUT /kb/{article_id}` · `DELETE /kb/{article_id}`

条目的读取、编辑、删除。`PUT` 字段同 `POST`，全部可选（只传要改的字段）。

### `POST /kb/{article_id}/helpful`

标记条目「有用」，返回累计次数。

---

## AI 排障助手

### `POST /assistant/troubleshoot`

输入报错，返回可执行的排查步骤。

```json
{ "error_text": "502 Bad Gateway Error: request to /api/v2/orders timed out after 5000ms" }
```

**响应**：

```json
{
  "hit": true,
  "engine": "kb",
  "confidence": 0.88,
  "summary": "网关能收到请求但拿不到上游响应，优先怀疑节点假死或连接池耗尽。",
  "steps": [
    { "title": "确认上游服务健康状态", "detail": "直接请求上游服务的健康检查接口…" }
  ],
  "articles": [
    { "id": 2, "title": "接口调用返回 502 Bad Gateway", "score": 8.6 }
  ]
}
```

`engine` 三种取值：

| 值 | 含义 |
|---|---|
| `llm+kb` | 配置了大模型，基于检索内容生成步骤 |
| `kb` | 未配大模型但命中知识库，复用条目自带步骤 |
| `fallback` | 未命中，按问题分类给通用排查清单 |

**命中规则**：BM25 分数 + 查询词覆盖率 + 精确短语（错误码/英文标识符）三重判据，
外加中英术语别名表（英文报错可匹配中文知识库）。

### `GET /assistant/status`

返回引擎状态与是否启用 LLM。

### `GET /assistant/history`

最近查询记录。参数：`limit`。

---

## 仪表盘

### `GET /dashboard`

参数：`days`（统计区间，默认 30 天）。

```json
{
  "metrics": {
    "total_tickets": 14,
    "open_tickets": 5,
    "resolved_tickets": 9,
    "avg_response_minutes": 46.4,
    "response_timeout_rate": 7.1,
    "response_timeout_count": 1,
    "resolve_timeout_count": 2,
    "kb_hit_rate": 80.0,
    "kb_linked_count": 4,
    "kb_articles": 8
  },
  "trend": [ { "date": "2026-11-02", "created": 2, "resolved": 1 } ],
  "by_category": [ { "category": "账号登录", "count": 3 } ],
  "by_status": [ { "status": "in_progress", "label": "处理中", "count": 3 } ],
  "recent": [ /* 最近工单 */ ],
  "top_kb": [ { "id": 1, "title": "...", "hits": 5 } ]
}
```

所有时长按**工作时间分钟**口径统计。

---

## 集成示例：外部系统自动建单

这是最常见的对接场景 —— 邮件、微信客服、监控告警都可以走这个入口。

```bash
#!/usr/bin/env bash
# 从邮件正文建单
curl -X POST http://<host>:8000/api/tickets \
  -H "Authorization: Bearer $POLARIS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "[告警] 订单服务 5xx 比例超过 5%",
    "content": "监控面板显示近 10 分钟 5xx 比例 5.3%，实例 order-api-7 疑似异常。",
    "requester_name": "监控告警",
    "channel": "email"
  }'
```

```python
# Python 侧批量建单
import httpx

client = httpx.Client(
    base_url="http://<host>:8000/api",
    headers={"Authorization": f"Bearer {TOKEN}"},
    timeout=10,
)

resp = client.post("/tickets", json={
    "title": "客户反馈导出功能异常",
    "content": "客户说导出的 CSV 是空的",
    "requester_email": "customer@example.com",
})
ticket = resp.json()["ticket"]
print(f"已建单 {ticket['code']}，优先级 {ticket['priority']}")
```

---

## 速率限制

当前版本**未实现速率限制**。若部署在公网，请在反向代理层（Nginx）自行配置：

```nginx
limit_req_zone $binary_remote_addr zone=polaris:10m rate=30r/m;

location /api/ {
    limit_req zone=polaris burst=10 nodelay;
    proxy_pass http://127.0.0.1:8000;
    # ... 其余 proxy_set_header 配置
}
```
