"""Fase 4a — fluxo de auth/OTP contra Postgres real (DEC-ORB-037): anti-lockout, expiração, reuso."""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.business.adapters import notification as notif_mod
from app.business.domain.lead import Lead
from app.business.repository.auth_repository import AuthRepository
from app.business.repository.lead_repository import LeadRepository
from app.business.service.auth_service import AuthService
from app.shared.security import new_session_token, otp_hash, token_pk

EMAIL = "ana@example.com"


@pytest_asyncio.fixture(autouse=True)
async def _reset_auth(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE business.auth_sessions, business.otp_codes CASCADE"))
    notif_mod.reset_notifications()
    yield
    notif_mod.reset_notifications()


@pytest_asyncio.fixture
def sm(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _svc(session) -> AuthService:
    return AuthService(AuthRepository(session), notif_mod.get_notification())


async def _make_lead(sm, email: str = EMAIL) -> str:
    async with sm() as session:
        lead = Lead(
            idempotency_key=f"k-{email}", name="Ana", email=email, phone="11999998888",
            vehicle="Onix", zipcode="01001000", consent=True,
        )
        await LeadRepository(session).add_lead(lead)
        await session.commit()
        return lead.id


async def _seed_otp(sm, code: str = "12345", *, minutes: int = 10) -> None:
    async with sm() as session:
        await AuthRepository(session).insert_otp(
            email=EMAIL, code_hash=otp_hash(EMAIL, code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
        )
        await session.commit()


async def test_request_otp_sends_only_if_lead_exists(sm):
    await _make_lead(sm)
    async with sm() as s:
        await _svc(s).request_otp(EMAIL)
        await s.commit()
    assert len(notif_mod.get_notification().sent) == 1  # há lead → envia
    async with sm() as s:
        await _svc(s).request_otp("ghost@example.com")  # sem lead
        await s.commit()
    assert len(notif_mod.get_notification().sent) == 1  # não spamma estranhos


async def test_request_otp_defers_send_off_critical_path(sm):
    """Fix do review 8e: com `defer`, o envio do OTP é AGENDADO (fora do caminho crítico), não executado
    inline → latência do 202 uniforme (fecha o timing side-channel de enumeração)."""
    await _make_lead(sm)
    scheduled: list = []

    def spy(func, **kwargs):  # stand-in de BackgroundTasks.add_task
        scheduled.append((func, kwargs))

    async with sm() as s:
        await _svc(s).request_otp(EMAIL, defer=spy)
        await s.commit()
    assert len(scheduled) == 1  # com lead → agenda o envio
    assert scheduled[0][0] == notif_mod.get_notification().send_otp
    assert scheduled[0][1]["email"] == EMAIL and "code" in scheduled[0][1]
    assert notif_mod.get_notification().sent == []  # NADA enviado inline (deferido, não executado)

    async with sm() as s:
        await _svc(s).request_otp("ghost@example.com", defer=spy)  # sem lead
        await s.commit()
    assert len(scheduled) == 1  # ghost não agenda nada


async def test_wrong_attempt_does_not_burn_then_correct_works(sm):
    lead_id = await _make_lead(sm)
    await _seed_otp(sm, "12345")
    async with sm() as s:  # palpite errado → None, mas NÃO consome (anti-lockout)
        assert await _svc(s).verify_otp(EMAIL, "00000") is None
        await s.commit()
    async with sm() as s:  # avança o cooldown (sem depender do relógio)
        await s.execute(text("UPDATE business.otp_codes SET last_attempt_at = now() - interval '90 seconds'"))
        await s.commit()
    async with sm() as s:  # o código legítimo ainda funciona
        token = await _svc(s).verify_otp(EMAIL, "12345")
        await s.commit()
    assert token is not None
    async with sm() as s:
        assert await _svc(s).validate_session(token) == lead_id


async def test_wrong_attempt_applies_cooldown(sm):
    await _make_lead(sm)
    await _seed_otp(sm, "12345")
    async with sm() as s:
        assert await _svc(s).verify_otp(EMAIL, "00000") is None  # attempts=1, last_attempt=now
        await s.commit()
    async with sm() as s:  # imediatamente: até o código CORRETO é throttled (cooldown ativo)
        assert await _svc(s).verify_otp(EMAIL, "12345") is None
        await s.commit()


async def test_expired_otp_rejected(sm):
    await _make_lead(sm)
    await _seed_otp(sm, "12345", minutes=-1)  # já expirado
    async with sm() as s:
        assert await _svc(s).verify_otp(EMAIL, "12345") is None
        await s.commit()


async def test_code_reuse_rejected(sm):
    await _make_lead(sm)
    await _seed_otp(sm, "12345")
    async with sm() as s:
        assert await _svc(s).verify_otp(EMAIL, "12345") is not None  # consome
        await s.commit()
    async with sm() as s:
        assert await _svc(s).verify_otp(EMAIL, "12345") is None  # já consumido
        await s.commit()


async def test_session_absolute_and_revoke(sm):
    lead_id = await _make_lead(sm)
    token = new_session_token()
    async with sm() as s:  # sessão com absoluto no passado
        await AuthRepository(s).insert_session(
            token_hash=token_pk(token), lead_id=lead_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            absolute_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        await s.commit()
    async with sm() as s:
        assert await _svc(s).validate_session(token) is None  # absoluto vencido


async def test_request_otp_endpoint_neutral_202(client, sm):
    """O endpoint injeta BackgroundTasks e responde 202 neutro tanto para e-mail registrado quanto não."""
    await _make_lead(sm)
    r1 = await client.post("/auth/request-otp", json={"email": EMAIL})
    r2 = await client.post("/auth/request-otp", json={"email": "nobody@example.com"})
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json() == r2.json()  # corpo idêntico — não revela existência do e-mail


async def test_session_endpoint_validates_token(client, sm):
    """GET /auth/session: token vivo → 200 {lead_id}; ausente/inválido → 401 (usado na rehidratação do front)."""
    lead_id = await _make_lead(sm)
    await _seed_otp(sm, "12345")
    ok = await client.post("/auth/verify-otp", json={"email": EMAIL, "code": "12345"})
    token = ok.json()["token"]
    good = await client.get("/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert good.status_code == 200 and good.json()["lead_id"] == lead_id
    assert (await client.get("/auth/session")).status_code == 401  # sem bearer
    assert (await client.get("/auth/session", headers={"Authorization": "Bearer nope"})).status_code == 401


async def test_verify_otp_endpoint(client, sm):
    await _make_lead(sm)
    await _seed_otp(sm, "12345")
    ok = await client.post("/auth/verify-otp", json={"email": EMAIL, "code": "12345"})
    assert ok.status_code == 200 and "token" in ok.json()
    bad = await client.post("/auth/verify-otp", json={"email": EMAIL, "code": "99999"})
    assert bad.status_code == 401
