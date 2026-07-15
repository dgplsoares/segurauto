"""Fase 5c.2 — polish do ConverseAgent (roteamento + resposta determinística), sem infra."""
from app.ai.agents.converse_agent import _fallback_reply, _route


def test_route_never_refuses_during_slot_filling():
    assert _route({"missing": ["vehicle"]}) == "respond"  # faltam slots → pede o próximo
    assert _route({"missing": [], "sufficient": True}) == "respond"
    assert _route({"missing": [], "progressed": True}) == "respond"
    # slots completos, off-topic sem contexto nem progresso → recusa/handoff
    assert _route({"missing": [], "sufficient": False, "progressed": False}) == "refuse"


def test_fallback_reply_asks_next_slot_acknowledges_and_confirms():
    assert "placa" in _fallback_reply(["vehicle"], False).lower()
    assert _fallback_reply(["vehicle"], True).startswith("Anotado!")
    assert "cotação" in _fallback_reply([], False).lower()  # slots completos → confirma
