"""add porter lead suppression

Revision ID: fc2b1d3e4f5a
Revises: fb1a0c2d3e4f
Create Date: 2026-07-13 17:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "fc2b1d3e4f5a"
down_revision: Union[str, Sequence[str], None] = "fb1a0c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "porter_leads",
        sa.Column(
            "do_not_call",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "porter_leads",
        sa.Column("suppressed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "porter_leads",
        sa.Column("suppression_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_porter_leads_do_not_call",
        "porter_leads",
        ["do_not_call"],
    )


def downgrade() -> None:
    op.drop_index("ix_porter_leads_do_not_call", table_name="porter_leads")
    op.drop_column("porter_leads", "suppression_reason")
    op.drop_column("porter_leads", "suppressed_at")
    op.drop_column("porter_leads", "do_not_call")
