"""Fase 2 — captura atômica e idempotente contra Postgres real (DEC-ORB-011/012)."""
import asyncio

from sqlalchemy import text

LEAD = {
    "name": "Ana Silva",
    "email": "ana@example.com",
    "phone": "11999998888",
    "vehicle": "Chevrolet Onix 2020",
    "zipcode": "01001000",
    "consent": True,
    "source": "meta",
}


async def _count_leads(engine, key: str) -> int:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT count(*) FROM business.leads WHERE idempotency_key = :k"), {"k": key}
        )
        return result.scalar_one()


async def test_capture_persists_and_enqueues_qualify(client, db_engine):
    resp = await client.post("/leads", json=LEAD, headers={"Idempotency-Key": "key-abc"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "received"
    assert body["deduped"] is False

    async with db_engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT intent_type, count(*) FROM business.outbox WHERE lead_id = :id GROUP BY intent_type"),
                {"id": body["id"]},
            )
        ).all()
    assert rows == [("qualify", 1)]  # só QUALIFY; CRM/Ads são encadeados pelo worker (Fase 3)


async def test_double_post_same_key_yields_one_lead(client, db_engine):
    headers = {"Idempotency-Key": "key-dup"}
    r1 = await client.post("/leads", json=LEAD, headers=headers)
    r2 = await client.post("/leads", json=LEAD, headers=headers)
    assert r1.status_code == 201 and r1.json()["deduped"] is False
    assert r2.status_code == 200 and r2.json()["deduped"] is True
    assert r1.json()["id"] == r2.json()["id"]
    assert await _count_leads(db_engine, "key-dup") == 1


async def test_concurrent_same_key_yields_one_lead(client, db_engine):
    headers = {"Idempotency-Key": "key-race"}
    r1, r2 = await asyncio.gather(
        client.post("/leads", json=LEAD, headers=headers),
        client.post("/leads", json=LEAD, headers=headers),
    )
    assert {r1.status_code, r2.status_code} <= {200, 201}
    assert await _count_leads(db_engine, "key-race") == 1  # UNIQUE + IntegrityError → 1 lead


async def test_missing_consent_is_rejected(client):
    bad = {**LEAD, "consent": False}
    resp = await client.post("/leads", json=bad, headers={"Idempotency-Key": "key-noconsent"})
    assert resp.status_code == 422
