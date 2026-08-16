import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import create_engine, create_session_factory
from app.core.deps import get_current_user
from app.core.exa import ExaClient
from app.core.llm.client import LLMClient
from app.core.log import configure_logging
from app.core.storage import S3Storage
from app.core.tools import ToolRegistry
from app.core.tracing import NullTracer, create_tracer, set_tracer
from app.features.agents import models as agent_models  # noqa: F401
from app.features.agents.router import router as agents_router
from app.features.auth.router import router as auth_router
from app.features.conversations import models as conversation_models  # noqa: F401
from app.features.conversations.buffer import InMemoryStreamStore
from app.features.conversations.router import router as conversations_router
from app.features.conversations.tools import WebSearchTool
from app.features.feedback.router import router as feedback_router
from app.features.kb import models as kb_models  # noqa: F401
from app.features.kb.ingestion.embed import GeminiEmbedder
from app.features.kb.router import router as kb_router
from app.features.kb.tools import KbSearchTool, QueryTableTool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log = configure_logging(settings.log_level)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    store = InMemoryStreamStore(ttl_seconds=settings.stream_buffer_ttl_seconds)
    llm = LLMClient.from_settings(settings, log=log)
    exa = ExaClient.from_settings(settings, log=log)
    embedder = GeminiEmbedder.from_settings(settings)
    storage = S3Storage.from_settings(settings)
    await storage.start()
    tracer = create_tracer(settings, log=log)
    set_tracer(tracer)
    tools = ToolRegistry(
        [
            WebSearchTool(exa),
            KbSearchTool(embedder, session_factory),
            QueryTableTool(session_factory, storage),
        ]
    )
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.stream_store = store
    app.state.llm = llm
    app.state.exa = exa
    app.state.embedder = embedder
    app.state.image_describer = llm
    app.state.storage = storage
    app.state.tools = tools
    app.state.log = log
    cleanup = asyncio.create_task(store.cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        await llm.aclose()
        await exa.aclose()
        await storage.aclose()
        await tracer.shutdown()
        set_tracer(NullTracer())
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ChatKB", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-vercel-ai-ui-message-stream"],
    )
    app.include_router(auth_router)
    app.include_router(
        conversations_router,
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        agents_router,
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        kb_router,
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(feedback_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
