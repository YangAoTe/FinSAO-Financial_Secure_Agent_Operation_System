"""Security approvals, grants, MFA, and safety locks.

Revision ID: 20261022_0002
Revises: 20261022_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0002"
down_revision: str | None = "20261022_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("operation_type", sa.String(100), nullable=False),
        sa.Column("target_account_id", sa.Uuid(), sa.ForeignKey("accounts.id")),
        sa.Column("recipient_id", sa.Uuid(), sa.ForeignKey("accounts.id")),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("risk_tier", sa.String(6), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("currency IN ('CNY','USD','EUR')", name="approval_currency"),
        sa.CheckConstraint("risk_tier IN ('GREEN','YELLOW','RED')", name="approval_risk_tier"),
    )
    op.create_index("ix_approvals_actor_user_id", "approvals", ["actor_user_id"])
    op.create_table(
        "authorization_grants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "approval_id", sa.Uuid(), sa.ForeignKey("approvals.id"), unique=True, nullable=False
        ),
        sa.Column("operation_id", sa.Uuid(), unique=True, nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("approval_id", sa.Uuid(), sa.ForeignKey("approvals.id"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("salt", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_mfa_challenges_approval_id", "mfa_challenges", ["approval_id"])
    op.create_table(
        "safety_locks",
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("safety_locks")
    op.drop_table("mfa_challenges")
    op.drop_table("authorization_grants")
    op.drop_table("approvals")
