# IdentityHub - Jira Integration for NHI Findings

A proof-of-concept integration for **IdentityHub**, a Non-Human Identity (NHI)
management platform. Organizations use IdentityHub to track and manage their
service accounts, API keys, service principals, and other machine identities
across cloud environments.

This project lets IdentityHub users report NHI findings (for example, a stale
service account, an overprivileged key, or an expiring credential) directly to
their own Jira workspace as tickets.

## Quick start

```bash
git clone https://github.com/asafkessler/identityhub-jira-integration.git
cd identityhub-jira-integration
docker compose up
```

Then open **http://localhost:5173**, create an account, connect your Jira
Cloud workspace (site URL, email, and an
[API token](https://id.atlassian.com/manage-profile/security/api-tokens)),
and report a finding. The API documentation is at
http://localhost:8000/api/docs. No `.env` or other setup is needed for a
local run; Docker is the only prerequisite ([installing it](#prerequisites)).

The rest of this document is reference: running without Docker, configuration,
the REST API, the bonus automation, project layout and security notes. Design
decisions are in [DECISIONS.md](DECISIONS.md), structure in
[ARCHITECTURE.md](ARCHITECTURE.md).

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

<details>
<summary><strong>Installing Docker, if you do not have it yet</strong></summary>

- **Windows.** Docker needs WSL 2 (a lightweight Linux that Windows manages).
  In PowerShell run `wsl --status`; if WSL is missing, run `wsl --install`
  and restart. Then install
  [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
  (keep "Use WSL 2" selected), start it, and wait for "Engine running" in the
  bottom-left corner. Open a **new** terminal afterwards.
- **macOS.** Install
  [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
  (pick the Apple silicon or Intel build), start it, and wait for the engine
  to report running.
- **Linux.** Install Docker Engine and the Compose plugin from
  [docs.docker.com/engine/install](https://docs.docker.com/engine/install/)
  for your distribution. On Debian/Ubuntu the packages are `docker-ce`,
  `docker-ce-cli`, `containerd.io` and `docker-compose-plugin`. Add your user
  to the `docker` group (`sudo usermod -aG docker $USER`, then log out and
  in) so `docker compose up` works without `sudo`.

Verify with:

```bash
docker --version && docker compose version
```

</details>

## Running the project

Two ways. Docker is the quickest; the local path is for working on the code.

### Option A: Docker (recommended)

From the repository root:

```bash
docker compose up
```

Then open **http://localhost:5173**. The API documentation is at
http://localhost:8000/api/docs.

That is all. No `.env` is needed: if the two application secrets are not
provided, the backend generates them once and keeps them in the `app-data`
volume (see [Configuration](#configuration-env)). The first run builds both
images, which takes a minute or two.

**Stopping, and what happens to your data**

```bash
docker compose down
```

stops and removes the containers but **keeps** the `app-data` volume: your
accounts, Jira connections, tickets and API keys are still there on the next
`docker compose up`. Containers are disposable; the data lives in the volume
on purpose. To start from a clean slate (delete the database and the
auto-generated secrets as well):

```bash
docker compose down -v
```

Note that the Docker setup and the local setup (Option B) use **separate
databases**: the volume for Docker, `backend/data/identityhub.db` for local.
An account registered in one does not exist in the other, and the
recent-tickets view shows the tickets *that database* recorded (see
"Where is the data?" below).

What runs:

| Container | Port | Role |
|---|---|---|
| `frontend` | 5173 | nginx serving the built React app and proxying `/api` to the backend |
| `backend` | 8000 | FastAPI + SQLite (file in the `app-data` volume), runs as a non-root user |

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
cd backend; py -3.13 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.\.venv\Scripts\python.exe -m app.keys | Add-Content -Encoding utf8 ..\.env
```

The third command generates the two required secrets and appends them to
`.env`. The commands call the virtual environment's Python directly, so no
"activate" step is needed. On Windows, `py -3.13` picks that interpreter
explicitly (use `-3.12` or `-3.11` if that is what you have); a bare
`python` may resolve to an older installation.

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

**With Docker**, a root `.env` is optional: Compose passes it to the backend
when present. When the secrets are absent, the container's entrypoint
generates them once into the data volume so that `docker compose up` works
with no setup. This is a local-evaluation convenience; in production the
secrets are supplied explicitly and are never stored next to the data.

Jira credentials are **not** environment configuration: every user enters
their own in the app after logging in, and they are stored encrypted per user.

**Where is the data?** SQLite, one file:

| Setup | Location |
|---|---|
| Local (Option B) | `backend/data/identityhub.db` (plus `-wal` / `-shm` companions), ignored by git |
| Docker | `/data/identityhub.db` inside the `backend` container, stored in the named volume `app-data`. Inspect it with `docker compose exec backend ls -la /data`, or in Docker Desktop under **Volumes** |

The recent-tickets view is served from this database, not from Jira: the app
lists the tickets **it** created and recorded. A fresh database therefore
shows an empty list even if the same Jira project already contains tickets
created from another installation. Reconciling from Jira by label is a
documented production follow-up (see DECISIONS.md, section 3).

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

The same can be done without the UI from the interactive API docs at
http://localhost:8000/api/docs: `POST /api/auth/register`, then
`PUT /api/jira/connection`, then `GET /api/jira/projects`.

## Using the REST API

External systems (scanners, CI/CD pipelines, automations) can create finding
tickets without a person filling in a form.

**1. Create an API key.** Log in, open **API keys**, and create a key with a
name that identifies the system that will use it. The full key is shown
**once**; store it in that system's secret store. (Equivalent API call:
`POST /api/keys`.)

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

`automations/blog-digest/digest.py` fetches the most recent post from
[oasis.security/blog](https://www.oasis.security/blog), asks Claude for a
short digest, and reports it as a ticket through the app's public API, like
any other external system would. It remembers the last post it reported, so
running it twice does not create two tickets.

**What you need**

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required. The AI summary is produced by the Claude API. Without a key the script stops and says so; there is no non-AI fallback, because the assignment asks for an AI-powered summary |
| `IDENTITYHUB_API_KEY` | Required. Create one in the app under **API keys** |
| `IDENTITYHUB_API_URL` | Default `http://localhost:8000` |
| `JIRA_PROJECT_KEY` | Default `SCRUM` |
| `DIGEST_MODEL` | Default `claude-opus-5-5` |

**Run it locally** (with the backend running):

```bash
cd automations/blog-digest && python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python digest.py --print-post
```

`--print-post` only shows which post would be used, without calling Claude or
creating anything. Then, with `ANTHROPIC_API_KEY` and `IDENTITYHUB_API_KEY`
exported:

```bash
.venv/bin/python digest.py --dry-run
```

prints the ticket that would be created, and

```bash
.venv/bin/python digest.py
```

creates it. On Windows create the environment with `py -3.13 -m venv .venv`
and use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.
Tests: `.venv/bin/python -m pytest`.

**Scheduled run (GitHub Actions).** `.github/workflows/blog-digest.yml` runs
the digest daily and on demand. The job is self-contained: it starts the
backend from the repository, registers a throwaway account, connects the Jira
workspace from repository secrets, creates an API key, and runs the digest.
Configure these secrets in the repository (Settings → Secrets and variables
→ Actions): `ANTHROPIC_API_KEY`, `JIRA_SITE_URL`, `JIRA_EMAIL`,
`JIRA_API_TOKEN`, and optionally `JIRA_PROJECT_KEY`. The run log shows the
post, the digest, and the created issue key; the key itself is masked.

## Project structure

```
backend/                 Python / FastAPI
  app/
    main.py              app factory: routers, error handlers, docs
    config.py            settings from the environment
    db.py                SQLAlchemy engine, SQLite pragmas (WAL), sessions
    models.py            the schema: users, sessions, jira_connections, tickets, api_keys
    core/                errors (one JSON shape), security (bcrypt, hashing, Fernet), deps
    auth/                register / login / logout / me
    jira/                Jira client + connection management + projects / issue types
    tickets/             create finding ticket (one service for UI and API), recent tickets
    api_keys/            per-user API keys
    public_api/v1/       the external API (X-API-Key)
  tests/                 pytest; an in-process fake Jira replaces the network
frontend/                React + Vite + TypeScript
  src/api/               the only module that performs HTTP; typed errors
  src/pages/             login/register, connect Jira, findings, API keys
  src/components/        ticket form, recent tickets, layout, error banner
automations/blog-digest/ bonus automation (see below)
docker-compose.yml       one-command run
ARCHITECTURE.md          how it is put together and how a request flows
DECISIONS.md             what was decided, what was rejected, and why
```

Each backend feature module follows the same layering: `router.py` (HTTP)
→ `service.py` (use case) → `repository.py` (queries, always scoped by
`user_id`), with `schemas.py` as the typed contract. See
[ARCHITECTURE.md](ARCHITECTURE.md).

## Security notes

- **Multi-tenancy.** Every table holding user data has a `user_id`, every
  query filters by it, and routes receive the authenticated user from the
  session or the API key, never from the request. A user cannot address
  another user's connection, tickets, or keys.
- **Sessions.** Server-side, identified by a random token whose hash is
  stored. Cookie is `HttpOnly` and `SameSite=Lax`; `Secure` is enabled via
  `COOKIE_SECURE=true` behind HTTPS. Logout deletes the session.
- **Passwords** are hashed with bcrypt. Login failures are generic and take
  the same time whether or not the email exists.
- **Jira tokens** are verified against Jira before being saved, encrypted at
  rest with a key that lives only in the environment, decrypted only for the
  duration of a request, and never returned by any endpoint.
- **API keys** are shown once and stored hashed; revocation is immediate.
- **Errors** never leak internals: unexpected failures return a generic 500
  and are logged server-side.
- **Secrets never enter git.** `.env` is ignored; `.env.example` has names
  only. Jira credentials are user data entered in the UI, not configuration.
- **Known limits of a POC** (documented in DECISIONS.md): API tokens instead
  of OAuth, no rate limiting on the public API, no CSRF token beyond
  `SameSite=Lax`, SQLite instead of PostgreSQL, no migrations tooling.
