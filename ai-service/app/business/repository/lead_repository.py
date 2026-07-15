"""`LeadRepository` — persiste lead + intents da outbox. Não commita (DEC-ORB-012): o boundary de
transação fica no endpoint (Fase 2); aqui só `flush`.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.domain.events import IntentType
from app.business.domain.lead import Lead
from app.business.repository.models import LeadRow, OutboxRow


class LeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_idempotency_key(self, key: str) -> LeadRow | None:
        result = await self.session.execute(
            select(LeadRow).where(LeadRow.idempotency_key == key)
        )
        return result.scalar_one_or_none()

    async def add_lead(self, lead: Lead) -> LeadRow:
        row = LeadRow(
            id=lead.id,
            idempotency_key=lead.idempotency_key,
            name=lead.name,
            email=lead.email,
            phone=lead.phone,
            vehicle=lead.vehicle,
            zipcode=lead.zipcode,
            consent=lead.consent,
            source=lead.source,
            click_id=lead.click_id,
            status=lead.status.value,
            score=lead.score,
            band=lead.band.value if lead.band else None,
            reason=lead.reason,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def enqueue(
        self,
        *,
        lead_id: str,
        intent_type: IntentType,
        request_id: str | None = None,
        payload: dict | None = None,
    ) -> OutboxRow:
        row = OutboxRow(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            intent_type=intent_type.value,
            status="pending",
            retry_count=0,
            request_id=request_id,
            payload=json.dumps(payload) if payload is not None else None,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def flush(self) -> None:
        await self.session.flush()
