from sqlalchemy import select

from api.db.models import PorterCallSessionModel, PorterTranscriptTurnModel
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.policy import SAFE_RATE_REPLACEMENT
from api.porter.state_machine import (
    PorterConversationContext,
    PorterConversationState,
    PorterDisposition,
    PorterSalesStateMachine,
    STATE_REQUIRED_FIELDS,
    record_porter_transcript_turn,
)


def test_normal_interested_conversation_reaches_next_action_then_interested():
    machine = PorterSalesStateMachine()
    context = PorterConversationContext()

    scripted_turns = [
        ("Yes, I have a minute.", {}),
        ("Sure, why are you calling?", {}),
        ("We need working capital for payroll.", {"funding_need": "payroll"}),
        ("Yes, we invoice businesses and have open A/R.", {"invoices_b2b": True, "has_outstanding_ar": True}),
        ("Payroll is the main need, not purchase orders.", {"has_payroll_need": True, "has_purchase_order_need": False}),
        ("About 250k revenue and need 75k.", {"monthly_revenue": "$250,000", "funding_amount": "$75,000"}),
        ("This week if possible.", {"urgency": "this_week"}),
        ("I understand.", {}),
        ("No current factor.", {"existing_factor_or_lender": "none"}),
    ]

    for user_text, captured in scripted_turns:
        context.captured_fields.update(captured)
        result = machine.transition(context, user_text)
        context.state = result.next_state

    assert context.state == PorterConversationState.NEXT_ACTION
    assert result.required_fields == STATE_REQUIRED_FIELDS[PorterConversationState.NEXT_ACTION]

    context.captured_fields["next_action"] = "specialist_follow_up"
    result = machine.transition(context, "Yes, sounds good.")

    assert result.next_state == PorterConversationState.CLOSE
    assert result.disposition == PorterDisposition.INTERESTED


def test_not_interested_reaches_not_interested_disposition():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.FUNDING_NEED),
        "Not interested, thanks.",
    )

    assert result.next_state == PorterConversationState.CLOSE
    assert result.disposition == PorterDisposition.NOT_INTERESTED


def test_send_info_reaches_send_info_without_sending_anything():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.OBJECTION_HANDLING),
        "Can you email me or send me information?",
    )

    assert result.next_state == PorterConversationState.CLOSE
    assert result.disposition == PorterDisposition.SEND_INFO
    assert result.reason == "send_info_requested"


def test_call_later_reaches_callback_requested():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.PERMISSION_CHECK),
        "Call me later tomorrow.",
    )

    assert result.next_state == PorterConversationState.CLOSE
    assert result.disposition == PorterDisposition.CALLBACK_REQUESTED


def test_rate_question_routes_to_objection_handling_and_policy_engine():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.REVENUE_AND_AMOUNT),
        "What are your rates?",
        agent_draft="Your rate will be 2%.",
    )

    assert result.next_state == PorterConversationState.OBJECTION_HANDLING
    assert result.reason == "policy_violation"
    assert result.policy_safe_text == SAFE_RATE_REPLACEMENT
    assert result.policy_violation_types == ("rate_claim",)


def test_human_request_routes_to_human_handoff():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.EXISTING_FUNDING),
        "I want to talk to a person.",
    )

    assert result.next_state == PorterConversationState.HUMAN_HANDOFF
    assert result.disposition == PorterDisposition.HUMAN_HANDOFF
    assert result.human_handoff_required is True


def test_unclear_answer_does_not_crash_or_skip_required_fields():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.REVENUE_AND_AMOUNT),
        "hmm",
    )

    assert result.next_state == PorterConversationState.REVENUE_AND_AMOUNT
    assert result.reason == "needs_clarification"
    assert result.required_fields == ("monthly_revenue", "funding_amount")


def test_greetings_identity_questions_and_ambiguous_speech_preserve_state():
    machine = PorterSalesStateMachine()
    state = PorterConversationState.REASON_FOR_CALL
    cases = (
        ("Hello.", "greeting"),
        ("Who are you?", "informational_question"),
        ("I know who are you.", "informational_question"),
        ("I want you.", "needs_clarification"),
    )

    for user_text, expected_reason in cases:
        result = machine.transition(
            PorterConversationContext(state=state),
            user_text,
        )

        assert result.next_state == state
        assert result.reason == expected_reason


def test_business_answer_still_advances_reason_for_call_state():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(state=PorterConversationState.REASON_FOR_CALL),
        "We are a manufacturing company.",
    )

    assert result.next_state == PorterConversationState.FUNDING_NEED
    assert result.reason == "advance"


def test_spoken_information_questions_do_not_advance_after_rate_objection():
    machine = PorterSalesStateMachine()
    state = PorterConversationState.OBJECTION_HANDLING
    questions = (
        "So how long do you take to provide the funding?",
        "mean by what part?",
        "Inways factor.",
        "and what it's factoring.",
    )

    for question in questions:
        result = machine.transition(PorterConversationContext(state=state), question)

        assert result.next_state == state
        assert result.reason == "informational_question"


def test_existing_factor_answer_is_not_mistaken_for_a_factoring_question():
    result = PorterSalesStateMachine().transition(
        PorterConversationContext(
            state=PorterConversationState.EXISTING_FUNDING,
            captured_fields={"existing_factor_or_lender": "none"},
        ),
        "No current factor.",
    )

    assert result.next_state == PorterConversationState.NEXT_ACTION
    assert result.reason == "advance"


async def test_every_transcript_turn_includes_state(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)
    call_session = PorterCallSessionModel(
        lead=leads[0],
        destination_phone=leads[0].phone,
        status="in_progress",
        prompt_version="porter-local-v1",
        knowledge_base_version="porter-kb-v1",
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    async_session.add(call_session)
    await async_session.flush()

    await record_porter_transcript_turn(
        async_session,
        call_session_id=call_session.id,
        speaker="assistant",
        text="Hi, is now an okay time?",
        state=PorterConversationState.OPENING,
    )
    await record_porter_transcript_turn(
        async_session,
        call_session_id=call_session.id,
        speaker="user",
        text="Yes.",
        state=PorterConversationState.PERMISSION_CHECK,
        raw_metadata={"source": "state_machine_test"},
    )
    await async_session.commit()

    rows = (
        await async_session.execute(
            select(PorterTranscriptTurnModel)
            .where(PorterTranscriptTurnModel.call_session_id == call_session.id)
            .order_by(PorterTranscriptTurnModel.timestamp, PorterTranscriptTurnModel.id)
        )
    ).scalars().all()

    assert [row.conversation_state for row in rows] == [
        "opening",
        "permission_check",
    ]
    assert rows[1].raw_metadata == {"source": "state_machine_test"}
