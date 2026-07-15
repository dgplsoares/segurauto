"""qualification_agent (LangGraph) sem infra: determinismo, caminho assess (stub), degradação."""
from app.ai.agents.config import AgentConfig
from app.ai.agents.qualification_agent import QualificationAgent, get_qualification_agent
from app.ai.providers.llm import StubLLM
from app.ai.providers.orchestrator import ModelOrchestrator
from app.shared.qualification import QualificationBand

FULL = dict(has_vehicle=True, has_phone=True, has_zipcode=True, consent=True, source="meta")


def _agent(*, use_llm_assess: bool, llm=None) -> QualificationAgent:
    config = AgentConfig(
        name="qualification", provider="stub", use_llm_assess=use_llm_assess,
        system_prompt="teste", max_retries=0,
    )
    return QualificationAgent(ModelOrchestrator(llm or StubLLM(), config), config)


async def test_default_rubric_only_is_deterministic():
    agent = get_qualification_agent()  # settings default = stub → use_llm_assess=False
    r1 = await agent.qualify(**FULL)
    r2 = await agent.qualify(**FULL)
    assert r1 == r2
    assert r1.score == 100 and r1.band is QualificationBand.HOT
    assert not r1.reason.startswith("[stub]")  # rubrica-only, sem LLM


async def test_assess_path_runs_with_stub_deterministic():
    agent = _agent(use_llm_assess=True)  # exercita o nó assess com StubLLM
    r1 = await agent.qualify(**FULL)
    r2 = await agent.qualify(**FULL)
    assert r1 == r2
    assert r1.reason.startswith("[stub]")  # a explicação veio do LLM stub
    assert r1.score == 100  # o score continua determinístico (rubrica)


class _FailingLLM:
    async def complete(self, *, system: str, user: str) -> str:
        raise RuntimeError("boom")


async def test_llm_error_degrades_to_rubric_reason():
    agent = _agent(use_llm_assess=True, llm=_FailingLLM())
    result = await agent.qualify(**FULL)
    # orchestrator degrada p/ None → combine usa o reason da rubrica (nunca falha o grafo)
    assert not result.reason.startswith("[stub]")
    assert result.score == 100
