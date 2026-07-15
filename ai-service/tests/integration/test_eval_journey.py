"""Jornada agregada do lead (DEC-ORB-042): agregação por e-mail, resolução da identidade canônica,
descoberta, escaping anti-XSS no render HTML e o gate fail-closed (só local/`enable_eval_api`)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

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


async def _auth_lead(sm, *, email: str, key: str) -> tuple[str, str]:
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


async def _complete_quote_turn(client, token: str, sid: str) -> None:
    await client.post(
        f"/support/sessions/{sid}/messages", headers=_hdr(token),
        json={"message": "placa ABC1D23, CEP 01310-100, não tenho corretor", "client_turn_id": "t"},
    )


async def test_journey_aggregates_lead_chat_quote_and_events(client, sm):
    lead_id, token = await _auth_lead(sm, email="journey@example.com", key="jk")
    sid = await _create_session(client, token)
    await _complete_quote_turn(client, token, sid)
    assert (await client.post("/auth/request-otp", json={"email": "journey@example.com"})).status_code == 202

    j = (await client.get("/eval/leads/journey", params={"email": "journey@example.com"})).json()
    assert j["resolved_lead_id"] == lead_id and j["canonical_identity"] is False  # sem identidade → fallback
    assert len(j["leads"]) == 1 and j["leads"][0]["email"] == "journey@example.com"
    assert len(j["chat_sessions"]) == 1
    assert [m["role"] for m in j["chat_sessions"][0]["messages"]] == ["user", "assistant"]
    assert len(j["quotes"]) == 1 and j["quotes"][0]["premium_cents"] > 0
    etypes = {e["event_type"] for e in j["integration_events"]}
    assert {"crm_price_quote", "notify_otp"} <= etypes


async def test_journey_case_insensitive_email(client, sm):
    await _auth_lead(sm, email="mixed@example.com", key="mx")
    j = (await client.get("/eval/leads/journey", params={"email": "MiXeD@Example.COM"})).json()
    assert j["email"] == "mixed@example.com" and len(j["leads"]) == 1


async def test_journey_resolves_canonical_identity_across_duplicate_leads(client, sm):
    email = "canon@example.com"
    async with sm() as session:
        for key in ("cA", "cB"):
            await LeadRepository(session).add_lead(Lead(
                idempotency_key=key, name="C", email=email, phone="11999998888",
                vehicle="Onix", zipcode="01001000", consent=True,
            ))
        await session.commit()
    async with sm() as session:
        await AuthRepository(session).insert_otp(
            email=email, code_hash=otp_hash(email, "12345"),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        await session.commit()
    async with sm() as session:
        auth = AuthService(AuthRepository(session), get_notification())
        token = await auth.verify_otp(email, "12345")
        await session.commit()
    async with sm() as session:
        canon = await AuthService(AuthRepository(session), get_notification()).validate_session(token)
        await session.commit()

    j = (await client.get("/eval/leads/journey", params={"email": email})).json()
    assert j["canonical_identity"] is True and j["resolved_lead_id"] == canon
    assert len(j["leads"]) == 2 and canon in j["lead_ids"]


async def test_journey_unknown_email_is_404(client):
    r = await client.get("/eval/leads/journey", params={"email": "nobody@example.com"})
    assert r.status_code == 404


async def test_discovery_lists_recent_leads(client, sm):
    await _auth_lead(sm, email="disco@example.com", key="dk")
    r = await client.get("/eval/leads")
    assert r.status_code == 200
    assert "disco@example.com" in {lead["email"] for lead in r.json()["leads"]}


async def test_journey_html_escapes_user_content(client, sm):
    """Anti-XSS: o conteúdo do chat (input livre) NUNCA pode virar markup na página de avaliação."""
    _, token = await _auth_lead(sm, email="xss@example.com", key="xk")
    sid = await _create_session(client, token)
    await client.post(
        f"/support/sessions/{sid}/messages", headers=_hdr(token),
        json={"message": "<script>alert('xss')</script>", "client_turn_id": "t"},
    )
    r = await client.get("/eval/leads/journey", params={"email": "xss@example.com", "format": "html"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "<script>alert('xss')</script>" not in r.text  # escapado, não injetado
    assert "&lt;script&gt;" in r.text


async def test_eval_api_gated_off_returns_404(client, monkeypatch):
    """Fail-closed (defesa em profundidade): fora de local e sem flag, o gate de rota devolve 404."""
    import app.eval.api.journey as journey_api

    monkeypatch.setattr(
        journey_api, "get_settings", lambda: SimpleNamespace(enable_eval_api=False, environment="prod")
    )
    assert (await client.get("/eval/leads")).status_code == 404
    assert (await client.get("/eval/leads/journey", params={"email": "x@example.com"})).status_code == 404
