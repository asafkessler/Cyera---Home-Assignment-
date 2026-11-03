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

**Decision: the app has its own simple sign-up and login (email + password),
with passwords hashed using bcrypt.**

The assignment requires login and logout but does not say where users come
from. Two options:

- **Pre-seeded users** (a fixed list created at startup). Less code, but a
  reviewer cannot create a second account to see tenant isolation for
  themselves.
- **Sign-up + login.** A few more lines, and it makes the multi-tenancy
  requirement demonstrable: open two browsers, register two users, connect
  two different Jira workspaces, and confirm that neither sees the other's
  data.

I chose sign-up + login. There is no email verification, password reset, or
SSO; those are outside the scope of a POC and are noted as production work.

**Assumptions:** the email address is the unique identifier (normalised to
lower case); passwords must be at least 8 characters; registering logs the
user in immediately, since a separate login right after sign-up adds a step
without adding security.

**Two small details that matter for security:**

- A failed login returns the same generic "invalid email or password" for an
  unknown email and for a wrong password, so the app does not reveal which
  accounts exist.
- A login attempt for an unknown email still runs a bcrypt comparison against
  a dummy hash. Without this, an unknown email would answer in microseconds
  and a known one in tens of milliseconds, and response timing alone would
  reveal which emails are registered.

### 1.2 Secure session management

**Decision: server-side sessions identified by a random opaque token stored in
an `HttpOnly`, `SameSite=Lax` cookie. Not JWT.**

- **Server-side** means the session record (user id, creation time, expiry)
  lives in the database, and the cookie carries only a random identifier. The
  server can revoke a session at any time (logout deletes the record), which
  stateless JWTs cannot do without extra machinery such as a blocklist.
- **`HttpOnly`** prevents JavaScript from reading the cookie, which neutralizes
  cookie theft through XSS.
- **`SameSite=Lax`** stops the browser from sending the cookie on cross-site
  requests, which blocks the common CSRF cases for a same-origin app.
- **`Secure`** is set when the app runs over HTTPS; in local development over
  plain HTTP it is off, and this is documented.
- Sessions expire after a fixed idle time. Logout deletes the session server
  side and clears the cookie.

**Why not JWT.** JWT is the right tool when many independent services must
verify identity without a shared store. Here there is one backend and one
database, and the ability to revoke a session instantly on logout matters
more than statelessness. JWT would have added questions about revocation and
key rotation without adding a benefit.

### 1.3 Multiple concurrent users without data interference (multi-tenancy)

**Decision: every tenant-owned table carries a `user_id`, and every query in
the data-access layer filters by the user of the current session. Tenant
isolation is enforced in one place, not in each route.**

This requirement is about **logical isolation**, not throughput: user A must
never see user B's Jira connection, tickets, or API keys, and must never be
able to create a ticket in user B's Jira. That is a correctness property of
the code and is independent of the database engine. Forgetting a `user_id`
filter leaks data in PostgreSQL exactly as it would in SQLite.

How it is enforced:

- The session resolves to exactly one user; routes receive that user as a
  dependency and never accept a user id from the request.
- Jira connections, created tickets, and API keys are all keyed by `user_id`.
- Jira credentials are decrypted only inside the Jira client, for the user
  making the request, and never cross a request boundary.
- API requests authenticated with an API key resolve to the key's owner, and
  the resulting ticket is created in that owner's Jira only.

**On SQLite and concurrency.** SQLite serializes writes (one writer at a time,
for milliseconds), while reads proceed in parallel. For a POC with a handful
of concurrent users this is invisible. Two settings make it robust: **WAL
mode** (readers do not block the writer and vice versa) and a **busy timeout**
so that a brief lock wait does not surface as an error. See the Database
section for the path to PostgreSQL if the write load ever grows.

**How this is demonstrated:** two browsers (or a normal and a private window),
two accounts, two Jira workspaces, tickets created from both; each account
sees only its own.

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

**How the connection is handled (product decisions):**

- The credentials are **verified before they are saved** by calling Jira's
  "myself" endpoint. A wrong site URL, email, or token fails immediately with
  a specific message, instead of surfacing later when the user tries to create
  a ticket.
- Connecting is a **one-time step**. On later logins the user goes straight to
  the ticket form. The UI always shows the connection status ("Connected to
  <site> as <email>" or "Not connected").
- The token is **never returned to the client** after saving, and the user can
  **disconnect** (which deletes the encrypted token) and reconnect.
- Credentials are encrypted at rest with a key supplied through the
  environment, so a copy of the database file alone does not expose tokens.

**Assumptions:**

- Jira Cloud only (`*.atlassian.net`). Jira Server / Data Center is out of scope.
- One Jira connection per user. A user who wants to switch workspaces
  disconnects and reconnects.
- The user's own Jira permissions apply. If the token owner cannot create
  issues in a project, the app surfaces that error rather than working around it.

---

## 2. Create NHI Finding Ticket UI

**Decisions (to be refined during implementation):**

- **Project selection:** the project list is fetched live from the connected
  Jira workspace, so the user picks from projects they actually have access
  to. No project keys are hard-coded.
- **Issue type:** fetched per project and selectable, defaulting to "Task".
  Jira projects differ in their issue types, so assuming "Task" exists
  everywhere would break on some workspaces.
- **Form fields:** summary and description are required, as the assignment
  states. Two small NHI-specific fields are added, **severity** and **identity
  type** (service account, API key, service principal, other), because the
  product is about NHI findings rather than generic Jira tickets. They are
  rendered into the issue description in a structured block, so no custom
  Jira fields are needed and the ticket works in any project.
- **Validation and errors:** the form validates before submitting, and every
  failure from Jira is translated into a message a user can act on (for
  example "You do not have permission to create issues in this project"
  rather than a raw HTTP 403).

---

## 3. Recent Tickets View

**Decision: the app records every ticket it creates in its own database, and
the recent-tickets view reads from that table. Each issue created in Jira is
also labelled `identityhub` for traceability on the Jira side.**

The requirement is "the 10 most recent tickets that were created from this
app, from the selected project". Two ways to know which tickets those are:

- **Query Jira** with JQL for issues carrying a label the app adds. Depends on
  Jira being reachable, on the label not being removed by a user, and on
  search indexing latency.
- **Record locally** at creation time (issue key, summary, URL, project,
  created time, owner). Fast, works when Jira is slow, and the record is
  owned by the app.

I chose the local record as the source of truth and the label as a secondary
marker. The view is filtered by the selected project and by the current user,
and it includes tickets created through the REST API as well as the form,
since both are "created from this app".

**Trade-off accepted:** if a ticket is deleted in Jira, it still appears in
the list until the app reconciles. For a POC this is acceptable and documented;
production would reconcile periodically or on click.

---

## 4. REST API

**Decision: ticket creation is implemented exactly once, as a single service
function, and both the UI endpoint and the public API endpoint call it.**

The form and the public API are two entry points into the same use case. If
each had its own implementation, they would drift: one would add the
`identityhub` label and the other would forget it, one would record the
ticket locally and the other would not, one would validate severity and the
other would accept anything. Instead, `tickets/service.py` owns the logic
(check the user's Jira connection, build the description, create the issue in
Jira, translate Jira's errors, record the ticket), and the two routers differ
only in **how the caller is authenticated**: session cookie for the UI,
API key for external systems. Both resolve to a user, and from that point on
the code path is identical.

The consequence worth stating: a ticket created by a scanner through the API
goes through the same validation, gets the same label, is recorded in the same
table, appears in the same recent-tickets view, and is isolated to the same
tenant as a ticket created by a person in the form. Multi-tenancy and
consistency are properties of one function, not of each endpoint.

**Further decisions (to be refined during implementation):**

- **Per-user API keys.** A user generates a key from the UI. The key is shown
  **once**, and only a hash of it is stored, so a database leak does not leak
  usable keys. Keys can be revoked from the UI. A request authenticated with a
  key acts as the key's owner, which is how multi-tenancy carries over to the
  API: a scanner creates tickets only in the Jira of the user who issued the
  key.
- **Transport:** the key is sent in an `X-API-Key` header, never in the URL,
  so it does not end up in server logs or browser history.
- **Versioned public prefix:** external endpoints live under `/api/v1/`,
  separate from the internal endpoints the UI uses. Versioning in the path is
  a statement that the contract will be kept backward compatible.
- **The request names the project.** External callers must say which Jira
  project to create the ticket in; there is no implicit "current project" for
  a machine client.
- **Status codes and errors:** `201` on creation with the issue key and URL,
  `400`/`422` on validation failures with the offending field named, `401`
  on a missing or invalid key, `404` on an unknown project, and `502` when
  Jira itself fails, with Jira's message passed through. All errors share one
  JSON shape (`code`, `message`, `details`).
- **OpenAPI / Swagger documentation.** The API is documented at `/docs`
  (interactive) and `/redoc`, generated from the typed request and response
  models so the documentation cannot drift from the code. The API-key scheme
  is declared, so the "Authorize" button works and the reviewer can create a
  real ticket from the browser. Each field has a description and a realistic
  NHI example; public and internal endpoints are grouped under separate tags.

---

## Bonus: NHI Blog Digest automation

**Decisions (to be refined during implementation):**

- **It goes through the app's REST API**, authenticated with an API key, like
  any external system would. The automation knows nothing about the database
  or the Jira credentials; it is the first client of requirement 4. The
  alternative, calling Jira directly, would duplicate the Jira code and bypass
  everything the app enforces.
- **Trigger:** a GitHub Actions workflow on a schedule, plus a manual
  command for demonstrations.
- **AI summary requires a provider key by design.** The summary is produced by
  the Claude API, and the automation needs an `ANTHROPIC_API_KEY`. Without
  one it stops with a clear message explaining what is missing. There is no
  silent fallback to a non-AI summary, because the assignment asks for an
  AI-powered summary and a degraded output would not meet it.
- **Why not a local model.** Bundling a local model would require a
  multi-gigabyte download and extra tooling on the reviewer's machine, which
  is far more friction than a key. The reviewer uses their own key; my own
  key is never shared or committed. In the scheduled workflow the key is a
  GitHub Secret, and the run logs are the evidence that the pipeline works.
- **Idempotency:** the automation remembers which post it already reported,
  so repeated runs do not create duplicate tickets for the same post.
- **Tickets created by the automation appear in the app's recent-tickets
  view automatically**, since they are created through the API and recorded
  like any other.

---

## Secrets and credential policy (applies everywhere)

- **No secret is ever committed.** `.env` is ignored by git; `.env.example`
  is committed with variable names only.
- **`.env` holds app-level secrets only:** the session signing secret, the
  encryption key for stored Jira credentials, and, for the bonus automation,
  the Claude API key.
- **Jira credentials are user data, not configuration.** They are entered in
  the UI, verified, encrypted, and stored per user. They never appear in
  `.env`, which is what allows several users with different Jira workspaces to
  share one deployment.
- **API keys are stored hashed** and shown to the user exactly once.
- **Secrets are never pasted into chats, emails, or tickets.** Reviewers use
  their own Jira account and their own AI provider key; the README says so.
