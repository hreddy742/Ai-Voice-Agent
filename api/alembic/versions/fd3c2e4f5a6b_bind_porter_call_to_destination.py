"""Bind each Porter call session to one attempt and destination.

Revision ID: fd3c2e4f5a6b
Revises: fc2b1d3e4f5a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "fd3c2e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "fc2b1d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "porter_call_sessions",
        sa.Column("attempt_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "porter_call_sessions",
        sa.Column("destination_phone", sa.String(length=16), nullable=True),
    )
    op.execute(
        """
        UPDATE porter_call_sessions AS calls
        SET destination_phone = leads.phone,
            attempt_id = 'legacy-' || calls.id::text
        FROM porter_leads AS leads
        WHERE leads.id = calls.lead_id
        """
    )
    op.alter_column("porter_call_sessions", "attempt_id", nullable=False)
    op.alter_column("porter_call_sessions", "destination_phone", nullable=False)
    op.create_unique_constraint(
        "uq_porter_call_sessions_attempt_id",
        "porter_call_sessions",
        ["attempt_id"],
    )
    op.create_index(
        "ix_porter_call_sessions_destination_phone",
        "porter_call_sessions",
        ["destination_phone"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_porter_call_sessions_destination_phone",
        table_name="porter_call_sessions",
    )
    op.drop_constraint(
        "uq_porter_call_sessions_attempt_id",
        "porter_call_sessions",
        type_="unique",
    )
    op.drop_column("porter_call_sessions", "destination_phone")
    op.drop_column("porter_call_sessions", "attempt_id")
