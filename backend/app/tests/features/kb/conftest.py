import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.db import Base
from app.main import create_app
from app.tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD, TEST_USERNAME
from app.tests.fakes import FakeEmbedder, FakeLLM, FakeStorage


def _auth_env(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    hashed = CryptContext(schemes=["bcrypt"]).hash(TEST_PASSWORD)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("AUTH_USERS", json.dumps({TEST_USERNAME: hashed}))
    monkeypatch.setenv("CORS_ORIGINS", json.dumps(["http://localhost:5173"]))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()


@pytest.fixture
async def fake_llm() -> FakeLLM:
    return FakeLLM(title="A short index summary.")


@pytest.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_llm: FakeLLM
) -> AsyncIterator[FastAPI]:
    _auth_env(monkeypatch, tmp_path / "kb.db")
    application = create_app()
    async with application.router.lifespan_context(application):
        async with application.state.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        application.state.llm = fake_llm
        application.state.embedder = FakeEmbedder()
        application.state.storage = FakeStorage()
        yield application
    get_settings.cache_clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
