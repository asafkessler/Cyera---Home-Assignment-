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

_To be documented once the stack is finalized._

## Running the project

_To be documented._

### Option A: Docker

_To be documented._

### Option B: Local (without Docker)

_To be documented._

## Configuration (`.env`)

_To be documented. A committed `.env.example` will list every variable._

## Connecting your Jira workspace

_To be documented._

## Using the REST API

_To be documented. Will include a `curl` example._

## Running the Blog Digest automation (bonus)

_To be documented._

## Project structure

_To be documented._

## Security notes

_To be documented._
