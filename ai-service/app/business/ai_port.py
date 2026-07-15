"""`AiPort` — a única porta pela qual o `business` fala com o `ai` (DEC-ORB-021).

- Na V1, `InProcessAiAdapter` roda in-process (Fase 1: rubrica determinística; Fase 3: delega aos
  agentes LangGraph do contexto `ai`).
- Na V2, este adapter é trocado por um **client HTTP** para o serviço de IA — mesmo contrato,
  sem tocar no domínio.
"""
from typing import Protocol, runtime_checkable

from app.business.domain.qualification import QualificationResult


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

    async def support(self, *, query: str) -> str: ...


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

    async def support(self, *, query: str) -> str:
        return f"[suporte] recebido: {' '.join(query.split())[:120]}"
