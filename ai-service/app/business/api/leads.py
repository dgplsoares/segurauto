"""`POST /leads` — captura atômica e idempotente (DEC-ORB-011/012/013).

Fluxo: valida → dedup por `Idempotency-Key` → persiste lead + intent na outbox (MESMA transação,
commit no endpoint) → 201. Sob corrida, `IntegrityError` na UNIQUE vira dedup → 1 lead garantido.
Não chama CRM/Ads (worker da Fase 3).
"""
import uuid

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.api.schemas import LeadCreate, LeadResponse
from app.business.repository.lead_repository import LeadRepository
from app.business.service.lead_service import LeadService
from app.shared.database import get_session
from app.shared.metrics import LEADS_CAPTURED
from app.shared.observability import request_id_ctx

router = APIRouter(tags=["leads"])


@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    payload: LeadCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
) -> LeadResponse:
    key = idempotency_key or payload.idempotency_key or uuid.uuid4().hex
    request_id = request_id_ctx.get()
    service = LeadService(LeadRepository(session))
    try:
        row, deduped = await service.capture(
            idempotency_key=key,
            name=payload.name,
            email=str(payload.email),
            phone=payload.phone,
            vehicle=payload.vehicle,
            zipcode=payload.zipcode,
            consent=payload.consent,
            source=payload.source,
            request_id=request_id,
        )
        await session.commit()
    except IntegrityError:
        # Corrida: outra requisição com a mesma chave venceu a UNIQUE → tratamos como dedup.
        await session.rollback()
        row = await LeadRepository(session).get_by_idempotency_key(key)
        deduped = True

    LEADS_CAPTURED.labels(result="deduped" if deduped else "created").inc()
    if deduped:
        response.status_code = status.HTTP_200_OK
    return LeadResponse(id=row.id, status=row.status, deduped=deduped, score=row.score, band=row.band)
