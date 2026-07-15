"""LLM stub determinístico (DEC-ORB-006/008): gate de CI sem segredos nem flakiness.
O provedor OpenAI real entra como implementação alternativa opt-in (Fase 3).
"""


class StubLLM:
    """Implementa `LLMPort`. Resposta previsível derivada do input (sem rede)."""

    async def complete(self, *, system: str, user: str) -> str:
        snippet = " ".join(user.split())[:120]
        return f"[stub] {snippet}"
