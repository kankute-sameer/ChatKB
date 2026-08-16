import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.core.db import Base
from app.core.llm.types import StreamEvent
from app.features.agents.appearance import APPEARANCE_PRESETS
from app.features.agents.builder import BUILDER_AGENT_ID
from app.features.agents.wrapper import BASE_INSTRUCTIONS, build_system_prompt
from app.features.kb.retrieve import ChunkHit
from app.features.kb.tools import KbSearchTool
from app.main import create_app
from app.tests.conftest import TEST_JWT_SECRET, TEST_PASSWORD, TEST_USERNAME
from app.tests.fakes import FakeEmbedder, FakeLLM
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from passlib.context import CryptContext

USER_PARTS = [{"type": "text", "text": "Make it a research assistant", "state": "done"}]


def _auth_env(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    hashed = CryptContext(schemes=["bcrypt"]).hash(TEST_PASSWORD)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("AUTH_USERS", json.dumps({TEST_USERNAME: hashed}))
    monkeypatch.setenv("CORS_ORIGINS", json.dumps(["http://localhost:5173"]))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("EXA_API_KEY", "test-exa-key")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    get_settings.cache_clear()


@pytest.fixture
async def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
async def app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fake_llm: FakeLLM
) -> AsyncIterator[FastAPI]:
    _auth_env(monkeypatch, tmp_path / "agents.db")
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
    return {"Authorization": "Bearer " + token}


async def _create_agent(
    client: AsyncClient, token: str, name: str = "Researcher"
) -> dict[str, object]:
    response = await client.post(
        "/v1/agents",
        headers=_headers(token),
        json={"name": name, "description": "Finds sources"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    return body


@pytest.mark.asyncio
async def test_create_agent_assigns_preset_and_empty_instructions(
    client: AsyncClient,
) -> None:
    token = await _token(client)
    body = await _create_agent(client, token)
    assert body["name"] == "Researcher"
    assert body["description"] == "Finds sources"
    assert body["instructions"] == ""
    assert body["visibility"] == "personal"
    assert body["isBuilder"] is False
    assert str(body["id"]).startswith("agt_")
    appearance = body["appearance"]
    assert isinstance(appearance, dict)
    assert appearance["type"] == "preset"
    assert appearance["key"] in APPEARANCE_PRESETS
    assert body["connectors"] == ["web_search"]


@pytest.mark.asyncio
async def test_remove_web_search_connector_drops_tool(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    token = await _token(client)
    created = await _create_agent(client, token)
    agent_id = str(created["id"])

    patched = await client.patch(
        f"/v1/agents/{agent_id}",
        headers=_headers(token),
        json={"connectors": [], "instructions": "No search."},
    )
    assert patched.status_code == 200
    assert patched.json()["connectors"] == []

    chat = await client.post(
        "/v1/conversations",
        headers=_headers(token),
        json={"agentId": agent_id},
    )
    assert chat.status_code == 200
    conversation_id = str(chat.json()["id"])

    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_no_search",
                "role": "user",
                "parts": USER_PARTS,
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200
    assert fake_llm.calls
    tool_names = {
        item.get("name")
        for item in (fake_llm.tools_seen[0] or [])
        if isinstance(item, dict)
    }
    assert "web_search" not in tool_names
    system = str(fake_llm.calls[0][0].get("content") or "")
    assert "When you use `web_search`" not in system


@pytest.mark.asyncio
async def test_agent_crud_and_instructions_endpoint(client: AsyncClient) -> None:
    token = await _token(client)
    created = await _create_agent(client, token, name="Ops")
    agent_id = str(created["id"])

    listed = await client.get("/v1/agents", headers=_headers(token))
    assert listed.status_code == 200
    rows = listed.json()
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0]["id"] == agent_id

    patched = await client.patch(
        f"/v1/agents/{agent_id}",
        headers=_headers(token),
        json={"instructions": "Answer with citations.", "name": "Ops Bot"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Ops Bot"
    assert patched.json()["instructions"] == "Answer with citations."

    instructions = await client.get(
        f"/v1/agents/{agent_id}/instructions",
        headers=_headers(token),
    )
    assert instructions.status_code == 200
    assert instructions.json() == {"instructions": "Answer with citations."}

    deleted = await client.delete(f"/v1/agents/{agent_id}", headers=_headers(token))
    assert deleted.status_code == 204
    missing = await client.get(f"/v1/agents/{agent_id}", headers=_headers(token))
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_agent_collections_replace_set_and_validate_ids(
    client: AsyncClient,
) -> None:
    token = await _token(client)
    agent = await _create_agent(client, token)
    collection_ids: list[str] = []
    for name in ("Resumes", "Policies"):
        created = await client.post(
            "/v1/collections",
            headers=_headers(token),
            json={"name": name},
        )
        assert created.status_code == 200
        collection_ids.append(str(created.json()["id"]))

    attached = await client.put(
        f"/v1/agents/{agent['id']}/collections",
        headers=_headers(token),
        json={"collectionIds": collection_ids},
    )
    assert attached.status_code == 200
    assert [row["id"] for row in attached.json()] == collection_ids

    replaced = await client.put(
        f"/v1/agents/{agent['id']}/collections",
        headers=_headers(token),
        json={"collectionIds": [collection_ids[1]]},
    )
    assert replaced.status_code == 200
    assert [row["id"] for row in replaced.json()] == [collection_ids[1]]

    invalid = await client.put(
        f"/v1/agents/{agent['id']}/collections",
        headers=_headers(token),
        json={"collectionIds": ["col_not_owned"]},
    )
    assert invalid.status_code == 400
    listed = await client.get(
        f"/v1/agents/{agent['id']}/collections",
        headers=_headers(token),
    )
    assert [row["id"] for row in listed.json()] == [collection_ids[1]]


@pytest.mark.asyncio
async def test_list_excludes_builder_and_builder_is_not_user_owned(
    client: AsyncClient,
) -> None:
    token = await _token(client)
    agent = await _create_agent(client, token)
    await client.post(
        "/v1/build-sessions",
        headers=_headers(token),
        json={"targetAgentId": str(agent["id"])},
    )
    listed = await client.get("/v1/agents", headers=_headers(token))
    ids = {row["id"] for row in listed.json()}
    assert BUILDER_AGENT_ID not in ids
    hidden = await client.get(f"/v1/agents/{BUILDER_AGENT_ID}", headers=_headers(token))
    assert hidden.status_code == 404


@pytest.mark.asyncio
async def test_conversation_with_agent_uses_wrapped_system_prompt(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    token = await _token(client)
    agent = await _create_agent(client, token)
    agent_id = str(agent["id"])
    await client.patch(
        f"/v1/agents/{agent_id}",
        headers=_headers(token),
        json={"instructions": "Always greet with ping."},
    )
    created = await client.post(
        "/v1/conversations",
        headers=_headers(token),
        json={"agentId": agent_id},
    )
    assert created.status_code == 200
    assert created.json()["targetAgentId"] == agent_id
    assert created.json()["sessionType"] == "chat"
    conversation_id = str(created.json()["id"])

    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_agent",
                "role": "user",
                "parts": USER_PARTS,
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200
    assert fake_llm.calls
    system = fake_llm.calls[0][0]
    assert system.get("role") == "system"
    content = str(system.get("content") or "")
    assert "Always greet with ping." in content
    assert content.startswith(BASE_INSTRUCTIONS[:40])
    assert "table named `data`" in content
    tool_names = {
        item.get("name")
        for item in (fake_llm.tools_seen[0] or [])
        if isinstance(item, dict)
    }
    assert "web_search" in tool_names
    assert "query_table" in tool_names
    assert "get_agent_setup" not in tool_names


@pytest.mark.asyncio
async def test_attached_collections_scope_kb_tool_and_persist_document_source(
    client: AsyncClient,
    app: FastAPI,
    fake_llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await _token(client)
    agent = await _create_agent(client, token)
    collection = await client.post(
        "/v1/collections",
        headers=_headers(token),
        json={"name": "Resume"},
    )
    collection_id = str(collection.json()["id"])
    attached = await client.put(
        f"/v1/agents/{agent['id']}/collections",
        headers=_headers(token),
        json={"collectionIds": [collection_id]},
    )
    assert attached.status_code == 200

    seen: dict[str, object] = {}

    async def fake_search(
        query: str,
        collection_ids: list[str],
        **kwargs: object,
    ) -> list[ChunkHit]:
        seen["query"] = query
        seen["collection_ids"] = collection_ids
        return [
            ChunkHit(
                chunk_id="chunk_resume",
                file_id="file_resume",
                collection_id=collection_id,
                text="Five years of Python experience.",
                section_header="Experience",
                page=2,
                anchor="experience-1",
                bbox=[0.1, 0.2, 0.8, 0.4],
                filename="resume.pdf",
                mime_type="application/pdf",
                score=0.03,
            )
        ]

    monkeypatch.setattr("app.features.kb.tools.hybrid_search", fake_search)
    app.state.tools.register(
        KbSearchTool(FakeEmbedder(), app.state.session_factory)
    )
    fake_llm.rounds = [
        [
            StreamEvent(
                type="tool-input-start",
                toolCallId="call_kb",
                toolName="kb_search",
                providerExecuted=True,
            ),
            StreamEvent(
                type="tool-input-available",
                toolCallId="call_kb",
                toolName="kb_search",
                input={"query": "Python experience"},
                providerExecuted=True,
            ),
        ],
        [
            StreamEvent(type="text-start", id="text_kb"),
            StreamEvent(type="text-delta", id="text_kb", delta="Found it."),
            StreamEvent(type="text-end", id="text_kb"),
        ],
    ]

    conversation = await client.post(
        "/v1/conversations",
        headers=_headers(token),
        json={"agentId": agent["id"]},
    )
    conversation_id = str(conversation.json()["id"])
    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_kb",
                "role": "user",
                "parts": USER_PARTS,
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200
    assert seen == {
        "query": "Python experience",
        "collection_ids": [collection_id],
    }
    loaded = await client.get(
        f"/v1/conversations/{conversation_id}",
        headers=_headers(token),
    )
    parts = loaded.json()["messages"][-1]["parts"]
    document = next(part for part in parts if part["type"] == "source-document")
    assert document["filename"] == "resume.pdf"
    assert document["page"] == 2


@pytest.mark.asyncio
async def test_build_session_runs_builder_tools_against_target(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    token = await _token(client)
    agent = await _create_agent(client, token, name="Draft")
    agent_id = str(agent["id"])

    first = await client.post(
        "/v1/build-sessions",
        headers=_headers(token),
        json={"targetAgentId": agent_id},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["resumed"] is False
    assert payload["targetAgent"]["id"] == agent_id
    conversation_id = str(payload["conversation"]["id"])
    assert payload["conversation"]["sessionType"] == "build"
    assert payload["conversation"]["targetAgentId"] == agent_id

    second = await client.post(
        "/v1/build-sessions",
        headers=_headers(token),
        json={"targetAgentId": agent_id},
    )
    assert second.status_code == 200
    assert second.json()["resumed"] is True
    assert second.json()["conversation"]["id"] == conversation_id

    chats = await client.get("/v1/conversations", headers=_headers(token))
    assert chats.json() == []

    fake_llm.rounds = [
        [
            StreamEvent(
                type="tool-input-start",
                toolCallId="call_setup",
                toolName="get_agent_setup",
                providerExecuted=True,
            ),
            StreamEvent(
                type="tool-input-available",
                toolCallId="call_setup",
                toolName="get_agent_setup",
                input={},
                providerExecuted=True,
            ),
        ],
        [
            StreamEvent(
                type="tool-input-start",
                toolCallId="call_write",
                toolName="update_agent_instructions",
                providerExecuted=True,
            ),
            StreamEvent(
                type="tool-input-available",
                toolCallId="call_write",
                toolName="update_agent_instructions",
                input={"instructions": "You research primary sources first."},
                providerExecuted=True,
            ),
        ],
        [
            StreamEvent(type="text-start", id="text_build"),
            StreamEvent(
                type="text-delta", id="text_build", delta="Instructions updated."
            ),
            StreamEvent(type="text-end", id="text_build"),
        ],
    ]

    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_build",
                "role": "user",
                "parts": USER_PARTS,
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200
    assert fake_llm.tools_seen
    first_tools = {
        item.get("name")
        for item in (fake_llm.tools_seen[0] or [])
        if isinstance(item, dict)
    }
    assert first_tools == {
        "get_agent_setup",
        "update_agent_instructions",
        "update_agent_metadata",
        "list_knowledge_bases",
        "attach_knowledge_bases",
    }
    system = str(fake_llm.calls[0][0].get("content") or "")
    assert "# Agent Creator" in system
    assert system.startswith(BASE_INSTRUCTIONS[:40])

    loaded = await client.get(f"/v1/agents/{agent_id}", headers=_headers(token))
    assert loaded.json()["instructions"] == "You research primary sources first."


@pytest.mark.asyncio
async def test_build_session_can_attach_relevant_knowledge_bases(
    client: AsyncClient, fake_llm: FakeLLM
) -> None:
    token = await _token(client)
    agent = await _create_agent(client, token, name="Resume screener")
    agent_id = str(agent["id"])

    resumes = await client.post(
        "/v1/collections",
        headers=_headers(token),
        json={
            "name": "Candidate resumes",
            "description": "PDF resumes for hiring",
        },
    )
    assert resumes.status_code == 200
    resumes_id = str(resumes.json()["id"])

    recipes = await client.post(
        "/v1/collections",
        headers=_headers(token),
        json={
            "name": "Kitchen recipes",
            "description": "Cooking notes",
        },
    )
    assert recipes.status_code == 200

    session = await client.post(
        "/v1/build-sessions",
        headers=_headers(token),
        json={"targetAgentId": agent_id},
    )
    assert session.status_code == 200
    conversation_id = str(session.json()["conversation"]["id"])

    fake_llm.rounds = [
        [
            StreamEvent(
                type="tool-input-start",
                toolCallId="call_list",
                toolName="list_knowledge_bases",
                providerExecuted=True,
            ),
            StreamEvent(
                type="tool-input-available",
                toolCallId="call_list",
                toolName="list_knowledge_bases",
                input={},
                providerExecuted=True,
            ),
        ],
        [
            StreamEvent(
                type="tool-input-start",
                toolCallId="call_attach",
                toolName="attach_knowledge_bases",
                providerExecuted=True,
            ),
            StreamEvent(
                type="tool-input-available",
                toolCallId="call_attach",
                toolName="attach_knowledge_bases",
                input={"collection_ids": [resumes_id]},
                providerExecuted=True,
            ),
        ],
        [
            StreamEvent(type="text-start", id="text_kb"),
            StreamEvent(
                type="text-delta",
                id="text_kb",
                delta="Attached Candidate resumes. Remove it if you do not want it.",
            ),
            StreamEvent(type="text-end", id="text_kb"),
        ],
    ]

    response = await client.post(
        "/v1/responses",
        headers=_headers(token),
        json={
            "id": conversation_id,
            "message": {
                "id": "msg_user_kb",
                "role": "user",
                "parts": [
                    {
                        "type": "text",
                        "text": "Screen candidates using our resume library",
                        "state": "done",
                    }
                ],
            },
            "stream": True,
            "trigger": "submit-message",
        },
    )
    assert response.status_code == 200

    attached = await client.get(
        f"/v1/agents/{agent_id}/collections",
        headers=_headers(token),
    )
    assert attached.status_code == 200
    assert [row["id"] for row in attached.json()] == [resumes_id]


def test_build_system_prompt_concatenates_base_and_instructions() -> None:
    class _Agent:
        instructions = "Be terse."

    prompt = build_system_prompt(_Agent())  # type: ignore[arg-type]
    assert prompt == f"{BASE_INSTRUCTIONS}\n\nBe terse."
