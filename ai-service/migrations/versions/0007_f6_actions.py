"""F6 — ações write-through-outbox: marca de confirmação de contrato + click_id (DEC-ORB-045)

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Marca de idempotência da confirmação de contrato (a de handoff já existe: handoff_requested_at).
    op.add_column(
        "chat_sessions",
        sa.Column("contract_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="business",
    )
    # Atribuição de campanha: gclid/fbclid capturado na LP → enviado na conversão (DEC-ORB-045).
    op.add_column(
        "leads",
        sa.Column("click_id", sa.String(120), nullable=True),
        schema="business",
    )


def downgrade() -> None:
    op.drop_column("leads", "click_id", schema="business")
    op.drop_column("chat_sessions", "contract_requested_at", schema="business")
