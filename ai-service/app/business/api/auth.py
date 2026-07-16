"""Endpoints de auth (DEC-ORB-037): request-otp (202 neutro), verify-otp (200 token / 401), logout.
Sem UI (o modal é a Fase 4c)."""
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.adapters.notification import get_notification
from app.business.api.deps import bearer_token, require_session
from app.business.repository.auth_repository import AuthRepository
from app.business.service.auth_service import AuthService
from app.shared.config import get_settings
from app.shared.database import get_session

router = APIRouter(tags=["auth"])


class RequestOtpIn(BaseModel):
    email: EmailStr


class VerifyOtpIn(BaseModel):
    email: EmailStr
    code: str


class VerifyOtpOut(BaseModel):
    token: str
    expires_in: int


def _service(session: AsyncSession) -> AuthService:
    return AuthService(AuthRepository(session), get_notification())


@router.post("/request-otp", status_code=status.HTTP_202_ACCEPTED)
async def request_otp(
    payload: RequestOtpIn,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    # O envio do OTP é adiado para depois da resposta (BackgroundTasks) → latência do 202 uniforme,
    # independente de o e-mail ser cliente ou não (fecha o timing side-channel — DEC-ORB-047/review 8e).
    await _service(session).request_otp(str(payload.email), defer=background_tasks.add_task)
    await session.commit()
    return {"status": "otp_sent_if_registered"}  # neutro — não revela existência do e-mail


@router.post("/verify-otp", response_model=VerifyOtpOut)
async def verify_otp(payload: VerifyOtpIn, session: AsyncSession = Depends(get_session)) -> VerifyOtpOut:
    token = await _service(session).verify_otp(str(payload.email), payload.code)
    await session.commit()
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_or_expired_otp")
    return VerifyOtpOut(token=token, expires_in=get_settings().session_idle_ttl_s)


@router.get("/session")
async def session_info(lead_id: str = Depends(require_session)) -> dict:
    """Valida a sessão do Bearer (200 {lead_id} | 401). Usado pela rehidratação do front (persistência):
    confirma se o token guardado no localStorage ainda vale antes de renderizar a UI autenticada. Reusa
    `require_session` (mesma regra de expiração + slide da janela idle)."""
    return {"lead_id": lead_id}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    token = bearer_token(authorization)
    if token:
        await _service(session).revoke(token)
        await session.commit()
