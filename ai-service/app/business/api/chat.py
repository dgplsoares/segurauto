"""Chat multi-turn de cotação (DEC-ORB-038): sessões stateful autenticadas.

`POST /support/sessions` (cria) · `POST /support/sessions/{id}/messages` (turno, boundary de commit) ·
`GET /support/sessions/{id}/messages` (histórico). Gate de posse em TODA leitura (anti-IDOR, E1); **404
neutro** (nunca 403); `session_id` do path como `str` (não 422). Pool ISOLADO do chat (DEC-ORB-040). Na
F5a.1 a resposta do turno é um stub — o `ConverseAgent` entra na F5a.2.
"""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.api.deps import require_session_chat
from app.business.domain.slots import missing_slots, validate_slots
from app.business.repository.chat_repository import ChatRepository
from app.business.repository.lead_repository import LeadRepository
from app.business.service.chat_service import ChatService, SessionNotFound
from app.business.service.confirm_service import ConfirmService, QuoteRequired
from app.business.service.quote_service import QuoteService, quote_public
from app.shared.config import get_settings
from app.shared.database import get_chat_session
from app.shared.observability import request_id_ctx

router = APIRouter(tags=["chat"])


def concurrency_http_error(exc: DBAPIError) -> HTTPException | None:
    """Mapeia os timeouts do pool do chat (DEC-ORB-040) para status retryable. O asyncpg embrulha
    `lock_timeout`/`statement_timeout` como `DBAPIError` **base** (NÃO `OperationalError`), então ramificamos
    pelo `sqlstate`; qualquer outro erro (ex.: `IntegrityError` inesperado) retorna None → propaga (500 visível)."""
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    if sqlstate == "55P03":  # lock_not_available (lock_timeout) — turno concorrente na mesma sessão
        return HTTPException(status.HTTP_409_CONFLICT, detail="session_busy")
    if sqlstate == "57014":  # query_canceled (statement_timeout)
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="turn_timeout")
    return None


class CreateSessionIn(BaseModel):
    seed_slots: dict | None = None  # validado server-side (schema de VALOR — E6)


class CreateSessionOut(BaseModel):
    session_id: str
    slots: dict
    missing_slots: list[str]


class TurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=get_settings().chat_message_max_len)
    client_turn_id: str | None = Field(default=None, max_length=64)


class QuoteOut(BaseModel):
    quote_id: str
    premium_cents: int
    currency: str
    coverages: list[str]
    broker_applied: bool
    pdf_ref: str | None


class TurnOut(BaseModel):
    session_id: str
    seq: int
    reply: str
    slots: dict
    missing_slots: list[str]
    ready_to_quote: bool
    handoff_suggested: bool
    replay: bool
    quote: QuoteOut | None = None  # preenchido no turno que gera a cotação (DEC-ORB-043)


class MessageOut(BaseModel):
    seq: int
    role: str
    content: str


class ConfirmIn(BaseModel):
    action: Literal["contract", "handoff"]


class ConfirmOut(BaseModel):
    session_id: str
    action: str
    status: str   # queued | already_requested (idempotente)
    message: str


@router.post("/support/sessions", response_model=CreateSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: CreateSessionIn,
    lead_id: str = Depends(require_session_chat),
    session: AsyncSession = Depends(get_chat_session),
) -> CreateSessionOut:
    # Semeia o slot `vehicle` a partir do lead JÁ persistido (o modal coletou a placa/veículo) → o agente
    # NÃO pergunta o mesmo dado duas vezes. Valor autoritativo do servidor, não do cliente.
    seed = dict(payload.seed_slots or {})
    lead = await LeadRepository(session).get_by_id(lead_id)
    if lead is not None and lead.vehicle and "vehicle" not in seed:
        seed["vehicle"] = lead.vehicle
    slots = validate_slots(seed)  # E6: valida VALOR, não só a chave
    row = await ChatRepository(session).create_session(lead_id=lead_id, slots=slots)
    await session.commit()
    return CreateSessionOut(session_id=row.id, slots=row.slots, missing_slots=missing_slots(row.slots))


@router.post("/support/sessions/{session_id}/messages", response_model=TurnOut)
async def post_turn(
    session_id: str,
    payload: TurnIn,
    lead_id: str = Depends(require_session_chat),
    session: AsyncSession = Depends(get_chat_session),
) -> TurnOut:
    svc = ChatService(ChatRepository(session))
    client_turn_id = payload.client_turn_id or uuid.uuid4().hex
    try:
        result = await svc.run_turn(
            session_id=session_id, lead_id=lead_id, message=payload.message, client_turn_id=client_turn_id
        )
        await session.commit()
    except SessionNotFound:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")  # neutro (nunca 403)
    except DBAPIError as exc:
        # lock/statement_timeout do pool do chat (DEC-ORB-040): turno concorrente na mesma sessão → falha
        # rápido (409), sem prender conexão. Erro não-esperado propaga (500) — não mascara IntegrityError.
        await session.rollback()
        mapped = concurrency_http_error(exc)
        if mapped is None:
            raise
        raise mapped
    return TurnOut(**result)


@router.get("/support/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(
    session_id: str,
    lead_id: str = Depends(require_session_chat),
    session: AsyncSession = Depends(get_chat_session),
) -> list[MessageOut]:
    repo = ChatRepository(session)
    if await repo.load_owned(session_id=session_id, lead_id=lead_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")  # gate de posse (E1)
    msgs = await repo.list_messages(session_id=session_id)
    return [MessageOut(seq=m.seq, role=m.role, content=m.content) for m in msgs]


@router.get("/support/sessions/{session_id}/quote", response_model=QuoteOut)
async def get_quote(
    session_id: str,
    lead_id: str = Depends(require_session_chat),
    session: AsyncSession = Depends(get_chat_session),
) -> QuoteOut:
    if await ChatRepository(session).load_owned(session_id=session_id, lead_id=lead_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")  # gate de posse (E1)
    row = await QuoteService(session).for_session(session_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")  # ainda sem cotação
    return QuoteOut(**quote_public(row))


@router.post("/support/sessions/{session_id}/confirm", response_model=ConfirmOut)
async def confirm_action(
    session_id: str,
    payload: ConfirmIn,
    lead_id: str = Depends(require_session_chat),
    session: AsyncSession = Depends(get_chat_session),
) -> ConfirmOut:
    """Confirmação explícita → ações write-through-outbox (DEC-ORB-045). Idempotente (2ª chamada = replay);
    gate de posse anti-IDOR (404 neutro); `contract` sem cotação → 409."""
    svc = ConfirmService(ChatRepository(session))
    try:
        result = await svc.confirm(
            session_id=session_id, lead_id=lead_id, action=payload.action,
            request_id=request_id_ctx.get(),
        )
        await session.commit()
    except SessionNotFound:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="not_found")  # neutro (nunca 403)
    except QuoteRequired:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="quote_required")
    except DBAPIError as exc:
        await session.rollback()
        mapped = concurrency_http_error(exc)  # confirmação concorrente na mesma sessão → 409 session_busy
        if mapped is None:
            raise
        raise mapped
    return ConfirmOut(**result)
