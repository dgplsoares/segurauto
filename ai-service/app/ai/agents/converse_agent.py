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


def _fallback_reply(missing: list) -> str:
    if missing:
        return f"Para seguir com a sua cotação, me informe {_SLOT_LABELS.get(missing[0], missing[0])}."
    return "Tenho tudo o que preciso — já vou preparar a sua cotação."


def _make_respond_node(orchestrator: ModelOrchestrator, config: AgentConfig):
    async def _respond_node(state: ConverseState) -> dict:
        missing = state.get("missing", [])
        filled = ", ".join(f"{k}={v}" for k, v in (state.get("slots") or {}).items()) or "nenhum ainda"
        faltam = ", ".join(_SLOT_LABELS.get(m, m) for m in missing) or "nada (dados completos)"
        history = "\n".join(f"{t.get('role')}: {t.get('content')}" for t in (state.get("transcript") or [])[-6:])
        system = (
            f"{config.system_prompt}\n\nDados já coletados: {filled}\nAinda faltam: {faltam}\n"
            f"Conversa até aqui:\n{history}\n\nContexto (base de conhecimento):\n{state.get('context', '')}"
        )
        reply = await orchestrator.complete(system=system, user=state["safe_message"])
        return {"reply": reply or _fallback_reply(missing)}

    return _respond_node


def _make_refuse_node(config: AgentConfig):
    def _refuse_node(state: ConverseState) -> dict:  # noqa: ARG001 — não usa o state
        return {"reply": config.rejection_message, "handoff_suggested": True}

    return _refuse_node


def _route(state: ConverseState) -> str:
    # Sempre responde durante o slot-filling; recusa só off-topic sem contexto RAG e sem progresso de slot.
    if state.get("sufficient") or state.get("progressed") or not state.get("missing"):
        return "respond"
    return "refuse"


def _build_graph(orchestrator: ModelOrchestrator, config: AgentConfig):
    graph = StateGraph(ConverseState)
    graph.add_node("guard_in", _guard_in_node)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("respond", _make_respond_node(orchestrator, config))
    graph.add_node("refuse", _make_refuse_node(config))
    graph.set_entry_point("guard_in")
    graph.add_edge("guard_in", "retrieve")
    graph.add_conditional_edges("retrieve", _route, {"respond": "respond", "refuse": "refuse"})
    graph.add_edge("respond", END)
    graph.add_edge("refuse", END)
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
