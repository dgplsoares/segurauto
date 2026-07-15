"""Dependencies de auth (DEC-ORB-037): `require_session` (Bearer → `lead_id`) — base do anti-IDOR da 4b."""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.adapters.notification import get_notification
from app.business.repository.auth_repository import AuthRepository
from app.business.service.auth_service import AuthService
from app.shared.database import get_chat_session, get_session


def bearer_token(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


async def _resolve_lead(session: AsyncSession, authorization: str | None) -> str:
    token = bearer_token(authorization)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")
    lead_id = await AuthService(AuthRepository(session), get_notification()).validate_session(token)
    if lead_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_session")
    await session.commit()  # persiste o slide (sliding window) ANTES do corpo do endpoint
    return lead_id


async def require_session(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> str:
    """Valida o token de sessão e devolve o `lead_id`. 401 se ausente/inválido."""
    return await _resolve_lead(session, authorization)


async def require_session_chat(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_chat_session),
) -> str:
    """Como `require_session`, mas no POOL ISOLADO do chat (DEC-ORB-040): o request de chat inteiro usa só
    conexões do pool do chat, então um turno lento nunca inani a captura (`/leads`) no pool principal."""
    return await _resolve_lead(session, authorization)
