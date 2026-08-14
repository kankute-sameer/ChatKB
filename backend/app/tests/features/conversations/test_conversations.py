import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from app.core.config import get_settings
from app.core.db import Base
from app.features.conversations.schemas import CreateResponseRequest, UIMessage
from app.features.conversations.service import ConversationService
from app.main import create_app
from app.tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD, TEST_USERNAME
from app.tests.fakes import FakeLLM
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext

USER_PARTS = [{"type": "text", "text": "Hi there", "state": "done"}]


def _auth_env(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    hashed = CryptContext(schemes=["bcrypt"]).hash(TEST_PASSWORD)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("AUTH_USERS", json.dumps({TEST_USERNAME: hashed}))
    monkeypatch.setenv("CORS_ORIGINS", json.dumps(["http://localhost:5173"]))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    get_settings.cache_clear()


@pytest.fixture
async def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_llm: FakeLLM
) -> AsyncIterator[FastAPI]:
    _auth_env(monkeypatch, tmp_path / "conv.db")
    application = create_app()
    async with application.router.lifespan_context(application):
        async with application.state.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        application.state.llm = fake_llm
        yield application
    get_settings.cache_clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


async def _token(client: AsyncClient) -> str:
    response = await client.post(
        "/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_conversation(client: AsyncClient, token: str) -> str:
    response = await client.post("/v1/conversations", headers=_headers(token))
    assert response.status_code == 200
    return str(response.json()["id"])


async def _start_generation(
    app: FastAPI,
    conversation_id: str,
    message_id: str,
) -> str:
    async with app.state.session_factory() as session:
        service = ConversationService(
            session,
            app.state.stream_store,
            app.state.llm,
            app.state.session_factory,
        )
        await service.start_response(
            TEST_USERNAME,
            CreateResponseRequest(
                id=conversation_id,
                message=UIMessage(
                    id=message_id,
                    role="user",
                    parts=USER_PARTS,
                ),
            ),
        )
    detail = await _get_conversation_state(app, conversation_id)
    active_id = detail["active_response_id"]
    assert isinstance(active_id, str)
    return active_id


async def _get_conversation_state(
    app: FastAPI, conversation_id: str
) -> dict[str, Any]:
    async with app.state.session_factory() as session:
        from app.features.conversations.repository import ConversationRepository

        repo = ConversationRepository(session)
        conversation = await repo.get(conversation_id)
        assert conversation is not None
        return {
            "active_response_id": conversation.active_response_id,
            "messages": conversation.messages,
        }


async def _wait_until_idle(
    client: AsyncClient, token: str, conversation_id: str
) -> dict[str, object]:
    import asyncio

    detail: dict[str, object] = {}
    for _ in range(100):
        response = await client.get(
            f"/v1/conversations/{conversation_id}",
            headers=_headers(token),
        )
        assert response.status_code == 200
        detail = response.json()
        if detail.get("activeResponseId") is None:
            return detail
        await asyncio.sleep(0.02)
    raise AssertionError(f"generation did not finish: {detail}")


def _assistant_text(detail: dict[str, object]) -> str:
    messages = detail.get("messages")
    assert isinstance(messages, list)
    chunks: list[str] = []
    for message in messages:
        assert isinstance(message, dict)
        if message.get("role") != "assistant":
            continue
        parts = message.get("parts")
        assert isinstance(parts, list)
        for part in parts:
            assert isinstance(part, dict)
            if part.get("type") == "text":
                chunks.append(str(part.get("text") or ""))
    return "".join(chunks)


@pytest.mark.asyncio
async def test_post_responses_streams_and_persists(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    del fake_llm
    token = await _token(client)
    conversation_id = await _create_conversation(client, token)
    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_http",
                "role": "user",
                "parts": USER_PARTS,
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    assert '"delta":"Hello"' in response.text
    assert '"delta":" world"' in response.text
    assert "data: [DONE]" in response.text
    detail = await _wait_until_idle(client, token, conversation_id)
    assert _assistant_text(detail) == "Hello world"


@pytest.mark.asyncio
async def test_generation_survives_reader_disconnect(
    client: AsyncClient, app: FastAPI, fake_llm: FakeLLM
) -> None:
    token = await _token(client)
    conversation_id = await _create_conversation(client, token)
    fake_llm.continue_event.clear()
    response_id = await _start_generation(app, conversation_id, "msg_user_1")
    task = app.state.stream_store.get_task(response_id)
    assert task is not None
    fake_llm.continue_event.set()
    await task
    detail = await _wait_until_idle(client, token, conversation_id)
    assert _assistant_text(detail) == "Hello world"
    assert detail.get("activeResponseId") is None


@pytest.mark.asyncio
async def test_resync_on_eviction_replays_final_message(
    client: AsyncClient, app: FastAPI
) -> None:
    token = await _token(client)
    conversation_id = await _create_conversation(client, token)
    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_2",
                "role": "user",
                "parts": USER_PARTS,
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200
    await _wait_until_idle(client, token, conversation_id)
    store = app.state.stream_store
    for response_id in list(store._entries):
        store.evict(response_id)

    replay = await client.get(
        f"/v1/conversations/{conversation_id}/stream",
        params={"activeResponseId": "resp_evicted"},
        headers=_headers(token),
    )
    assert replay.status_code == 200
    body = replay.text
    assert "Hello world" in body
    assert '"type":"text-start"' in body
    assert '"type":"text-delta"' in body
    assert '"type":"text-end"' in body
    assert '"type":"finish"' in body


@pytest.mark.asyncio
async def test_stream_returns_204_when_no_active_response(
    client: AsyncClient,
) -> None:
    token = await _token(client)
    conversation_id = await _create_conversation(client, token)
    response = await client.get(
        f"/v1/conversations/{conversation_id}/stream",
        headers=_headers(token),
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_stop_with_stale_active_stream_id_is_noop(
    client: AsyncClient, app: FastAPI, fake_llm: FakeLLM
) -> None:
    token = await _token(client)
    conversation_id = await _create_conversation(client, token)
    fake_llm.continue_event.clear()
    response_id = await _start_generation(app, conversation_id, "msg_user_3")

    stop = await client.post(
        f"/v1/conversations/{conversation_id}/stop",
        headers=_headers(token),
        json={"activeStreamId": "resp_stale"},
    )
    assert stop.status_code == 200
    assert stop.json() == {"success": True}

    still_live = await client.get(
        f"/v1/conversations/{conversation_id}",
        headers=_headers(token),
    )
    assert still_live.json()["activeResponseId"] == response_id

    fake_llm.continue_event.set()
    task = app.state.stream_store.get_task(response_id)
    assert task is not None
    await task
    detail = await _wait_until_idle(client, token, conversation_id)
    assert _assistant_text(detail) == "Hello world"
