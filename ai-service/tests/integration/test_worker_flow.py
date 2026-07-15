"""Fase 3c — worker: enriquecimento assíncrono, idempotência (worker 2× → efeitos 1×) e dead-letter."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.business import worker

LEAD = {
    "name": "Ana Silva",
    "email": "ana@example.com",
    "phone": "11999998888",
    "vehicle": "Chevrolet Onix 2020",
    "zipcode": "01001000",
    "consent": True,
    "source": "meta",
}


@pytest.fixture(autouse=True)
def _reset_fakes():
    worker.reset_adapters()
    yield
    worker.reset_adapters()


async def _capture(client, key: str) -> str:
    resp = await client.post("/leads", json=LEAD, headers={"Idempotency-Key": key})
    return resp.json()["id"]


async def test_worker_enriches_and_effects_once(client, db_engine):
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    lead_id = await _capture(client, "w-1")

    n1 = await worker.drain_once(sm)
    assert n1 == 4  # qualify + crm_sync + ads_meta + ads_google

    async with db_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, score, band FROM business.leads WHERE id = :i"), {"i": lead_id}
            )
        ).one()
    assert row.status == "synced"
    assert row.score == 100 and row.band == "hot"

    assert worker._crm().calls == 1
    assert len(worker._ads_meta().events) == 1
    assert len(worker._ads_google().events) == 1

    # worker 2× → efeitos 1× (intents 'done' não são re-pegas)
    n2 = await worker.drain_once(sm)
    assert n2 == 0
    assert worker._crm().calls == 1
    assert len(worker._ads_meta().events) == 1


async def test_handler_idempotent_on_reprocess(client, db_engine):
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    lead_id = await _capture(client, "w-2")
    await worker.drain_once(sm)
    assert len(worker._ads_meta().events) == 1

    # simula at-least-once: força reprocesso da conversão do Meta
    async with db_engine.begin() as conn:
        await conn.execute(
            text("UPDATE business.outbox SET status='pending' WHERE lead_id=:i AND intent_type='ads_meta'"),
            {"i": lead_id},
        )
    await worker.drain_once(sm)
    # o event_id é estável → o fake deduplica → continua 1 evento
    assert len(worker._ads_meta().events) == 1


async def test_dead_letter_after_max_retries(client, db_engine, monkeypatch):
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    lead_id = await _capture(client, "w-3")

    async def _boom(session, row):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "_handle", _boom)
    for _ in range(worker.MAX_RETRIES):
        async with sm() as session:
            await worker.process_one(session)
        async with db_engine.begin() as conn:  # re-arma sem depender do relógio
            await conn.execute(text("UPDATE business.outbox SET next_attempt_at=NULL WHERE status='pending'"))

    async with db_engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, retry_count FROM business.outbox WHERE lead_id=:i AND intent_type='qualify'"),
                {"i": lead_id},
            )
        ).one()
    assert row.status == "dead"
    assert row.retry_count == worker.MAX_RETRIES
