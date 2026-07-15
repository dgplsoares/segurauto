"""`POST /ai/support` — contrato HTTP do suporte (DEC-ORB-021). Recebe a sessão do request p/ o RAG
(read); não persiste conversa (single-turn). Na V2 é o endpoint que o `AiPort` (client HTTP) chama."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.config import get_support_config
from app.ai.agents.support_agent import get_support_agent
from app.ai.providers.embeddings import get_embedder
from app.ai.rag.rag_service import RagService
from app.ai.rag.vector_store import VectorStore
from app.shared.database import get_session

router = APIRouter(tags=["ai"])


class SupportRequest(BaseModel):
    query: str


class SupportResponse(BaseModel):
    answer: str
    sufficient: bool
    handoff_suggested: bool


@router.post("/support", response_model=SupportResponse)
async def support(req: SupportRequest, session: AsyncSession = Depends(get_session)) -> SupportResponse:
    cfg = get_support_config()
    rag = RagService(VectorStore(session), get_embedder(), k=cfg.rag_k, min_score=cfg.rag_min_score)
    result = await get_support_agent().answer(req.query, rag=rag)
    return SupportResponse(**result)
