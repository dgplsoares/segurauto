"""Orquestração do turno de chat (DEC-ORB-038/040). Não commita (boundary no endpoint).

Sob o `FOR UPDATE` da sessão (lock + anti-IDOR num round-trip): idempotência de turno (replay em retry),
alocação auto-curável de `seq` (`MAX`+1), append user+assistant, persistência de slots. A geração da
resposta é um **seam** (`_generate`): na F5a.1 é um stub determinístico; a F5a.2 pluga o `ConverseAgent`
(via `AiPort.converse`) que extrai/valida slots e responde grounded.
"""
from datetime import datetime, timezone

from app.business.domain.slots import is_ready_to_quote, missing_slots
from app.business.repository.chat_repository import ChatRepository


class SessionNotFound(Exception):
    """Sessão inexistente ou de outro lead (→ 404 neutro)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ChatService:
    def __init__(self, repo: ChatRepository) -> None:
        self.repo = repo

    async def run_turn(self, *, session_id: str, lead_id: str, message: str, client_turn_id: str) -> dict:
        sess = await self.repo.load_owned_for_update(session_id=session_id, lead_id=lead_id)
        if sess is None:
            raise SessionNotFound

        # Idempotência de turno (E2): mesmo client_turn_id → replay do assistant já gravado (sem novo seq).
        existing = await self.repo.user_message_by_turn(session_id=session_id, client_turn_id=client_turn_id)
        if existing is not None:
            assistant = await self.repo.message_at_seq(session_id=session_id, seq=existing.seq + 1)
            reply = assistant.content if assistant else ""
            seq = assistant.seq if assistant else existing.seq
            return self._result(sess, seq=seq, reply=reply, replay=True)

        base = await self.repo.max_seq(session_id=session_id)  # auto-curável (E4)
        user_seq, assistant_seq = base + 1, base + 2
        await self.repo.add_message(
            session_id=session_id, seq=user_seq, role="user", content=message, client_turn_id=client_turn_id
        )

        reply, new_slots, handoff = self._generate(message, dict(sess.slots))

        await self.repo.add_message(session_id=session_id, seq=assistant_seq, role="assistant", content=reply)
        sess.slots = new_slots
        sess.last_turn_at = _now()
        if is_ready_to_quote(new_slots) and sess.quote_ready_at is None:
            sess.quote_ready_at = _now()  # GANCHO F5b — só SINALIZA, não cota
        if handoff and sess.handoff_requested_at is None:
            sess.handoff_requested_at = _now()
        return self._result(sess, seq=assistant_seq, reply=reply, replay=False)

    def _generate(self, message: str, slots: dict) -> tuple[str, dict, bool]:
        """STUB da F5a.1 (a F5a.2 substitui pelo `ConverseAgent`). Não extrai slots ainda; só devolve um
        ack determinístico para exercitar persistência/idempotência/seq. `message` não é ecoado (evita
        refletir input não-confiável)."""
        return "[stub] recebido. O consultor multi-turn entra na F5a.2.", slots, False

    def _result(self, sess, *, seq: int, reply: str, replay: bool) -> dict:
        return {
            "session_id": sess.id,
            "seq": seq,
            "reply": reply,
            "slots": dict(sess.slots),
            "missing_slots": missing_slots(sess.slots),
            "ready_to_quote": sess.quote_ready_at is not None,
            "handoff_suggested": sess.handoff_requested_at is not None,
            "replay": replay,
        }
