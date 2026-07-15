"""identities + chat_sessions + chat_messages (DEC-ORB-038/041)

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Identidade canônica por e-mail verificado (âncora estável da sessão — DEC-ORB-041).
    op.create_table(
        "identities",
        sa.Column("email_normalized", sa.String(320), primary_key=True),
        sa.Column("canonical_lead_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="business",
    )

    # Sessão de conversa, escopada ao lead canônico (id NU, sem FK cruzada de schema — DEC-ORB-021).
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("slots", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("quote_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handoff_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handoff_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_turn_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="business",
    )
    op.create_index("ix_business_chat_sessions_lead_id", "chat_sessions", ["lead_id"], schema="business")

    # Mensagens: UNIQUE(session_id, seq) ordena/dedup o turno; UNIQUE(session_id, client_turn_id) dá
    # idempotência de turno lógico; FK+CASCADE só DENTRO de business (mesmo schema — inv.3).
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("client_turn_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["business.chat_sessions.id"], ondelete="CASCADE", name="fk_chat_messages_session"
        ),
        sa.UniqueConstraint("session_id", "seq", name="uq_chat_messages_session_seq"),
        sa.UniqueConstraint("session_id", "client_turn_id", name="uq_chat_messages_session_turn"),
        schema="business",
    )


def downgrade() -> None:
    op.drop_table("chat_messages", schema="business")
    op.drop_table("chat_sessions", schema="business")
    op.drop_table("identities", schema="business")
