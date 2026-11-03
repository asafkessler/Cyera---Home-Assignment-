# Design Decisions & Assumptions

This document records the assumptions I made and the reasoning behind the main
design decisions, organized by the functional requirement each one belongs to.
The assignment intentionally leaves room for interpretation, so wherever I had
to choose, I explain what I chose, what I rejected, and why.

Setup instructions live in [README.md](README.md).

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
