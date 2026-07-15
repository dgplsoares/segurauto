"""support_agent (LangGraph, DEC-ORB-024/026): `guard_in → retrieve → [cond] → generate|refuse`.

Single-turn, **stateless**. A `RagService` (com a sessão do request) é passada no state — o nó nunca abre
o engine global. `rag_mode=rag_preferred`: contexto insuficiente → **recusa** (não alucina). O input do
usuário e os documentos são **dados não-confiáveis** (scope-and-strip + system prompt).
"""
import re
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.ai.agents.config import AgentConfig, get_support_config
from app.ai.providers.llm import get_llm
from app.ai.providers.orchestrator import ModelOrchestrator

_INJECTION_RE = re.compile(
    r"(?i)(ignore\s+(as\s+|todas\s+as\s+)?(instru\w+|previous|anteriores)|desconsidere|system\s+prompt|"
    r"forget\s+(the\s+)?(above|previous)|act\s+as|aja\s+como|revele|reveal)"
)
_HANDOFF_TERMS = ("corretor", "contratar", "fechar", "falar com humano", "atendente", "comprar")


def strip_injection(query: str) -> str:
    """Neutraliza diretivas de prompt-injection, mantendo a pergunta (scope-and-strip)."""
    return " ".join(_INJECTION_RE.sub(" ", query).split())[:500]


def detect_handoff(query: str) -> bool:
    q = query.lower()
    return any(term in q for term in _HANDOFF_TERMS)


class SupportState(TypedDict, total=False):
    query: str
    rag: Any  # RagService (passada por invocação; não serializada)
    safe_query: str
    context: str
    sufficient: bool
    answer: str
    handoff_suggested: bool


def _guard_in_node(state: SupportState) -> dict:
    return {
        "safe_query": strip_injection(state["query"]),
        "handoff_suggested": detect_handoff(state["query"]),
    }


async def _retrieve_node(state: SupportState) -> dict:
    result = await state["rag"].retrieve(state["safe_query"])
    return {"context": result.context, "sufficient": result.sufficient}


def _make_generate_node(orchestrator: ModelOrchestrator, config: AgentConfig):
    async def _generate_node(state: SupportState) -> dict:
        system = f"{config.system_prompt}\n\nContexto:\n{state.get('context', '')}"
        answer = await orchestrator.complete(system=system, user=state["safe_query"])
        return {"answer": answer or config.rejection_message}

    return _generate_node


def _make_refuse_node(config: AgentConfig):
    def _refuse_node(state: SupportState) -> dict:  # noqa: ARG001 — não usa o state
        return {"answer": config.rejection_message, "handoff_suggested": True}

    return _refuse_node


def _route_by_sufficiency(state: SupportState) -> str:
    return "generate" if state.get("sufficient") else "refuse"


def _build_graph(orchestrator: ModelOrchestrator, config: AgentConfig):
    graph = StateGraph(SupportState)
    graph.add_node("guard_in", _guard_in_node)
    graph.add_node("retrieve", _retrieve_node)
    graph.add_node("generate", _make_generate_node(orchestrator, config))
    graph.add_node("refuse", _make_refuse_node(config))
    graph.set_entry_point("guard_in")
    graph.add_edge("guard_in", "retrieve")
    graph.add_conditional_edges("retrieve", _route_by_sufficiency, {"generate": "generate", "refuse": "refuse"})
    graph.add_edge("generate", END)
    graph.add_edge("refuse", END)
    return graph.compile()


class SupportAgent:
    def __init__(self, orchestrator: ModelOrchestrator, config: AgentConfig) -> None:
        self.config = config
        self._graph = _build_graph(orchestrator, config)

    async def answer(self, query: str, *, rag) -> dict:
        final = await self._graph.ainvoke({"query": query, "rag": rag})
        return {
            "answer": final.get("answer", self.config.rejection_message),
            "sufficient": bool(final.get("sufficient", False)),
            "handoff_suggested": bool(final.get("handoff_suggested", False)),
        }


@lru_cache
def get_support_agent() -> SupportAgent:
    config = get_support_config()
    return SupportAgent(ModelOrchestrator(get_llm(), config), config)
