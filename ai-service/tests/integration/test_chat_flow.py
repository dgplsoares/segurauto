"""Fase 5a.1 — persistência de conversa + endpoints (DEC-ORB-038/040/041).

Cobre o happy path e os furos do pentest endereçados nesta fatia: anti-IDOR (E1), idempotência de turno
(E2), seq monotônico/auto-curável (E4) e continuidade por `canonical_lead_id` (DEC-ORB-041).
"""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import text
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


async def test_turn_extracts_slots_and_signals_ready_to_quote(client, sm):
    _, token = await _auth_lead(sm)
    sid = await _create_session(client, token)
    r = await client.post(
        f"/support/sessions/{sid}/messages",
        json={"message": "placa ABC1D23, CEP 01310-100, não tenho corretor", "client_turn_id": "t1"},
        headers=_hdr(token),
    )
    assert r.status_code == 200
    body = r.json()
    # Extração determinística no turno (E6) → slots completos → sinaliza pronto para cotar (F5b não cota).
    assert body["slots"] == {"vehicle": "ABC1D23", "zipcode": "01310100", "has_broker": False}
    assert body["missing_slots"] == [] and body["ready_to_quote"] is True


async def test_quote_generated_when_slots_complete(client, sm):
    _, token = await _auth_lead(sm)
    sid = await _create_session(client, token)
    r = await client.post(
        f"/support/sessions/{sid}/messages",
        json={"message": "placa ABC1D23, CEP 01310-100, não tenho corretor", "client_turn_id": "t1"},
        headers=_hdr(token),
    )
    q = r.json()["quote"]
    assert q is not None and q["premium_cents"] > 0 and q["currency"] == "BRL"
    assert q["broker_applied"] is False and q["pdf_ref"]  # PDF = marcador
    r2 = await client.get(f"/support/sessions/{sid}/quote", headers=_hdr(token))  # GET devolve a mesma
    assert r2.status_code == 200 and r2.json()["quote_id"] == q["quote_id"]


async def test_quote_broker_discount_only_for_authorized(client, sm):
    _, token_a = await _auth_lead(sm, email="ba@example.com", key="qa")
    sid_a = await _create_session(client, token_a)
    ra = await client.post(f"/support/sessions/{sid_a}/messages", headers=_hdr(token_a),
        json={"message": "placa ABC1D23, CEP 01310-100, tenho corretor código ABC123", "client_turn_id": "t"})
    _, token_b = await _auth_lead(sm, email="bb@example.com", key="qb")
    sid_b = await _create_session(client, token_b)
    rb = await client.post(f"/support/sessions/{sid_b}/messages", headers=_hdr(token_b),
        json={"message": "placa ABC1D23, CEP 01310-100, tenho corretor código ZZZ999", "client_turn_id": "t"})
    qa, qb = ra.json()["quote"], rb.json()["quote"]
    # broker_code autorizado (ABC123) → desconto server-side; não-autorizado (ZZZ999) → sem desconto (E6).
    assert qa["broker_applied"] is True and qb["broker_applied"] is False
    assert qa["premium_cents"] < qb["premium_cents"]


async def test_get_quote_anti_idor(client, sm):
    _, token_a = await _auth_lead(sm, email="qi-a@example.com", key="qia")
    _, token_b = await _auth_lead(sm, email="qi-b@example.com", key="qib")
    sid_a = await _create_session(client, token_a)
    await client.post(f"/support/sessions/{sid_a}/messages", headers=_hdr(token_a),
        json={"message": "placa ABC1D23, CEP 01310-100, não tenho corretor", "client_turn_id": "t"})
    r = await client.get(f"/support/sessions/{sid_a}/quote", headers=_hdr(token_b))  # B lê a cotação de A
    assert r.status_code == 404  # neutro


async def test_quote_records_crm_price_quote_event(client, sm, db_engine):
    """F5b.2 (DEC-ORB-044): a cotação registra a chamada crm_price_quote em integration_events."""
    _, token = await _auth_lead(sm)
    sid = await _create_session(client, token)
    await client.post(f"/support/sessions/{sid}/messages", headers=_hdr(token),
        json={"message": "placa ABC1D23, CEP 01310-100, não tenho corretor", "client_turn_id": "t"})
    async with db_engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT event_type FROM business.integration_events WHERE session_id=:s"), {"s": sid}
        )).first()
    assert row is not None and row.event_type == "crm_price_quote"


async def test_otp_records_notify_event_without_code(client, sm, db_engine):
    """F5b.2: request-otp de lead existente registra notify_otp — NUNCA o código (segurança)."""
    await _auth_lead(sm, email="otpev@example.com", key="otpev")  # cria o lead
    assert (await client.post("/auth/request-otp", json={"email": "otpev@example.com"})).status_code == 202
    async with db_engine.connect() as conn:
        row = (await conn.execute(
            text("SELECT request::text AS req FROM business.integration_events WHERE event_type='notify_otp'")
        )).first()
    assert row is not None and "purpose" in row.req and "code" not in row.req


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
