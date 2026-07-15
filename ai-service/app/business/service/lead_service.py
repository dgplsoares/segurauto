"""`LeadService.capture` — dedup + persist + enfileira o enriquecimento na outbox (DEC-ORB-011/012/013).

NÃO commita (boundary no endpoint) e NÃO chama CRM/Ads (isso é o worker da Fase 3). Só grava o
lead e a intent `QUALIFY` (o worker qualifica e, então, encadeia CRM/Ads).
"""
import logging

from app.business.domain.events import IntentType
from app.business.domain.lead import Lead
from app.business.repository.lead_repository import LeadRepository
from app.business.repository.models import LeadRow

logger = logging.getLogger("segurauto.business")


def _mask(value: str | None) -> str:
    """Mascara PII em log (DEC-ORB-018)."""
    if not value:
        return "-"
    return value[:2] + "***"


class LeadService:
    def __init__(self, repo: LeadRepository) -> None:
        self.repo = repo

    async def capture(
        self,
        *,
        idempotency_key: str,
        name: str,
        email: str,
        phone: str,
        vehicle: str,
        zipcode: str,
        consent: bool,
        source: str | None,
        request_id: str | None = None,
    ) -> tuple[LeadRow, bool]:
        """Retorna (lead, deduped). Não commita."""
        existing = await self.repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            logger.info("lead_deduped lead_id=%s status=%s source=%s", existing.id, existing.status, source or "-")
            return existing, True

        lead = Lead(
            idempotency_key=idempotency_key,
            name=name,
            email=email,
            phone=phone,
            vehicle=vehicle,
            zipcode=zipcode,
            consent=consent,
            source=source,
        )
        row = await self.repo.add_lead(lead)
        await self.repo.enqueue(lead_id=lead.id, intent_type=IntentType.QUALIFY, request_id=request_id)
        logger.info(
            "lead_received lead_id=%s email=%s phone=%s source=%s",
            lead.id, _mask(email), _mask(phone), source or "-",
        )
        return row, False
