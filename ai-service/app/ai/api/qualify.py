"""`POST /ai/qualify` — contrato HTTP **stateless** (DEC-ORB-021). Recebe atributos do lead → resultado
estruturado. Não acessa tabelas de negócio; na V2 é o endpoint que o `AiPort` (client HTTP) chama."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.agents.qualification_agent import get_qualification_agent

router = APIRouter(tags=["ai"])


class QualifyRequest(BaseModel):
    has_vehicle: bool
    has_phone: bool
    has_zipcode: bool
    consent: bool
    source: str | None = None


class QualifyResponse(BaseModel):
    score: int
    band: str
    reason: str


@router.post("/qualify", response_model=QualifyResponse)
async def qualify(req: QualifyRequest) -> QualifyResponse:
    result = await get_qualification_agent().qualify(
        has_vehicle=req.has_vehicle,
        has_phone=req.has_phone,
        has_zipcode=req.has_zipcode,
        consent=req.consent,
        source=req.source,
    )
    return QualifyResponse(score=result.score, band=result.band.value, reason=result.reason)
