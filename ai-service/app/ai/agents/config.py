"""`AgentConfig` (DEC-ORB-022): parâmetros do agente. V1 env/hardcoded → V2 painel admin."""
from dataclasses import dataclass
from functools import lru_cache

from app.shared.config import get_settings

QUALIFICATION_SYSTEM_PROMPT = (
    "Você é um analista de qualificação de leads de seguro de automóvel. Explique em UMA frase curta, "
    "objetiva e em português, o motivo da pontuação do lead, sem inventar dados."
)


@dataclass(frozen=True)
class AgentConfig:
    name: str
    provider: str  # stub | openai
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 200
    use_llm_assess: bool = False  # False = rubrica-only determinístico (CI)
    system_prompt: str = ""
    timeout_s: float = 15.0
    max_retries: int = 2
    backoff_base: float = 0.5


@lru_cache
def get_qualification_config() -> AgentConfig:
    provider = get_settings().llm_provider.lower()
    return AgentConfig(
        name="qualification",
        provider=provider,
        use_llm_assess=(provider == "openai"),
        system_prompt=QUALIFICATION_SYSTEM_PROMPT,
    )
