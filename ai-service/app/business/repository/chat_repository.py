"""Persistência da conversa (DEC-ORB-038). Não commita (boundary no endpoint).

Gate de posse **compartilhado** (E1): `load_owned_for_update` (turno, com lock) e `load_owned` (leitura)
revalidam `lead_id` no backend — `chat_messages` não tem `lead_id`, então nenhuma leitura toca mensagens
sem antes confirmar a posse da sessão. `seq` é auto-curável via `MAX` (E4); idempotência por `client_turn_id`.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.repository.models import ChatMessageRow, ChatSessionRow


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, *, lead_id: str, slots: dict) -> ChatSessionRow:
        row = ChatSessionRow(id=str(uuid.uuid4()), lead_id=lead_id, slots=slots or {})
        self.session.add(row)
        await self.session.flush()
        return row

    async def load_owned_for_update(self, *, session_id: str, lead_id: str) -> ChatSessionRow | None:
        """Lock + anti-IDOR num round-trip (idioma de `active_otp_for_update`)."""
        result = await self.session.execute(
            select(ChatSessionRow)
            .where(ChatSessionRow.id == session_id, ChatSessionRow.lead_id == lead_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def load_owned(self, *, session_id: str, lead_id: str) -> ChatSessionRow | None:
        """Gate de posse SEM lock, para leituras (E1: toda leitura revalida a posse)."""
        result = await self.session.execute(
            select(ChatSessionRow).where(ChatSessionRow.id == session_id, ChatSessionRow.lead_id == lead_id)
        )
        return result.scalar_one_or_none()

    async def user_message_by_turn(self, *, session_id: str, client_turn_id: str) -> ChatMessageRow | None:
        result = await self.session.execute(
            select(ChatMessageRow).where(
                ChatMessageRow.session_id == session_id,
                ChatMessageRow.client_turn_id == client_turn_id,
            )
        )
        return result.scalar_one_or_none()

    async def message_at_seq(self, *, session_id: str, seq: int) -> ChatMessageRow | None:
        result = await self.session.execute(
            select(ChatMessageRow).where(ChatMessageRow.session_id == session_id, ChatMessageRow.seq == seq)
        )
        return result.scalar_one_or_none()

    async def max_seq(self, *, session_id: str) -> int:
        """Fonte ÚNICA do próximo seq (E4): evita a poison pill de um `last_seq` dessincronizado."""
        result = await self.session.execute(
            select(func.coalesce(func.max(ChatMessageRow.seq), 0)).where(ChatMessageRow.session_id == session_id)
        )
        return int(result.scalar_one())

    async def add_message(
        self, *, session_id: str, seq: int, role: str, content: str, client_turn_id: str | None = None
    ) -> ChatMessageRow:
        row = ChatMessageRow(
            id=str(uuid.uuid4()), session_id=session_id, seq=seq, role=role,
            content=content, client_turn_id=client_turn_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_messages(self, *, session_id: str) -> list[ChatMessageRow]:
        result = await self.session.execute(
            select(ChatMessageRow).where(ChatMessageRow.session_id == session_id).order_by(ChatMessageRow.seq)
        )
        return list(result.scalars().all())
