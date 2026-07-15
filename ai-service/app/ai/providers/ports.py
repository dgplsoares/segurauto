"""Portas do contexto `ai` (DEC-ORB-006). StubLLM/HeuristicRerank default; OpenAI/Cohere opt-in."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


@runtime_checkable
class RerankPort(Protocol):
    def rerank(self, query: str, docs: list[str], top_k: int = 3) -> list[tuple[int, float]]:
        """Retorna [(índice_do_doc, score)] ordenado do mais relevante ao menos, top_k."""
        ...
