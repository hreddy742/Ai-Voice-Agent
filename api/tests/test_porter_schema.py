from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from api.db.models import (
    PorterAgentEventModel,
    PorterCallOutcomeModel,
    PorterCallSessionModel,
    PorterKnowledgeBaseChunkModel,
    PorterLeadModel,
    PorterPolicyViolationModel,
    PorterPromptVersionModel,
    PorterQualificationAnswerModel,
    PorterTranscriptTurnModel,
)


PORTER_TABLES = {
    "porter_leads",
    "porter_call_sessions",
    "porter_transcript_turns",
    "porter_qualification_answers",
    "porter_policy_violations",
    "porter_agent_events",
    "porter_knowledge_base_chunks",
    "porter_prompt_versions",
    "porter_call_outcomes",
    "porter_phone_suppressions",
}


def _lead() -> PorterLeadModel:
    return PorterLeadModel(
        company_name="Fake Acme Staffing LLC",
        industry="Staffing",
        location="Birmingham, AL",
        contact_name="Test Contact",
        phone="+15550101010",
        email="test.contact@example.com",
        website="https://example.com/acme-staffing",
        evidence_summary="Fake fixture: hiring growth suggests payroll pressure.",
        evidence_url="https://example.com/fake-evidence",
        funding_signal_type="payroll_pressure",
        lead_source="porter_local_fixture",
        lead_score_before_call=82.5,
        notes="Clearly fake test data.",
    )


def _call_session(lead: PorterLeadModel) -> PorterCallSessionModel:
    return PorterCallSessionModel(
        lead=lead,
        destination_phone=lead.phone,
        status="created",
        prompt_version="porter-local-v1",
        knowledge_base_version="porter-kb-v1",
        human_review_required=True,
        crm_sync_status="not_ready",
    )


async def test_porter_migration_tables_exist(db_connection):
    table_names = await db_connection.run_sync(
        lambda sync_conn: set(inspect(sync_conn).get_table_names())
    )

    assert PORTER_TABLES.issubset(table_names)

    call_columns = await db_connection.run_sync(
        lambda sync_conn: {
            column["name"]: column
            for column in inspect(sync_conn).get_columns("porter_call_sessions")
        }
    )
    call_uniques = await db_connection.run_sync(
        lambda sync_conn: inspect(sync_conn).get_unique_constraints(
            "porter_call_sessions"
        )
    )

    assert call_columns["attempt_id"]["nullable"] is False
    assert call_columns["destination_phone"]["nullable"] is False
    assert any(unique["column_names"] == ["attempt_id"] for unique in call_uniques)


async def test_porter_models_create_read_update_records(async_session):
    lead = _lead()
    call_session = _call_session(lead)
    prompt_version = PorterPromptVersionModel(
        version="porter-local-v1",
        description="Initial Porter local validation prompt.",
        system_prompt="Use Porter-approved conservative language.",
        policy_version="porter-policy-v1",
        is_active=True,
    )
    kb_chunk = PorterKnowledgeBaseChunkModel(
        knowledge_base_version="porter-kb-v1",
        source_title="Porter funding options",
        source_url="https://example.com/fake-porter-kb",
        chunk_index=0,
        chunk_text="Porter may be able to help after review.",
        chunk_metadata={"fixture": True},
    )
    qualification = PorterQualificationAnswerModel(
        call_session=call_session,
        funding_need="Payroll funding",
        funding_amount="$50,000",
        monthly_revenue="$200,000",
        invoices_b2b=True,
        has_outstanding_ar=True,
        has_payroll_need=True,
        has_purchase_order_need=False,
        existing_factor_or_lender="No",
        urgency="this_week",
        raw_answers={"source": "test"},
    )
    outcome = PorterCallOutcomeModel(
        call_session=call_session,
        disposition="interested",
        call_summary="Lead is interested and needs human review.",
        objections=["asked about rates"],
        next_action="human_follow_up",
    )
    violation = PorterPolicyViolationModel(
        call_session=call_session,
        violation_type="approval_promise",
        blocked_text="You are approved.",
        safe_replacement="I can't confirm approval without Porter review.",
    )
    event = PorterAgentEventModel(
        call_session=call_session,
        event_type="state_transition",
        event_payload={"from": "opening", "to": "permission_check"},
    )

    async_session.add_all(
        [prompt_version, kb_chunk, call_session, qualification, outcome, violation, event]
    )
    await async_session.commit()

    call_session.status = "completed"
    call_session.ended_at = datetime.now(UTC)
    await async_session.commit()

    refreshed = await async_session.get(PorterCallSessionModel, call_session.id)

    assert refreshed is not None
    assert refreshed.lead.company_name == "Fake Acme Staffing LLC"
    assert refreshed.status == "completed"
    assert refreshed.qualification_answers.funding_need == "Payroll funding"
    assert refreshed.outcome.disposition == "interested"
    assert refreshed.policy_violations[0].violation_type == "approval_promise"
    assert refreshed.agent_events[0].event_payload["to"] == "permission_check"


async def test_porter_required_fields_are_enforced(db_connection):
    nested = await db_connection.begin_nested()
    try:
        with pytest.raises(IntegrityError):
            await db_connection.execute(
                text(
                    """
                    INSERT INTO porter_leads (
                        company_name, industry, location, contact_name, phone, email,
                        website, evidence_summary, evidence_url, funding_signal_type,
                        lead_source, lead_score_before_call
                    )
                    VALUES (
                        NULL, 'Staffing', 'Birmingham, AL', 'Test Contact',
                        '+15550101010', 'test.contact@example.com',
                        'https://example.com/acme-staffing',
                        'Fake fixture: hiring growth suggests payroll pressure.',
                        'https://example.com/fake-evidence', 'payroll_pressure',
                        'porter_local_fixture', 82.5
                    )
                    """
                )
            )
    finally:
        await nested.rollback()


async def test_invalid_porter_disposition_is_rejected(db_connection):
    nested = await db_connection.begin_nested()
    try:
        lead_id = (
            await db_connection.execute(
                text(
                    """
                    INSERT INTO porter_leads (
                        company_name, industry, location, contact_name, phone, email,
                        website, evidence_summary, evidence_url, funding_signal_type,
                        lead_source, lead_score_before_call
                    )
                    VALUES (
                        'Fake Acme Staffing LLC', 'Staffing', 'Birmingham, AL',
                        'Test Contact', '+15550101010', 'test.contact@example.com',
                        'https://example.com/acme-staffing',
                        'Fake fixture: hiring growth suggests payroll pressure.',
                        'https://example.com/fake-evidence', 'payroll_pressure',
                        'porter_local_fixture', 82.5
                    )
                    RETURNING id
                    """
                )
            )
        ).scalar_one()
        call_session_id = (
            await db_connection.execute(
                text(
                    """
                    INSERT INTO porter_call_sessions (
                        lead_id, attempt_id, destination_phone,
                        prompt_version, knowledge_base_version
                    )
                    VALUES (
                        :lead_id, '00000000-0000-0000-0000-000000000001',
                        '+15550101010', 'porter-local-v1', 'porter-kb-v1'
                    )
                    RETURNING id
                    """
                ),
                {"lead_id": lead_id},
            )
        ).scalar_one()

        with pytest.raises(IntegrityError):
            await db_connection.execute(
                text(
                    """
                    INSERT INTO porter_call_outcomes (
                        call_session_id, disposition, call_summary, objections
                    )
                    VALUES (
                        :call_session_id, 'definitely_funded',
                        'Invalid disposition should not persist.', '[]'::jsonb
                    )
                    """
                ),
                {"call_session_id": call_session_id},
            )
    finally:
        await nested.rollback()


async def test_porter_transcript_turns_persist_in_order(async_session):
    call_session = _call_session(_lead())
    base_time = datetime.now(UTC)
    first_turn = PorterTranscriptTurnModel(
        call_session=call_session,
        speaker="assistant",
        text="Hi, is now an okay time?",
        conversation_state="opening",
        timestamp=base_time,
        raw_metadata={"turn": 1},
    )
    second_turn = PorterTranscriptTurnModel(
        call_session=call_session,
        speaker="user",
        text="Yes, briefly.",
        conversation_state="permission_check",
        timestamp=base_time + timedelta(seconds=3),
        raw_metadata={"turn": 2},
    )
    async_session.add_all([second_turn, first_turn])
    await async_session.commit()

    result = await async_session.execute(
        select(PorterTranscriptTurnModel)
        .where(PorterTranscriptTurnModel.call_session_id == call_session.id)
        .order_by(PorterTranscriptTurnModel.timestamp, PorterTranscriptTurnModel.id)
    )
    turns = result.scalars().all()

    assert [turn.text for turn in turns] == [
        "Hi, is now an okay time?",
        "Yes, briefly.",
    ]
    assert [turn.conversation_state for turn in turns] == [
        "opening",
        "permission_check",
    ]
