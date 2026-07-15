"""auth_sessions + otp_codes (DEC-ORB-037)

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),  # sha256 do token (nunca o cru)
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        schema="business",
    )
    op.create_index("ix_business_auth_sessions_lead_id", "auth_sessions", ["lead_id"], schema="business")
    op.create_index("ix_business_auth_sessions_expires_at", "auth_sessions", ["expires_at"], schema="business")

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="business",
    )
    op.create_index("ix_business_otp_codes_email", "otp_codes", ["email"], schema="business")


def downgrade() -> None:
    op.drop_table("otp_codes", schema="business")
    op.drop_table("auth_sessions", schema="business")
