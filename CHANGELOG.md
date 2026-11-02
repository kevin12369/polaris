# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-02

First public release.

### Added

**Tickets** — submission with AI-assisted classification (category, priority, confidence
and reasoning), SLA countdowns computed over working hours, a strict status machine
(`new → triaged → in_progress → pending → resolved → closed`), and a full event timeline
covering every note, transition and SLA settlement.

**Knowledge base** — manual authoring plus one-click promotion of a resolved ticket.
Promotion captures the source ticket number, category and resolution, and generates a
summary plus generalised troubleshooting steps. Retrieval uses BM25 with Chinese-aware
tokenisation.

**AI troubleshooting assistant** — paste an error, get a diagnosis and 3–6 actionable
steps with the articles each step came from. Three-tier degradation: `llm+kb` when an LLM
endpoint is configured, `kb` when the knowledge base matched, `fallback` to a standard
checklist when it did not — it never invents an answer.

**Dashboard** — ticket volume, average first response, SLA breach rate and knowledge-base
hit rate, plus daily trends and category/status breakdowns rendered as inline SVG.

**Multi-tenancy** — each company is an isolated workspace; every query is tenant-scoped
and cross-tenant access returns 404 without leaking resource existence. Two roles
(`admin`, `agent`), JWT auth with PBKDF2 password hashing.

**Working hours** — per-tenant schedule with configurable workdays and start/end times,
so SLA countdowns reflect an actual rota rather than a fixed Mon–Fri assumption.

**Bilingual UI** — Chinese and English with a one-click switch in the sidebar. The
preference is stored locally and the initial language follows the browser. No
i18n framework dependency; the dictionary lives in `frontend/src/i18n.js`.

**Static demo page** — a zero-dependency single-file HTML demo with mock data,
published to GitHub Pages at <https://kevin12369.github.io/polaris/>.

### Engineering

- 93 assertions across three suites (SLA maths, retrieval relevance, end-to-end flows),
  all passing in CI on Linux with Python 3.12.
- CI covers backend tests, the frontend production build and Docker image builds
  (including `docker compose config` validation).
- Lightweight schema migrations run on startup, so adding a column to an existing
  SQLite database no longer requires a manual step.
- `.gitattributes` pins LF line endings so the Docker build works on Linux hosts.
- MIT licensed.

### Notes

- SQLite suits 5–50 users; move to PostgreSQL beyond that.
- Ticket attachments are not implemented — descriptions and error text only.
- Inbound email/chat ingestion is not implemented; `POST /api/tickets` is the
  integration point.
