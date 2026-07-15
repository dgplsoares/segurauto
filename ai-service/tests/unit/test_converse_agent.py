"""Fase 5c.2 — resposta determinística do ConverseAgent (fallback do slot-filling), sem infra."""
from app.ai.agents.converse_agent import _fallback_reply


def test_fallback_reply_asks_next_slot_acknowledges_and_confirms():
    assert "placa" in _fallback_reply(["vehicle"], False).lower()
    assert _fallback_reply(["vehicle"], True).startswith("Anotado!")
    assert "cotação" in _fallback_reply([], False).lower()  # slots completos → confirma
