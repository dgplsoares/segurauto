"""Fase 4b — support_agent (RAG) + `/support/chat` autenticado (DEC-ORB-026/037)."""
from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.agents.config import get_support_config
from app.ai.agents.support_agent import get_support_agent
from app.ai.providers.embeddings import get_embedder
from app.ai.rag.ingestion import IngestionService
from app.ai.rag.rag_service import RagService
from app.ai.rag.vector_store import VectorStore
from app.business.domain.lead import Lead
from app.business.repository.auth_repository import AuthRepository
from app.business.repository.lead_repository import LeadRepository
from app.shared.security import new_session_token, token_pk

KB = (
    "## Coberturas\n\nCobrimos roubo e furto do veículo pela tabela FIPE.\n\n"
    "## Assistência\n\nAssistência 24h com guincho e chaveiro."
)


@pytest_asyncio.fixture(autouse=True)
async def _seed(db_engine):
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE ai.embeddings, ai.documents, business.auth_sessions CASCADE"))
    async with sm() as session:
        await IngestionService(VectorStore(session), get_embedder()).ingest(title="KB", content=KB)
        await session.commit()
    yield


@pytest_asyncio.fixture
def sm(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


def _rag(session):
    cfg = get_support_config()
    return RagService(VectorStore(session), get_embedder(), k=cfg.rag_k, min_score=cfg.rag_min_score)


async def test_in_domain_answers_and_sufficient(sm):
    async with sm() as session:
        res = await get_support_agent().answer("cobre roubo furto", rag=_rag(session))
    assert res["sufficient"] is True
    assert res["answer"]


async def test_out_of_domain_refuses_and_suggests_handoff(sm):
    async with sm() as session:
        res = await get_support_agent().answer("qual a capital da frança", rag=_rag(session))
    assert res["sufficient"] is False
    assert res["handoff_suggested"] is True  # rag_preferred: recusa + handoff


async def test_commercial_intent_flags_handoff(sm):
    async with sm() as session:
        res = await get_support_agent().answer("quero falar com corretor sobre roubo", rag=_rag(session))
    assert res["handoff_suggested"] is True


async def test_support_chat_requires_session(client):
    r = await client.post("/support/chat", json={"message": "cobre roubo?"})
    assert r.status_code == 401  # anti-IDOR: sem token, sem chat


async def test_support_chat_with_valid_session(client, sm):
    token = new_session_token()
    async with sm() as session:
        lead = Lead(
            idempotency_key="k-chat", name="Ana", email="ana@example.com", phone="11999998888",
            vehicle="Onix", zipcode="01001000", consent=True,
        )
        await LeadRepository(session).add_lead(lead)
        await AuthRepository(session).insert_session(
            token_hash=token_pk(token), lead_id=lead.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            absolute_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
        )
        await session.commit()
    r = await client.post(
        "/support/chat", json={"message": "cobre roubo?"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert "answer" in r.json()
