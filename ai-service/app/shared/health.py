"""Endpoints de saúde (DEC-ORB-016).

- `/health`      liveness — não depende do banco.
- `/health/ready` readiness — checa o banco (SELECT 1); 503 se indisponível.
"""
from fastapi import APIRouter, Response, status

from app.shared.database import ping
from app.shared.metrics import render_metrics

router = APIRouter(tags=["ops"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(response: Response) -> dict:
    db_ok = await ping()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "db": False}
    return {"status": "ready", "db": True}


@router.get("/metrics")
async def metrics() -> Response:
    return render_metrics()
