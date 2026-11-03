# IdentityHub - Jira Integration for NHI Findings

A proof-of-concept integration for **IdentityHub**, a Non-Human Identity (NHI)
management platform. Organizations use IdentityHub to track and manage their
service accounts, API keys, service principals, and other machine identities
across cloud environments.

This project lets IdentityHub users report NHI findings (for example, a stale
service account, an overprivileged key, or an expiring credential) directly to
their own Jira workspace as tickets.

## What it does

- **Login and logout** with secure, server-side sessions. Multiple users can
  work concurrently, each with their own Jira connection and their own data.
- **Connect a Jira Cloud workspace** after login. Credentials are verified
  against Jira before they are saved, and stored encrypted.
- **Create an NHI finding ticket** from a form: pick a Jira project from the
  connected workspace, enter a summary and a description, and the app creates
  a real issue in Jira.
- **Recent tickets view**: the 10 most recent tickets created from this app in
  the selected project, with title, creation time, and a link that opens the
  issue in Jira in a new tab.
- **REST API** for external systems (scanners, CI/CD pipelines) to create
  finding tickets programmatically, protected by a per-user API key.
- **Bonus - NHI Blog Digest**: an automation that fetches the latest post from
  oasis.security/blog, summarizes it with AI, and opens a Jira ticket with the
  summary.

Design decisions and assumptions are documented in [DECISIONS.md](DECISIONS.md).

## Prerequisites

Either:

- **Docker** (Docker Desktop or Docker Engine with Compose), or
- **Python 3.11+** and **Node.js 20+** for running without Docker.

Plus a **Jira Cloud** account (free tier is fine) and an Atlassian API token
for connecting your workspace, see [Connecting your Jira workspace](#connecting-your-jira-workspace).

## Running the project

_To be documented._

### Option A: Docker

_To be documented._

### Option B: Local (without Docker)

**1. Configuration.** From the repository root, create your `.env` and generate
the two secrets it needs:

```bash
cp .env.example .env
```

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

```bash
python -m app.keys >> ../.env
```

(On Windows, activate with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.)

**2. Backend.** From `backend/`, with the virtual environment active:

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now at http://localhost:8000. Interactive documentation (Swagger UI)
is at http://localhost:8000/api/docs, and a health check at
http://localhost:8000/api/health.

**3. Frontend.** _To be documented._

**Running the backend tests:**

```bash
cd backend && python -m pytest
```

## Configuration (`.env`)

All configuration lives in one `.env` file in the repository root, which git
ignores. [`.env.example`](.env.example) lists every variable with comments.

| Variable | Required | Purpose |
|---|---|---|
| `APP_SECRET_KEY` | yes | Random string (32+ chars) used for session material |
| `APP_ENCRYPTION_KEY` | yes | Fernet key that encrypts stored Jira API tokens at rest |
| `DATABASE_URL` | no | SQLAlchemy URL. Defaults to a SQLite file under `backend/data/`. Point it at PostgreSQL for production |
| `SESSION_TTL_HOURS` | no | Session lifetime, default 168 (7 days) |
| `COOKIE_SECURE` | no | Set `true` behind HTTPS |
| `ANTHROPIC_API_KEY` | bonus only | Used by the blog-digest automation for the AI summary |

Both secrets can be generated with `python -m app.keys` from the `backend/`
directory. If either is missing or malformed, the backend refuses to start and
prints exactly what to do.

Jira credentials are **not** environment configuration: every user enters
their own in the app after logging in, and they are stored encrypted per user.

## Connecting your Jira workspace

Each user connects their own Jira Cloud workspace from inside the app, after
logging in. You need three things:

1. **Site URL**: your Jira address, e.g. `https://your-team.atlassian.net`.
2. **Email**: the Atlassian account email.
3. **API token**: create one at
   https://id.atlassian.com/manage-profile/security/api-tokens
   ("Create API token", classic, not scoped). Copy it immediately; Atlassian
   shows it only once.

The app verifies the three values against Jira before saving them, so a typo
is reported right away. The token is stored encrypted and is never shown
again; you can disconnect at any time, which deletes it.

Until the web UI is in place, you can do this from the interactive API docs
at http://localhost:8000/api/docs: `POST /api/auth/register`, then
`PUT /api/jira/connection`, then `GET /api/jira/projects`.

## Using the REST API

_To be documented. Will include a `curl` example._

## Running the Blog Digest automation (bonus)

_To be documented._

## Project structure

_To be documented._

## Security notes

_To be documented._
