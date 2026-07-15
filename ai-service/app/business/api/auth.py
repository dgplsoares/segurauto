"""Endpoints de auth (DEC-ORB-037): request-otp (202 neutro), verify-otp (200 token / 401), logout.
Sem UI (o modal é a Fase 4c)."""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.adapters.notification import get_notification
from app.business.api.deps import bearer_token
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
async def request_otp(payload: RequestOtpIn, session: AsyncSession = Depends(get_session)) -> dict:
    await _service(session).request_otp(str(payload.email))
    await session.commit()
    return {"status": "otp_sent_if_registered"}  # neutro — não revela existência do e-mail


@router.post("/verify-otp", response_model=VerifyOtpOut)
async def verify_otp(payload: VerifyOtpIn, session: AsyncSession = Depends(get_session)) -> VerifyOtpOut:
    token = await _service(session).verify_otp(str(payload.email), payload.code)
    await session.commit()
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_or_expired_otp")
    return VerifyOtpOut(token=token, expires_in=get_settings().session_idle_ttl_s)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> None:
    token = bearer_token(authorization)
    if token:
        await _service(session).revoke(token)
        await session.commit()
