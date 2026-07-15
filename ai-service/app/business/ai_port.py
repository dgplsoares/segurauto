"""`AiPort` — a única porta pela qual o `business` fala com o `ai` (DEC-ORB-021).

- Na V1, `InProcessAiAdapter` roda in-process (Fase 1: rubrica determinística; Fase 3: delega aos
  agentes LangGraph do contexto `ai`).
- Na V2, este adapter é trocado por um **client HTTP** para o serviço de IA — mesmo contrato,
  sem tocar no domínio.
"""
from typing import Protocol, runtime_checkable

from app.shared.qualification import QualificationResult


@runtime_checkable
class AiPort(Protocol):
    async def qualify(
        self,
        *,
        has_vehicle: bool,
        has_phone: bool,
        has_zipcode: bool,
        consent: bool,
        source: str | None,
    ) -> QualificationResult: ...

    async def support(self, *, query: str, session) -> dict: ...

    async def converse(
        self, *, transcript: list, slots: dict, missing: list, progressed: bool, user_message: str, session
    ) -> dict: ...


class InProcessAiAdapter:
    """Implementação in-process do `AiPort`. `qualify` delega ao grafo do contexto `ai` (o único
    ponto onde `business` toca `ai` — na V2 vira client HTTP para `/ai/qualify`)."""

    async def qualify(
        self,
        *,
        has_vehicle: bool,
        has_phone: bool,
        has_zipcode: bool,
        consent: bool,
        source: str | None,
    ) -> QualificationResult:
        from app.ai.agents.qualification_agent import get_qualification_agent  # seam business→ai

        return await get_qualification_agent().qualify(
            has_vehicle=has_vehicle,
            has_phone=has_phone,
            has_zipcode=has_zipcode,
            consent=consent,
            source=source,
        )

    async def support(self, *, query: str, session) -> dict:
        # O suporte LÊ o RAG → recebe a sessão (detalhe in-process; na V2 o client HTTP a ignora).
        from app.ai.agents.config import get_support_config
        from app.ai.agents.support_agent import get_support_agent
        from app.ai.providers.embeddings import get_embedder
        from app.ai.rag.rag_service import RagService
        from app.ai.rag.vector_store import VectorStore

        cfg = get_support_config()
        rag = RagService(VectorStore(session), get_embedder(), k=cfg.rag_k, min_score=cfg.rag_min_score)
        return await get_support_agent().answer(query, rag=rag)

    async def converse(
        self, *, transcript: list, slots: dict, missing: list, progressed: bool, user_message: str, session
    ) -> dict:
        # O consultor LÊ o RAG → recebe a sessão (detalhe in-process; na V2 o client HTTP a ignora). A
        # extração de slots é do business (determinística) — o agente só recebe o estado e gera a resposta.
        from app.ai.agents.config import get_converse_config
        from app.ai.agents.converse_agent import get_converse_agent
        from app.ai.providers.embeddings import get_embedder
        from app.ai.rag.rag_service import RagService
        from app.ai.rag.vector_store import VectorStore

        cfg = get_converse_config()
        rag = RagService(VectorStore(session), get_embedder(), k=cfg.rag_k, min_score=cfg.rag_min_score)
        return await get_converse_agent().converse(
            transcript=transcript, slots=slots, missing=missing, progressed=progressed,
            user_message=user_message, rag=rag,
        )
