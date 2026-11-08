# Roadmap

How Polaris evolves. **This document is alive** — it is updated after every release, and
issue and milestone status is reflected here.

- [中文](ROADMAP.md)

---

## Current release

**v1.1.0** — Statutory holiday support

SLA countdowns previously skipped weekends and nights but kept running through statutory
holidays — a ticket created during the National Day week would count down for all seven
days off. v1.1.0 fixes that.

- Chinese statutory holidays built in (data from the State Council notice)
- Make-up working days count normally (weekend days designated as working)
- Workspaces can add their own days off (company shutdowns) and extra working days (on-call)
- Years without bundled data fall back to the regular weekday schedule instead of failing

---

## Planned

### v1.2 — Attachments and channel ingestion

| Feature | Description | Why |
|---|---|---|
| ✅ Ticket attachments | Upload screenshots and log files | Troubleshooting lives on screenshots; text descriptions slow everything down |
| Email → ticket | IMAP polling or webhook | Customers report issues by email out of habit |
| WeChat Work ingestion | Enterprise WeChat / Official Account messages → tickets | Target customers communicate on WeChat |

Attachments are done (v1.2.0): extension *and* magic-number checks, random storage paths,
downloads forced as attachments with `nosniff`, SVG excluded, 10 MB per file and 10 per ticket.

Virus scanning is not wired up yet — only the type allow list and magic-number check are applied.
Channel ingestion is still queued.

### v1.3 — Knowledge base improvements

- Version history for articles (what changed, who changed it)
- Duplicate detection (suggest merging near-identical articles)
- Matched-term highlighting in search results
- Bulk import/export (CSV)

### v2.0 — Scale

- PostgreSQL support (multi-instance deployment, concurrent writes)
- Ticket merge and split (the same issue reported through several channels)
- Custom fields (contract number, store ID, affected user count — every business cares about different things)
- Webhook subscriptions (push ticket status changes to external systems)
- Audit log (a complete record of who did what, when)

---

## Shipped

| Version | Contents | Date |
|---|---|---|
| v1.2.0 | Ticket attachments: screenshots and logs, with full security checks | 2026-11 |
| v1.1.0 | Statutory holiday calendar: built-in + per-workspace overrides | 2026-11 |
| v1.0.0 | First public release: tickets / knowledge base / AI troubleshooting / dashboard | 2026-11-02 |

---

## How to take part

This is not a list of "we plan to do this" — it is a list of "come do this with us":

- Want a feature → open a [Feature Request](https://github.com/kevin12369/polaris/issues/new?template=feature_request.yml)
- Want to discuss first → [Discussions](https://github.com/kevin12369/polaris/discussions)
- Ready to code → read [CONTRIBUTING.md](../CONTRIBUTING.md) and pick up an issue labelled `good first issue`
- Think the roadmap is wrong → open an issue and say so. Roadmaps change.

## How priorities are set

Ordered by "how many small businesses actually need this", not "how hard is it technically".
The judgements come from real usage feedback and the profile of the target customers:

1. **Attachments** — the direct bottleneck in troubleshooting efficiency; the most common complaint
2. **Channel ingestion** — decides whether the system can actually replace the WeChat group
3. **PostgreSQL** — only needed once a customer really exceeds 50 people; not urgent
