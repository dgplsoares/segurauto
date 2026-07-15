"""API de avaliação/jornada (DEC-ORB-042). Montada só em local/`enable_eval_api` (fail-closed no `main`).

- `GET /eval/leads` — descoberta: leads recentes (o avaliador escolhe um e-mail).
- `GET /eval/leads/journey?email=...&format=json|html` — a jornada agregada do lead.

O gate `require_eval_enabled` re-checa o flag como defesa em profundidade (além do gate de montagem):
se por engano o router for incluído fora de local, ainda responde 404.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.render import render_html
from app.eval.service.journey_service import JourneyService
from app.shared.config import get_settings
from app.shared.database import get_session

router = APIRouter(tags=["eval"])


def require_eval_enabled() -> None:
    s = get_settings()
    if not (s.enable_eval_api or s.environment == "local"):
        # Fail-closed: fora de local e sem flag, a superfície simplesmente não existe.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


@router.get("/leads", dependencies=[Depends(require_eval_enabled)])
async def list_recent_leads(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return {"leads": await JourneyService(session).recent_leads(limit=limit)}


@router.get("/leads/journey", dependencies=[Depends(require_eval_enabled)])
async def lead_journey(
    email: str = Query(..., min_length=3, max_length=320),
    format: str = Query(default="json", pattern="^(json|html)$"),
    session: AsyncSession = Depends(get_session),
):
    journey = await JourneyService(session).journey(email)
    if journey is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead_not_found")
    if format == "html":
        return HTMLResponse(render_html(journey))
    return journey
