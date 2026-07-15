"""Testes contra provedores REAIS de LLM (DEC-ORB-006/046) — **opt-in**, NÃO rodam no CI.

Pulados a menos que `LLM_PROVIDER` seja `openai`/`anthropic` **e** a respectiva chave esteja no ambiente.
Fazem uma chamada real (consome tokens). Rode explicitamente, ex.:

    LLM_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... pytest ai-service/tests/real -q
"""
import pytest

from app.ai.providers.llm import AnthropicLLM, OpenAILLM
from app.shared.config import get_settings


def _ready_provider() -> str | None:
    s = get_settings()
    provider = s.llm_provider.lower()
    if provider == "anthropic" and s.anthropic_api_key:
        return "anthropic"
    if provider == "openai" and s.openai_api_key:
        return "openai"
    return None


@pytest.mark.skipif(_ready_provider() is None, reason="opt-in: exige LLM_PROVIDER real + a chave no .env")
async def test_real_provider_completes_nonempty():
    s = get_settings()
    llm = AnthropicLLM(model=s.anthropic_model) if _ready_provider() == "anthropic" else OpenAILLM(model=s.openai_model)
    reply = await llm.complete(system="Responda apenas 'ok'.", user="diga ok")
    assert isinstance(reply, str) and reply.strip()  # o provider real devolveu texto
