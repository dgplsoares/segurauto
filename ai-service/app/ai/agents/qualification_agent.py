"""`qualification_agent` (LangGraph, DEC-ORB-008/024): `rubric → [cond] → assess → combine`.

O **score é determinístico** (rubrica); o LLM só **explica** (nó `assess`). A aresta condicional usa
`AgentConfig.use_llm_assess` (default False = rubrica-only → **CI determinístico**). **Stateless**
(sem DB/RAG) — a qualificação pontua os atributos do lead, não recupera conhecimento.
"""
from functools import lru_cache
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.ai.agents.config import AgentConfig, get_qualification_config
from app.ai.providers.llm import get_llm
from app.ai.providers.orchestrator import ModelOrchestrator
from app.business.domain.qualification import QualificationResult, rubric_score


class QualState(TypedDict, total=False):
    has_vehicle: bool
    has_phone: bool
    has_zipcode: bool
    consent: bool
    source: str | None
    rubric: QualificationResult
    assessment: str | None
    result: QualificationResult


def _rubric_node(state: QualState) -> dict:
    result = rubric_score(
        has_vehicle=state["has_vehicle"],
        has_phone=state["has_phone"],
        has_zipcode=state["has_zipcode"],
        consent=state["consent"],
        source=state.get("source"),
    )
    return {"rubric": result}


def _make_assess_node(orchestrator: ModelOrchestrator):
    async def _assess_node(state: QualState) -> dict:
        rubric = state["rubric"]
        user = (
            f"Lead com score {rubric.score}/100 (faixa {rubric.band.value}); sinais: {rubric.reason}. "
            "Explique o motivo em uma frase."
        )
        text = await orchestrator.complete(system=orchestrator.config.system_prompt, user=user)
        return {"assessment": text}

    return _assess_node


def _combine_node(state: QualState) -> dict:
    rubric = state["rubric"]
    reason = state.get("assessment") or rubric.reason
    return {"result": QualificationResult(score=rubric.score, band=rubric.band, reason=reason)}


def _make_router(config: AgentConfig):
    def _route(state: QualState) -> str:  # noqa: ARG001 — assinatura exigida pelo LangGraph
        return "assess" if config.use_llm_assess else "combine"

    return _route


def _build_graph(orchestrator: ModelOrchestrator, config: AgentConfig):
    # Nota: nomes de nó NÃO podem colidir com chaves de estado (langgraph) — por isso "score", não "rubric".
    graph = StateGraph(QualState)
    graph.add_node("score", _rubric_node)
    graph.add_node("assess", _make_assess_node(orchestrator))
    graph.add_node("combine", _combine_node)
    graph.set_entry_point("score")
    graph.add_conditional_edges("score", _make_router(config), {"assess": "assess", "combine": "combine"})
    graph.add_edge("assess", "combine")
    graph.add_edge("combine", END)
    return graph.compile()


class QualificationAgent:
    def __init__(self, orchestrator: ModelOrchestrator, config: AgentConfig) -> None:
        self.config = config
        self._graph = _build_graph(orchestrator, config)

    async def qualify(
        self,
        *,
        has_vehicle: bool,
        has_phone: bool,
        has_zipcode: bool,
        consent: bool,
        source: str | None,
    ) -> QualificationResult:
        final = await self._graph.ainvoke(
            {
                "has_vehicle": has_vehicle,
                "has_phone": has_phone,
                "has_zipcode": has_zipcode,
                "consent": consent,
                "source": source,
            }
        )
        return final["result"]


@lru_cache
def get_qualification_agent() -> QualificationAgent:
    config = get_qualification_config()
    return QualificationAgent(ModelOrchestrator(get_llm(), config), config)
