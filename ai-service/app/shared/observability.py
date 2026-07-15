"""Observabilidade base (DEC-ORB-015/019/036).

- `configure_logging`: logging estruturado + `request_id` em toda linha + **masking de PII** (defesa em profundidade).
- `RequestIdMiddleware` (**pure-ASGI**): gera o `request_id` **server-side**; só aceita `X-Request-Id` de
  **origem confiável** (assinado pelo BFF) e **nunca ecoa** valor do cliente; sobrevive ao streaming (chat F4).
"""
import hashlib
import hmac
import logging
import re
import uuid
from contextvars import ContextVar

from app.shared.config import get_settings

# Correlação: propagada in-process via contextvars; na V2 vem/segue por header assinado.
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


# ---- Masking de PII (DEC-ORB-036 + E8): padrões SEGUROS que não colidem com UUID/ids ----
# UUID: 8-4-4-4-12 (com hífens) e request_id = uuid4().hex (32 hex, sem hífen). Os padrões abaixo exigem
# hífen na posição do CEP/telefone e ancoram a placa em 7 chars com \b — nenhum casa segmentos de UUID.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")       # só o formato pontuado (não bare 11 dígitos)
_CEP_RE = re.compile(r"\b\d{5}-\d{3}\b")                     # CEP formatado (hífen na pos.5 → não casa uuid)
# Telefone BR: exige parêntese OU espaço separando o DDD (senão casaria dígitos de UUID tipo 2345678-1234).
_PHONE_RE = re.compile(r"\(\d{2}\)\s?\d{4,5}-\d{4}|\b\d{2}\s\d{4,5}-\d{4}\b")
_PLACA_RE = re.compile(r"(?i)\b[A-Z]{3}-?\d[A-Z0-9]\d{2}\b")  # E8: case-insensitive (7 chars + \b → não uuid)


def redact_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text)
    text = _CPF_RE.sub("[cpf]", text)
    text = _CEP_RE.sub("[cep]", text)
    text = _PHONE_RE.sub("[telefone]", text)
    text = _PLACA_RE.sub("[placa]", text)
    return text


class PiiRedactingFilter(logging.Filter):
    """Rede de segurança: redige PII na linha renderizada (não substitui `_mask` nos call-sites)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_pii(record.getMessage()).replace("\r", " ").replace("\n", " ")  # anti log-forging
        record.args = ()
        # Tracebacks só são formatados no handler (exc_text ainda é None aqui) → pré-formata e redige agora;
        # com exc_text setado, o Formatter não re-formata o exc_info cru.
        if record.exc_info:
            record.exc_text = redact_pii(logging.Formatter().formatException(record.exc_info))
        elif record.exc_text:
            record.exc_text = redact_pii(record.exc_text)
        return True


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
    pii_filter = PiiRedactingFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(pii_filter)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # echo-off defense-in-depth


_RID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _resolve_inbound_rid(scope) -> str | None:
    """Aceita `X-Request-Id` só se assinado pela origem confiável (BFF); senão gera server-side."""
    secret = get_settings().trusted_proxy_secret
    if not secret:
        return None
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    rid = headers.get("x-request-id")
    sig = headers.get("x-request-id-sig")
    if not rid or not sig or not _RID_RE.match(rid):
        return None
    expected = hmac.new(secret.encode(), rid.encode(), hashlib.sha256).hexdigest()
    return rid if hmac.compare_digest(sig, expected) else None


class RequestIdMiddleware:
    """Middleware pure-ASGI: seta o `request_id` na task do request (sobrevive ao streaming) e injeta o
    header `X-Request-Id` na resposta com o valor SERVER-SIDE (nunca o do cliente)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        rid = _resolve_inbound_rid(scope) or uuid.uuid4().hex
        token = request_id_ctx.set(rid)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", rid.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            request_id_ctx.reset(token)
