"""schemas business/ai + leads/outbox + documents/embeddings (pgvector)

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schemas separados por contexto (DEC-ORB-021) + extensão vetorial (DEC-ORB-003).
    op.execute("CREATE SCHEMA IF NOT EXISTS business")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- business.leads (idempotency_key UNIQUE — DEC-ORB-011) ---
    op.create_table(
        "leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("vehicle", sa.String(200), nullable=False),
        sa.Column("zipcode", sa.String(20), nullable=False),
        sa.Column("consent", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("score", sa.Integer, nullable=True),
        sa.Column("band", sa.String(20), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_leads_idempotency_key"),
        schema="business",
    )
    op.create_index("ix_business_leads_email", "leads", ["email"], schema="business")
    op.create_index("ix_business_leads_phone", "leads", ["phone"], schema="business")
    op.create_index("ix_business_leads_status", "leads", ["status"], schema="business")

    # --- business.outbox (correlação + retry/status — DEC-ORB-012/018/019) ---
    op.create_table(
        "outbox",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lead_id", sa.String(36), nullable=False),  # ref por id; sem FK cruzada de schema
        sa.Column("intent_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("payload", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="business",
    )
    op.create_index("ix_business_outbox_status", "outbox", ["status"], schema="business")
    op.create_index("ix_business_outbox_lead_id", "outbox", ["lead_id"], schema="business")

    # --- ai.documents + ai.embeddings (RAG; FK apenas DENTRO do schema ai) ---
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="ai",
    )
    op.execute(
        """
        CREATE TABLE ai.embeddings (
            id varchar(36) PRIMARY KEY,
            document_id varchar(36) NOT NULL REFERENCES ai.documents(id) ON DELETE CASCADE,
            chunk text NOT NULL,
            embedding vector(1536)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai.embeddings")
    op.drop_table("documents", schema="ai")
    op.drop_table("outbox", schema="business")
    op.drop_table("leads", schema="business")
    op.execute("DROP SCHEMA IF EXISTS ai CASCADE")
    op.execute("DROP SCHEMA IF EXISTS business CASCADE")
