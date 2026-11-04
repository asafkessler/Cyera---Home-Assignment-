# Architecture

This document describes how the project is structured and how a request flows
through it. The reasoning behind the choices is in [DECISIONS.md](DECISIONS.md).

## System overview

```
┌──────────────────────┐        HTTP (JSON, session cookie)        ┌──────────────────────────┐
│  frontend/           │ ────────────────────────────────────────▶ │  backend/                │
│  React + Vite        │                                           │  FastAPI                 │
│  (browser)           │ ◀──────────────────────────────────────── │                          │
└──────────────────────┘                                           │  routers → services →    │
                                                                   │  repositories → SQLite   │
┌──────────────────────┐        HTTP (JSON, X-API-Key header)      │                          │
│  External systems    │ ────────────────────────────────────────▶ │  jira client (httpx)     │
│  scanners, CI/CD,    │                                           │            │             │
│  blog-digest bonus   │ ◀──────────────────────────────────────── └────────────┼─────────────┘
└──────────────────────┘                                                        │ HTTPS, Basic auth
                                                                                ▼
                                                                   ┌──────────────────────────┐
                                                                   │  Jira Cloud REST API v3  │
                                                                   │  (one site per user)     │
                                                                   └──────────────────────────┘
```

Two kinds of clients reach the same backend through two authentication
methods, and both end up in the same ticket-creation service. The UI has no
privileged path: everything it can do, it does through HTTP endpoints.

## Repository layout

```
identityhub-jira-integration/
├── backend/                     # Python / FastAPI application
│   ├── app/
│   │   ├── main.py              # app factory: routers, error handlers, CORS, docs
│   │   ├── config.py            # settings loaded from environment (.env)
│   │   ├── db.py                # engine, session factory, SQLite pragmas (WAL, busy timeout)
│   │   ├── models.py            # SQLAlchemy ORM models (the schema)
│   │   ├── core/
│   │   │   ├── errors.py        # AppError hierarchy + handlers → uniform JSON errors
│   │   │   ├── security.py      # password hashing, random tokens, hashing, Fernet encryption
│   │   │   └── deps.py          # FastAPI dependencies: db session, current_user, api_key_user
│   │   ├── auth/                # register / login / logout / me
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   ├── jira/                # Jira connection + Jira HTTP client
│   │   │   ├── client.py        # JiraClient (httpx) + JiraAuthProvider interface
│   │   │   ├── router.py        # connection status / connect / disconnect / projects / issue types
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   ├── tickets/             # finding tickets: create + recent (shared by UI and public API)
│   │   │   ├── router.py        # internal endpoints used by the UI
│   │   │   ├── service.py       # create_finding_ticket(): the single business entry point
│   │   │   ├── repository.py
│   │   │   ├── schemas.py
│   │   │   └── description.py   # renders the NHI finding into a Jira description (ADF)
│   │   ├── api_keys/            # create / list / revoke per-user API keys
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   └── public_api/
│   │       └── v1/
│   │           ├── router.py    # /api/v1/findings — authenticated with X-API-Key
│   │           └── schemas.py   # the external contract, documented with examples
│   ├── tests/                   # pytest: unit tests for services, API tests with a mocked Jira
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # React + Vite + TypeScript application
│   ├── src/
│   │   ├── api/                 # one typed client for the backend; the only place that calls fetch
│   │   ├── pages/               # Login, Register, ConnectJira, Dashboard, ApiKeys
│   │   ├── components/          # TicketForm, RecentTickets, ConnectionBadge, ErrorBanner, ...
│   │   ├── App.tsx              # routing + auth gate
│   │   └── main.tsx
│   ├── vite.config.ts           # dev proxy: /api → backend, so cookies are same-origin
│   ├── nginx.conf               # production image: serve static files, proxy /api → backend
│   ├── package.json
│   └── Dockerfile
├── automations/
│   └── blog-digest/             # bonus: fetch → summarize (Claude) → POST /api/v1/findings
├── .github/workflows/           # bonus schedule (and CI if time permits)
├── docker-compose.yml
├── .env.example
├── README.md
├── DECISIONS.md
└── ARCHITECTURE.md
```

### Backend layering

Each feature module has the same four files, and dependencies point in one
direction only:

| Layer | File | Responsibility | Knows about |
|---|---|---|---|
| HTTP | `router.py` | Parse the request, call one service function, shape the response. No business logic. | schemas, service |
| Business | `service.py` | The use case: validate state, orchestrate repositories and the Jira client, raise `AppError`s. | repository, jira client, models |
| Data access | `repository.py` | Queries. **Every function that touches tenant data takes `user_id`** and filters by it. | models, db session |
| Contract | `schemas.py` | Pydantic models for requests and responses. Also feed the OpenAPI docs. | nothing |

The ticket-creation use case lives once, in `tickets/service.py`. The UI
router and the public API router both call it. That is what guarantees that a
ticket created by a scanner is validated, labelled, recorded, and isolated
exactly like one created from the form.

### Error handling

Services raise typed errors (`NotAuthenticated`, `JiraNotConnected`,
`JiraAuthFailed`, `ProjectNotFound`, `JiraUnavailable`, `ValidationFailed`,
...). One handler in `main.py` maps each to a status code and renders the same
JSON body everywhere:

```json
{ "error": { "code": "jira_auth_failed",
             "message": "Jira rejected the credentials. Check the email and API token.",
             "details": { "site_url": "https://example.atlassian.net" } } }
```

`code` is stable and machine-readable (for the automation and for the UI to
branch on); `message` is written for a person. Framework-level errors (unknown
route, wrong method) and unexpected exceptions are rendered in the same shape,
the latter as a generic `internal_error` with the cause logged server-side.

## Data model

```
users                     sessions                    jira_connections
─────────────────         ─────────────────           ─────────────────────────
id            PK          id            PK            id                PK
email         unique      token_hash    unique        user_id           FK users, unique
password_hash             user_id       FK users      site_url
created_at                created_at                  email
                          expires_at                  api_token_encrypted
                          last_seen_at                jira_account_id
                                                      display_name
                                                      connected_at
                                                      last_verified_at

tickets                                   api_keys
───────────────────────────               ─────────────────────────
id            PK                          id            PK
user_id       FK users   ◀── tenant       user_id       FK users   ◀── tenant
project_key                               name
issue_key     (e.g. SCRUM-12)             key_prefix    (first 8 chars, for display)
issue_id      (Jira internal id)          key_hash      unique
summary                                   created_at
issue_url                                 last_used_at
source        'ui' | 'api'                revoked_at    nullable
created_at
index (user_id, project_key, created_at desc)
```

Notes:

- `sessions.token_hash` and `api_keys.key_hash`: the database stores a hash of
  the random secret, never the secret itself. The cookie and the API key are
  the only copies.
- `jira_connections.api_token_encrypted`: Fernet ciphertext; the key comes
  from `APP_ENCRYPTION_KEY` in the environment. Decryption happens only inside
  the Jira client for the duration of a request.
- `tickets.source` records whether a ticket came from the form or from the
  public API; both appear in the recent-tickets view.

## API surface

All backend routes are mounted under `/api`, so the frontend proxy needs a
single rule. Internal routes are authenticated by the session cookie; the
public route by the `X-API-Key` header.

### Internal (session cookie, used by the UI)

| Method | Path | Purpose | Success | Errors |
|---|---|---|---|---|
| POST | `/api/auth/register` | Create account | 201 user | 409 email taken, 422 validation |
| POST | `/api/auth/login` | Start session, set cookie | 200 user | 401 invalid credentials |
| POST | `/api/auth/logout` | End session, clear cookie | 204 | |
| GET | `/api/auth/me` | Current user + Jira connection status | 200 | 401 |
| GET | `/api/jira/connection` | Connection status (never the token) | 200 | 401 |
| PUT | `/api/jira/connection` | Verify credentials against Jira, encrypt, save | 200 status | 400 bad site URL, 401 session, 422 validation, 502 Jira unreachable, 400 `jira_auth_failed` |
| DELETE | `/api/jira/connection` | Remove stored credentials | 204 | 401 |
| GET | `/api/jira/projects` | Projects visible to the connected user | 200 list | 401, 409 not connected, 502 |
| GET | `/api/jira/projects/{key}/issue-types` | Issue types available for creation | 200 list | 401, 404 project, 409, 502 |
| POST | `/api/tickets` | Create a finding ticket from the form | 201 ticket | 401, 409 not connected, 404 project, 422, 502 |
| GET | `/api/tickets?project_key=X&limit=10` | Recent tickets created by this app, this user, this project | 200 list | 401, 422 |
| GET | `/api/keys` | List this user's API keys (prefix, name, dates) | 200 list | 401 |
| POST | `/api/keys` | Create a key; **the full key is returned only in this response** | 201 key | 401, 422 |
| DELETE | `/api/keys/{id}` | Revoke | 204 | 401, 404 |

### Public (`X-API-Key` header, for external systems)

| Method | Path | Purpose | Success | Errors |
|---|---|---|---|---|
| POST | `/api/v1/findings` | Create an NHI finding ticket | 201 `{issue_key, issue_url, project_key, created_at}` | 401 missing/invalid/revoked key, 404 project, 409 key owner has no Jira connection, 422 validation, 502 Jira failed |
| GET | `/api/v1/projects` | Projects the key's owner can create tickets in (lets a scanner discover valid `project_key`s) | 200 list | 401, 409, 502 |

Request body for `POST /api/v1/findings`:

```json
{
  "project_key": "SCRUM",
  "summary": "Stale service account: svc-deploy-prod",
  "description": "No authentication events in 94 days. Owner team: platform.",
  "severity": "high",
  "identity_type": "service_account",
  "issue_type": "Task"
}
```

`severity` (`low` | `medium` | `high` | `critical`) and `identity_type`
(`service_account` | `api_key` | `service_principal` | `other`) are optional;
`issue_type` defaults to `Task`.

Documentation: Swagger UI at `/api/docs`, ReDoc at `/api/redoc`, raw spec at
`/api/openapi.json`.

### Calls made to Jira (REST API v3)

| Purpose | Jira endpoint |
|---|---|
| Verify credentials on connect | `GET /rest/api/3/myself` |
| List projects | `GET /rest/api/3/project/search` (paginated) |
| Issue types for a project | `GET /rest/api/3/issue/createmeta/{projectKey}/issuetypes` |
| Create issue | `POST /rest/api/3/issue` (description in Atlassian Document Format, label `identityhub`) |

Authentication: HTTP Basic with `email:api_token`, through the
`JiraAuthProvider` interface so an OAuth provider could replace it.

## Request flows

**Connect Jira**

```
UI  PUT /api/jira/connection {site_url, email, api_token}
 → router: validate shape (https URL, email format, non-empty token)
 → service: build a JiraClient with these credentials
          → GET /myself   (fails → JiraAuthFailed 400 / JiraUnavailable 502)
          encrypt token, upsert jira_connections for user_id
 ← 200 {site_url, email, display_name, connected_at}
```

**Create ticket (form or API)**

```
UI  POST /api/tickets {project_key, summary, ...}          API  POST /api/v1/findings {...}
 → deps.current_user (session cookie)                       → deps.api_key_user (hash lookup, not revoked)
 → tickets.service.create_finding_ticket(user, payload, source="ui" | "api")
      → jira.repository.get_connection(user_id)      (none → JiraNotConnected 409)
      → JiraClient(connection).create_issue(project_key, issue_type, summary, description ADF, labels)
           Jira 400 "project does not exist" → ProjectNotFound 404
           Jira 401/403                       → JiraAuthFailed 400 (with a hint to reconnect)
           network / 5xx                      → JiraUnavailable 502
      → tickets.repository.insert(user_id, project_key, issue_key, issue_url, summary, source)
 ← 201 {issue_key, issue_url, summary, project_key, created_at}
```

**Recent tickets**

```
UI  GET /api/tickets?project_key=SCRUM&limit=10
 → tickets.repository.list_recent(user_id, project_key, limit)   (local table, no Jira call)
 ← 200 [{issue_key, summary, issue_url, created_at, source}, ...]
```

## Frontend structure

Five screens, one typed API client, no global state library:

| Route | Screen | What it does |
|---|---|---|
| `/login`, `/register` | Auth | Forms; on success redirect to `/` |
| `/connect` | Connect Jira | Three fields + "Test and connect"; shows the specific error on failure; shown automatically if not connected |
| `/` | Dashboard | Connection badge, project selector, ticket form, recent tickets list (refreshes after a create) |
| `/keys` | API keys | Create (shows key once with a copy button), list, revoke; includes a ready-to-copy `curl` example |

The API client (`src/api/`) is the only module that performs HTTP calls, maps
the uniform error body to a typed error, and keeps credentials (the session
cookie) out of JavaScript entirely.

Frontend routes deliberately avoid the `/api` prefix (the keys page lives at
`/keys`, not `/api-keys`), because everything under `/api` is forwarded to
the backend by the dev proxy and by nginx.

## Running

- **Docker Compose:** two services, `backend` (uvicorn, port 8000) and
  `frontend` (nginx serving the Vite build and proxying `/api` to the backend,
  port 5173). One `docker compose up`.
- **Local:** backend with uvicorn on 8000, frontend with Vite dev server on
  5173 proxying `/api` to 8000. The README gives the commands.
