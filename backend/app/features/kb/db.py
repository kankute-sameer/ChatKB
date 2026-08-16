from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.kb.models import AgentCollection, Collection, KbChunk, KbFile


class KbRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_collection(self, collection: Collection) -> Collection:
        self.session.add(collection)
        await self.session.flush()
        return collection

    async def get_collection(self, collection_id: str) -> Collection | None:
        return await self.session.get(Collection, collection_id)

    async def get_collection_for_update(
        self,
        collection_id: str,
    ) -> Collection | None:
        result = await self.session.execute(
            select(Collection)
            .where(Collection.id == collection_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_owned_collection(
        self, collection_id: str, owner_id: str
    ) -> Collection | None:
        result = await self.session.execute(
            select(Collection)
            .options(selectinload(Collection.files))
            .where(Collection.id == collection_id, Collection.owner_id == owner_id)
        )
        return result.scalar_one_or_none()

    async def list_collections(self, owner_id: str) -> list[Collection]:
        result = await self.session.execute(
            select(Collection)
            .where(Collection.owner_id == owner_id)
            .order_by(Collection.updated_at.desc())
        )
        return list(result.scalars().all())

    async def delete_collection(self, collection: Collection) -> None:
        await self.session.delete(collection)
        await self.session.flush()

    async def create_file(self, kb_file: KbFile) -> KbFile:
        self.session.add(kb_file)
        await self.session.flush()
        return kb_file

    async def get_file(self, file_id: str) -> KbFile | None:
        return await self.session.get(KbFile, file_id)

    async def get_file_in_collection(
        self, file_id: str, collection_id: str
    ) -> KbFile | None:
        result = await self.session.execute(
            select(KbFile).where(
                KbFile.id == file_id,
                KbFile.collection_id == collection_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_files(self, collection_id: str) -> list[KbFile]:
        result = await self.session.execute(
            select(KbFile)
            .where(KbFile.collection_id == collection_id)
            .order_by(KbFile.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_ready_files(self, collection_id: str) -> list[KbFile]:
        result = await self.session.execute(
            select(KbFile)
            .where(
                KbFile.collection_id == collection_id,
                KbFile.status == "ready",
            )
            .order_by(KbFile.filename.asc(), KbFile.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete_file(self, kb_file: KbFile) -> None:
        await self.session.delete(kb_file)
        await self.session.flush()

    async def replace_chunks(self, file_id: str, chunks: list[KbChunk]) -> None:
        await self.session.execute(delete(KbChunk).where(KbChunk.file_id == file_id))
        self.session.add_all(chunks)
        await self.session.flush()

    async def touch(self, row: Collection | KbFile) -> None:
        row.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def get_agent_collection_ids(self, agent_id: str) -> list[str]:
        result = await self.session.execute(
            select(AgentCollection.collection_id)
            .where(AgentCollection.agent_id == agent_id)
            .order_by(AgentCollection.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_collection_agent_ids(self, collection_id: str) -> list[str]:
        result = await self.session.execute(
            select(AgentCollection.agent_id)
            .where(AgentCollection.collection_id == collection_id)
            .order_by(AgentCollection.created_at.asc())
        )
        return list(result.scalars().all())

    async def attach_agent_collection(
        self,
        agent_id: str,
        collection_id: str,
    ) -> None:
        existing = await self.session.get(
            AgentCollection,
            {"agent_id": agent_id, "collection_id": collection_id},
        )
        if existing is not None:
            return
        self.session.add(
            AgentCollection(
                agent_id=agent_id,
                collection_id=collection_id,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def detach_agent_collection(
        self,
        agent_id: str,
        collection_id: str,
    ) -> None:
        await self.session.execute(
            delete(AgentCollection).where(
                AgentCollection.agent_id == agent_id,
                AgentCollection.collection_id == collection_id,
            )
        )
        await self.session.flush()

    async def set_agent_collections(self, agent_id: str, ids: list[str]) -> None:
        await self.session.execute(
            delete(AgentCollection).where(AgentCollection.agent_id == agent_id)
        )
        now = datetime.now(UTC)
        seen: set[str] = set()
        for collection_id in ids:
            if collection_id in seen:
                continue
            seen.add(collection_id)
            self.session.add(
                AgentCollection(
                    agent_id=agent_id,
                    collection_id=collection_id,
                    created_at=now,
                )
            )
        await self.session.flush()

    async def owned_collection_ids(
        self, owner_id: str, ids: list[str]
    ) -> list[str]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Collection.id).where(
                Collection.owner_id == owner_id,
                Collection.id.in_(ids),
            )
        )
        found = set(result.scalars().all())
        return [collection_id for collection_id in ids if collection_id in found]

    async def list_collections_by_ids(self, ids: list[str]) -> list[Collection]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Collection).where(Collection.id.in_(ids))
        )
        by_id = {row.id: row for row in result.scalars().all()}
        return [by_id[collection_id] for collection_id in ids if collection_id in by_id]
