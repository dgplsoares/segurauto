"""`LeadService.capture` — dedup + persist + enfileira o enriquecimento (DEC-ORB-011/012/013/035).

No dedup, compara o **e-mail normalizado**: dono legítimo do retry → `dedup`; colisão de key com outra
identidade → `conflict` (o endpoint devolve 409 neutro, sem vazar nada — LEAK-1/DEC-ORB-035). Não commita.
"""
import hashlib
import logging

from app.business.domain.events import IntentType
from app.business.domain.lead import Lead
from app.business.repository.lead_repository import LeadRepository
from app.business.repository.models import LeadRow

logger = logging.getLogger("segurauto.business")

CREATED = "created"
DEDUP = "dedup"
CONFLICT = "conflict"


def _mask(value: str | None) -> str:
    """Mascara PII em log (DEC-ORB-018)."""
    if not value:
        return "-"
    return value[:2] + "***"


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _key_sha(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


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
        click_id: str | None = None,
        request_id: str | None = None,
    ) -> tuple[LeadRow | None, str]:
        """Retorna (lead, kind) — kind ∈ {created, dedup, conflict}. Não commita."""
        norm_email = _norm_email(email)
        existing = await self.repo.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            return self._resolve_existing(existing, norm_email, idempotency_key)

        lead = Lead(
            idempotency_key=idempotency_key, name=name, email=norm_email, phone=phone,
            vehicle=vehicle, zipcode=zipcode, consent=consent, source=source, click_id=click_id,
        )
        row = await self.repo.add_lead(lead)
        await self.repo.enqueue(lead_id=lead.id, intent_type=IntentType.QUALIFY, request_id=request_id)
        logger.info(
            "lead_received lead_id=%s email=%s phone=%s source=%s",
            lead.id, _mask(norm_email), _mask(phone), source or "-",
        )
        return row, CREATED

    async def resolve_after_conflict(self, *, idempotency_key: str, email: str) -> tuple[LeadRow | None, str]:
        """Ramo de corrida (IntegrityError na UNIQUE da key): re-lê e aplica a MESMA regra de e-mail."""
        existing = await self.repo.get_by_idempotency_key(idempotency_key)
        if existing is None:
            return None, CONFLICT
        return self._resolve_existing(existing, _norm_email(email), idempotency_key)

    def _resolve_existing(self, existing: LeadRow, norm_email: str, key: str) -> tuple[LeadRow | None, str]:
        if _norm_email(existing.email) == norm_email:
            logger.info("lead_deduped lead_id=%s status=%s", existing.id, existing.status)
            return existing, DEDUP
        # LEAK-1: a key pertence a OUTRA identidade → não vaza nada (log sem PII, só hash da key).
        logger.warning("idempotency_key_conflict key_sha=%s", _key_sha(key))
        return None, CONFLICT
