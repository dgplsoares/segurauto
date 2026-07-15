"""F6 (DEC-ORB-045) — confirmação explícita → ações write-through-outbox.

Cobre: enfileiramento das 3 intents de contrato + registro no audit pelo worker; idempotência (2ª
confirmação = replay, efeito 1×); exigência de cotação; handoff; propagação do click_id na conversão;
gate anti-IDOR e auth. Precisa de Postgres migrado (0007)."""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.business.domain.lead import Lead
from app.business.repository.auth_repository import AuthRepository
from app.business.repository.lead_repository import LeadRepository
from app.business.worker import drain_once, reset_adapters
from app.shared.security import new_session_token, token_pk

_F6_INTENTS = "('notify','conversion','crm_update')"


@pytest_asyncio.fixture
def sm(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _auth_lead(sm, *, email="ana@example.com", key="k1", click_id=None) -> tuple[str, str]:
    token = new_session_token()
    async with sm() as s:
        lead = Lead(
            idempotency_key=key, name="Ana", email=email, phone="11999998888",
            vehicle="Onix", zipcode="01001000", consent=True, click_id=click_id,
        )
        await LeadRepository(s).add_lead(lead)
        await AuthRepository(s).insert_session(
            token_hash=token_pk(token), lead_id=lead.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            absolute_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        await s.commit()
        return lead.id, token


async def _quoted_session(client, token: str) -> str:
    sid = (await client.post("/support/sessions", json={}, headers=_hdr(token))).json()["session_id"]
    await client.post(
        f"/support/sessions/{sid}/messages", headers=_hdr(token),
        json={"message": "placa ABC1D23, CEP 01310-100, não tenho corretor", "client_turn_id": "t"},
    )
    return sid


async def _events(db_engine, lead_id: str) -> list:
    async with db_engine.connect() as conn:
        return (await conn.execute(text(
            "SELECT event_type, request::text AS req, response::text AS resp "
            "FROM business.integration_events WHERE lead_id=:l ORDER BY created_at"
        ), {"l": lead_id})).all()


async def _f6_intent_count(db_engine, lead_id: str) -> int:
    async with db_engine.connect() as conn:
        return (await conn.execute(text(
            f"SELECT count(*) FROM business.outbox WHERE lead_id=:l AND intent_type IN {_F6_INTENTS}"
        ), {"l": lead_id})).scalar()


async def test_confirm_contract_enqueues_actions_and_worker_records_events(client, sm, db_engine):
    reset_adapters()
    lead_id, token = await _auth_lead(sm, click_id="gclid_ABC123")
    sid = await _quoted_session(client, token)

    r = await client.post(f"/support/sessions/{sid}/confirm", json={"action": "contract"}, headers=_hdr(token))
    assert r.status_code == 200 and r.json()["status"] == "queued"
    assert await _f6_intent_count(db_engine, lead_id) == 3  # notify + conversion + crm_update

    await drain_once(sm)
    evs = await _events(db_engine, lead_id)
    types = [e.event_type for e in evs]
    assert types.count("ads_conversion") == 2 and "crm_update" in types and "notify_contract" in types
    conv = next(e for e in evs if e.event_type == "ads_conversion")
    assert "contract_intent" in conv.req and "gclid_ABC123" in conv.req  # click_id propagado
    notify = next(e for e in evs if e.event_type == "notify_contract")
    assert "quote_confirmation" in notify.req and "@" not in notify.resp  # audit sem PII


async def test_confirm_is_idempotent_effect_once(client, sm, db_engine):
    reset_adapters()
    lead_id, token = await _auth_lead(sm)
    sid = await _quoted_session(client, token)
    r1 = await client.post(f"/support/sessions/{sid}/confirm", json={"action": "contract"}, headers=_hdr(token))
    r2 = await client.post(f"/support/sessions/{sid}/confirm", json={"action": "contract"}, headers=_hdr(token))
    assert r1.json()["status"] == "queued" and r2.json()["status"] == "already_requested"
    assert await _f6_intent_count(db_engine, lead_id) == 3  # a 2ª confirmação NÃO reenfileira (efeito 1×)


async def test_confirm_contract_requires_quote(client, sm):
    _, token = await _auth_lead(sm)
    sid = (await client.post("/support/sessions", json={}, headers=_hdr(token))).json()["session_id"]
    r = await client.post(f"/support/sessions/{sid}/confirm", json={"action": "contract"}, headers=_hdr(token))
    assert r.status_code == 409 and r.json()["detail"] == "quote_required"


async def test_confirm_handoff_enqueues_and_records(client, sm, db_engine):
    # Sessão limpa (handoff não exige cotação; e evita o detector de handoff disparar em "corretor").
    reset_adapters()
    lead_id, token = await _auth_lead(sm)
    sid = (await client.post("/support/sessions", json={}, headers=_hdr(token))).json()["session_id"]
    r = await client.post(f"/support/sessions/{sid}/confirm", json={"action": "handoff"}, headers=_hdr(token))
    assert r.status_code == 200 and r.json()["status"] == "queued"
    await drain_once(sm)
    assert any(e.event_type == "handoff" for e in await _events(db_engine, lead_id))


async def test_confirm_handoff_not_swallowed_when_detector_marked_hint(client, sm, db_engine):
    # Revisão adversarial: o detector do chat seta handoff_requested_at (resposta "não tenho corretor"
    # no slot) SEM enfileirar. A confirmação explícita PRECISA enfileirar HANDOFF mesmo assim.
    reset_adapters()
    lead_id, token = await _auth_lead(sm)
    sid = await _quoted_session(client, token)  # a msg contém "corretor" → dispara o detector
    async with db_engine.connect() as conn:
        marked = (await conn.execute(text(
            "SELECT handoff_requested_at IS NOT NULL FROM business.chat_sessions WHERE id=:s"), {"s": sid}
        )).scalar()
        n_before = (await conn.execute(text(
            "SELECT count(*) FROM business.outbox WHERE lead_id=:l AND intent_type='handoff'"), {"l": lead_id}
        )).scalar()
    assert marked is True and n_before == 0  # hint setado pelo detector, mas nada enfileirado

    r = await client.post(f"/support/sessions/{sid}/confirm", json={"action": "handoff"}, headers=_hdr(token))
    assert r.status_code == 200 and r.json()["status"] == "queued"  # NÃO 'already_requested'
    await drain_once(sm)
    assert any(e.event_type == "handoff" for e in await _events(db_engine, lead_id))


async def test_confirm_anti_idor_other_session_is_404(client, sm):
    _, token_a = await _auth_lead(sm, email="a@example.com", key="ka")
    _, token_b = await _auth_lead(sm, email="b@example.com", key="kb")
    sid_b = await _quoted_session(client, token_b)
    r = await client.post(f"/support/sessions/{sid_b}/confirm", json={"action": "handoff"}, headers=_hdr(token_a))
    assert r.status_code == 404  # neutro


async def test_confirm_requires_auth(client):
    assert (await client.post("/support/sessions/x/confirm", json={"action": "handoff"})).status_code == 401
