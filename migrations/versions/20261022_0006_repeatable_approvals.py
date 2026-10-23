"""Allow distinct, repeatable approvals for resource operations."""

from collections.abc import Sequence

from alembic import op

revision: str = "20261022_0006"
down_revision: str | None = "20261022_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("approvals_operation_id_key", "approvals", type_="unique")
    op.drop_constraint(
        "authorization_grants_operation_id_key", "authorization_grants", type_="unique"
    )
    op.create_index("ix_approvals_operation_id", "approvals", ["operation_id"])
    op.create_index(
        "ix_authorization_grants_operation_id", "authorization_grants", ["operation_id"]
    )


def downgrade() -> None:
    # The older schema allowed only one approval/grant per operation. Keep the
    # newest approval and remove its superseded dependent rows before restoring
    # those constraints, so a populated development database is downgradeable.
    duplicate_approvals = """
        SELECT id
        FROM (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY operation_id ORDER BY created_at DESC, id DESC
                   ) AS position
            FROM approvals
        ) ranked
        WHERE position > 1
    """
    op.execute(f"DELETE FROM mfa_challenges WHERE approval_id IN ({duplicate_approvals})")
    op.execute(f"DELETE FROM authorization_grants WHERE approval_id IN ({duplicate_approvals})")
    op.execute(f"DELETE FROM approvals WHERE id IN ({duplicate_approvals})")
    op.drop_index("ix_authorization_grants_operation_id", table_name="authorization_grants")
    op.drop_index("ix_approvals_operation_id", table_name="approvals")
    op.create_unique_constraint(
        "authorization_grants_operation_id_key", "authorization_grants", ["operation_id"]
    )
    op.create_unique_constraint("approvals_operation_id_key", "approvals", ["operation_id"])
