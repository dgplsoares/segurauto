"""Fase 8a (DEC-ORB-046) — factory de provider, classificação de erro, circuit-breaker e a política de
fallback do orchestrator (auth/quota não retenta e abre o breaker; 429/timeout retenta e degrada). Sem rede."""
from types import SimpleNamespace

import app.ai.providers.llm as llm_mod
from app.ai.agents.config import AgentConfig
from app.ai.providers.llm import AnthropicLLM, LLMError, OpenAILLM, StubLLM, _classify
from app.ai.providers.orchestrator import CircuitBreaker, ModelOrchestrator, get_breaker, reset_breakers


def _settings(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        llm_provider=provider, openai_model="gpt-4o-mini", anthropic_model="claude-opus-4-8",
        openai_api_key="x", anthropic_api_key="y",
    )


def test_get_llm_dispatches_by_provider(monkeypatch):
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _settings("stub"))
    assert isinstance(llm_mod.get_llm(), StubLLM)
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _settings("openai"))
    assert isinstance(llm_mod.get_llm(), OpenAILLM)
    monkeypatch.setattr(llm_mod, "get_settings", lambda: _settings("anthropic"))
    m = llm_mod.get_llm()
    assert isinstance(m, AnthropicLLM) and m.model == "claude-opus-4-8"


def test_classify_error_reasons():
    assert _classify(429, None, None).reason == "rate_limit" and _classify(429, None, None).retryable
    assert _classify(429, "insufficient_quota", None).reason == "quota"          # quota vence o 429
    assert not _classify(429, "insufficient_quota", None).retryable              # e NÃO é retryable
    assert _classify(401, None, None).reason == "auth" and not _classify(401, None, None).retryable
    assert _classify(403, None, "billing_error").reason == "quota"               # billing da Anthropic
    assert _classify(500, None, None).reason == "server" and _classify(500, None, None).retryable
    assert _classify(400, None, None).reason == "bad_request"


async def test_stub_llm_is_deterministic():
    assert await StubLLM().complete(system="s", user="  quero  cotar  ") == "[stub] quero cotar"


def test_circuit_breaker_opens_and_recovers():
    b = CircuitBreaker(threshold=2, cooldown_s=999)
    assert b.allow()
    b.record_failure()
    assert b.allow()               # 1 falha soft não abre
    b.record_failure()
    assert not b.allow()           # 2ª abre
    b.record_success()
    assert b.allow()               # sucesso zera
    b.record_failure(hard=True)
    assert not b.allow()           # 'hard' (auth/quota) abre na 1ª


class _FakeLLM:
    def __init__(self, *, raises: Exception | None = None, text: str = "ok") -> None:
        self.raises, self.text, self.calls = raises, text, 0

    async def complete(self, *, system: str, user: str) -> str:
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        return self.text


def _cfg() -> AgentConfig:
    return AgentConfig(name="t", provider="openai", model="m", max_retries=2, backoff_base=0.0, timeout_s=5.0)


async def test_orchestrator_returns_text_on_success():
    reset_breakers()
    llm = _FakeLLM(text="oi")
    assert await ModelOrchestrator(llm, _cfg()).complete(system="s", user="u") == "oi"
    assert llm.calls == 1 and get_breaker("openai").allow()


async def test_orchestrator_non_retryable_no_retry_and_opens_breaker():
    reset_breakers()
    llm = _FakeLLM(raises=LLMError(retryable=False, reason="quota"))
    out = await ModelOrchestrator(llm, _cfg()).complete(system="s", user="u")
    assert out is None and llm.calls == 1               # NÃO retentou (quota)
    assert not get_breaker("openai").allow()            # e abriu o breaker


async def test_orchestrator_retryable_retries_then_degrades():
    reset_breakers()
    llm = _FakeLLM(raises=LLMError(retryable=True, reason="rate_limit"))
    out = await ModelOrchestrator(llm, _cfg()).complete(system="s", user="u")
    assert out is None and llm.calls == 3               # 1 + max_retries(2), depois degrada


async def test_orchestrator_breaker_open_short_circuits():
    reset_breakers()
    get_breaker("openai").record_failure(hard=True)     # breaker já aberto
    llm = _FakeLLM(text="oi")
    out = await ModelOrchestrator(llm, _cfg()).complete(system="s", user="u")
    assert out is None and llm.calls == 0               # nem chamou o LLM (protege latência/saldo)
