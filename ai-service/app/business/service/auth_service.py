"""`AuthService` (DEC-ORB-037): OTP + sessão. Não commita (boundary no endpoint).

Anti-lockout (B2): tentativa errada de OTP incrementa `attempts` + aplica **cooldown/backoff**, mas
**não consome** o código (só o palpite correto consome). Identidade = e-mail verificado (lead mais recente).
"""
import logging
from datetime import datetime, timedelta, timezone

from app.business.repository.auth_repository import AuthRepository
from app.business.repository.models import OtpCodeRow
from app.shared.config import get_settings
from app.shared.security import gen_otp, new_session_token, otp_hash, otp_matches, token_pk

logger = logging.getLogger("segurauto.business")


def _norm_email(email: str) -> str:
    return email.strip().lower()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    def __init__(self, repo: AuthRepository, notification) -> None:
        self.repo = repo
        self.notif = notification

    async def request_otp(self, email: str) -> None:
        """Sempre 202 neutro. Rate-limit silencioso; envia só se houver lead (não spamma estranhos)."""
        email = _norm_email(email)
        s = get_settings()
        now = _now()
        last = await self.repo.latest_otp(email)
        if last is not None and (now - last.created_at).total_seconds() < s.otp_resend_interval_s:
            return
        window_start = now - timedelta(seconds=s.otp_rate_window_s)
        if await self.repo.count_otps_since(email, window_start) >= s.otp_rate_max:
            return
        await self.repo.supersede_active(email)
        code = gen_otp(s.otp_length)
        await self.repo.insert_otp(
            email=email, code_hash=otp_hash(email, code), expires_at=now + timedelta(seconds=s.otp_ttl_s)
        )
        if await self.repo.latest_lead_by_email(email) is not None:
            await self.notif.send_otp(email=email, code=code)

    async def verify_otp(self, email: str, code: str) -> str | None:
        """Retorna o token da sessão, ou None (401). Palpite errado NÃO consome o código (anti-lockout)."""
        email = _norm_email(email)
        s = get_settings()
        now = _now()
        otp = await self.repo.active_otp_for_update(email)
        if otp is None or otp.expires_at <= now:
            return None
        if self._throttled(otp, now):
            return None
        if not otp_matches(email, code, otp.code_hash):
            otp.attempts += 1
            otp.last_attempt_at = now
            return None
        otp.consumed_at = now  # só o palpite CORRETO consome
        lead = await self.repo.latest_lead_by_email(email)
        if lead is None:
            return None
        canonical_lead_id = await self._canonical_lead_id(email, lead.id)
        token = new_session_token()
        await self.repo.insert_session(
            token_hash=token_pk(token), lead_id=canonical_lead_id,
            expires_at=now + timedelta(seconds=s.session_idle_ttl_s),
            absolute_expires_at=now + timedelta(seconds=s.session_absolute_ttl_s),
        )
        logger.info("session_issued lead_id=%s", canonical_lead_id)
        return token

    async def _canonical_lead_id(self, email: str, resolved_lead_id: str) -> str:
        """Âncora estável por identidade (DEC-ORB-041): a re-auth resolve sempre o mesmo `lead_id`, então
        o gate segue estrito em `lead_id` sem afrouxar para e-mail. Sem corrida: o `FOR UPDATE` do OTP
        serializa dois verify do mesmo e-mail (o 2º acha o código já consumido)."""
        ident = await self.repo.get_identity(email)
        if ident is not None:
            return ident.canonical_lead_id
        await self.repo.insert_identity(email_normalized=email, canonical_lead_id=resolved_lead_id)
        return resolved_lead_id

    def _throttled(self, otp: OtpCodeRow, now: datetime) -> bool:
        if otp.last_attempt_at is None:
            return False
        backoff = min(2**otp.attempts, 60)  # cooldown cresce com attempts (cap 60s); não trava para sempre
        return (now - otp.last_attempt_at).total_seconds() < backoff

    async def validate_session(self, token: str) -> str | None:
        now = _now()
        sess = await self.repo.get_session(token_pk(token))
        if sess is None or sess.revoked_at is not None:
            return None
        if sess.absolute_expires_at <= now or sess.expires_at <= now:
            return None
        s = get_settings()
        if (now - sess.last_seen_at).total_seconds() >= s.session_slide_coalesce_s:
            sess.last_seen_at = now
            sess.expires_at = now + timedelta(seconds=s.session_idle_ttl_s)  # sliding
        return sess.lead_id

    async def revoke(self, token: str) -> None:
        await self.repo.revoke(token_pk(token))
