"""Fase 3.5 — masking de PII (sem corromper UUID) e X-Request-Id não-ecoado (DEC-ORB-036)."""
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.shared.observability import redact_pii


def test_pii_redacts_email_placa_but_keeps_uuid():
    line = "lead_received lead_id=d6cd8754-c397-4d87-8330-55b1e48c5520 email=ana@example.com placa=ABC1D23"
    out = redact_pii(line)
    assert "ana@example.com" not in out and "[email]" in out
    assert "[placa]" in out
    assert "d6cd8754-c397-4d87-8330-55b1e48c5520" in out  # UUID (correlação) intacto — não corrompe


def test_pii_redacts_cpf_formatado():
    assert redact_pii("cpf=123.456.789-09") == "cpf=[cpf]"
    # bare 11 dígitos NÃO é redigido (evitaria corromper ids); confia no _mask nos call-sites
    assert "12345678909" in redact_pii("x=12345678909")


async def test_forged_request_id_is_not_echoed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health", headers={"X-Request-Id": "forged-evil-123"})
    rid = resp.headers.get("X-Request-Id")
    assert rid is not None and rid != "forged-evil-123"  # server-side ignora o valor do cliente
