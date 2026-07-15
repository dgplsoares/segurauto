"""Observabilidade base (DEC-ORB-015/019).

- `configure_logging`: logging estruturado, idempotente, com `request_id` em toda linha.
- `RequestIdMiddleware`: gera/propaga `X-Request-Id` (correlação transport-agnostic — sobrevive
  à fronteira assíncrona e, na V2, ao hop HTTP entre serviços).
"""
import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Correlação: propagada in-process via contextvars; na V2 vem/segue por header.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Logger dedicado ao caminho dos agentes (tokens/latência = custo — DEC-ORB-015/019).
agent_logger = logging.getLogger("segurauto.agent")


def log_agent_turn(
    *,
    agent: str,
    model: str,
    outcome: str,
    latency_ms: float | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    """Log estruturado de um turno de agente (grep-able)."""
    agent_logger.info(
        "agent_turn agent=%s model=%s outcome=%s latency_ms=%s in_tokens=%s out_tokens=%s",
        agent, model, outcome,
        f"{latency_ms:.0f}" if latency_ms is not None else "-",
        input_tokens if input_tokens is not None else "-",
        output_tokens if output_tokens is not None else "-",
    )

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [rid=%(request_id)s] %(message)s"
_factory_installed = False


def _install_record_factory() -> None:
    """Injeta `request_id` em TODO LogRecord (inclusive de libs), evitando KeyError no formato."""
    global _factory_installed
    if _factory_installed:
        return
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id_ctx.get()
        return record

    logging.setLogRecordFactory(record_factory)
    _factory_installed = True


def configure_logging(level: str = "INFO") -> None:
    """Configuração mínima e idempotente de logging, chamada no startup."""
    _install_record_factory()
    logging.basicConfig(level=level.upper(), format=_LOG_FORMAT, force=True)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex
        token = request_id_ctx.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = rid
            return response
        finally:
            request_id_ctx.reset(token)
