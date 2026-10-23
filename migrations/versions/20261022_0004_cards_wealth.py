"""Wealth assessments, holdings, and orders."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0004"
down_revision: str | None = "20261022_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "risk_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("risk_tier", sa.String(6), nullable=False),
        *timestamps(),
        sa.CheckConstraint("risk_tier IN ('GREEN','YELLOW','RED')", name="assessment_risk_tier"),
    )
    op.create_index("ix_risk_assessments_user_id", "risk_assessments", ["user_id"])
    op.create_table(
        "wealth_holdings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("wealth_products.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("user_id", "product_id", name="uq_holding_user_product"),
        sa.CheckConstraint("amount >= 0", name="ck_holding_nonnegative"),
        sa.CheckConstraint("currency IN ('CNY','USD','EUR')", name="holding_currency"),
    )
    op.create_table(
        "wealth_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("wealth_products.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), sa.ForeignKey("transactions.id")),
        *timestamps(),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_wealth_user_idempotency"),
        sa.CheckConstraint("amount > 0", name="ck_wealth_order_positive"),
        sa.CheckConstraint("currency IN ('CNY','USD','EUR')", name="wealth_order_currency"),
    )


def downgrade() -> None:
    op.drop_table("wealth_orders")
    op.drop_table("wealth_holdings")
    op.drop_table("risk_assessments")
