from datetime import UTC, datetime
from typing import Any

from app.features.conversations.models import Conversation, Message
from app.features.conversations.schemas import UIMessage
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, conversation: Conversation) -> Conversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get(self, conversation_id: str) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()

    async def get_owned(
        self, conversation_id: str, owner_id: str
    ) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.owner_id == owner_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: str, limit: int) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .where(
                Conversation.owner_id == owner_id,
                Conversation.session_type == "chat",
            )
            .order_by(Conversation.last_active_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def find_build_session(
        self, owner_id: str, target_agent_id: str
    ) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.owner_id == owner_id,
                Conversation.target_agent_id == target_agent_id,
                Conversation.session_type == "build",
            )
            .order_by(Conversation.last_active_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def add_message(
        self,
        conversation_id: str,
        message: UIMessage,
        *,
        created_at: datetime | None = None,
    ) -> Message:
        row = Message(
            id=message.id,
            conversation_id=conversation_id,
            role=message.role,
            parts=list(message.parts),
            created_at=created_at or datetime.now(UTC),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def upsert_message(
        self,
        conversation_id: str,
        message: UIMessage,
    ) -> Message:
        existing = await self.session.get(Message, message.id)
        if existing is not None:
            existing.parts = list(message.parts)
            existing.role = message.role
            await self.session.flush()
            return existing
        return await self.add_message(conversation_id, message)

    async def latest_assistant_message(self, conversation_id: str) -> Message | None:
        result = await self.session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_message(
        self,
        conversation_id: str,
        message_id: str,
    ) -> Message | None:
        result = await self.session.execute(
            select(Message).where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
            )
        )
        return result.scalar_one_or_none()

    async def set_active_response(
        self,
        conversation_id: str,
        response_id: str | None,
        last_event_id: int | None = None,
    ) -> None:
        values: dict[str, Any] = {
            "active_response_id": response_id,
            "updated_at": datetime.now(UTC),
            "last_active_at": datetime.now(UTC),
        }
        if last_event_id is not None or response_id is None:
            values["last_event_id"] = last_event_id
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(**values)
        )
        await self.session.commit()

    async def update_last_event_id(self, conversation_id: str, event_id: int) -> None:
        await self.session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                last_event_id=event_id,
                updated_at=datetime.now(UTC),
            )
        )
        await self.session.commit()

    async def set_title(self, conversation_id: str, title: str) -> None:
        await self.session.execute(
            update(Conversation)
            .where(
                Conversation.id == conversation_id,
                Conversation.title.is_(None),
            )
            .values(title=title, updated_at=datetime.now(UTC))
        )
        await self.session.commit()
