"""Persistência do auth (sessões + OTP). Não commita (boundary no endpoint)."""
import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.repository.models import AuthSessionRow, IdentityRow, LeadRow, OtpCodeRow


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_otp(self, email: str) -> OtpCodeRow | None:
        result = await self.session.execute(
            select(OtpCodeRow).where(OtpCodeRow.email == email).order_by(OtpCodeRow.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def count_otps_since(self, email: str, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(OtpCodeRow).where(
                OtpCodeRow.email == email, OtpCodeRow.created_at >= since
            )
        )
        return int(result.scalar_one())

    async def supersede_active(self, email: str) -> None:
        await self.session.execute(
            update(OtpCodeRow)
            .where(OtpCodeRow.email == email, OtpCodeRow.consumed_at.is_(None))
            .values(consumed_at=func.now())
        )

    async def insert_otp(self, *, email: str, code_hash: str, expires_at: datetime) -> OtpCodeRow:
        row = OtpCodeRow(id=str(uuid.uuid4()), email=email, code_hash=code_hash, expires_at=expires_at)
        self.session.add(row)
        await self.session.flush()
        return row

    async def active_otp_for_update(self, email: str) -> OtpCodeRow | None:
        result = await self.session.execute(
            select(OtpCodeRow)
            .where(OtpCodeRow.email == email, OtpCodeRow.consumed_at.is_(None))
            .order_by(OtpCodeRow.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def latest_lead_by_email(self, email: str) -> LeadRow | None:
        result = await self.session.execute(
            select(LeadRow).where(LeadRow.email == email).order_by(LeadRow.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def insert_session(
        self, *, token_hash: str, lead_id: str, expires_at: datetime, absolute_expires_at: datetime
    ) -> AuthSessionRow:
        row = AuthSessionRow(
            token_hash=token_hash, lead_id=lead_id,
            expires_at=expires_at, absolute_expires_at=absolute_expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_session(self, token_hash: str) -> AuthSessionRow | None:
        result = await self.session.execute(
            select(AuthSessionRow).where(AuthSessionRow.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_hash: str) -> None:
        await self.session.execute(
            update(AuthSessionRow).where(AuthSessionRow.token_hash == token_hash).values(revoked_at=func.now())
        )

    async def get_identity(self, email_normalized: str) -> IdentityRow | None:
        result = await self.session.execute(
            select(IdentityRow).where(IdentityRow.email_normalized == email_normalized)
        )
        return result.scalar_one_or_none()

    async def insert_identity(self, *, email_normalized: str, canonical_lead_id: str) -> IdentityRow:
        row = IdentityRow(email_normalized=email_normalized, canonical_lead_id=canonical_lead_id)
        self.session.add(row)
        await self.session.flush()
        return row
