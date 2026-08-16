import pytest

from app.core import db


@pytest.mark.asyncio
async def test_plain_postgresql_url_uses_asyncpg_and_registers_pgvector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registered = []
    monkeypatch.setattr(db, "_register_pgvector", registered.append)

    engine = db.create_engine("postgresql://user:pass@localhost:5432/chatkb")
    try:
        assert engine.url.drivername == "postgresql+asyncpg"
        assert registered == [engine]
    finally:
        await engine.dispose()
