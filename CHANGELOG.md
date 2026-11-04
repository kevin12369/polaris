# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-04

### Added

**Statutory holiday support.** SLA countdowns previously skipped weekends and nights but
kept running through statutory holidays — a ticket created during the National Day week
counted down for all seven days off. Now:

- Chinese statutory holidays are built in (`backend/app/holidays.py`), with the 2026
  arrangement taken from the State Council notice of 2025-11-04
- Make-up working days count normally (e.g. Saturday 10 October, designated a working day
  for the National Day adjustment)
- Workspaces can add their own days off (company shutdowns) and extra working days (on-call)
  via the settings API and the Settings screen
- Years without bundled data fall back to the regular weekday schedule instead of failing

**API reference.** New `docs/API.md` and `docs/API.en.md` documenting every endpoint, with
integration examples for email and chat ingestion. The deployment guide previously linked to
an `docs/API.md` that did not exist.

**Roadmap.** New `docs/ROADMAP.md` and `docs/ROADMAP.en.md` — a living document of what is
planned and why, ordered by how many small businesses actually need each item.

**Community infrastructure.** CONTRIBUTING, CODE_OF_CONDUCT and SECURITY policies; issue
forms for bugs and feature requests; a pull request template; Discussions enabled with 30
bilingual labels.

**Maintenance automation.**
- Dependabot for pip, npm and GitHub Actions dependencies
- Stale bot: flags issues after 60 days of inactivity, closes them 14 days later
- Labeler: applies module/type/area labels based on changed files
- Release drafter: generates release notes and the next version number from merged PRs
- Weekly health check: runs the full test suite and build; opens an issue on failure
- `scripts/release.sh`: test → tag → release → upload source archive in one command

### Fixed

- The custom test runner in `tests/test_sla.py` sat in the middle of the file, so any test
  appended after it never ran. Moved to the end of the file.
- The working-hours endpoint now validates holiday dates as `YYYY-MM-DD` and rejects
  malformed input with a clear message instead of silently accepting it.

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
