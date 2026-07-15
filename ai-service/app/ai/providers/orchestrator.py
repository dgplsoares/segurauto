"""`ModelOrchestrator` (DEC-ORB-018/022/046): chama o LLM com timeout + retry/backoff, classifica falhas e
protege latência/saldo com um **circuit-breaker por provider**. Degrada para `None` em erro (o agente cai no
fallback DETERMINÍSTICO — cotação/handoff seguem funcionando; nunca no eco do stub).

Política (respondendo ao trade-off da fase): `insufficient_quota`/401 abrem o breaker na hora e NÃO são
retentados (retry só queimaria tempo/saldo); 429/5xx/timeout retentam com backoff e degradam ao esgotar.
"""
import asyncio
import time

from prometheus_client import Counter

from app.ai.agents.config import AgentConfig
from app.ai.providers.llm import LLMError
from app.shared.observability import log_agent_turn

LLM_ERROR = Counter("llm_error_total", "Falhas do provider de LLM por motivo", ["reason"])
LLM_FALLBACK = Counter("llm_fallback_total", "Degradações para o determinístico", ["agent", "reason"])


class CircuitBreaker:
    """Abre após `threshold` falhas consecutivas (ou 1 falha 'hard' de auth/quota); reabre após `cooldown_s`."""

    def __init__(self, threshold: int = 3, cooldown_s: float = 30.0) -> None:
        self.threshold, self.cooldown_s = threshold, cooldown_s
        self._fails = 0
        self._open_until = 0.0

    def allow(self) -> bool:
        return time.monotonic() >= self._open_until

    def record_success(self) -> None:
        self._fails, self._open_until = 0, 0.0

    def record_failure(self, *, hard: bool = False) -> None:
        self._fails += 1
        if hard or self._fails >= self.threshold:
            self._open_until = time.monotonic() + self.cooldown_s


_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(provider: str) -> CircuitBreaker:
    return _breakers.setdefault(provider, CircuitBreaker())


def reset_breakers() -> None:
    """Zera os breakers (testes)."""
    _breakers.clear()


class ModelOrchestrator:
    def __init__(self, llm, config: AgentConfig) -> None:
        self.llm = llm
        self.config = config

    def _degrade(self, breaker: CircuitBreaker, *, hard: bool, reason: str, start: float) -> None:
        breaker.record_failure(hard=hard)
        LLM_FALLBACK.labels(agent=self.config.name, reason=reason).inc()
        log_agent_turn(
            agent=self.config.name, model=self.config.model, outcome="error",
            latency_ms=(time.monotonic() - start) * 1000,
        )

    async def complete(self, *, system: str, user: str) -> str | None:
        breaker = get_breaker(self.config.provider)
        if not breaker.allow():  # provider em incidente/sem saldo → serve determinístico sem chamar
            LLM_FALLBACK.labels(agent=self.config.name, reason="breaker_open").inc()
            return None
        start = time.monotonic()
        for attempt in range(self.config.max_retries + 1):
            try:
                text = await asyncio.wait_for(
                    self.llm.complete(system=system, user=user), timeout=self.config.timeout_s
                )
                breaker.record_success()
                log_agent_turn(
                    agent=self.config.name, model=self.config.model, outcome="ok",
                    latency_ms=(time.monotonic() - start) * 1000,
                )
                return text
            except LLMError as e:
                LLM_ERROR.labels(reason=e.reason).inc()
                if not e.retryable:  # auth/quota/bad_request → não retenta; abre o breaker
                    self._degrade(breaker, hard=True, reason=e.reason, start=start)
                    return None
                if attempt >= self.config.max_retries:
                    self._degrade(breaker, hard=False, reason=e.reason, start=start)
                    return None
            except asyncio.TimeoutError:  # retryable
                LLM_ERROR.labels(reason="timeout").inc()
                if attempt >= self.config.max_retries:
                    self._degrade(breaker, hard=False, reason="timeout", start=start)
                    return None
            except Exception:  # noqa: BLE001 — erro inesperado do adapter: retryable, mas rótulo honesto
                LLM_ERROR.labels(reason="unknown").inc()
                if attempt >= self.config.max_retries:
                    self._degrade(breaker, hard=False, reason="unknown", start=start)
                    return None
            await asyncio.sleep(self.config.backoff_base * (2**attempt))
        return None
