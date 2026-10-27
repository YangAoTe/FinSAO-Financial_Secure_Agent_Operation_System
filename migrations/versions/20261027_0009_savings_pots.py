"""Add virtual savings pots and idempotent contribution history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261027_0009"
down_revision: str | None = "20261026_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_tasks", sa.Column("public_message", sa.Text(), nullable=True))
    op.drop_constraint("agent_task_status", "agent_tasks", type_="check")
    op.create_check_constraint(
        "agent_task_status",
        "agent_tasks",
        "status IN ('RUNNING','NEEDS_CLARIFICATION','WAITING_APPROVAL','COMPLETED',"
        "'FAILED','CANCELLED','HUMAN_TAKEOVER')",
    )
    op.create_table(
        "savings_pots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("target_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("saved_amount", sa.Numeric(18, 2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "allocation_mode", sa.String(32), nullable=False, server_default="VIRTUAL_ALLOCATION"
        ),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("target_amount > 0", name="ck_savings_pot_positive_target"),
        sa.CheckConstraint("saved_amount >= 0", name="ck_savings_pot_nonnegative_saved"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_savings_pot_user_key"),
    )
    op.create_index("ix_savings_pots_user_id", "savings_pots", ["user_id"])
    op.create_table(
        "savings_contributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("savings_pots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("amount > 0", name="ck_savings_contribution_positive"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_savings_contribution_user_key"),
    )
    op.create_index("ix_savings_contributions_pot_id", "savings_contributions", ["pot_id"])
    op.create_index("ix_savings_contributions_user_id", "savings_contributions", ["user_id"])


def downgrade() -> None:
    op.drop_table("savings_contributions")
    op.drop_table("savings_pots")
    op.drop_constraint("agent_task_status", "agent_tasks", type_="check")
    op.create_check_constraint(
        "agent_task_status",
        "agent_tasks",
        "status IN ('RUNNING','WAITING_APPROVAL','COMPLETED','FAILED',"
        "'CANCELLED','HUMAN_TAKEOVER')",
    )
    op.drop_column("agent_tasks", "public_message")
