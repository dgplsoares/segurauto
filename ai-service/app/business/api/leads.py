"""`POST /leads` — captura atômica e idempotente (DEC-ORB-011/012/013/035).

Fluxo: valida → dedup por `Idempotency-Key` (comparando e-mail) → persiste + intent na outbox (MESMA
transação, commit no endpoint) → 201. Retry do dono → 200. **Colisão de key com outra identidade → 409
neutro** (não vaza dados de outro lead). Não chama CRM/Ads (worker da Fase 3).
"""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.api.schemas import LeadCreate, LeadResponse
from app.business.repository.lead_repository import LeadRepository
from app.business.service.lead_service import CONFLICT, DEDUP, LeadService
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
        row, kind = await service.capture(
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
        await session.rollback()
        row, kind = await service.resolve_after_conflict(idempotency_key=key, email=str(payload.email))

    LEADS_CAPTURED.labels(result=kind).inc()
    if kind == CONFLICT:
        # Neutro: não devolve id/status/score/band/e-mail de outra identidade (LEAK-1).
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="idempotency_key_conflict")
    if kind == DEDUP:
        response.status_code = status.HTTP_200_OK
    return LeadResponse(id=row.id, status=row.status, deduped=(kind == DEDUP))
