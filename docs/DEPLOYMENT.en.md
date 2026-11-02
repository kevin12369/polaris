# Deployment Guide

This guide is for operators and implementers: how to run Polaris on a single server.

- [中文](部署指南.md)

---

## Requirements

| Item | Requirement |
|---|---|
| Server | 2 vCPU / 2 GB is enough (a small cloud instance is fine) |
| Docker | 20.10+ with Docker Compose v2 |
| Disk | 1 GB to start (the database grows with ticket volume) |
| Domain | Optional — use an IP and port if you do not have one |

No database server, message queue or AI service required.

---

## Deploying in three steps

### Step 1: Clone and configure

```bash
git clone https://github.com/kevin12369/polaris.git polaris
cd polaris
cp .env.example .env
```

Generate a random secret for `SECRET_KEY` (it signs login tokens):

```bash
python3 -c "import secrets;print(secrets.token_urlsafe(48))"
```

Available `.env` settings:

```bash
WEB_PORT=8080              # Port the web UI is exposed on
SECRET_KEY=<random string> # Required — change this
TOKEN_TTL_HOURS=72         # Login token lifetime
CORS_ORIGINS=*             # Narrow this to your domain in production
LLM_BASE_URL=              # Optional, OpenAI-compatible endpoint
LLM_API_KEY=               # Optional
LLM_MODEL=gpt-4o-mini      # Optional
```

### Step 2: Start

```bash
docker compose up -d --build
```

Then open `http://<server-ip>:<WEB_PORT>`. Backend health check:

```bash
curl http://127.0.0.1:8000/api/health
```

### Step 3: Create a workspace

Open the home page, click "Create free workspace", and fill in the company name, your name, email and password.

Each company gets a fully isolated space. Administrators can add agents from the interface, or via the API:

```bash
curl -X POST http://<host>:8000/api/auth/members \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Alex","email":"agent@company.com","password":"initial-password","role":"agent"}'
```

### Seed demo data (optional)

```bash
cd backend
python -m app.seed --reset
```

Demo account `demo@acme.com` / `demo1234`. **Delete or change it before going live.**

---

## Go-live checklist

- [ ] `SECRET_KEY` set to a random value
- [ ] Demo account deleted or re-passworded
- [ ] Database backed up to external storage
- [ ] `CORS_ORIGINS` narrowed to your real domain
- [ ] Firewall exposes only the required ports (web + SSH)
- [ ] HTTPS reverse proxy configured (optional but recommended)

---

## Operations

```bash
# Logs
docker compose logs -f backend

# Back up
docker compose exec backend sh -c "cat /app/data/support.db" > backup-$(date +%F).db

# Restore
docker compose exec -T backend sh -c "cat > /app/data/support.db" < backup-2026-11-02.db

# Restart the backend
docker compose restart backend

# Inspect volumes
docker volume ls | grep polaris-data
```

### Database migrations

SQLite's `CREATE TABLE` does not add columns to existing tables. The app runs a lightweight
migration on startup to add any new fields; you will see `[migrate] 已补齐字段: ...` in the logs.
To run it manually:

```bash
docker compose exec backend python -m app.migrations
```

### Upgrading from the old project name (support-workbench → polaris)

The rename also changed the Docker volume name. **If you deployed under the old name, migrate the
volume once** — otherwise `docker compose up` starts with an empty database:

```bash
# Full volume names are <project-directory>_<volume-name>; check with docker volume ls first
docker volume ls | grep -E "sw-data|polaris-data"

# 1. Back up the old volume
docker run --rm -v support-workbench_sw-data:/old -v $(pwd):/backup alpine \
  tar czf /backup/old-sw-data.tar.gz -C /old .

# 2. Copy it into the new volume
docker compose up -d backend          # start once to create the new volume
docker run --rm -v support-workbench_sw-data:/old -v polaris_polaris-data:/new alpine \
  sh -c "cp -a /old/. /new/"

# 3. Restart the backend
docker compose restart backend
```

> The volume names above assume the project directories are `polaris` and `support-workbench`.
> Substitute the actual names from step 0 if yours differ.

Skip this entirely if you have not deployed yet.

---

## Reverse proxy and HTTPS

Example Nginx configuration:

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

The frontend container ships with Nginx and already proxies `/api/` to the backend, so exposing
`WEB_PORT` directly is enough.

---

## FAQ

**Where is the data stored, and can it be lost?**
In the `polaris-data` Docker volume — a single SQLite file. Deleting and recreating containers does
not lose it. Copy the file for a full backup.

**Can we use PostgreSQL instead?**
Yes, the changes are modest. Below 50 people there is no reason to bother: SQLite is simpler and faster.

**How many people is it good for?**
5 to 50 without trouble. Past a hundred, move to PostgreSQL.

**How is it secured?**
Passwords are hashed with PBKDF2-HMAC-SHA256 (120k rounds); sessions use JWT. Secrets come from
environment variables. If you configure an LLM endpoint, only troubleshooting text is sent to it;
without one, nothing leaves your server.

**How do we create tickets from email or chat?**
POST JSON to `POST /api/tickets`. See the [API reference](../README.en.md#5-api-reference).

---

## Project layout

```
polaris/
├── backend/
│   ├── app/
│   │   ├── main.py          # Application entry point
│   │   ├── config.py        # Configuration and SLA policy
│   │   ├── models.py        # ORM models
│   │   ├── sla.py           # Working-hour SLA maths
│   │   ├── migrations.py    # Lightweight schema migrations
│   │   ├── seed.py          # Demo data
│   │   ├── onboard.py       # Provision a company space from the CLI
│   │   ├── routers/         # API routes
│   │   └── services/        # Retrieval / classification / troubleshooting
│   ├── tests/               # 93 assertions across three suites
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── views/           # Six views
│   │   ├── i18n.js          # Bilingual dictionary
│   │   └── store.js         # Session state
│   ├── Dockerfile
│   └── nginx.conf
├── demo/
│   └── index.html           # Static demo page (GitHub Pages)
├── docs/
│   ├── DEPLOYMENT.en.md
│   └── 部署指南.md
├── docker-compose.yml
└── .env.example
```
