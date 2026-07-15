"""Fase 5a.1 — persistência de conversa + endpoints (DEC-ORB-038/040/041).

Cobre o happy path e os furos do pentest endereçados nesta fatia: anti-IDOR (E1), idempotência de turno
(E2), seq monotônico/auto-curável (E4) e continuidade por `canonical_lead_id` (DEC-ORB-041).
"""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.business.adapters.notification import get_notification
from app.business.domain.lead import Lead
from app.business.repository.auth_repository import AuthRepository
from app.business.repository.lead_repository import LeadRepository
from app.business.service.auth_service import AuthService
from app.shared.security import new_session_token, otp_hash, token_pk


@pytest_asyncio.fixture
def sm(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _auth_lead(sm, *, email: str = "ana@example.com", key: str = "k1") -> tuple[str, str]:
    """Cria um lead + sessão autenticada e devolve (lead_id, token)."""
    token = new_session_token()
    async with sm() as session:
        lead = Lead(
            idempotency_key=key, name="Ana", email=email, phone="11999998888",
            vehicle="Onix", zipcode="01001000", consent=True,
        )
        await LeadRepository(session).add_lead(lead)
        await AuthRepository(session).insert_session(
            token_hash=token_pk(token), lead_id=lead.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            absolute_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        await session.commit()
        return lead.id, token


async def _create_session(client, token: str) -> str:
    r = await client.post("/support/sessions", json={}, headers=_hdr(token))
    assert r.status_code == 201
    return r.json()["session_id"]


async def test_create_session_and_turn_persist_history(client, sm):
    _, token = await _auth_lead(sm)
    sid = await _create_session(client, token)

    r = await client.post(
        f"/support/sessions/{sid}/messages",
        json={"message": "quero cotar meu Onix", "client_turn_id": "t1"}, headers=_hdr(token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["seq"] == 2 and body["replay"] is False and body["reply"]

    r = await client.get(f"/support/sessions/{sid}/messages", headers=_hdr(token))
    msgs = r.json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "quero cotar meu Onix"  # content do usuário gravado (auditoria)


async def test_turn_idempotency_replays_not_duplicates(client, sm):
    _, token = await _auth_lead(sm)
    sid = await _create_session(client, token)
    body = {"message": "oi", "client_turn_id": "same-turn"}

    r1 = await client.post(f"/support/sessions/{sid}/messages", json=body, headers=_hdr(token))
    r2 = await client.post(f"/support/sessions/{sid}/messages", json=body, headers=_hdr(token))

    assert r1.json()["replay"] is False and r2.json()["replay"] is True
    assert r1.json()["seq"] == r2.json()["seq"]  # mesmo turno lógico, sem novo seq
    msgs = (await client.get(f"/support/sessions/{sid}/messages", headers=_hdr(token))).json()
    assert len(msgs) == 2  # não duplicou o turno


async def test_seq_is_monotonic_across_turns(client, sm):
    _, token = await _auth_lead(sm)
    sid = await _create_session(client, token)
    url = f"/support/sessions/{sid}/messages"
    s1 = await client.post(url, json={"message": "a", "client_turn_id": "1"}, headers=_hdr(token))
    s2 = await client.post(url, json={"message": "b", "client_turn_id": "2"}, headers=_hdr(token))
    assert (s1.json()["seq"], s2.json()["seq"]) == (2, 4)


async def test_anti_idor_other_lead_gets_neutral_404(client, sm):
    _, token_a = await _auth_lead(sm, email="a@example.com", key="ka")
    _, token_b = await _auth_lead(sm, email="b@example.com", key="kb")
    sid_b = await _create_session(client, token_b)

    r_post = await client.post(
        f"/support/sessions/{sid_b}/messages", json={"message": "x", "client_turn_id": "z"}, headers=_hdr(token_a)
    )
    r_get = await client.get(f"/support/sessions/{sid_b}/messages", headers=_hdr(token_a))
    assert r_post.status_code == 404 and r_get.status_code == 404  # neutro (não 403, não 200)


async def test_nonexistent_session_is_404(client, sm):
    _, token = await _auth_lead(sm)
    r = await client.post(
        "/support/sessions/does-not-exist/messages", json={"message": "x", "client_turn_id": "z"}, headers=_hdr(token)
    )
    assert r.status_code == 404


async def test_endpoints_require_session(client):
    assert (await client.post("/support/sessions", json={})).status_code == 401
    assert (await client.post("/support/sessions/x/messages", json={"message": "y"})).status_code == 401
    assert (await client.get("/support/sessions/x/messages")).status_code == 401


async def test_seed_slots_validated_and_missing_reported(client, sm):
    _, token = await _auth_lead(sm)
    r = await client.post(
        "/support/sessions",
        json={"seed_slots": {"zipcode": "01310-100", "vehicle": "Onix", "junk": "drop-me", "has_broker": False}},
        headers=_hdr(token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["slots"] == {"zipcode": "01310100", "vehicle": "Onix", "has_broker": False}  # 'junk' descartado
    assert body["missing_slots"] == []  # vehicle+zipcode+has_broker(False) → completo


async def _insert_otp(sm, email: str, code: str) -> None:
    async with sm() as session:
        await AuthRepository(session).insert_otp(
            email=email, code_hash=otp_hash(email, code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        await session.commit()


async def _verify(sm, email: str, code: str) -> str | None:
    async with sm() as session:
        token = await AuthService(AuthRepository(session), get_notification()).verify_otp(email, code)
        await session.commit()
        return token


async def _resolve(sm, token: str) -> str | None:
    async with sm() as session:
        lead_id = await AuthService(AuthRepository(session), get_notification()).validate_session(token)
        await session.commit()
        return lead_id


async def test_canonical_lead_id_stable_across_reauth(sm):
    """DEC-ORB-041: reenviar o form (nova lead, mesmo e-mail) + re-auth resolve a MESMA âncora."""
    email = "dup@example.com"
    async with sm() as session:
        for key in ("kA", "kB"):
            await LeadRepository(session).add_lead(Lead(
                idempotency_key=key, name="Dup", email=email, phone="11999998888",
                vehicle="Onix", zipcode="01001000", consent=True,
            ))
        await session.commit()

    await _insert_otp(sm, email, "12345")
    token1 = await _verify(sm, email, "12345")
    canon1 = await _resolve(sm, token1)

    # nova lead C (mesmo e-mail) + nova verificação
    async with sm() as session:
        await LeadRepository(session).add_lead(Lead(
            idempotency_key="kC", name="Dup", email=email, phone="11999998888",
            vehicle="Onix", zipcode="01001000", consent=True,
        ))
        await session.commit()
    await _insert_otp(sm, email, "67890")
    token2 = await _verify(sm, email, "67890")
    canon2 = await _resolve(sm, token2)

    assert token1 and token2
    assert canon1 == canon2  # continuidade: mesma identidade → mesmo lead_id
