"""`POST /ai/qualify` — contrato stateless, sem infra (gate de CI). Determinístico com stub."""
from httpx import ASGITransport, AsyncClient

from app.main import app

PAYLOAD = {"has_vehicle": True, "has_phone": True, "has_zipcode": True, "consent": True, "source": "meta"}


async def test_qualify_endpoint_structured_and_deterministic():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/ai/qualify", json=PAYLOAD)
        r2 = await ac.post("/ai/qualify", json=PAYLOAD)
    assert r1.status_code == 200
    body = r1.json()
    assert set(body) == {"score", "band", "reason"}
    assert body["score"] == 100 and body["band"] == "hot"
    assert r1.json() == r2.json()  # determinístico
