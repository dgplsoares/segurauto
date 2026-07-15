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

    # Ops (health/ready/metrics)
    app.include_router(health_router)

    # Contexto business
    from app.business.api.auth import router as auth_router
    from app.business.api.chat import router as chat_router
    from app.business.api.leads import router as leads_router
    from app.business.api.support import router as support_router

    app.include_router(leads_router)
    app.include_router(auth_router, prefix="/auth")
    app.include_router(support_router)
    app.include_router(chat_router)  # /support/sessions (chat multi-turn — F5a)

    # Contexto ai — contrato stateless /ai/* (DEC-ORB-021)
    from app.ai.api.converse import router as ai_converse_router
    from app.ai.api.qualify import router as ai_qualify_router
    from app.ai.api.support import router as ai_support_router

    app.include_router(ai_qualify_router, prefix="/ai")
    app.include_router(ai_support_router, prefix="/ai")
    app.include_router(ai_converse_router, prefix="/ai")
    return app


app = create_app()
