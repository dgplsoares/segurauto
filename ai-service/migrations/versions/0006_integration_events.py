"""integration_events (DEC-ORB-044)

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("request", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("response", postgresql.JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(20), server_default="ok", nullable=False),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="business",
    )
    op.create_index(
        "ix_business_integration_events_lead_id", "integration_events", ["lead_id"], schema="business"
    )
    op.create_index(
        "ix_business_integration_events_session_id", "integration_events", ["session_id"], schema="business"
    )


def downgrade() -> None:
    op.drop_table("integration_events", schema="business")
