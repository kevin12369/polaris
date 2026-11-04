# 安全策略（Security Policy）

**最后更新：2026-11-04**

Polaris 是一个**装在客户自己服务器上**的工单系统，里面存着客户的真实报障内容、
联系方式和内部处理记录。我们把安全当作正经事做，但也要诚实地说清楚：
**这是一个单人维护的小项目，没有专职安全团队，也做不到企业级产品的防护强度。**

下面这份文档告诉你三件事：我们支持哪些版本、发现漏洞该怎么报告、以及——

**哪些地方我们自己知道还不够好。**

---

## 目录

- [支持的版本](#支持的版本)
- [报告安全漏洞](#报告安全漏洞)
- [报告时请提供什么](#报告时请提供什么)
- [响应时限](#响应时限)
- [已知的安全边界](#已知的安全边界)
- [生产环境配置建议](#生产环境配置建议)
- [安全相关的开发约定](#安全相关的开发约定)

---

## 支持的版本

| 版本 | 状态 | 说明 |
|---|---|---|
| **1.x** | ✅ 支持 | 当前发布线（最新为 v1.0.0），修复会发到 `main` 并打新的 patch 版本 |
| 0.x 及更早 | ❌ 不再支持 | 仅存在于历史提交中，请先升级 |

**当前发布线的部署方式是 `docker compose up -d --build`** —— 也就是说，
你的容器里跑的是 `main` 分支的代码。**这意味着修复一旦合入 `main`，重新 build 就自动生效，
不需要等你发版本。** 这是本项目的一个便利，也是下面几条注意事项的前提。

升级方式：

```bash
git pull
docker compose up -d --build
```

> 升级前请先备份数据库。方法见 [README 运维章节](README.md#六运维)：
> ```bash
> docker compose exec backend sh -c "cat /app/data/support.db" > backup-$(date +%F).db
> ```

---

## 报告安全漏洞

### ⚠️ 请不要开公开 Issue

**公开的 Issue 意味着所有人都能看到漏洞细节，包括攻击者。**
在你写下 Issue 的那一刻，漏洞就可能已经被利用了。

同样地，**请不要在 Discussions 里提**，也不要在公开 PR 里贴 PoC。

### 正确渠道：邮件

请发邮件到：**`security@kevin12369.dev`**

邮件主题建议写成：`[SECURITY] 简短的漏洞标题`

如果你的邮件发不出去，可以先开一个**不包含任何技术细节**的 Issue，
只留一句「想私下报告一个安全问题，请联系我」，我会通过 Issue 里的联系方式和你取得联系。

### 报告之后会发生什么

1. 我会确认收到（见 [响应时限](#响应时限)）。
2. 我会在**私下**和你一起复现、评估影响范围。
3. 确认是漏洞后，我会写修复并在 `main` 上发布。
4. **修复发布后**，我会请你在新版本上验证。
5. 是否公开披露、是否致谢、披露时间点——**都听你的**。我不会在你确认之前公开任何细节。

> **如果我觉得这不是漏洞**，我也会直接告诉你，并说明我的判断依据。
> 这不是拒绝，只是技术讨论。开源项目里误报很常见，不影响你继续贡献。

---

## 报告时请提供什么

信息越具体，我定位问题的速度越快。请尽量提供以下内容：

### 1. 漏洞类型和影响

- 你认为这是什么类型的问题？（越权访问 / 认证绕过 / SQL 注入 / XSS / 敏感信息泄露 / 权限提升 / 其他）
- **实际能造成什么后果？** 比如「普通坐席能读到别家企业的工单」比「这里有个问题」有用得多。
- 需要什么前置条件？（普通用户？需要特定租户？需要管理员配合？）

### 2. 复现步骤

按顺序写，每一步都要能被别人照着做出来：

```
1. 注册企业空间 A（demo@acme.com / demo1234）
2. 用管理员账号登录，添加一个坐席账号 agent@test.com
3. 用 agent@test.com 登录，获取其 access_token
4. 调用 GET /api/tickets?company_id=<B租户ID>
5. 观察到返回了 B 租户的工单数据
```

### 3. 证明材料（PoC）

- 请求和响应的完整内容（**token 请替换成无效的假值**，比如 `Bearer <REDACTED>`）
- 相关的脚本或 curl 命令
- 截图（如果有 UI 层面表现）

### 4. 环境信息

| 项目 | 说明 |
|---|---|
| Polaris 版本 | `git log -1 --format=%h`，或看 `/api/health` 返回的 `version` |
| 部署方式 | Docker Compose / 本地开发 |
| 运行环境 | 操作系统、Docker 版本、Python 版本、Node 版本 |
| 浏览器 | 如果涉及前端，注明浏览器和版本 |

### 5. 已经排查过的部分

你已经试过什么、结果如何。这能帮我少走弯路。

---

## 响应时限

**以下是我们的目标（target），不是有法律约束力的 SLA。**
单人维护的项目可能遇到休假、生病等不可控因素，我们承诺「尽力而为」，
但不想用 SLA 条款做出我们无法保证的承诺。

| 阶段 | 目标时限 | 说明 |
|---|---|---|
| **确认收到** | **48 小时内** | 确认邮件已收到，并告知是否复现成功 |
| **初步评估** | 7 天内 | 给出影响范围评估和修复计划 |
| **给出修复或缓解方案** | **7 天内** | 要么发布修复版本，要么给出临时缓解措施（如配置收敛、feature flag） |
| **发布修复** | 严重漏洞 14 天内 / 一般问题随下个版本 | 视问题复杂度和影响面而定 |

**影响范围严重的话，响应会更快。** 涉及数据泄露、认证绕过、远程代码执行这类问题会插队处理。

如果超过上述时限你还没收到回复，**再发一封邮件**就行——可能是邮件进了垃圾箱。

---

## 已知的安全边界

这一节是本文档最重要的部分。**我们把自己知道的问题写在这里，
好过让你自己挖出来。** 下面每一条都是当前版本的真实状态，不是假设。

### 1. 默认 `SECRET_KEY` 是弱密钥，必须修改

```python
# backend/app/config.py
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-in-production")
```

如果没设置环境变量，**所有部署实例共用同一个公开可见的默认密钥**。
后果：任何人都能伪造出任意用户的合法 JWT，直接以管理员身份登录。

```bash
# 生成一个随机密钥
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

然后写进 `.env` 的 `SECRET_KEY=`。**这是部署前必须做的第一件事。**

> 顺带一提：如果在你已经用弱密钥跑过的环境里改成了强密钥，
> 所有人手上的旧 token 会立即失效，需要重新登录。这是一次性的，可接受。

### 2. `CORS_ORIGINS` 默认是 `*`，生产环境必须收敛

```python
# backend/app/config.py
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
```

配合 `allow_credentials=True`，默认配置下**任意网站的脚本都能带着用户的 cookie/token
调用你的 API**（CSRF 类风险）。生产环境请显式指定：

```bash
# .env
CORS_ORIGINS=https://polaris.example.com
```

多个域名用逗号分隔。改成实际域名之后，即使有人做了恶意站点，也跨域读不到你的接口。

### 3. JWT 没有黑名单，登出只是前端清除

**这是一个已知的架构限制，请务必理解：**

- 后端**没有** `/api/auth/logout` 接口。JWT 是无状态令牌，签发之后服务端不记录，
  也就无法主动作废。
- 登出逻辑完全在前端：清除 `localStorage` 里的 `sw_token` / `sw_user` / `sw_company`
  就结束了（见 `frontend/src/api.js`）。
- **后果**：一个已经被复制出去的 token，在它过期之前（默认 `TOKEN_TTL_HOURS=72`，即 72 小时）
  依然有效，即使原用户已经点了「退出登录」。
- **缓解手段**：把 `TOKEN_TTL_HOURS` 调小（比如 `8`），缩短窗口期。
  需要立刻踢人下线的话，只能改密码或重启后端并轮换 `SECRET_KEY`。

### 4. SQLite 单文件，无加密

- 数据库就是一个磁盘上的文件（Docker 卷 `polaris-data` 里的 `support.db`），
  **没有加密**。拿到这个文件的人可以直接读到全部工单内容。
- 备份文件同理——`docker compose exec backend ... > backup.db` 产出的是明文文件。
- **必须做**：
  - 数据库文件和备份文件都用加密卷（LUKS、BitLocker 等）或加密归档；
  - 备份文件**不要**放在 Web 目录下，不要传到对象存储的公开路径；
  - 给备份文件设置最小权限（`chmod 600`）。

### 5. SQLite 不适合多实例部署

当前部署模型是**单实例**：一个后端容器 + 一个 SQLite 文件。

- **不要**把后端容器横向扩到 2 个及以上。SQLite 不支持多进程并发写，
  多个实例会写坏数据库或产生锁冲突。
- 需要多实例或更高并发时，请迁移到 PostgreSQL（代码改动不大，README「常见问题」里有说明）。
- 多实例方案落地前，「单实例」这条边界必须被明确接受。

### 6. 工单附件尚未实现；将来实现时必须处理恶意文件

- **当前状态**：**没有附件功能**。工单里的报错内容是用文字描述 + 报错文本承载的。
  所以目前不存在「上传恶意文件」这个攻击面。
- **将来如果实现上传**，以下必须处理（这是给未来贡献者的明确要求）：
  - **限制类型**：只允许明确的白名单（如 `.txt` / `.log` / `.png` / `.jpg` / `.pdf`），
    不要靠扩展名判断，要看文件实际内容（magic number）；
  - **限制大小**：设置单文件上限和总容量上限（部署指南里 Nginx 侧是 `client_max_body_size 20m`）；
  - **重新编码或改名存储**：文件名由服务端生成，不保留用户原始文件名；
  - **存储隔离**：文件不放在可静态访问的目录里，通过接口鉴权后下发，
    或者至少用随机名 + 禁止执行；
  - **禁止解析执行**：绝不因为用户上传了脚本/HTML 就在服务端去渲染或运行它；
  - **病毒扫描**：如果预期会有非可信用户上传，接到扫描流程里。

### 7. 其他

- **密码哈希**用的是 PBKDF2-HMAC-SHA256，120,000 轮随机盐 —— 这是安全的，
  不用改。密码最短 6 位（`backend/app/security.py`）。这属于强度偏弱的一端，
  但对内部工具够用；如果你需要更强，可以后续加入 bcrypt/argon2 支持。
- **没有速率限制**：登录接口、注册接口都没有防暴力破解的限流。
  如果你的部署暴露在公网，请在反向代理层（Nginx）加上 `limit_req`。
- **没有审计日志**：工单的「处理记录」记录了业务动作（谁在何时改了什么状态），
  但没有记录登录登出、权限变更这类管理操作。
- **接入大模型时数据会出网**：配置了 `LLM_BASE_URL` / `LLM_API_KEY` 之后，
  排障文本会发送到你指定的接口（可能是第三方）。**不配置则完全不出网。**
  如果你的工单含敏感信息，请确认这个取舍是可接受的。

---

## 生产环境配置建议

上线前请逐条对照 [部署指南的上线检查清单](docs/部署指南.md#上线检查清单)，
下面是把关键项展开的说明。

### 1. 换掉 SECRET_KEY

```bash
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

写进 `.env`：

```bash
SECRET_KEY=<粘贴上面生成的随机串>
```

### 2. 收敛 CORS_ORIGINS

```bash
CORS_ORIGINS=https://polaris.example.com
```

### 3. 只开放必要端口

- **后端容器端口不要暴露到公网。** `docker-compose.yml` 里后端用的是 `expose: "8000"`,
  只在内部网络可见——这是对的，保持原样。
- 对外只暴露 Web 端口（`WEB_PORT`，默认 `8080`）和 SSH。
- 防火墙示例（以 ufw 为例）：

  ```bash
  ufw allow 22/tcp
  ufw allow 8080/tcp
  ufw enable
  ```

### 4. 配置 HTTPS 反向代理

**不要在公网上用明文 HTTP 传输密码和 token。**

前端容器自带 Nginx 并已内置 `/api/` 反向代理规则。对外用 Nginx/Caddy 做一层 TLS 终止：

```nginx
server {
    listen 443 ssl http2;
    server_name polaris.example.com;

    ssl_certificate     /etc/letsencrypt/live/polaris.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/polaris.example.com/privkey.pem;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

完整示例见 [docs/部署指南.md](docs/部署指南.md#反向代理与-https)。

### 5. 备份要加密

```bash
# 备份到加密卷或加密归档，不要留在 Web 目录
docker compose exec backend sh -c "cat /app/data/support.db" > backup-$(date +%F).db
chmod 600 backup-$(date +%F).db
```

定期把备份同步到**与本机分离**的存储（另一台机器 / 加密对象存储），
并**实际演练过一次恢复**——没验证过的备份等于没有备份。

### 6. 删掉演示账号

```bash
# 演示数据如果不需要，直接清空
cd backend && ./.venv/Scripts/python -m app.seed --reset
```

至少要**改掉 `demo@acme.com` 的密码**（默认 `demo1234`），或者把它删掉。
用默认密码的公开账号跑公网，等于没有认证。

### 7. 缩小令牌有效期

```bash
TOKEN_TTL_HOURS=8
```

配合上面「JWT 无黑名单」的说明——窗口期越短，被盗 token 的可用时间越短。

### 参考环境变量速查

| 变量 | 默认值 | 生产环境建议 |
|---|---|---|
| `SECRET_KEY` | 弱默认值 | **必改**，随机 48 字节以上 |
| `CORS_ORIGINS` | `*` | **必改**，收敛为实际域名 |
| `TOKEN_TTL_HOURS` | `72` | 视使用场景调小到 `8`~`24` |
| `LLM_BASE_URL` / `LLM_API_KEY` | 空 | 不填则完全不出网；填了注意数据流向 |
| `DATABASE_URL` | `sqlite:///data/support.db` | 单实例保持默认即可 |
| `WEB_PORT` | `8080` | 按需修改，注意同步防火墙和反代配置 |

---

## 安全相关的开发约定

给贡献者的硬性要求（PR 涉及这些点时会被要求修改）：

1. **密钥绝不进代码库。** 所有敏感配置走环境变量，在 `backend/app/config.py` 里集中读取，
   新增配置项**必须同步更新 `.env.example`**。
2. **所有查询必须带租户过滤。** 每个查询都要有 `company_id` 约束。
   多租户隔离是这个项目的核心安全边界，加新接口时**最容易漏掉过滤条件**——
   写完请对照 `backend/tests/test_e2e.py` 里的越权用例自查。
3. **不要记录敏感信息到日志。** 密码、token、完整 JWT 串不要进日志或错误信息。
   用户贴的报错文本可能含客户数据，日志里转发前先脱敏。
4. **新增接口默认需要鉴权。** `backend/app/deps.py` 里的 `get_current_user` / `get_company`
   是默认依赖。写新路由时明确声明依赖，不要图省事。
5. **不要引入会削弱安全性的依赖。** 新的依赖会让供应链攻击面变大，
   引入前先在 Issue 里说明理由。
6. **涉及鉴权、租户隔离、上传、密钥的改动，请在 PR 描述里单独标出来**，
   并附上对应的测试用例。

---

## 致谢

感谢 responsibly 报告安全问题的人。

- 感谢你**私下**报告而不是直接发公开 Issue；
- 感谢你**写清楚了影响**而不只是说「有个洞」；
- 感谢你给维护者留出修复和发布的时间。

在修复发布后，如果你愿意，我们会在 `CHANGELOG.md` 里致谢你（署你的 GitHub 用户名，
或者匿名，随你）。**这份致谢是我们能给的、最实在的回报。**

---

## 其他

- **行为问题**（不是漏洞）→ 看 [行为准则](CODE_OF_CONDUCT.md)，举报邮箱是 `maintainers@kevin12369.dev`
- **功能 bug** → 直接开 [Issue](https://github.com/kevin12369/polaris/issues)
- **功能讨论** → [Discussions](https://github.com/kevin12369/polaris/discussions)
- **贡献指南** → [CONTRIBUTING.md](CONTRIBUTING.md)
