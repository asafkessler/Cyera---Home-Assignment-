"""
FastAPI application factory.

Wires together configuration, the database, error handling, CORS, API
documentation, and the feature routers. Routers are added per feature module
as they are implemented.
"""
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.auth.router import router as auth_router
from app.jira.router import router as jira_router
from app.tickets.router import router as tickets_router
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.db import init_db

API_DESCRIPTION = """
IdentityHub's Jira integration lets users report **Non-Human Identity (NHI)
findings** (stale service accounts, overprivileged keys, expiring credentials)
as Jira tickets in their own workspace.

Two kinds of clients use this API:

* **The web UI**, authenticated with a session cookie (endpoints tagged *Auth*,
  *Jira*, *Tickets*, *API keys*).
* **External systems** such as scanners and CI/CD pipelines, authenticated with
  a per-user API key in the `X-API-Key` header (endpoints tagged *Public API v1*).

All errors share one shape:

```json
{"error": {"code": "jira_not_connected", "message": "...", "details": {}}}
```
"""

TAGS_METADATA = [
    {"name": "System", "description": "Health and metadata."},
    {"name": "Public API v1", "description": "For scanners, CI/CD pipelines and other external systems. Requires `X-API-Key`."},
    {"name": "Auth", "description": "Account registration, login, logout."},
    {"name": "Jira", "description": "Connect a Jira Cloud workspace and browse its projects."},
    {"name": "Tickets", "description": "Create NHI finding tickets and list recent ones."},
    {"name": "API keys", "description": "Manage API keys for the public API."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="IdentityHub Jira Integration",
        version=__version__,
        description=API_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # the session cookie must travel with requests
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    system = APIRouter(prefix="/api", tags=["System"])

    @system.get("/health", summary="Health check")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "environment": settings.app_env}

    app.include_router(system)
    app.include_router(auth_router)
    app.include_router(jira_router)
    app.include_router(tickets_router)
    return app


app = create_app()
