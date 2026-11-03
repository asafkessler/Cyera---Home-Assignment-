"""
Application settings, loaded from environment variables (and a .env file).

Everything the app needs from its environment is declared here, once, with a
type and a default. Nothing else in the codebase reads os.environ directly.
"""
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# <repo root>/backend/app/config.py  ->  parents[2] is the repo root
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The root .env is the single place for local configuration.
        # A backend/.env is also honoured, for people who run the backend alone.
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"

    # SQLAlchemy URL. SQLite file by default; swap for PostgreSQL in production.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'identityhub.db'}"

    # Required secrets. No defaults on purpose: a missing secret must fail
    # loudly at startup, never silently fall back to a known value.
    app_secret_key: str
    app_encryption_key: str

    # Sessions
    session_ttl_hours: int = 24 * 7
    session_cookie_name: str = "identityhub_session"
    cookie_secure: bool = False  # set True behind HTTPS

    # Origins allowed to call the API from a browser (the Vite dev server).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("app_encryption_key")
    @classmethod
    def _must_be_a_fernet_key(cls, value: str) -> str:
        try:
            Fernet(value.encode())
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "APP_ENCRYPTION_KEY is not a valid Fernet key. "
                "Generate one with:  python -m app.keys"
            ) from exc
        return value

    @field_validator("app_secret_key")
    @classmethod
    def _must_be_long_enough(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError(
                "APP_SECRET_KEY must be at least 32 characters. "
                "Generate one with:  python -m app.keys"
            )
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them (cached)."""
    try:
        return Settings()
    except Exception as exc:  # pydantic.ValidationError, surfaced as a readable message
        raise SystemExit(
            "\nConfiguration error:\n"
            f"{exc}\n\n"
            "Copy .env.example to .env in the repository root and fill in the values.\n"
            "Secrets can be generated with:  python -m app.keys\n"
        ) from exc
