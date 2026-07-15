"""Providers de IA fake (StubLLM/HeuristicRerank) — determinísticos, sem rede (DEC-ORB-006)."""
from app.ai.providers.llm import StubLLM
from app.ai.providers.ports import LLMPort, RerankPort
from app.ai.providers.rerank import HeuristicRerank


async def test_stub_llm_deterministic():
    llm = StubLLM()
    a = await llm.complete(system="s", user="Olá mundo")
    b = await llm.complete(system="s", user="Olá mundo")
    assert a == b
    assert a.startswith("[stub]")


def test_stub_llm_satisfies_port():
    assert isinstance(StubLLM(), LLMPort)


def test_heuristic_rerank_orders_by_overlap():
    rr = HeuristicRerank()
    docs = ["seguro cobre roubo e furto", "assistencia 24h guincho", "carro reserva"]
    ranked = rr.rerank("cobre roubo", docs, top_k=3)
    assert ranked[0][0] == 0                     # doc mais sobreposto vem primeiro
    assert ranked[0][1] >= ranked[1][1] >= ranked[2][1]


def test_heuristic_rerank_satisfies_port():
    assert isinstance(HeuristicRerank(), RerankPort)
