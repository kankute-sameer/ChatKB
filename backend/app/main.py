import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import create_engine, create_session_factory
from app.core.deps import get_current_user
from app.core.llm.client import LLMClient
from app.features.auth.router import router as auth_router
from app.features.conversations import models as conversation_models  # noqa: F401
from app.features.conversations.buffer import InMemoryStreamStore
from app.features.conversations.router import router as conversations_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    store = InMemoryStreamStore(ttl_seconds=settings.stream_buffer_ttl_seconds)
    llm = LLMClient.from_settings(settings)
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.stream_store = store
    app.state.llm = llm
    cleanup = asyncio.create_task(store.cleanup_loop())
    try:
        yield
    finally:
        cleanup.cancel()
        await llm.aclose()
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
