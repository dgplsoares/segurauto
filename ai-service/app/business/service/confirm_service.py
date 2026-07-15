"""Confirmação explícita do lead → ações write-through-outbox (DEC-ORB-045).

Duas ações, ambas idempotentes por uma marca na sessão (sob `FOR UPDATE` = lock + anti-IDOR num
round-trip): `contract` enfileira NOTIFY + CONVERSION + CRM_UPDATE; `handoff` enfileira HANDOFF. Não
commita (o boundary é o endpoint). Os efeitos externos (fakes) rodam no worker, at-least-once.

Fronteira "não é CRM" (DEC-ORB-034): `crm_update` é só um SINAL ao CRM; o funil de vendas é do CRM.
"""
from datetime import datetime, timezone

from app.business.domain.events import IntentType
from app.business.repository.chat_repository import ChatRepository
from app.business.repository.lead_repository import LeadRepository
from app.business.service.chat_service import SessionNotFound
from app.business.service.quote_service import QuoteService

# Canais da confirmação de contrato (decisão F6: todos fakes via NotificationPort).
NOTIFY_CHANNELS = ("email", "whatsapp", "sms")

_CONTRACT_MSG = (
    "Perfeito! Registramos o seu interesse. Você vai receber a confirmação por e-mail, WhatsApp e SMS, "
    "e um corretor entra em contato para finalizar. 🚗"
)
_HANDOFF_MSG = "Combinado! Um corretor da SegurAuto vai continuar o seu atendimento em instantes. 👌"


class QuoteRequired(Exception):
    """Confirmar contrato exige uma cotação na sessão (→ 409)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConfirmService:
    def __init__(self, repo: ChatRepository) -> None:
        self.repo = repo

    async def confirm(self, *, session_id: str, lead_id: str, action: str, request_id: str | None) -> dict:
        sess = await self.repo.load_owned_for_update(session_id=session_id, lead_id=lead_id)
        if sess is None:
            raise SessionNotFound
        leads = LeadRepository(self.repo.session)

        if action == "handoff":
            # Gate na marca DEDICADA da confirmação (single-writer). NÃO usar handoff_requested_at: o
            # detector do chat também a seta (como hint, sem enfileirar), o que engoliria o enqueue.
            if sess.handoff_confirmed_at is not None:
                return self._result(session_id, action, "already_requested", _HANDOFF_MSG)
            now = _now()
            sess.handoff_confirmed_at = now
            sess.handoff_requested_at = sess.handoff_requested_at or now  # mantém o hint coerente
            await leads.enqueue(
                lead_id=lead_id, intent_type=IntentType.HANDOFF,
                request_id=request_id, payload={"session_id": session_id},
            )
            return self._result(session_id, action, "queued", _HANDOFF_MSG)

        # action == "contract"
        if await QuoteService(self.repo.session).for_session(session_id) is None:
            raise QuoteRequired  # não dá para contratar sem cotação
        if sess.contract_requested_at is not None:
            return self._result(session_id, action, "already_requested", _CONTRACT_MSG)
        sess.contract_requested_at = _now()
        for intent, payload in (
            (IntentType.CONVERSION, {"session_id": session_id}),
            (IntentType.CRM_UPDATE, {"session_id": session_id}),
            (IntentType.NOTIFY, {"session_id": session_id, "channels": list(NOTIFY_CHANNELS)}),
        ):
            await leads.enqueue(lead_id=lead_id, intent_type=intent, request_id=request_id, payload=payload)
        return self._result(session_id, action, "queued", _CONTRACT_MSG)

    def _result(self, session_id: str, action: str, status: str, message: str) -> dict:
        return {"session_id": session_id, "action": action, "status": status, "message": message}
