import json
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from app.core.config import get_settings
from app.main import create_app

TEST_USERNAME = "alice"
TEST_PASSWORD = "test-password-123"
TEST_JWT_SECRET = "test-jwt-secret-not-for-production"


@pytest.fixture(autouse=True)
def aws_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET", "test-chatkb-bucket")


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Generator[TestClient, None, None]:
    hashed = CryptContext(schemes=["bcrypt"]).hash(TEST_PASSWORD)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("AUTH_USERS", json.dumps({TEST_USERNAME: hashed}))
    monkeypatch.setenv("CORS_ORIGINS", json.dumps(["http://localhost:5173"]))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
