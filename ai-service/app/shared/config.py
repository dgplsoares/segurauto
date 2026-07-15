"""Configuração central (DEC-ORB-001/006/021).

Todos os parâmetros vêm de variáveis de ambiente (nunca literais espalhados — prepara a V2).
Os seams de integração (CRM/Ads/LLM) escolhem fake (default) vs real por aqui.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # App
    app_name: str = "segurauto-ai-service"
    environment: str = "local"
    log_level: str = "INFO"

    # Banco (Postgres + pgvector). Schemas separados business.* / ai.* (DEC-ORB-021).
    database_url: str = "postgresql+asyncpg://segurauto:segurauto@db:5432/segurauto"

    # Seams de integração — fake default / real opt-in (DEC-ORB-001/006/014)
    use_fake_crm: bool = True
    use_fake_ads: bool = True

    # LLM — stub determinístico default; OpenAI opt-in (DEC-ORB-006/008)
    llm_provider: str = "stub"  # stub | openai
    openai_api_key: str | None = None

    @property
    def masked_openai_key(self) -> str:
        """Nunca logar a chave em claro (DEC-ORB-018 — PII/segredos)."""
        return "set" if self.openai_api_key else "unset"


@lru_cache
def get_settings() -> Settings:
    return Settings()
