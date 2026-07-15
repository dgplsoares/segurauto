"""`POST /support/chat` — suporte ao lead **autenticado** (`require_session` → anti-IDOR). Só o lead
dono da sessão conversa. Single-turn / stateless (histórico persistente é a Fase 5)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.business.ai_port import InProcessAiAdapter
from app.business.api.deps import require_session
from app.shared.database import get_session

router = APIRouter(tags=["support"])

_ai = InProcessAiAdapter()


class SupportChatRequest(BaseModel):
    message: str


class SupportChatResponse(BaseModel):
    answer: str
    handoff_suggested: bool


@router.post("/support/chat", response_model=SupportChatResponse)
async def support_chat(
    payload: SupportChatRequest,
    lead_id: str = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> SupportChatResponse:
    result = await _ai.support(query=payload.message, session=session)
    return SupportChatResponse(answer=result["answer"], handoff_suggested=result["handoff_suggested"])
