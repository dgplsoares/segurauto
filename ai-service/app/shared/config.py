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

    # API de avaliação/jornada (DEC-ORB-042). Read-only, expõe a jornada agregada do lead. FAIL-CLOSED:
    # só é montada em environment=local OU com este flag explicitamente ligado (nunca por acidente em prod).
    enable_eval_api: bool = False

    # Banco (Postgres + pgvector). Schemas separados business.* / ai.* (DEC-ORB-021).
    database_url: str = "postgresql+asyncpg://segurauto:segurauto@db:5432/segurauto"

    # Seams de integração — fake default / real opt-in (DEC-ORB-001/006/014)
    use_fake_crm: bool = True
    use_fake_ads: bool = True

    # LLM — stub determinístico default; provider real opt-in (DEC-ORB-006/008/046)
    llm_provider: str = "stub"  # stub | openai | anthropic
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-opus-4-8"  # override p/ custo, ex.: claude-haiku-4-5

    # Embeddings — stub determinístico default; OpenAI opt-in (DEC-ORB-023)
    embeddings_provider: str = "stub"  # stub | openai

    # Correlação: segredo compartilhado com o BFF p/ assinar X-Request-Id (DEC-ORB-036). Sem ele,
    # o request_id é sempre gerado server-side (seguro por default).
    trusted_proxy_secret: str | None = None

    # E-mail (SMTP genérico — DEC-ORB-047). Provider é INFRA trocável: a app não conhece o fornecedor,
    # só fala SMTP. Trocar de provider = mudar estas vars, zero código. Efetivo só com use_fake_notifications=0.
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_ssl: bool = True          # True → TLS implícito (porta 465); False → STARTTLS (porta 587)
    smtp_user: str = ""
    smtp_password: str | None = None
    smtp_timeout_s: int = 15
    mail_from: str = "SegurAuto <noreply@localhost>"  # remetente; domínio precisa estar verificado no provider
    mail_bcc: str | None = None

    # Auth / OTP (DEC-ORB-037). auth_pepper é fail-closed fora de environment=local.
    auth_pepper: str | None = None
    use_fake_notifications: bool = True
    otp_ttl_s: int = 600            # 10 min
    otp_length: int = 5
    otp_max_attempts: int = 5
    otp_resend_interval_s: int = 30
    otp_rate_window_s: int = 900    # 15 min
    otp_rate_max: int = 5
    session_idle_ttl_s: int = 1800      # 30 min (sliding)
    session_absolute_ttl_s: int = 43200  # 12 h
    session_slide_coalesce_s: int = 60

    # Chat multi-turn (DEC-ORB-038/040). Pool ISOLADO + timeouts: um turno lento não inani a captura.
    chat_pool_size: int = 5
    chat_pool_max_overflow: int = 5
    chat_lock_timeout_ms: int = 3000        # espera máx. pelo FOR UPDATE (turno concorrente → 409 rápido)
    chat_statement_timeout_ms: int = 20000  # teto de statement no pool do chat
    chat_transcript_max_turns: int = 20     # janela do transcrito passado à IA (E8)
    chat_message_max_len: int = 2000        # cap de entrada da mensagem (E8)

    @property
    def masked_openai_key(self) -> str:
        """Nunca logar a chave em claro (DEC-ORB-018 — PII/segredos)."""
        return "set" if self.openai_api_key else "unset"

    @property
    def masked_anthropic_key(self) -> str:
        return "set" if self.anthropic_api_key else "unset"

    @property
    def masked_smtp_password(self) -> str:
        """Nunca logar a senha/API key do SMTP em claro (DEC-ORB-018/047)."""
        return "set" if self.smtp_password else "unset"


@lru_cache
def get_settings() -> Settings:
    return Settings()
