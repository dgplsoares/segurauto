"""Registro append-only das trocas com sistemas externos (DEC-ORB-044). Não commita (boundary no caller).

O caller monta `request`/`response` explicitamente — nunca despeja objetos crus. O evento de OTP registra só
o e-mail (**nunca o código**). Habilita a jornada do lead (DEC-ORB-042).
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.business.repository.models import IntegrationEventRow


async def record_integration_event(
    session: AsyncSession,
    *,
    event_type: str,
    request: dict,
    response: dict,
    status: str = "ok",
    lead_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
) -> IntegrationEventRow:
    row = IntegrationEventRow(
        id=str(uuid.uuid4()), lead_id=lead_id, session_id=session_id, event_type=event_type,
        request=request, response=response, status=status, request_id=request_id,
    )
    session.add(row)
    await session.flush()
    return row
