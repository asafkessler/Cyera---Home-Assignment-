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

**1. Configuration and backend setup.** Run from the repository root. Pick
the block for your operating system.

macOS / Linux:

```bash
cp .env.example .env
```

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python -m app.keys >> ../.env
```

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

```powershell
cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe -m app.keys | Add-Content -Encoding utf8 ..\.env
```

The third command generates the two required secrets and appends them to
`.env`. The commands call the virtual environment's Python directly, so no
"activate" step is needed.

**2. Backend.** From `backend/`:

macOS / Linux:

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API is now at http://localhost:8000. Interactive documentation (Swagger UI)
is at http://localhost:8000/api/docs, and a health check at
http://localhost:8000/api/health.

**3. Frontend.** In a second terminal, from `frontend/`:

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to the backend on
port 8000, so the UI and the API share one origin and the session cookie
works without any CORS configuration.

**Running the backend tests** (from `backend/`, same Python as above):

```bash
.venv/bin/python -m pytest
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

**Where do tickets show up in Jira?** In the project you selected. In a
Scrum project new issues go to the **Backlog** (not the active sprint board)
until someone pulls them into a sprint; in a Kanban project they appear on the
board right away. The ticket link in the app always opens the issue directly.

Until the web UI is in place, you can do this from the interactive API docs
at http://localhost:8000/api/docs: `POST /api/auth/register`, then
`PUT /api/jira/connection`, then `GET /api/jira/projects`.

## Using the REST API

External systems (scanners, CI/CD pipelines, automations) can create finding
tickets without a person filling in a form.

**1. Create an API key.** Log in, open **API keys**, and create a key with a
name that identifies the system that will use it. The full key is shown
**once**; store it in that system's secret store. (Before the UI exists:
`POST /api/keys` in the API docs.)

**2. Send findings.** Put the key in the `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/api/v1/findings \
  -H "X-API-Key: ihk_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "project_key": "SCRUM",
    "summary": "Stale service account: svc-deploy-prod",
    "description": "No authentication events in 94 days. Owner team: platform.",
    "severity": "high",
    "identity_type": "service_account"
  }'
```

A successful call returns `201` with the issue key and a direct link:

```json
{"issue_key": "SCRUM-12", "issue_url": "https://your-team.atlassian.net/browse/SCRUM-12",
 "project_key": "SCRUM", "summary": "Stale service account: svc-deploy-prod",
 "source": "api", "created_at": "2026-11-04T08:15:02Z"}
```

| Field | Required | Notes |
|---|---|---|
| `project_key` | yes | A project in the key owner's workspace. `GET /api/v1/projects` lists them |
| `summary` | yes | Ticket title, up to 255 characters |
| `description` | yes | Free text; line breaks become paragraphs |
| `severity` | no | `low`, `medium`, `high`, `critical` |
| `identity_type` | no | `service_account`, `api_key`, `service_principal`, `other` |
| `issue_type` | no | Defaults to `Task`; must exist in the project |

**Errors** all have the same shape, with a stable `code` to branch on:

| Status | `code` | When |
|---|---|---|
| 401 | `invalid_api_key` | Header missing, key unknown, or key revoked |
| 404 | `project_not_found` | Project does not exist or is not visible to the key owner |
| 409 | `jira_not_connected` | The key owner has not connected a Jira workspace |
| 422 | `validation_failed` | A field is invalid; `details.fields` names it. Also used when `issue_type` is not available in the project |
| 502 | `jira_unavailable` | Jira unreachable or returned an unexpected error |

The interactive documentation at http://localhost:8000/api/docs lists every
endpoint with examples. Click **Authorize**, paste a key, and you can create a
real ticket from the browser. A machine-readable spec is at
`/api/openapi.json`.

Tickets created through the API are recorded like any other and appear in
the app's recent-tickets view with source `api`.

## Running the Blog Digest automation (bonus)

_To be documented._

## Project structure

_To be documented._

## Security notes

_To be documented._
