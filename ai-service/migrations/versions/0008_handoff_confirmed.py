"""F6 fix — marca DEDICADA da confirmação de handoff (revisão adversarial)

Revision ID: 0008
Revises: 0007

`handoff_requested_at` (0004) é escrito por DOIS produtores: o detector do chat (hint, sem enfileirar) e a
confirmação explícita. Usar essa marca como gate de idempotência do enqueue fazia a confirmação ser
engolida quando o detector já a tinha setado. Esta coluna é escrita SÓ pela confirmação (single-writer),
espelhando `contract_requested_at`.
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("handoff_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        schema="business",
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "handoff_confirmed_at", schema="business")
