# Design Decisions & Assumptions

This document records the assumptions I made and the reasoning behind the main
design decisions, organized by the functional requirement each one belongs to.
The assignment intentionally leaves room for interpretation, so wherever I had
to choose, I explain what I chose, what I rejected, and why.

Setup instructions live in [README.md](README.md).

---

## Cross-cutting technology choices

These decisions are not tied to a single functional requirement; they shape
the whole project.

### Stack: Python (FastAPI) backend + React (Vite) frontend, in one repository

**Decision: a Python backend and a React frontend, as two separate
applications inside a single repository (monorepo).**

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3, FastAPI | Input validation and typed request/response models via Pydantic; OpenAPI (Swagger) documentation generated from the code; native async for calls to Jira |
| Database | SQLite via SQLAlchemy | See the Database section below |
| Jira client | httpx | Async HTTP client; no dependency on an Atlassian SDK, so every call to Jira is explicit and reviewable |
| Password hashing | bcrypt | Industry standard |
| Credential encryption | `cryptography` (Fernet, AES-128-CBC + HMAC) | Authenticated symmetric encryption in one call; key supplied via environment |
| Frontend | React + Vite + TypeScript | Small, widely understood; Vite gives a fast dev server and a static build |
| Running | Docker Compose, plus a documented local path | Two ways to run, so at least one works on any reviewer's machine |

**Why two applications and not one.** The assignment explicitly evaluates
"clear separation between UI and backend layers". Keeping the frontend as its
own application with its own dependencies makes that separation physical:
the UI cannot import backend code, and the two communicate only over HTTP
through the same API that any other client would use. The alternative, a
backend that also renders HTML pages, would have put both layers in one
process and blurred the boundary I am being asked to demonstrate.

**Why one repository and not two.** A single `git clone` and a single command
to run everything. Two repositories would double the setup steps for the
reviewer without adding any architectural clarity.

**Why Python for the backend.** The backend holds everything that matters for
the evaluation: session handling, tenant isolation, credential encryption,
API-key authentication, and error handling around Jira. I chose the language
in which I can reason about and defend that code most precisely. FastAPI in
particular gives request validation and API documentation for free, which
directly serves requirement 4 (REST API).

**Alternative considered: Node.js + TypeScript end to end.** One language for
both layers, one toolchain, and a shared type definition for the API contract.
This is a perfectly good choice for a project of this shape, and arguably the
smoother one. I rejected it only because the backend is where the risk and
the scrutiny are, and that is where I want the strongest footing.

**Alternative considered: Next.js full-stack.** Fastest to build, but the API
routes and the UI live in the same framework and the same process, which
works against the layer separation being evaluated.

### Database: SQLite, with a one-line path to PostgreSQL

**Decision: SQLite for the POC, accessed through an ORM so that switching to
PostgreSQL is a configuration change, not a code change.**

The assignment asks for a solution that is "runnable in the easiest, most
frictionless way possible". The database is the first place that requirement
bites:

- **PostgreSQL is a server.** It runs as a separate process, listens on a port,
  and the app connects to it over the network with credentials. A reviewer
  would have to install it, start it, create a database and a user, and
  configure the connection string before seeing the app at all.
- **SQLite is a library.** The whole database is a single file in the project
  directory, created automatically on first run. The driver ships with Python.
  No installation, no background process, no credentials.

For this POC the data is small and simple (users, Jira connections, tickets
created through the app, API keys), and the write load is a handful of
requests per minute. SQLite handles that comfortably.

**Why production would use PostgreSQL instead**, and what I am consciously
giving up:

- **Concurrent writers.** SQLite locks the whole file for a write, so writes
  are serialized. PostgreSQL supports thousands of concurrent writers.
- **Horizontal scaling.** Several app instances cannot share one SQLite file.
  PostgreSQL is a central server every instance connects to.
- **Access control.** Anyone who can read the SQLite file reads everything.
  PostgreSQL has users, roles and row-level permissions.
- **Richer features.** Strict typing, JSON operators, full-text search, online
  backups and replication.

**How the switch stays cheap:** the application code never writes
SQLite-specific SQL. It works against ORM models, and the ORM generates the
dialect. The only difference between the two databases is the connection
string in `.env`:

```
DATABASE_URL=sqlite:///./identityhub.db
DATABASE_URL=postgresql://user:password@host/identityhub
```

**Why not simply add a PostgreSQL container to Docker Compose:** it would be
easy, but then the non-Docker path in the README would require installing
PostgreSQL again. I want both paths (Docker and local) to work with zero
external services.

---

## 1. Jira Integration + Authentication

### 1.1 User login to the app + logout

_To be documented._

### 1.2 Secure session management

_To be documented._

### 1.3 Multiple concurrent users without data interference (multi-tenancy)

_To be documented._

### 1.4 Ability to integrate with Jira after logon

**Decision: users connect Jira with an Atlassian API token (site URL + email +
token), not OAuth 2.0.**

Jira Cloud offers two ways for a third-party app to act on behalf of a user:

- **API token**: the user creates a token at id.atlassian.com and pastes it,
  together with their site URL and email, into the app. The app authenticates
  with HTTP Basic auth (`email:token`).
- **OAuth 2.0 (3LO)**: the app is registered in the Atlassian Developer Console,
  the user is redirected to Atlassian to grant consent, and the app receives
  short-lived access tokens plus a refresh token.

From a pure end-user UX standpoint, OAuth is the better experience: three clicks
inside the app instead of leaving it to generate and copy a token. In a
production product, OAuth is the right choice. I chose the API token for this
POC for three reasons that are not about UX:

1. **Frictionless for the reviewer.** With OAuth, whoever runs the project must
   first register their own OAuth app in the Atlassian Developer Console,
   configure a callback URL, and place a `client_id` and `client_secret` in
   `.env`. Shipping my own client secret in the repository is not an option.
   Those setup steps would land on the reviewer before they even run the app.
   With a token, they run the app and paste.

2. **Amount of code and risk within the time budget.** A correct OAuth
   implementation involves the authorization redirect, CSRF protection via a
   `state` parameter, the code-for-token exchange, resolving the `cloudId` of
   the user's site, access-token expiry after one hour, refresh-token rotation,
   and handling concurrent refreshes. Each of these is a place where a mistake
   is a real security bug, in exactly the area this assignment evaluates. The
   token approach is a few lines of Basic auth, which leaves time to do the
   credential handling itself properly.

3. **It fits the product's subject.** A Jira API token is itself a Non-Human
   Identity. The integration therefore creates an NHI, and I treat it as one:
   the token is verified against Jira before it is saved, encrypted at rest,
   never returned to the client after saving, and revocable from the UI. In
   production I would replace it with OAuth and short-lived tokens, which is
   the same lifecycle discipline IdentityHub asks its customers to apply to
   their own machine identities.

**I could have solved this with OAuth as well.** The flow is well documented
and I have described it step by step above. To keep that door open, the Jira
authentication method is isolated behind a single interface
(`JiraAuthProvider`) that the rest of the backend consumes. The token-based
provider is the only implementation today. An OAuth provider would implement
the same interface, and the ticket, project, and recent-tickets code would not
change.

**Assumptions:**

- Jira Cloud only (`*.atlassian.net`). Jira Server / Data Center is out of scope.
- One Jira connection per user. A user who wants to switch workspaces
  disconnects and reconnects.
- The user's own Jira permissions apply. If the token owner cannot create
  issues in a project, the app surfaces that error rather than working around it.

---

## 2. Create NHI Finding Ticket UI

_To be documented._

---

## 3. Recent Tickets View

_To be documented._

---

## 4. REST API

_To be documented._

---

## Bonus: NHI Blog Digest automation

_To be documented._
