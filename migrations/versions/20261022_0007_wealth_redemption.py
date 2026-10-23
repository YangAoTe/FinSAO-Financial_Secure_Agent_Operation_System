"""Add explicit wealth order types and redemption capability."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0007"
down_revision: str | None = "20261022_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wealth_products",
        sa.Column(
            "supports_redemption",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "wealth_orders",
        sa.Column(
            "order_type",
            sa.String(12),
            nullable=False,
            server_default="SUBSCRIPTION",
        ),
    )
    op.create_check_constraint(
        "wealth_order_type",
        "wealth_orders",
        "order_type IN ('SUBSCRIPTION','REDEMPTION')",
    )


def downgrade() -> None:
    op.drop_constraint("wealth_order_type", "wealth_orders", type_="check")
    op.drop_column("wealth_orders", "order_type")
    op.drop_column("wealth_products", "supports_redemption")
