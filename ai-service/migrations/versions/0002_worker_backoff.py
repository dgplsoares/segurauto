"""outbox.next_attempt_at — backoff persistente do worker (DEC-ORB-025)

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "outbox",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        schema="business",
    )


def downgrade() -> None:
    op.drop_column("outbox", "next_attempt_at", schema="business")
