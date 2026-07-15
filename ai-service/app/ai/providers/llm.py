"""LLMPort e adapters (DEC-ORB-006/008/046).

- `StubLLM` — determinístico, default e do CI (sem rede).
- `OpenAILLM` / `AnthropicLLM` — reais, opt-in por `.env`; import do SDK **lazy** (não pesa o CI/stub).

Os adapters normalizam falhas em `LLMError(retryable, reason)` para o `ModelOrchestrator` decidir retry vs.
degradação (e o circuit-breaker) de forma provider-agnóstica — `insufficient_quota`/401 NÃO são retentados.
"""
from app.shared.config import get_settings


class LLMError(Exception):
    """Falha normalizada de um provider real. `retryable`: 429/5xx/timeout. Não-retryable: 401/quota/400."""

    def __init__(self, *, retryable: bool, reason: str) -> None:
        super().__init__(reason)
        self.retryable = retryable
        self.reason = reason


class StubLLM:
    """Resposta previsível derivada do input (sem rede). Nunca levanta `LLMError`."""

    async def complete(self, *, system: str, user: str) -> str:
        snippet = " ".join(user.split())[:120]
        return f"[stub] {snippet}"


def _classify(status: int | None, code: str | None, etype: str | None) -> LLMError:
    """Mapeia (status, code, type) de OpenAI/Anthropic → LLMError. `insufficient_quota`/billing = não-retryable."""
    code, etype = (code or "").lower(), (etype or "").lower()
    if "insufficient_quota" in code or "billing" in etype or "credit" in etype:
        return LLMError(retryable=False, reason="quota")
    if status == 429:
        return LLMError(retryable=True, reason="rate_limit")
    if status in (401, 403):
        return LLMError(retryable=False, reason="auth")
    if status is not None and status >= 500:
        return LLMError(retryable=True, reason="server")
    return LLMError(retryable=False, reason="bad_request")


class OpenAILLM:
    """LLM real (opt-in). Import de `openai` só quando usado. Modelo via ENV (DEC-ORB-001)."""

    def __init__(self, model: str, temperature: float = 0.2, max_tokens: int = 400) -> None:
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens

    async def complete(self, *, system: str, user: str) -> str:
        try:
            import openai
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMError(retryable=False, reason="sdk_missing") from exc
        client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        try:
            resp = await client.chat.completions.create(
                model=self.model, temperature=self.temperature, max_tokens=self.max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
        except openai.APIStatusError as e:
            raise _classify(getattr(e, "status_code", None), getattr(e, "code", None), None) from e
        except (openai.APITimeoutError, openai.APIConnectionError) as e:
            raise LLMError(retryable=True, reason="timeout") from e
        return resp.choices[0].message.content or ""


class AnthropicLLM:
    """LLM real da Anthropic (opt-in). Import de `anthropic` lazy. Modelo via ENV (default Opus 4.8)."""

    def __init__(self, model: str, max_tokens: int = 400) -> None:
        self.model, self.max_tokens = model, max_tokens

    async def complete(self, *, system: str, user: str) -> str:
        try:
            import anthropic
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMError(retryable=False, reason="sdk_missing") from exc
        client = AsyncAnthropic(api_key=get_settings().anthropic_api_key)
        try:
            resp = await client.messages.create(
                model=self.model, max_tokens=self.max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIStatusError as e:
            raise _classify(getattr(e, "status_code", None), None, getattr(e, "type", None)) from e
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as e:
            raise LLMError(retryable=True, reason="timeout") from e
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def get_llm():
    """Factory: stub (default/CI) | openai | anthropic — escolhido por `LLM_PROVIDER` no `.env`."""
    s = get_settings()
    provider = s.llm_provider.lower()
    if provider == "openai":
        return OpenAILLM(model=s.openai_model)
    if provider == "anthropic":
        return AnthropicLLM(model=s.anthropic_model)
    return StubLLM()
