"""Subscription lifecycle and renewal reminders."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0003"
down_revision: str | None = "20261022_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions", sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE")
    )
    op.add_column("subscriptions", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.create_table(
        "renewal_reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("subscription_id", sa.Uuid(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("remind_on", sa.Date(), nullable=False),
        sa.Column("delivered", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("subscription_id", "remind_on", name="uq_reminder_subscription_date"),
    )


def downgrade() -> None:
    op.drop_table("renewal_reminders")
    op.drop_column("subscriptions", "cancelled_at")
    op.drop_column("subscriptions", "status")
