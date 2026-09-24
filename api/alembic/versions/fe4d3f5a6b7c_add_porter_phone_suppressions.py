"""Add normalized Porter phone suppressions.

Revision ID: fe4d3f5a6b7c
Revises: fd3c2e4f5a6b
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "fe4d3f5a6b7c"
down_revision: Union[str, Sequence[str], None] = "fd3c2e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "porter_phone_suppressions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_call_session_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_call_session_id"],
            ["porter_call_sessions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone", name="uq_porter_phone_suppressions_phone"),
    )
    op.execute(
        """
        WITH normalized AS (
            SELECT DISTINCT
                CASE
                    WHEN length(regexp_replace(phone, '[^0-9]', '', 'g')) = 10
                    THEN '+1' || regexp_replace(phone, '[^0-9]', '', 'g')
                    ELSE '+' || regexp_replace(phone, '[^0-9]', '', 'g')
                END AS phone,
                suppression_reason
            FROM porter_leads
            WHERE do_not_call = true
        )
        INSERT INTO porter_phone_suppressions (phone, reason, created_at, updated_at)
        SELECT phone, coalesce(max(suppression_reason), 'legacy_do_not_call'), now(), now()
        FROM normalized
        WHERE length(phone) BETWEEN 9 AND 16
        GROUP BY phone
        """
    )


def downgrade() -> None:
    op.drop_table("porter_phone_suppressions")
