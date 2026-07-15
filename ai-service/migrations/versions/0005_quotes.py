"""quotes (DEC-ORB-043)

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("premium_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), server_default="BRL", nullable=False),
        sa.Column("slots", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("coverages", postgresql.JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("broker_applied", sa.Boolean, server_default="false", nullable=False),
        sa.Column("pdf_ref", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["business.chat_sessions.id"], ondelete="CASCADE", name="fk_quotes_session"
        ),
        sa.UniqueConstraint("session_id", name="uq_quotes_session"),  # uma cotação por sessão (re-cota = F6)
        schema="business",
    )
    op.create_index("ix_business_quotes_lead_id", "quotes", ["lead_id"], schema="business")


def downgrade() -> None:
    op.drop_table("quotes", schema="business")
