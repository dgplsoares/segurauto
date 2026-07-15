"""`ModelOrchestrator` (DEC-ORB-018/022): chama o LLM com timeout + retry/backoff e registra o turno.
Degrada para `None` em erro/timeout (o agente cai no fallback determinístico)."""
import asyncio
import time

from app.ai.agents.config import AgentConfig
from app.shared.observability import log_agent_turn


class ModelOrchestrator:
    def __init__(self, llm, config: AgentConfig) -> None:
        self.llm = llm
        self.config = config

    async def complete(self, *, system: str, user: str) -> str | None:
        start = time.monotonic()
        for attempt in range(self.config.max_retries + 1):
            try:
                text = await asyncio.wait_for(
                    self.llm.complete(system=system, user=user), timeout=self.config.timeout_s
                )
                log_agent_turn(
                    agent=self.config.name, model=self.config.model, outcome="ok",
                    latency_ms=(time.monotonic() - start) * 1000,
                )
                return text
            except Exception:
                if attempt >= self.config.max_retries:
                    log_agent_turn(
                        agent=self.config.name, model=self.config.model, outcome="error",
                        latency_ms=(time.monotonic() - start) * 1000,
                    )
                    return None
                await asyncio.sleep(self.config.backoff_base * (2**attempt))
        return None
