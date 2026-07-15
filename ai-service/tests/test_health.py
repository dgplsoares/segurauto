"""Fase 0 — smoke do esqueleto. `/health` (liveness) responde sem infra (gate de CI sem rede)."""
from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_liveness():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_sets_request_id_header():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    # Correlação (DEC-ORB-019): a resposta ecoa X-Request-Id.
    assert resp.headers.get("X-Request-Id")
