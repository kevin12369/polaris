# API Reference

Every HTTP endpoint in Polaris. Interactive docs (Swagger UI) ship with the service:

```
http://<host>:8000/docs
```

- [中文](API.md)

---

## Conventions

**Base URL**: `http://<host>:8000/api`

**Authentication**: every endpoint except `/health`, `/auth/register` and `/auth/login`
requires a bearer token.

```bash
curl -H "Authorization: Bearer <token>" http://<host>:8000/api/tickets
```

**Getting a token**:

```bash
curl -X POST http://<host>:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@company.com","password":"your-password"}'
```

Use the `access_token` from the response. Default lifetime is 72 hours
(controlled by `TOKEN_TTL_HOURS`).

**Tenant isolation**: all data is scoped by `company_id`. Accessing another workspace's
resource with your token returns `404` (not `403`, so resource existence is not leaked).

**Error responses**:

```json
{ "detail": "工单不存在" }
```

| Status | Meaning |
|---|---|
| `400` | Invalid input (e.g. an illegal status transition) |
| `401` | Not authenticated or invalid token |
| `403` | Insufficient permission (e.g. a non-admin changing working hours) |
| `404` | Resource does not exist, or belongs to another tenant |
| `409` | Conflict (e.g. email already registered) |

---

## Health check

### `GET /health`

No authentication required.

```bash
curl http://<host>:8000/api/health
```

```json
{
  "status": "ok",
  "app": "Polaris 北极星 · 客服工单管理平台",
  "version": "1.1.0",
  "llm_enabled": false,
  "llm_model": null
}
```

---

## Authentication

### `POST /auth/register`

Self-signup. Creates an isolated company workspace.

```json
{
  "company_name": "Acme Inc.",     // required, unique
  "name": "Alex Chen",              // required
  "email": "you@company.com",      // required, unique
  "password": "at least 6 chars",  // required
  "industry": "Enterprise software" // optional
}
```

**Response `201`**:

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": 1, "name": "Alex Chen", "email": "you@company.com", "role": "admin" },
  "company": { "id": 1, "name": "Acme Inc.", "plan": "trial", "seats": 10 }
}
```

**Error `409`**: email already registered, or the company name is taken.

### `POST /auth/login`

```json
{ "email": "you@company.com", "password": "your-password" }
```

Same response shape as register. **Error `401`**: bad credentials.

### `GET /auth/me`

Returns the current user and their company.

### `GET /auth/members`

Lists workspace members (admin only).

### `POST /auth/members`

Adds an agent (admin only).

```json
{
  "name": "Sam",
  "email": "sam@company.com",
  "password": "initial-password",
  "role": "agent"        // optional, defaults to agent
}
```

Roles: `admin` (can add members) / `agent`.

### `GET /auth/overview`

Trial status: seats used, quota, expiry.

---

## Working hours

SLA countdowns run on working hours, Monday to Friday 09:00–18:00 by default.

### `GET /settings/work-schedule`

```json
{
  "work_days": [0, 1, 2, 3, 4],
  "work_start_hour": 9,
  "work_end_hour": 18,
  "is_default": true,
  "day_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
  "builtin_holidays": ["2026-01-01", "2026-01-02", "..."],
  "builtin_extra_workdays": ["2026-01-04", "2026-02-14", "..."],
  "builtin_years": [2026],
  "custom_holidays": [],
  "custom_extra_workdays": []
}
```

`work_days` uses `0-6` for Monday to Sunday.

`builtin_holidays` / `builtin_extra_workdays` are read-only statutory holidays from the
State Council notice. `custom_*` are yours to edit.

### `PUT /settings/work-schedule`

Admin only. Changes affect **newly created tickets only**; existing SLA deadlines stay put.

```json
{
  "work_days": [0, 1, 2, 3, 4, 5],
  "work_start_hour": 9,
  "work_end_hour": 18,
  "holidays": ["2026-11-20"],
  "extra_workdays": ["2026-11-21"]
}
```

**Error `400`**: empty work-day list, out-of-range day, end hour not after start hour,
or a malformed date (`YYYY-MM-DD` required).
**Error `403`**: not an administrator.

---

## Tickets

### `POST /tickets`

Submit a ticket. **Leave category and priority empty to have them inferred** by the local
rule engine.

```json
{
  "title": "All users see \"Invalid username or password\"",  // required
  "content": "Started this morning, nothing changed on our side", // optional
  "requester_name": "John",                                    // optional
  "requester_email": "john@customer.com",                      // optional
  "channel": "email",                                           // optional
  "priority": "P2",                                             // optional, skips inference
  "category": "账号登录"                                         // optional
}
```

**Response `201`**:

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

> SLA deadlines are **fixed at creation time** based on priority. A later `PATCH` that
> changes priority does not rewrite history.

### `GET /tickets`

Query parameters:

| Parameter | Description |
|---|---|
| `status` | Filter by status |
| `priority` | Filter by priority |
| `category` | Filter by category |
| `q` | Keyword (title / description / ticket code) |
| `assignee` | Assignee user id |
| `limit` | Page size, default 50 |
| `offset` | Offset, default 0 |

```bash
curl -H "Authorization: Bearer $T" \
  "http://<host>:8000/api/tickets?status=in_progress&priority=P1&limit=20"
```

Response: `{ "total": 42, "items": [ /* tickets */ ] }`

### `GET /tickets/meta`

Category, priority and status dictionaries.

### `GET /tickets/{ticket_id}`

Ticket detail plus the full event timeline.

```json
{
  "ticket": { /* ticket */ },
  "events": [
    { "id": 1, "type": "created", "actor": "Alex", "note": "..." },
    { "id": 2, "type": "status", "actor": "System", "note": "AI 自动分类为「账号登录」" }
  ]
}
```

### `PATCH /tickets/{ticket_id}`

Override category, priority, assignee or tags.

```json
{
  "priority": "P2",
  "category": "账号登录",
  "assignee_id": 2,
  "tags": ["vip", "已联系"]
}
```

Every change is written to the timeline as a manual edit.

### `POST /tickets/{ticket_id}/status`

Status transition. **Invalid transitions return `400`.**

```json
{ "to_status": "in_progress", "note": "Investigating" }
```

Allowed transitions:

```
new          → triaged | in_progress | pending | resolved | closed
triaged      → in_progress | pending | resolved | closed
in_progress  → pending | resolved | closed
pending      → in_progress | resolved | closed
resolved     → closed | in_progress
closed       → in_progress
```

Add `resolution_note` when transitioning to `resolved` — it becomes the raw material for
knowledge capture.

### `POST /tickets/{ticket_id}/comment`

```json
{ "note": "Contacted the customer, waiting for logs" }
```

### `POST /tickets/{ticket_id}/suggest`

Search the knowledge base using the ticket's own content.

```json
{ "content": "optional; defaults to the ticket content" }
```

### `POST /tickets/{ticket_id}/promote-to-kb`

Promote a ticket into a knowledge article.

```json
{
  "title": "Auth service pool exhaustion caused total login failure",
  "summary": "optional; generated if omitted",
  "content": "optional; taken from the ticket timeline if omitted",
  "category": "optional",
  "steps": [ { "title": "Check the pool config", "detail": "..." } ]
}
```

**Response `201`**: the new article, plus the ticket's `kb_hit` set to `true` and
`linked_kb_ids` extended.

---

## Knowledge base

### `GET /kb`

Parameters: `q` (full-text search), `category`, `source` (`manual` / `ticket`), `limit`, `offset`.

```bash
curl -H "Authorization: Bearer $T" "http://<host>:8000/api/kb?q=502&limit=10"
```

Response: `{ "total": 8, "items": [...] }`

### `POST /kb`

```json
{
  "title": "Diagnosing 502 gateway errors",  // required
  "content": "Root cause, symptoms, resolution",
  "summary": "optional",
  "category": "接口API",
  "tags": ["502", "gateway"],
  "steps": [ { "title": "Step one", "detail": "..." } ]
}
```

### `GET /kb/categories`

Categories in use, with counts.

### `GET /kb/{article_id}` · `PUT /kb/{article_id}` · `DELETE /kb/{article_id}`

Read, edit, delete. `PUT` takes the same fields as `POST`, all optional.

### `POST /kb/{article_id}/helpful`

Mark an article helpful; returns the running total.

---

## AI troubleshooting assistant

### `POST /assistant/troubleshoot`

```json
{ "error_text": "502 Bad Gateway Error: request to /api/v2/orders timed out after 5000ms" }
```

**Response**:

```json
{
  "hit": true,
  "engine": "kb",
  "confidence": 0.88,
  "summary": "The gateway gets the request but no usable response...",
  "steps": [
    { "title": "Check upstream health directly", "detail": "..." }
  ],
  "articles": [
    { "id": 2, "title": "API calls return 502 Bad Gateway", "score": 8.6 }
  ]
}
```

Three engine states:

| Engine | Trigger | Behaviour |
|---|---|---|
| `llm+kb` | An LLM endpoint is configured | Steps generated from the retrieved content |
| `kb` | No LLM, but the KB matched | Reuses the article's own steps |
| `fallback` | No KB match | Standard checklist for the issue category |

**Matching rules**: BM25 score + query-token coverage + exact phrase match (error codes and
English identifiers), plus a Chinese-English term alias table so English error messages match
Chinese articles.

### `GET /assistant/status`

Engine status and whether an LLM is enabled.

### `GET /assistant/history`

Recent queries. Parameter: `limit`.

---

## Dashboard

### `GET /dashboard`

Parameter: `days` (default 30).

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
  "recent": [ /* recent tickets */ ],
  "top_kb": [ { "id": 1, "title": "...", "hits": 5 } ]
}
```

All durations are measured in **working minutes**.

---

## Integration example: creating tickets from an external system

The most common integration — email, chat, monitoring alerts all funnel through here.

```bash
#!/usr/bin/env bash
curl -X POST http://<host>:8000/api/tickets \
  -H "Authorization: Bearer $POLARIS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "[Alert] 5xx rate on order service above 5%",
    "content": "5xx ratio 5.3% over the last 10 minutes; instance order-api-7 looks suspect.",
    "requester_name": "Monitoring",
    "channel": "email"
  }'
```

```python
import httpx

client = httpx.Client(
    base_url="http://<host>:8000/api",
    headers={"Authorization": f"Bearer {TOKEN}"},
    timeout=10,
)

resp = client.post("/tickets", json={
    "title": "Customer reports export is broken",
    "content": "Customer says the exported CSV is empty",
    "requester_email": "customer@example.com",
})
ticket = resp.json()["ticket"]
print(f"Created {ticket['code']} with priority {ticket['priority']}")
```

---

## Rate limiting

Not implemented in this version. If you deploy on a public network, configure it in your
reverse proxy:

```nginx
limit_req_zone $binary_remote_addr zone=polaris:10m rate=30r/m;

location /api/ {
    limit_req zone=polaris burst=10 nodelay;
    proxy_pass http://127.0.0.1:8000;
    # ... the usual proxy_set_header directives
}
```
