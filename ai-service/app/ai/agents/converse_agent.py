"""converse_agent (LangGraph, DEC-ORB-024/039): consultor de cotação multi-turn.

`guard_in → retrieve → [cond] → respond | refuse`. STATELESS e reentrante: a `RagService` (com a sessão do
request) e o transcrito são passados por invocação; o nó nunca abre o engine global nem consulta o banco de
negócio. A EXTRAÇÃO de slots é do `business` (determinística, E6) — este agente só GERA a resposta, informado
dos slots já coletados e dos que faltam. `rag_mode=rag_preferred`: dúvida off-topic sem contexto e sem
progresso de slot → recusa + handoff (não alucina). Nós disjuntos das state keys (gotcha LangGraph).
"""
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.ai.agents.config import AgentConfig, get_converse_config
from app.ai.providers.llm import get_llm
from app.ai.providers.orchestrator import ModelOrchestrator
from app.shared.guards import detect_handoff, strip_injection

_SLOT_LABELS = {
    "vehicle": "a placa do veículo",
    "zipcode": "o CEP",
    "has_broker": "se você já tem corretor",
    "broker_code": "o código do seu corretor",
}


class ConverseState(TypedDict, total=False):
    user_message: str
    transcript: list
    slots: dict
    missing: list
    progressed: bool
    rag: Any  # RagService (passada por invocação; não serializada)
    safe_message: str
    context: str
    sufficient: bool
    reply: str
    handoff_suggested: bool


def _guard_in_node(state: ConverseState) -> dict:
    return {
        "safe_message": strip_injection(state["user_message"]),
        "handoff_suggested": detect_handoff(state["user_message"]),
    }


async def _retrieve_node(state: ConverseState) -> dict:
    result = await state["rag"].retrieve(state["safe_message"])
    return {"context": result.context, "sufficient": result.sufficient}


def _fallback_reply(missing: list, progressed: bool = False) -> str:
    if not missing:
        return "Perfeito, tenho tudo o que preciso — preparei a sua cotação. 🚗"
    label = _SLOT_LABELS.get(missing[0], missing[0])
    prefix = "Anotado! " if progressed else ""
    return f"{prefix}Para seguir com a sua cotação, me informe {label}."


def _make_respond_node(orchestrator: ModelOrchestrator, config: AgentConfig):
    async def _respond_node(state: ConverseState) -> dict:
        missing = state.get("missing", [])
        progressed = bool(state.get("progressed"))
        # Sem LLM real (stub de CI/local), a resposta DETERMINÍSTICA conduz o slot-filling — melhor que o
        # eco do stub; o número/decisão da cotação já vêm do business (não do LLM). Qualquer provider real
        # (openai/anthropic) passa a gerar a frase; se ele falhar, o orchestrator devolve None e cai aqui.
        if config.provider == "stub":
            return {"reply": _fallback_reply(missing, progressed)}
        filled = ", ".join(f"{k}={v}" for k, v in (state.get("slots") or {}).items()) or "nenhum ainda"
        faltam = ", ".join(_SLOT_LABELS.get(m, m) for m in missing) or "nada (dados completos)"
        history = "\n".join(f"{t.get('role')}: {t.get('content')}" for t in (state.get("transcript") or [])[-6:])
        system = (
            f"{config.system_prompt}\n\nDados já coletados: {filled}\nAinda faltam: {faltam}\n"
            f"Conversa até aqui:\n{history}\n\nContexto (base de conhecimento):\n{state.get('context', '')}"
        )
        reply = await orchestrator.complete(system=system, user=state["safe_message"])
        return {"reply": reply or _fallback_reply(missing, progressed)}

    return _respond_node


def _build_graph(orchestrator: ModelOrchestrator, config: AgentConfig):
    graph = StateGraph(ConverseState)
    graph.add_node("guard_in", _guard_in_node)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("respond", _make_respond_node(orchestrator, config))
    graph.set_entry_point("guard_in")
    graph.add_edge("guard_in", "retrieve")
    # O consultor de cotação SEMPRE responde (pede o próximo slot / responde FAQ / confirma) — nunca recusa:
    # recusar follow-ups on-topic (ex.: "é mensal ou anual?" pós-cotação) seria péssimo p/ um bot de vendas.
    # O handoff (guard_in → handoff_suggested) segue disponível para intenção comercial/humana.
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


class ConverseAgent:
    def __init__(self, orchestrator: ModelOrchestrator, config: AgentConfig) -> None:
        self.config = config
        self._graph = _build_graph(orchestrator, config)

    async def converse(
        self, *, transcript: list, slots: dict, missing: list, progressed: bool, user_message: str, rag
    ) -> dict:
        final = await self._graph.ainvoke({
            "user_message": user_message, "transcript": transcript, "slots": slots,
            "missing": missing, "progressed": progressed, "rag": rag,
        })
        return {
            "reply": final.get("reply", self.config.rejection_message),
            "sufficient": bool(final.get("sufficient", False)),
            "handoff_suggested": bool(final.get("handoff_suggested", False)),
        }


@lru_cache
def get_converse_agent() -> ConverseAgent:
    config = get_converse_config()
    return ConverseAgent(ModelOrchestrator(get_llm(), config), config)
