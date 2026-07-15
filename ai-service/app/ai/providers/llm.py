"""LLMPort: `StubLLM` determinístico (default, CI) e `OpenAILLM` (opt-in, import lazy). DEC-ORB-006/008."""
from app.shared.config import get_settings


class StubLLM:
    """Resposta previsível derivada do input (sem rede)."""

    async def complete(self, *, system: str, user: str) -> str:
        snippet = " ".join(user.split())[:120]
        return f"[stub] {snippet}"


class OpenAILLM:
    """LLM real (opt-in). Import de `openai` só quando efetivamente usado."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.2) -> None:
        self.model = model
        self.temperature = temperature

    async def complete(self, *, system: str, user: str) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("OpenAILLM requer o pacote `openai` (opt-in).") from exc
        client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        resp = await client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""


def get_llm():
    if get_settings().llm_provider.lower() == "openai":
        return OpenAILLM()
    return StubLLM()
