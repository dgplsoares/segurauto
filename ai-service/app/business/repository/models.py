"""Modelos ORM do contexto `business` (schema `business`). Sem FK para o schema `ai` (DEC-ORB-021)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
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
