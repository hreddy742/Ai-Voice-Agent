"""add porter schema

Revision ID: fb1a0c2d3e4f
Revises: b7e3c9a1d2f4
Create Date: 2026-07-09 13:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "fb1a0c2d3e4f"
down_revision: Union[str, Sequence[str], None] = "b7e3c9a1d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "porter_leads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("industry", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("contact_name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("website", sa.String(), nullable=False),
        sa.Column("evidence_summary", sa.Text(), nullable=False),
        sa.Column("evidence_url", sa.String(), nullable=False),
        sa.Column("funding_signal_type", sa.String(), nullable=False),
        sa.Column("lead_source", sa.String(), nullable=False),
        sa.Column("lead_score_before_call", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_porter_leads_company_name", "porter_leads", ["company_name"])
    op.create_index("ix_porter_leads_lead_source", "porter_leads", ["lead_source"])

    op.create_table(
        "porter_prompt_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.String(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )

    op.create_table(
        "porter_knowledge_base_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_version", sa.String(), nullable=False),
        sa.Column("source_title", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "knowledge_base_version",
            "source_title",
            "chunk_index",
            name="uq_porter_kb_version_source_chunk",
        ),
    )
    op.create_index(
        "ix_porter_kb_chunks_version",
        "porter_knowledge_base_chunks",
        ["knowledge_base_version"],
    )

    op.create_table(
        "porter_call_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("dograh_call_id", sa.Integer(), nullable=True),
        sa.Column(
            "status", sa.String(), server_default=sa.text("'created'"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prompt_version", sa.String(), nullable=False),
        sa.Column("knowledge_base_version", sa.String(), nullable=False),
        sa.Column(
            "human_review_required",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "crm_sync_status",
            sa.String(),
            server_default=sa.text("'not_ready'"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('created', 'in_progress', 'completed', 'failed', 'needs_review')",
            name="ck_porter_call_sessions_status",
        ),
        sa.CheckConstraint(
            "crm_sync_status IN ('not_ready', 'ready', 'synced', 'failed', 'disabled')",
            name="ck_porter_call_sessions_crm_sync_status",
        ),
        sa.ForeignKeyConstraint(["dograh_call_id"], ["workflow_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["porter_leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_porter_call_sessions_dograh_call_id",
        "porter_call_sessions",
        ["dograh_call_id"],
    )
    op.create_index(
        "ix_porter_call_sessions_lead_id", "porter_call_sessions", ["lead_id"]
    )

    op.create_table(
        "porter_agent_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column(
            "event_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["call_session_id"], ["porter_call_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_porter_agent_events_session", "porter_agent_events", ["call_session_id"]
    )
    op.create_index("ix_porter_agent_events_type", "porter_agent_events", ["event_type"])

    op.create_table(
        "porter_call_outcomes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_session_id", sa.Integer(), nullable=False),
        sa.Column("disposition", sa.String(), nullable=False),
        sa.Column("call_summary", sa.Text(), nullable=False),
        sa.Column(
            "objections",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("next_action", sa.String(), nullable=True),
        sa.Column("human_handoff_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "disposition IN ("
            "'interested', 'not_interested', 'callback_requested', 'send_info', "
            "'human_handoff', 'disqualified', 'voicemail', 'gatekeeper', "
            "'no_answer', 'unknown'"
            ")",
            name="ck_porter_call_outcomes_disposition",
        ),
        sa.ForeignKeyConstraint(
            ["call_session_id"], ["porter_call_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_session_id", name="uq_porter_outcome_call_session"),
    )
    op.create_index(
        "ix_porter_call_outcomes_disposition",
        "porter_call_outcomes",
        ["disposition"],
    )

    op.create_table(
        "porter_policy_violations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_session_id", sa.Integer(), nullable=False),
        sa.Column("violation_type", sa.String(), nullable=False),
        sa.Column("blocked_text", sa.Text(), nullable=False),
        sa.Column("safe_replacement", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["call_session_id"], ["porter_call_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_porter_policy_violations_session",
        "porter_policy_violations",
        ["call_session_id"],
    )
    op.create_index(
        "ix_porter_policy_violations_type",
        "porter_policy_violations",
        ["violation_type"],
    )

    op.create_table(
        "porter_qualification_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_session_id", sa.Integer(), nullable=False),
        sa.Column("funding_need", sa.Text(), nullable=True),
        sa.Column("funding_amount", sa.String(), nullable=True),
        sa.Column("monthly_revenue", sa.String(), nullable=True),
        sa.Column("invoices_b2b", sa.Boolean(), nullable=True),
        sa.Column("has_outstanding_ar", sa.Boolean(), nullable=True),
        sa.Column("has_payroll_need", sa.Boolean(), nullable=True),
        sa.Column("has_purchase_order_need", sa.Boolean(), nullable=True),
        sa.Column("existing_factor_or_lender", sa.String(), nullable=True),
        sa.Column("urgency", sa.String(), nullable=True),
        sa.Column("callback_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "raw_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["call_session_id"], ["porter_call_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "call_session_id", name="uq_porter_qualification_call_session"
        ),
    )

    op.create_table(
        "porter_transcript_turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("call_session_id", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("conversation_state", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "raw_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "speaker IN ('assistant', 'user', 'system', 'tool')",
            name="ck_porter_transcript_turns_speaker",
        ),
        sa.ForeignKeyConstraint(
            ["call_session_id"], ["porter_call_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_porter_transcript_turns_session_time",
        "porter_transcript_turns",
        ["call_session_id", "timestamp", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_porter_transcript_turns_session_time", table_name="porter_transcript_turns"
    )
    op.drop_table("porter_transcript_turns")
    op.drop_table("porter_qualification_answers")
    op.drop_index(
        "ix_porter_policy_violations_type", table_name="porter_policy_violations"
    )
    op.drop_index(
        "ix_porter_policy_violations_session", table_name="porter_policy_violations"
    )
    op.drop_table("porter_policy_violations")
    op.drop_index(
        "ix_porter_call_outcomes_disposition", table_name="porter_call_outcomes"
    )
    op.drop_table("porter_call_outcomes")
    op.drop_index("ix_porter_agent_events_type", table_name="porter_agent_events")
    op.drop_index("ix_porter_agent_events_session", table_name="porter_agent_events")
    op.drop_table("porter_agent_events")
    op.drop_index(
        "ix_porter_call_sessions_lead_id", table_name="porter_call_sessions"
    )
    op.drop_index(
        "ix_porter_call_sessions_dograh_call_id", table_name="porter_call_sessions"
    )
    op.drop_table("porter_call_sessions")
    op.drop_index(
        "ix_porter_kb_chunks_version", table_name="porter_knowledge_base_chunks"
    )
    op.drop_table("porter_knowledge_base_chunks")
    op.drop_table("porter_prompt_versions")
    op.drop_index("ix_porter_leads_lead_source", table_name="porter_leads")
    op.drop_index("ix_porter_leads_company_name", table_name="porter_leads")
    op.drop_table("porter_leads")
