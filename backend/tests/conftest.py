"""
Test configuration.

Settings are read at import time, so the environment is prepared before the
app is imported: an isolated temporary SQLite file and throwaway secrets.
"""
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_TMP = Path(tempfile.mkdtemp(prefix="identityhub-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["APP_SECRET_KEY"] = "test-secret-key-that-is-definitely-long-enough"
os.environ["APP_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:  # runs the lifespan (creates tables)
        yield c
