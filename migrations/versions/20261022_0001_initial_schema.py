"""Initial banking schema.

Revision ID: 20261022_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

currency = sa.Enum("CNY", "USD", "EUR", name="currency", native_enum=False, create_constraint=True)
risk_tier = sa.Enum(
    "GREEN", "YELLOW", "RED", name="risk_tier", native_enum=False, create_constraint=True
)
account_status = sa.Enum(
    "ACTIVE", "FROZEN", "CLOSED", name="account_status", native_enum=False, create_constraint=True
)
transaction_status = sa.Enum(
    "PENDING",
    "COMPLETED",
    "FAILED",
    "REVERSED",
    name="transaction_status",
    native_enum=False,
    create_constraint=True,
)
transfer_status = sa.Enum(
    "DRAFT",
    "PENDING_AUTHORIZATION",
    "AUTHORIZED",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "EXPIRED",
    name="transfer_status",
    native_enum=False,
    create_constraint=True,
)
card_status = sa.Enum(
    "ACTIVE",
    "FROZEN",
    "LOST",
    "CANCELLED",
    "EXPIRED",
    name="card_status",
    native_enum=False,
    create_constraint=True,
)
money = sa.Numeric(18, 2)


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
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("risk_tier", risk_tier, nullable=False),
        *timestamps(),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("account_number", sa.String(34), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("status", account_status, nullable=False),
        sa.Column("balance", money, nullable=False, server_default="0"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps(),
        sa.CheckConstraint(
            "(is_system AND user_id IS NULL) OR (NOT is_system AND user_id IS NOT NULL)",
            name="ck_accounts_owner_or_system",
        ),
        sa.CheckConstraint(
            "balance >= 0 OR is_system", name="ck_accounts_customer_balance_nonnegative"
        ),
    )
    op.create_index("ix_accounts_user_id", "accounts", ["user_id"])
    op.create_table(
        "beneficiaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("nickname", sa.String(80)),
        sa.Column(
            "destination_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False
        ),
        *timestamps(),
        sa.UniqueConstraint(
            "user_id", "destination_account_id", name="uq_beneficiary_owner_target"
        ),
    )
    op.create_index("ix_beneficiaries_user_id", "beneficiaries", ["user_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("reference", sa.String(80), nullable=False, unique=True),
        sa.Column("status", transaction_status, nullable=False),
        sa.Column("amount", money, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("category", sa.String(80)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_transactions_positive_amount"),
    )
    op.create_index("ix_transactions_posted_at", "transactions", ["posted_at"])
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.Uuid(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("debit", money, nullable=False, server_default="0"),
        sa.Column("credit", money, nullable=False, server_default="0"),
        sa.Column("currency", currency, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)",
            name="ck_ledger_exactly_one_side",
        ),
        sa.UniqueConstraint("transaction_id", "account_id", name="uq_ledger_transaction_account"),
    )
    op.create_index("ix_ledger_account_created", "ledger_entries", ["account_id", "created_at"])
    op.create_table(
        "transfer_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            "destination_account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("amount", money, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("status", transfer_status, nullable=False),
        sa.Column("idempotency_key", sa.String(120)),
        sa.Column("request_hash", sa.String(64)),
        sa.Column("transaction_id", sa.Uuid(), sa.ForeignKey("transactions.id")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_transfer_drafts_positive_amount"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_transfer_user_idempotency"),
    )
    op.create_index("ix_transfer_drafts_user_id", "transfer_drafts", ["user_id"])
    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("limit_amount", money, nullable=False),
        sa.Column("currency", currency, nullable=False),
        *timestamps(),
        sa.CheckConstraint("limit_amount > 0", name="ck_budgets_positive_limit"),
        sa.UniqueConstraint("user_id", "category", "month", name="uq_budget_user_category_month"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("merchant_name", sa.String(120), nullable=False),
        sa.Column("amount", money, nullable=False),
        sa.Column("currency", currency, nullable=False),
        sa.Column("next_billing_date", sa.Date(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_subscriptions_positive_amount"),
        sa.UniqueConstraint("user_id", "merchant_name", name="uq_subscription_user_merchant"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_table(
        "cards",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("last_four", sa.String(4), nullable=False),
        sa.Column("status", card_status, nullable=False),
        sa.Column("spending_limit", money, nullable=False),
        *timestamps(),
        sa.CheckConstraint("spending_limit > 0", name="ck_cards_positive_limit"),
        sa.CheckConstraint("char_length(last_four) = 4", name="ck_cards_last_four_length"),
    )
    op.create_index("ix_cards_account_id", "cards", ["account_id"])
    op.create_table(
        "wealth_products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("product_type", sa.String(80), nullable=False),
        sa.Column("risk_tier", risk_tier, nullable=False),
        sa.Column("minimum_amount", money, nullable=False),
        sa.Column("currency", currency, nullable=False),
        *timestamps(),
        sa.CheckConstraint("minimum_amount > 0", name="ck_wealth_positive_minimum"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(80)),
        sa.Column("trace_id", sa.String(80), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_audit_events_trace_id", "audit_events", ["trace_id"])
    op.create_index("ix_audit_actor_occurred", "audit_events", ["actor_user_id", "occurred_at"])


def downgrade() -> None:
    for table in [
        "audit_events",
        "wealth_products",
        "cards",
        "subscriptions",
        "budgets",
        "transfer_drafts",
        "ledger_entries",
        "transactions",
        "beneficiaries",
        "accounts",
        "users",
    ]:
        op.drop_table(table)
