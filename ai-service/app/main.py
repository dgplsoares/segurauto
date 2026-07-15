"""Entrypoint do ai-service (FastAPI).

Monólito modular extraível (DEC-ORB-021): os contextos `business` e `ai` são montados aqui.
Na Fase 0 só o esqueleto + `/health`; as rotas de negócio (`/leads`) e de IA (`/ai/*`) entram
nas fases seguintes.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.shared.config import get_settings
from app.shared.health import router as health_router
from app.shared.observability import RequestIdMiddleware, configure_logging

logger = logging.getLogger("segurauto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logger.info(
        "ai-service iniciando env=%s llm_provider=%s openai_key=%s fake_crm=%s fake_ads=%s",
        s.environment, s.llm_provider, s.masked_openai_key, s.use_fake_crm, s.use_fake_ads,
    )
    yield
    logger.info("ai-service encerrando")


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level)
    app = FastAPI(title=s.app_name, version="0.0.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)

    # Ops
    app.include_router(health_router)

    # Contextos (montados nas próximas fases):
    # from app.business.api.leads import router as leads_router; app.include_router(leads_router)
    # from app.ai.api.endpoints import router as ai_router;     app.include_router(ai_router, prefix="/ai")
    return app


app = create_app()
