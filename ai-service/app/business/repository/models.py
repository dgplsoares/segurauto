"""Modelos ORM do contexto `business` (schema `business`). Sem FK para o schema `ai` (DEC-ORB-021)."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LeadRow(Base):
    __tablename__ = "leads"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str] = mapped_column(String(40), index=True)
    vehicle: Mapped[str] = mapped_column(String(200))
    zipcode: Mapped[str] = mapped_column(String(20))
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="received", index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    band: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    click_id: Mapped[str | None] = mapped_column(String(120), nullable=True)  # gclid/fbclid da LP (F6)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxRow(Base):
    """Efeitos externos gravados na MESMA transação do lead (DEC-ORB-012). `lead_id` referencia
    `business.leads.id` por id (sem FK cruzada de schema). Correlação preservada em `request_id`."""

    __tablename__ = "outbox"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36), index=True)
    intent_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|done|dead
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSessionRow(Base):
    """Sessão autenticada (DEC-ORB-037): `token_hash` = sha256 do token (nunca o cru) → `lead_id`."""

    __tablename__ = "auth_sessions"
    __table_args__ = {"schema": "business"}

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)  # idle (sliding)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OtpCodeRow(Base):
    """OTP (DEC-ORB-037): `code_hash` = HMAC(pepper, email:code). Tentativa errada incrementa `attempts` +
    `last_attempt_at` (cooldown), mas **não consome** (`consumed_at`) — anti-lockout."""

    __tablename__ = "otp_codes"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdentityRow(Base):
    """Identidade canônica por e-mail verificado (DEC-ORB-041). `canonical_lead_id` é a âncora **estável**
    da sessão: a re-auth resolve sempre o mesmo `lead_id`, dando continuidade sem afrouxar o gate."""

    __tablename__ = "identities"
    __table_args__ = {"schema": "business"}

    email_normalized: Mapped[str] = mapped_column(String(320), primary_key=True)
    canonical_lead_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatSessionRow(Base):
    """Conversa de cotação (DEC-ORB-038). Escopada ao `lead_id` canônico (id NU, sem FK cruzada de schema).
    `slots` = estado de slot-filling business-owned; `quote_ready_at`/`handoff_*` são ganchos ortogonais
    (F5b/handoff), nunca `funnel_status` (DEC-ORB-034)."""

    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")  # active | closed
    slots: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    quote_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handoff_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handoff_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # F6
    # Gate da confirmação de handoff (F6) — single-writer, distinto do hint handoff_requested_at (2 writers).
    handoff_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_turn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatMessageRow(Base):
    """Mensagem da conversa (DEC-ORB-038). `seq` ordena/dedup o turno; `client_turn_id` dá **idempotência
    de turno lógico** (replay em retry). `content` NUNCA é logado cru (masking central, inv.10)."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_chat_messages_session_seq"),
        UniqueConstraint("session_id", "client_turn_id", name="uq_chat_messages_session_turn"),
        {"schema": "business"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business.chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_turn_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuoteRow(Base):
    """Cotação gerada na conversa (DEC-ORB-043). Escopada à sessão; prêmio em **centavos** (vem do CRM, não
    do LLM). Uma por sessão (re-cota = F6). `pdf_ref` é só um marcador (sem bytes)."""

    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_quotes_session"),
        {"schema": "business"},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("business.chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(String(36), index=True)
    premium_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), server_default="BRL")
    slots: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    coverages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    broker_applied: Mapped[bool] = mapped_column(Boolean, server_default="false")
    pdf_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntegrationEventRow(Base):
    """Audit append-only das trocas com sistemas externos (fakes) — DEC-ORB-044. Habilita a jornada
    (DEC-ORB-042). `request`/`response` já mascarados de PII pelo caller; o OTP NUNCA registra o código."""

    __tablename__ = "integration_events"
    __table_args__ = {"schema": "business"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)  # crm_sync|crm_price_quote|ads_conversion|notify
    request: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    response: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(20), server_default="ok")  # sucessos; falhas ficam no outbox/retry
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
