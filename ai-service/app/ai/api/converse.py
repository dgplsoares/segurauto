"""`POST /ai/converse` — contrato HTTP STATELESS do consultor de cotação (DEC-ORB-021/039).

Recebe transcrito + slots + faltantes MONTADOS pelo caller e devolve a resposta. ⚠️ **Sem `session_id`/
`lead_id` no contrato** (furo IDOR-LOW da reanálise): o contexto `ai` nunca ganha uma chave para consultar
conversa cross-lead — todo o anti-IDOR mora no endpoint de turno do `business`. A `AsyncSession` recebida é
só infra do RAG (base de conhecimento compartilhada), não escopo de lead.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.config import get_converse_config
from app.ai.agents.converse_agent import get_converse_agent
from app.ai.providers.embeddings import get_embedder
from app.ai.rag.rag_service import RagService
from app.ai.rag.vector_store import VectorStore
from app.shared.database import get_session

router = APIRouter(tags=["ai"])


class ConverseRequest(BaseModel):
    user_message: str
    transcript: list = []
    slots: dict = {}
    missing: list = []
    progressed: bool = False


class ConverseResponse(BaseModel):
    reply: str
    sufficient: bool
    handoff_suggested: bool


@router.post("/converse", response_model=ConverseResponse)
async def converse(req: ConverseRequest, session: AsyncSession = Depends(get_session)) -> ConverseResponse:
    cfg = get_converse_config()
    rag = RagService(VectorStore(session), get_embedder(), k=cfg.rag_k, min_score=cfg.rag_min_score)
    result = await get_converse_agent().converse(
        transcript=req.transcript, slots=req.slots, missing=req.missing,
        progressed=req.progressed, user_message=req.user_message, rag=rag,
    )
    return ConverseResponse(**result)
