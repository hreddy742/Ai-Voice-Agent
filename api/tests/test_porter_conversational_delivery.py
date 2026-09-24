import pytest

from api.porter.cold_call_flow import (
    PorterCallerIntent,
    PorterColdCallContext,
    PorterColdCallStage,
    decide_porter_cold_call_turn,
)
from api.porter.cold_call_scripts import (
    BOOKING,
    COLD_CALL_PERMISSION,
    DISCLOSURE,
    PITCH,
    PORTER_AGENT_INSTRUCTIONS,
)
from api.porter.delivery import (
    PorterAcknowledgement,
    contains_multiple_questions,
    pending_question,
    problem_summary,
    spoken_question,
    tailored_handoff,
)


def turn(context: PorterColdCallContext, text: str):
    decision = decide_porter_cold_call_turn(context, text)
    decision.apply(context)
    return decision


def test_core_agent_turns_are_short_and_ask_one_primary_question():
    context = PorterColdCallContext(stage=PorterColdCallStage.OPENING)
    responses = [COLD_CALL_PERMISSION]
    for answer in ("yes", "business customers", "net 45", "payroll gets tight"):
        responses.append(turn(context, answer).response_text)

    assert all(len(response.split()) <= 35 for response in responses)
    assert all(not contains_multiple_questions(response) for response in responses)


def test_agent_instructions_enforce_natural_truthful_telephony_delivery():
    lowered = " ".join(PORTER_AGENT_INSTRUCTIONS.lower().split())

    assert "one primary question" in lowered
    assert "direct question before returning" in lowered
    assert "don't guess" in lowered
    assert "fake filler words" in lowered
    assert "imply that you're human" in lowered
    assert "ai assistant with porter capital" in lowered
    assert "return only words that should be spoken aloud" in lowered


def test_agent_instructions_limit_john_approved_estimates():
    lowered = " ".join(PORTER_AGENT_INSTRUCTIONS.lower().split())

    assert "accounts receivable multiplied by 90 percent" in lowered
    assert "annual revenue multiplied by 10 percent" in lowered
    assert "preliminary illustration" in lowered
    assert "never an approval" in lowered


def test_permission_opener_is_truthful_brief_and_does_not_repeat_the_pitch():
    lowered = COLD_CALL_PERMISSION.lower()

    assert "aiva" in lowered
    assert "an ai" in lowered
    assert "porter capital" in lowered
    assert "cold call" in lowered
    assert "30 seconds" in lowered
    assert "working capital" not in lowered
    assert "unpaid invoices" not in lowered
    assert len(COLD_CALL_PERMISSION.split()) <= 35
    assert not contains_multiple_questions(COLD_CALL_PERMISSION)


def test_pitch_keeps_the_approved_value_and_soft_check_in():
    lowered = PITCH.lower()

    assert "cash from invoices faster" in lowered
    assert "simple as that" in lowered
    assert PITCH.lower().endswith("does that sound relevant?")
    assert len(PITCH.split()) <= 35
    assert not contains_multiple_questions(PITCH)


def test_booking_is_warm_brief_and_collects_callback_details_once():
    lowered = BOOKING.lower()

    assert "financing advisors" in lowered
    assert "number" in lowered
    assert "day" not in lowered
    assert "time" not in lowered
    assert len(BOOKING.split()) <= 35
    assert not contains_multiple_questions(BOOKING)


def test_general_pitch_interest_moves_to_advisor_value_offer():
    context = PorterColdCallContext(stage=PorterColdCallStage.OPENING)

    decision = turn(context, "Yes, I have 20 seconds")

    assert "I'll keep it brief" in decision.response_text
    assert decision.response_text.count("?") == 1

    industry = turn(context, "Yes")
    assert industry.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER


def test_stt_s_or_sis_confirms_identity_without_repeating_the_question():
    for transcript in ("S", "SIS"):
        context = PorterColdCallContext(
            stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
            awaiting_field="identity_confirmation",
            lead_name="Morgan Test",
        )

        decision = turn(context, transcript)

        assert decision.response_text == COLD_CALL_PERMISSION
        assert context.stage == PorterColdCallStage.OPENING


def test_no_invoice_funding_need_closes_without_fabricating_customer_type():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.RELEVANCE,
        awaiting_field="customer_type",
    )

    decision = turn(context, "No")

    assert decision.should_close is True
    assert decision.last_agent_act == "no_current_need_close"
    assert context.captured_fields == {"invoice_funding_need": "no"}


def test_existing_factor_answer_offers_advisor_review_without_satisfaction_question():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
    )

    decision = turn(context, "We already factor our invoices")

    assert decision.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert "funded billions" in decision.response_text
    assert "compare" in decision.response_text
    assert context.captured_fields["current_funding_method"] == "factor"


def test_acknowledgements_are_contextual_and_do_not_repeat_back_to_back():
    first = spoken_question(
        "How are you covering the gap?",
        kind=PorterAcknowledgement.HARDSHIP,
        turn_index=0,
    )
    second = spoken_question(
        "Is this something you need now?",
        kind=PorterAcknowledgement.HARDSHIP,
        previous=first.acknowledgement,
        turn_index=1,
    )

    assert first.acknowledgement in {"I understand.", "I hear you."}
    assert second.acknowledgement != first.acknowledgement


def test_misunderstood_question_is_rephrased_with_bounded_variation():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PAYMENT_TIMING,
        awaiting_field="payment_timing",
    )

    first = turn(context, "maybe")
    second = turn(context, "I do not understand")

    assert first.response_text == pending_question("payment_timing", attempt=1)
    assert second.response_text == pending_question("payment_timing", attempt=2)
    assert first.response_text != second.response_text


def test_silence_recovery_waits_rephrases_then_preserves_unknown():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PAYMENT_TIMING,
        awaiting_field="payment_timing",
    )

    first = turn(context, "[silence]")
    second = turn(context, "[silence]")
    third = turn(context, "[silence]")

    assert first.response_text == "Take your time."
    assert second.response_text == pending_question("payment_timing", attempt=1)
    assert third.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert "payment_timing" not in context.captured_fields


def test_summary_uses_only_confirmed_facts_and_preserves_unknowns():
    text = problem_summary(
        {
            "payment_timing": "Customers pay in 45 days",
            "operational_impact": "It puts pressure on payroll",
        }
    )

    assert "45 days" in text
    assert "payroll" in text
    assert "credit line" not in text
    assert "factoring company" not in text
    assert text.count("?") == 1


def test_direct_question_is_answered_before_pending_discovery_resumes():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CURRENT_FUNDING,
        awaiting_field="current_financing_solution",
    )

    rates = turn(context, "What rates do you charge?")
    resumed = turn(context, "We use a bank line")

    assert rates.intent == PorterCallerIntent.RATES
    assert "0.2 and 2 percent" in rates.response_text
    assert "1 and 5 percent" not in rates.response_text
    assert rates.response_text.endswith(pending_question("current_funding"))
    assert rates.next_stage == PorterColdCallStage.CURRENT_FUNDING
    assert resumed.next_stage == PorterColdCallStage.ADVISOR_OFFER


def test_nested_direct_questions_preserve_one_unfinished_discovery_stage():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CURRENT_FUNDING,
        awaiting_field="current_financing_solution",
    )

    rates = turn(context, "What rates do you charge?")
    disclosure = turn(context, "Are you an AI?")
    speed = turn(context, "How fast is funding?")

    assert rates.intent == PorterCallerIntent.RATES
    assert disclosure.intent == PorterCallerIntent.AI_DISCLOSURE
    assert speed.intent == PorterCallerIntent.FUNDING_SPEED
    assert context.stage == PorterColdCallStage.CURRENT_FUNDING
    assert context.awaiting_field == "current_financing_solution"

    resumed = turn(context, "We use a bank line.")

    assert resumed.intent == PorterCallerIntent.ANSWER
    assert resumed.next_stage == PorterColdCallStage.ADVISOR_OFFER


def test_presence_check_is_answered_before_identity_confirmation_resumes():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
        awaiting_field="identity_confirmation",
        lead_name="Morgan Test",
    )

    decision = turn(context, "Hey, are you there?")

    assert decision.response_text == "Yes, I'm here. Is this Morgan Test?"
    assert decision.intent == PorterCallerIntent.ANSWER
    assert context.stage == PorterColdCallStage.IDENTITY_CONFIRMATION
    assert context.unclear_turn_count == 0


def test_incomplete_fragment_is_rephrased_instead_of_captured():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PROVIDER_LIMITATION,
        awaiting_field="provider_limitation",
        captured_fields={"current_funding_method": "factor"},
    )

    decision = turn(context, "need more of")

    assert decision.intent == PorterCallerIntent.UNCLEAR
    assert "provider_limitation" not in context.captured_fields
    assert decision.response_text != "Is this something you're looking at now, or later on?"


def test_problem_summary_correction_updates_and_restates_confirmed_facts():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PROBLEM_CONFIRMATION,
        awaiting_field="problem_confirmation",
        captured_fields={
            "payment_timing": "30 days",
            "operational_impact": "Payroll gets tight",
        },
    )

    correction = turn(context, "Actually, customers pay in 60 days")

    assert correction.intent == PorterCallerIntent.CORRECTION
    assert context.captured_fields["payment_timing"] == "customers pay in 60 days"
    assert "60 days" in correction.response_text
    assert "payroll" in correction.response_text


def test_tailored_porter_explanation_connects_to_confirmed_payroll_problem():
    text = tailored_handoff({"operational_impact": "Payroll is due before payment"})

    assert "gap between customer payment and payroll" in text
    assert "eligible invoices" in text
    assert text.count("?") == 1


def test_human_request_uses_a_natural_scheduling_transition():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PAYMENT_TIMING,
        awaiting_field="payment_timing",
    )

    decision = turn(context, "I want to speak with a human")

    assert decision.intent == PorterCallerIntent.HUMAN_REQUEST
    assert decision.next_stage == PorterColdCallStage.BOOKING
    assert "best number" in decision.response_text.lower()


@pytest.mark.parametrize(
    ("text", "expected_act"),
    [
        ("Do not call me again", "close"),
        ("This is the wrong number", "close"),
        ("Call me back Friday morning", "callback_confirmation_question"),
    ],
)
def test_outcome_specific_endings_close_cleanly(text: str, expected_act: str):
    context = PorterColdCallContext(stage=PorterColdCallStage.OPENING)

    decision = turn(context, text)

    assert decision.should_close is (expected_act == "close")
    assert decision.last_agent_act == expected_act


def test_disclosure_is_truthful_without_human_impersonation_or_fake_fillers():
    lowered = DISCLOSURE.lower()

    assert "i'm an ai" in lowered
    assert "actual person" in lowered
    assert "i'm human" not in lowered
    assert not any(filler in lowered.split() for filler in ("um", "uh", "erm"))


def test_disclosure_preserves_context_and_actual_person_routes_to_booking():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PITCH,
        awaiting_field="pitch_response",
    )

    disclosure = turn(context, "Are you an AI?")

    assert disclosure.intent == PorterCallerIntent.AI_DISCLOSURE
    assert disclosure.response_text.startswith(DISCLOSURE)
    assert context.stage == PorterColdCallStage.PITCH

    handoff = turn(context, "I'd rather talk to an actual person.")

    assert handoff.intent == PorterCallerIntent.HUMAN_REQUEST
    assert context.stage == PorterColdCallStage.BOOKING


def test_confirmed_problem_advances_to_tailored_handoff_then_booking():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PROBLEM_CONFIRMATION,
        awaiting_field="problem_confirmation",
        captured_fields={
            "payment_timing": "45 days",
            "operational_impact": "Payroll gets tight",
            "current_financing_solution": "A bank line",
        },
    )

    offer = turn(context, "yes")
    booking = turn(context, "yes, connect me")

    assert "payroll" in offer.response_text
    assert offer.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert booking.next_stage == PorterColdCallStage.BOOKING
