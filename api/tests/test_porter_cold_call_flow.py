from api.porter.cold_call_flow import (
    ADVISOR_OFFER,
    CALLBACK_CONFIRMATION,
    CALLBACK_TODAY_QUESTION,
    CALLBACK_TIME_ONLY_QUESTION,
    CALLBACK_TIME_QUESTION,
    CASH_FLOW_QUESTION,
    CONNECTION_CLOSE,
    COMPANY_NAME_QUESTION,
    CONTACT_NAME_QUESTION,
    CONTACT_REFERRAL_QUESTION,
    REFERRAL_CONTACT_DETAILS_QUESTION,
    FINAL_QUESTIONS_PROMPT,
    FACTORING_ANSWER,
    FUNDING_SPEED_ANSWER,
    EXISTING_FACTOR_COMPARISON,
    HAPPY_FACTOR_EXPLORE,
    CURRENT_FACTOR_CHALLENGE_QUESTION,
    MONTHLY_INVOICING_QUESTION,
    MONTHLY_VOLUME_UNIT_CLARIFICATION,
    NO_RESPONSE_CLOSE,
    PARTIAL_AMOUNT_CLARIFICATION,
    ADVISOR_EXPLANATION,
    CALL_PURPOSE_ANSWER,
    OPENING_CLARIFICATION,
    OPENING_GREETING_RESPONSE,
    PHONE_QUESTION,
    EMAIL_QUESTION,
    PorterCallerIntent,
    PorterColdCallContext,
    PorterColdCallStage,
    VOICEMAIL_MESSAGE,
    UNCLEAR_RETRY,
    WARM_CLOSE,
    THIRD_HELLO,
    decide_porter_cold_call_turn,
)
from api.porter.cold_call_scripts import (
    ALREADY_HAS_FACTOR,
    BOOKING,
    COLD_CALL_PERMISSION,
    EXIT,
    NOT_INTERESTED,
    NOT_INTERESTED_CLOSE,
    PITCH,
    PORTER_OPTION,
    QUALIFIER_FOLLOW_UP,
    QUALIFIER_OPENING,
    RATES,
    WRONG_NUMBER_CLOSE,
)


def _turn(context: PorterColdCallContext, text: str):
    decision = decide_porter_cold_call_turn(context, text)
    decision.apply(context)
    return decision


def test_do_not_call_phrases_stop_from_every_stage():
    phrases = (
        "Do not call me again",
        "Don't call this number",
        "Take me off your list",
        "Put me on your do not call list",
    )
    stages = (
        PorterColdCallStage.OPENING,
        PorterColdCallStage.PITCH,
        PorterColdCallStage.CURRENT_FUNDING,
        PorterColdCallStage.BOOKING,
    )

    for stage in stages:
        for phrase in phrases:
            decision = _turn(PorterColdCallContext(stage=stage), phrase)
            assert decision.intent == PorterCallerIntent.STOP
            assert decision.should_close is True
            assert decision.response_text == EXIT


def test_live_connection_identity_and_permission_are_separate_stages():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CONNECTION_CHECK,
        awaiting_field="connection",
        last_agent_act="connection_check",
        lead_name="Morgan Test",
        lead_company="Summit Staffing",
    )

    answered = _turn(context, "Hello.")
    confirmed = _turn(context, "Yes, speaking.")
    accepted = _turn(context, "Yes.")

    assert answered.response_text == "Hey — is this Morgan Test with Summit Staffing?"
    assert answered.intent == PorterCallerIntent.GREETING
    assert confirmed.response_text == COLD_CALL_PERMISSION
    assert accepted.response_text == PITCH
    assert context.stage == PorterColdCallStage.PITCH


def test_natural_thirty_second_permission_advances_without_clarification():
    context = PorterColdCallContext()

    decision = _turn(context, "I have 30 seconds, you can continue.")

    assert decision.response_text == PITCH
    assert decision.intent == PorterCallerIntent.AFFIRMATIVE
    assert context.stage == PorterColdCallStage.PITCH


def test_shorter_permission_window_advances_to_the_pitch():
    context = PorterColdCallContext()

    decision = _turn(context, "I only have 20 seconds.")

    assert "I'll keep it brief" in decision.response_text
    assert decision.intent == PorterCallerIntent.AFFIRMATIVE
    assert context.stage == PorterColdCallStage.PITCH


def test_any_stated_short_permission_window_advances_to_the_pitch():
    context = PorterColdCallContext()

    decision = _turn(context, "I just have 10 seconds.")

    assert "I'll keep it brief" in decision.response_text
    assert context.stage == PorterColdCallStage.PITCH


def test_mhm_at_pitch_moves_to_the_advisor_value_offer():
    context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)

    decision = _turn(context, "Mhm.")

    assert decision.next_stage == PorterColdCallStage.ADVISOR_OFFER


def test_pitch_recovery_stays_on_the_pitch_and_honors_a_short_request():
    context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)

    unclear = _turn(context, "and")
    short_version = _turn(context, "make it short")

    assert "unpaid invoices" in unclear.response_text
    assert "briefly explain why I called" not in unclear.response_text
    assert "cash from invoices faster" in short_version.response_text.lower()
    assert "does that sound relevant" in short_version.response_text.lower()
    assert context.stage == PorterColdCallStage.PITCH


def test_hedged_pitch_acceptance_and_information_question_do_not_restart_permission():
    context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)

    accepted = _turn(context, "uh... yes, go ahead")
    assert accepted.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER

    pitch_context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)
    information = _turn(pitch_context, "What do you do?")

    assert information.intent == PorterCallerIntent.MORE_INFORMATION
    assert "working capital" in information.response_text
    assert "Does that sound relevant" in information.response_text
    assert "30 seconds" not in information.response_text
    assert pitch_context.stage == PorterColdCallStage.PITCH


def test_connection_check_retries_three_hellos_then_closes():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CONNECTION_CHECK,
        awaiting_field="connection",
        last_agent_act="connection_check",
    )

    second_hello = _turn(context, "[silence]")
    third_hello = _turn(context, "[silence]")
    close = _turn(context, "[silence]")

    assert second_hello.response_text == "Hello?"
    assert third_hello.response_text == THIRD_HELLO
    assert close.response_text == NO_RESPONSE_CLOSE
    assert close.should_close is True
    assert context.stage == PorterColdCallStage.COMPLETE


def test_identity_rejection_confirms_company_before_requesting_a_referral():
    for caller_text in ("No, this isn't Morgan.", "This isn't Morgan."):
        context = PorterColdCallContext(
            stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
            awaiting_field="identity_confirmation",
            last_agent_act="identity_confirmation_question",
            lead_name="Morgan Test",
            lead_company="Summit Staffing",
        )

        company_check = _turn(context, caller_text)
        wrong_company = _turn(context, "I'm not from Summit Staffing.")

        assert company_check.response_text == "Got it — did I at least reach Summit Staffing?"
        assert company_check.intent == PorterCallerIntent.WRONG_PERSON
        assert wrong_company.response_text == WRONG_NUMBER_CLOSE
        assert wrong_company.should_close is True
        assert context.stage == PorterColdCallStage.COMPLETE


def test_unclear_identity_answer_gets_a_shorter_human_retry():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
        awaiting_field="identity_confirmation",
        last_agent_act="identity_confirmation_question",
        lead_name="Morgan Test",
        lead_company="Summit Staffing",
    )

    decision = _turn(context, "you know")

    assert decision.response_text == (
        "I just want to make sure I reached Morgan Test. Is that you?"
    )
    assert context.stage == PorterColdCallStage.IDENTITY_CONFIRMATION


def test_confirmed_company_checks_the_alternate_contact_role_first():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
        awaiting_field="identity_confirmation",
        last_agent_act="identity_confirmation_question",
        lead_name="Morgan Test",
        lead_company="Summit Staffing",
    )

    _turn(context, "No, this isn't Morgan.")
    confirmed_company = _turn(context, "Yes, this is Summit Staffing.")

    assert "working-capital decisions" in confirmed_company.response_text
    assert context.stage == PorterColdCallStage.SAME_COMPANY_ROLE_CHECK


def test_permission_rejection_distinguishes_bad_timing_from_cold_call():
    bad_timing = PorterColdCallContext()
    cold_call = PorterColdCallContext()

    assert _turn(bad_timing, "No.").response_text == NOT_INTERESTED
    callback = _turn(bad_timing, "It's just bad timing, I'm in a meeting.")

    assert callback.response_text == CALLBACK_TIME_QUESTION
    assert callback.intent == PorterCallerIntent.BUSY
    assert bad_timing.stage == PorterColdCallStage.CALLBACK_DETAILS

    assert _turn(cold_call, "No.").response_text == NOT_INTERESTED
    close = _turn(cold_call, "Mostly because it's a cold call.")

    assert close.response_text == NOT_INTERESTED_CLOSE
    assert close.should_close is True
    assert cold_call.captured_fields["not_interested_reason"] == (
        "Mostly because it's a cold call."
    )


def test_approved_flow_routes_general_interest_to_the_advisor_offer():
    context = PorterColdCallContext()

    assert _turn(context, "Yes.").response_text == PITCH
    assert context.stage == PorterColdCallStage.PITCH

    offer = _turn(context, "Yes, go ahead.")
    assert offer.response_text == ADVISOR_OFFER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER


def test_unclear_opening_clarifies_instead_of_repeating_permission_verbatim():
    context = PorterColdCallContext()

    unclear = _turn(context, "transit")

    assert unclear.response_text == OPENING_CLARIFICATION
    assert unclear.intent == PorterCallerIntent.UNCLEAR
    assert context.stage == PorterColdCallStage.OPENING

    accepted = _turn(context, "Yeah")

    assert accepted.response_text == PITCH
    assert context.stage == PorterColdCallStage.PITCH

    offer = _turn(context, "Yes.")

    assert offer.response_text == ADVISOR_OFFER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER


def test_greeting_and_call_purpose_do_not_consume_connection_retries():
    context = PorterColdCallContext()

    greeting = _turn(context, "hello")
    ambiguous = _turn(context, "now")
    purpose = _turn(context, "what is it is a new calling for?")

    assert greeting.response_text == OPENING_GREETING_RESPONSE
    assert greeting.intent == PorterCallerIntent.GREETING
    assert ambiguous.response_text == OPENING_CLARIFICATION
    assert purpose.response_text == CALL_PURPOSE_ANSWER
    assert purpose.intent == PorterCallerIntent.MORE_INFORMATION
    assert purpose.should_close is False
    assert context.stage == PorterColdCallStage.OPENING
    assert context.unclear_turn_count == 0

    accepted = _turn(context, "go ahead")

    assert accepted.response_text == PITCH
    assert context.stage == PorterColdCallStage.PITCH


def test_existing_factor_answer_is_not_mistaken_for_factoring_question():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
    )

    decision = _turn(context, "We are doing the invoice factoring.")

    assert decision.response_text == EXISTING_FACTOR_COMPARISON
    assert decision.intent == PorterCallerIntent.ANSWER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER
    assert context.captured_fields["current_financing_solution"] == (
        "We are doing the invoice factoring."
    )


def test_existing_factor_accepts_common_stt_factory_transcriptions():
    transcripts = (
        "It was factory. We do invoice factory.",
        "Yes, we do in most factory.",
        "video factor invoices",
        "we're doing what factoring",
        "invoice factoring",
        "Lido factoring voices",
    )

    for transcript in transcripts:
        context = PorterColdCallContext(
            stage=PorterColdCallStage.EXISTING_FACTOR,
            awaiting_field="current_financing_solution",
            last_agent_act="existing_factor_question",
        )

        decision = _turn(context, transcript)

        assert decision.response_text == EXISTING_FACTOR_COMPARISON
        assert context.stage == PorterColdCallStage.ADVISOR_OFFER
        assert context.captured_fields["current_financing_solution"] == transcript


def test_existing_factor_treats_no_as_no_factor_and_stt_know_as_unclear():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
        captured_fields={"industry": "IP staffing"},
    )

    unclear = _turn(context, "know")
    no_factor = _turn(context, "No")

    assert "already factoring" in unclear.response_text
    assert unclear.intent == PorterCallerIntent.UNCLEAR
    assert "credit line" in no_factor.response_text
    assert context.stage == PorterColdCallStage.CURRENT_FUNDING
    assert context.captured_fields["industry"] == "IP staffing"
    assert context.captured_fields["current_financing_solution"] == "No"


def test_no_business_closes_cleanly_from_discovery_without_a_handoff():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CURRENT_FUNDING,
        awaiting_field="current_financing_solution",
        last_agent_act="current_funding_question",
    )

    decision = _turn(context, "I don't have any kind of business.")

    assert decision.should_close is True
    assert decision.response_text == (
        "Got it — then this isn't relevant right now. Thanks for letting me know. Take care."
    )
    assert context.stage == PorterColdCallStage.COMPLETE
    assert context.captured_fields == {
        "business_status": "no_business",
        "next_action": "not_interested",
    }


def test_prepaid_customers_close_instead_of_being_misclassified_as_a_factor():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CURRENT_FUNDING,
        awaiting_field="current_financing_solution",
        last_agent_act="current_funding_question",
    )

    decision = _turn(
        context,
        "Right now my customers pay me upfront, so there is no invoice to factor.",
    )

    assert decision.should_close is True
    assert "isn't creating a need" in decision.response_text
    assert context.stage == PorterColdCallStage.COMPLETE
    assert context.captured_fields == {
        "payment_timing": "Right now my customers pay me upfront, so there is no invoice to factor.",
        "next_action": "not_interested",
    }


def test_unclear_industry_transcription_is_not_captured():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.INDUSTRY,
        awaiting_field="industry",
        last_agent_act="industry_question",
    )

    decision = _turn(context, "I take on something.")

    assert decision.response_text == "What type of business do you run?"
    assert decision.intent == PorterCallerIntent.UNCLEAR
    assert context.captured_fields == {}


def test_uncertain_mixed_industry_transcription_is_not_echoed_back_verbatim():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.INDUSTRY,
        awaiting_field="industry",
        last_agent_act="industry_question",
    )

    decision = _turn(context, "We are in a trucking NID consulting.")

    assert decision.response_text == QUALIFIER_OPENING
    assert "NID" not in decision.response_text


def test_single_word_industry_is_captured_instead_of_treated_as_eligibility():
    for industry in ("parking", "trucking"):
        context = PorterColdCallContext(
            stage=PorterColdCallStage.INDUSTRY,
            awaiting_field="industry",
            last_agent_act="industry_question",
        )

        decision = _turn(context, industry)

        assert decision.response_text == QUALIFIER_OPENING
        assert decision.intent == PorterCallerIntent.ANSWER
        assert context.captured_fields["industry"] == industry
        assert context.stage == PorterColdCallStage.EXISTING_FACTOR


def test_direct_industry_eligibility_question_routes_to_advisor():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.INDUSTRY,
        awaiting_field="industry",
        last_agent_act="industry_question",
    )

    decision = _turn(context, "Do you work with trucking?")

    assert decision.intent == PorterCallerIntent.INDUSTRY_ELIGIBILITY
    assert context.stage == PorterColdCallStage.INDUSTRY
    assert context.captured_fields == {}


def test_one_word_industry_correction_updates_field_and_repeats_factor_question():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
        captured_fields={"industry": "parking"},
    )

    correction = _turn(context, "trucking")

    assert correction.response_text == QUALIFIER_FOLLOW_UP.format(
        natural_reaction="trucking"
    )
    assert context.captured_fields["industry"] == "trucking"
    assert context.stage == PorterColdCallStage.EXISTING_FACTOR


def test_negative_permission_answer_enters_not_interested_flow_without_looping():
    context = PorterColdCallContext()

    refusal = _turn(context, "no no")

    assert refusal.response_text == NOT_INTERESTED
    assert refusal.intent == PorterCallerIntent.NOT_INTERESTED
    assert context.stage == PorterColdCallStage.NOT_INTERESTED_REASON

    reason = _turn(context, "something I need right now")

    assert reason.response_text == NOT_INTERESTED_CLOSE
    assert reason.should_close is True
    assert context.stage == PorterColdCallStage.COMPLETE


def test_negative_pitch_answer_enters_not_interested_flow():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.PITCH,
        last_agent_act="pitch",
    )

    refusal = _turn(context, "No, thanks.")

    assert refusal.response_text == NOT_INTERESTED
    assert context.stage == PorterColdCallStage.NOT_INTERESTED_REASON


def test_happy_existing_factor_prospect_gets_one_exploration_offer_then_warm_close():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.FACTOR_SATISFACTION,
        awaiting_field="factor_satisfaction",
        last_agent_act="factor_satisfaction_question",
    )

    offer = _turn(context, "Yes.")
    close = _turn(context, "No thanks, not right now.")

    assert offer.response_text == HAPPY_FACTOR_EXPLORE
    assert offer.response_text != PITCH
    assert offer.should_close is False
    assert close.response_text == WARM_CLOSE
    assert close.should_close is True
    assert context.stage == PorterColdCallStage.COMPLETE


def test_happy_existing_factor_prospect_can_explore_porter_comparison():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.FACTOR_EXPLORATION,
        awaiting_field="factor_exploration",
        last_agent_act="factor_exploration_question",
    )

    decision = _turn(context, "Yes, I'd like to explore it.")

    assert decision.response_text == BOOKING
    assert decision.should_close is False
    assert context.stage == PorterColdCallStage.BOOKING


def test_factor_comparison_accepts_natural_go_ahead_variant():
    context = PorterColdCallContext(stage=PorterColdCallStage.FACTOR_EXPLORATION)

    decision = _turn(context, "Definitely, go ahead.")

    assert decision.response_text == BOOKING
    assert context.stage == PorterColdCallStage.BOOKING


def test_dissatisfied_factor_path_explains_questions_and_requests_advisor_consent():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.FACTOR_SATISFACTION,
        awaiting_field="factor_satisfaction",
        last_agent_act="factor_satisfaction_question",
        captured_fields={
            "payment_timing": "45 days",
            "operational_impact": "Payroll gets tight",
            "current_financing_solution": "Invoice factoring",
            "current_funding_method": "factor",
        },
    )

    challenge_question = _turn(context, "No.")
    advisor_offer = _turn(context, "The timeline is the issue.")
    booking = _turn(context, "Yes, connect me.")

    assert challenge_question.response_text == CURRENT_FACTOR_CHALLENGE_QUESTION
    assert "different setup" in advisor_offer.response_text
    assert advisor_offer.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert booking.response_text == BOOKING
    assert context.stage == PorterColdCallStage.BOOKING


def test_ambiguous_monthly_range_collects_unit_before_advisor_offer():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.MONTHLY_INVOICING_VOLUME,
        awaiting_field="monthly_invoicing_volume",
        last_agent_act="monthly_invoicing_question",
    )

    clarification = _turn(context, "about 100 to 150")
    advisor_offer = _turn(context, "thousand")

    assert clarification.response_text == MONTHLY_VOLUME_UNIT_CLARIFICATION
    assert context.captured_fields["monthly_invoicing_volume"] == (
        "about 100 to 150 thousand"
    )
    assert advisor_offer.response_text == ADVISOR_OFFER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER


def test_advisor_explanation_does_not_close_or_lose_offer():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.ADVISOR_OFFER,
        awaiting_field="advisor_offer",
        last_agent_act="advisor_offer_question",
    )

    explanation = _turn(context, "No, why don't you explain?")
    accepted = _turn(context, "Yes, connect me.")

    assert explanation.response_text == ADVISOR_EXPLANATION
    assert explanation.should_close is False
    assert accepted.response_text == BOOKING
    assert context.stage == PorterColdCallStage.BOOKING


def test_information_questions_hold_and_resume_pending_stage():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
    )

    rates = _turn(context, "Can I know what rates you provide?")
    speed = _turn(context, "So how much time do you take to fund the business?")
    repeated_speed = _turn(context, "It's time that you take to fund a business.")

    assert rates.response_text.startswith(RATES)
    assert speed.response_text.startswith(FUNDING_SPEED_ANSWER)
    assert repeated_speed.response_text.startswith(FUNDING_SPEED_ANSWER)
    assert all("covering" in item.response_text for item in (rates, speed, repeated_speed))
    assert context.stage == PorterColdCallStage.EXISTING_FACTOR
    assert context.captured_fields == {}

    resume = _turn(context, "Yes.")

    assert resume.response_text == EXISTING_FACTOR_COMPARISON
    assert resume.intent == PorterCallerIntent.ANSWER
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER


def test_discovery_reason_question_is_answered_without_repeating_the_pending_question():
    context = PorterColdCallContext(stage=PorterColdCallStage.FACTOR_SATISFACTION)

    decision = _turn(context, "Why are you asking all of this?")

    assert "worth your time" in decision.response_text
    assert "comfortable with" not in decision.response_text
    assert context.stage == PorterColdCallStage.FACTOR_SATISFACTION


def test_factoring_question_does_not_capture_or_advance():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CASH_FLOW_CHALLENGE,
        awaiting_field="cash_flow_challenge",
        last_agent_act="cash_flow_question",
    )

    decision = _turn(context, "And what is factoring?")

    assert decision.response_text.startswith(FACTORING_ANSWER)
    assert "main issue" in decision.response_text
    assert context.stage == PorterColdCallStage.CASH_FLOW_CHALLENGE
    assert context.captured_fields == {}


def test_short_qualification_path_captures_only_confirmed_fields():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
        captured_fields={"industry": "IT consulting."},
    )

    current_funding = _turn(context, "No, we do not factor.")
    advisor_offer = _turn(context, "We use internal cash.")
    booking_question = _turn(context, "Yes, connect me.")
    final_questions = _turn(context, "Use this number.")
    assert "internal cash" in current_funding.response_text
    assert advisor_offer.response_text == PORTER_OPTION
    assert booking_question.response_text == BOOKING
    assert final_questions.response_text == CALLBACK_TODAY_QUESTION
    today = _turn(context, "Today.")
    time = _turn(context, "3 pm.")
    confirmed = _turn(context, "Yes.")
    close = _turn(context, "No, that's all.")
    assert time.response_text == CALLBACK_CONFIRMATION
    assert confirmed.response_text == FINAL_QUESTIONS_PROMPT
    assert close.should_close is True
    assert context.captured_fields == {
        "industry": "IT consulting.",
        "current_financing_solution": "We use internal cash.",
        "current_funding_method": "internal_cash",
        "phone": "Use this number.",
        "callback_day": "today",
        "callback_request": "today at 3 pm.",
    }


def test_context_metadata_round_trip_preserves_conversation_state():
    original = PorterColdCallContext(
        stage=PorterColdCallStage.MONTHLY_INVOICING_VOLUME,
        awaiting_field="monthly_invoicing_volume",
        last_agent_act="knowledge_answer",
        captured_fields={"industry": "IT consulting"},
    )

    restored = PorterColdCallContext.from_metadata(original.to_metadata())

    assert restored == original


def test_busy_caller_collects_callback_time_before_closing():
    context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)

    busy = _turn(context, "I'm busy right now.")

    assert busy.response_text == CALLBACK_TIME_QUESTION
    assert busy.intent == PorterCallerIntent.BUSY
    assert context.stage == PorterColdCallStage.CALLBACK_DETAILS
    assert busy.should_close is False

    scheduled = _turn(context, "Tomorrow afternoon works.")

    assert scheduled.response_text == CALLBACK_CONFIRMATION
    assert scheduled.should_close is False
    assert context.captured_fields["callback_request"] == "Tomorrow afternoon works."
    assert _turn(context, "Yes.").next_stage == PorterColdCallStage.FINAL_QUESTIONS


def test_callback_with_time_confirms_without_an_extra_question():
    context = PorterColdCallContext()

    decision = _turn(context, "Call me back Friday morning.")

    assert decision.response_text == CALLBACK_CONFIRMATION
    assert decision.intent == PorterCallerIntent.CALLBACK
    assert decision.should_close is False
    assert context.stage == PorterColdCallStage.CALLBACK_CONFIRMATION
    assert context.captured_fields["callback_request"] == "call me back friday morning"


def test_opening_callback_with_time_confirms_without_an_extra_question():
    context = PorterColdCallContext()

    decision = _turn(context, "Call me back Friday afternoon.")

    assert decision.response_text == CALLBACK_CONFIRMATION
    assert decision.intent == PorterCallerIntent.CALLBACK
    assert decision.should_close is False
    assert context.stage == PorterColdCallStage.CALLBACK_CONFIRMATION


def test_callback_without_a_time_asks_for_one():
    context = PorterColdCallContext()

    decision = _turn(context, "Call me back next week.")

    assert decision.response_text == CALLBACK_TIME_QUESTION
    assert decision.should_close is False
    assert context.stage == PorterColdCallStage.CALLBACK_DETAILS


def test_voicemail_uses_noninteractive_message_and_closes():
    context = PorterColdCallContext()

    decision = _turn(context, "Please leave a message after the tone.")

    assert decision.response_text == VOICEMAIL_MESSAGE
    assert decision.intent == PorterCallerIntent.VOICEMAIL
    assert decision.should_close is True


def test_wrong_person_collects_contact_referral_then_contact_details():
    context = PorterColdCallContext()

    wrong_person = _turn(context, "You've got the wrong person.")

    assert wrong_person.response_text == CONTACT_REFERRAL_QUESTION
    assert context.stage == PorterColdCallStage.CONTACT_REFERRAL

    referral = _turn(context, "You should speak with Maria in finance.")

    assert referral.response_text == REFERRAL_CONTACT_DETAILS_QUESTION
    assert referral.should_close is False
    assert context.captured_fields["contact_referral"] == (
        "You should speak with Maria in finance."
    )


def test_human_request_enters_booking_state():
    context = PorterColdCallContext(stage=PorterColdCallStage.INDUSTRY)

    decision = _turn(context, "Can I talk to a human?")

    assert decision.response_text == BOOKING
    assert decision.intent == PorterCallerIntent.HUMAN_REQUEST
    assert context.stage == PorterColdCallStage.BOOKING


def test_booking_phone_number_does_not_count_as_callback_time():
    context = PorterColdCallContext(stage=PorterColdCallStage.BOOKING)

    phone = _turn(context, "205-555-0100")

    assert phone.response_text == CALLBACK_TODAY_QUESTION
    assert context.stage == PorterColdCallStage.CALLBACK_TODAY
    assert context.captured_fields["phone"] == "205-555-0100"
    assert "best_callback_time" not in context.captured_fields

    _turn(context, "today")
    _turn(context, "3 pm")
    _turn(context, "yes")
    close = _turn(context, "No, that's all")

    assert close.should_close is True
    assert "current arrangement" not in close.response_text


def test_booking_callback_time_does_not_count_as_phone_number():
    context = PorterColdCallContext(stage=PorterColdCallStage.BOOKING)

    callback_time = _turn(context, "Friday at 3 pm")

    assert callback_time.response_text == PHONE_QUESTION
    assert context.stage == PorterColdCallStage.BOOKING
    assert "best_callback_time" not in context.captured_fields
    assert "phone" not in context.captured_fields


def test_booking_accepts_oclock_and_respects_a_booking_refusal():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.BOOKING,
        captured_fields={"phone": "Use this number"},
    )

    scheduled = _turn(context, "Today at 3 o'clock.")

    assert scheduled.next_stage == PorterColdCallStage.CALLBACK_TODAY
    assert "best_callback_time" not in context.captured_fields

    refusal = _turn(PorterColdCallContext(stage=PorterColdCallStage.BOOKING), "You can't book me at all.")

    assert refusal.should_close is True


def test_booking_stage_answers_a_rate_question_without_pushing_contact_details():
    context = PorterColdCallContext(stage=PorterColdCallStage.BOOKING)

    decision = _turn(context, "What rates do you provide?")

    assert decision.response_text == RATES
    assert context.stage == PorterColdCallStage.BOOKING


def test_identity_question_answers_then_returns_to_identity_confirmation():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CONNECTION_CHECK,
        lead_name="Morgan Test",
    )

    decision = _turn(context, "Yes, who's this?")

    assert "Aiva" in decision.response_text
    assert "Morgan Test" in decision.response_text
    assert "say that another way" not in decision.response_text
    assert context.stage == PorterColdCallStage.IDENTITY_CONFIRMATION


def test_stt_rate_misrecognition_and_exact_quote_question_are_answered_before_booking():
    context = PorterColdCallContext(stage=PorterColdCallStage.ADVISOR_OFFER)

    misrecognized = _turn(context, "What grades do you guys provide?")
    exact_quote = _turn(context, "Could you calculate me the exact number?")

    assert misrecognized.response_text.startswith(RATES)
    assert exact_quote.response_text.startswith(RATES)
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER


def test_booking_collects_phone_then_invites_one_final_question_before_closing():
    context = PorterColdCallContext(stage=PorterColdCallStage.BOOKING)

    phone = _turn(context, "You can call me at 659-253-2045.")
    rate = _turn(context, "What rates do you provide?")
    close = _turn(context, "No, that's all.")

    assert phone.response_text == CALLBACK_TODAY_QUESTION
    assert context.captured_fields["phone"] == "You can call me at 659-253-2045."
    assert rate.response_text.startswith(RATES)
    assert close.should_close is True


def test_booking_script_collects_only_a_callback_number():
    assert "best number" in BOOKING.lower()
    assert "day and time" not in BOOKING.lower()


def test_same_company_alternate_contact_moves_through_role_and_name_before_intro():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.COMPANY_CONFIRMATION,
        lead_company="Summit Staffing",
    )

    role = _turn(context, "Yes, this is Summit Staffing.")
    name = _turn(context, "Yes, I handle financing.")
    intro = _turn(context, "Jamie Lee.")

    assert role.next_stage == PorterColdCallStage.SAME_COMPANY_ROLE_CHECK
    assert name.next_stage == PorterColdCallStage.ALTERNATE_CONTACT_NAME
    assert intro.response_text == COLD_CALL_PERMISSION
    assert context.captured_fields["alternate_contact_name"] == "Jamie Lee."


def test_existing_factor_at_interest_check_goes_to_comparison_before_booking():
    context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)

    decision = _turn(context, "We already use invoice factoring.")

    assert decision.response_text == EXISTING_FACTOR_COMPARISON
    assert decision.next_stage == PorterColdCallStage.ADVISOR_OFFER
    assert context.captured_fields["current_funding_method"] == "factor"


def test_booking_requires_callback_confirmation_before_final_questions():
    context = PorterColdCallContext(stage=PorterColdCallStage.BOOKING)

    _turn(context, "Use this number.")
    _turn(context, "Today.")
    confirmation = _turn(context, "3 pm.")
    final_questions = _turn(context, "Yes.")

    assert confirmation.next_stage == PorterColdCallStage.CALLBACK_CONFIRMATION
    assert final_questions.response_text == FINAL_QUESTIONS_PROMPT
    assert context.stage == PorterColdCallStage.FINAL_QUESTIONS


def test_audio_delivery_problem_checks_the_connection_then_repeats_or_closes():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
    )

    first = _turn(context, "Hey, your voice is not audible. Could you repeat that?")
    second = _turn(context, "I still can't hear you.")

    assert first.response_text == "Sorry about that. Can you hear me now?"
    assert first.should_close is False
    assert second.should_close is True
    assert "connection isn't working" in second.response_text

    confirmed_context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
    )
    _turn(confirmed_context, "I can't hear you.")
    confirmed = _turn(confirmed_context, "Yes, I can hear you now.")

    assert confirmed.response_text.startswith("Great.")
    assert "factoring" in confirmed.response_text.lower()
    assert confirmed.should_close is False


def test_final_questions_treats_a_polite_decline_as_a_clean_close():
    context = PorterColdCallContext(stage=PorterColdCallStage.FINAL_QUESTIONS)

    decision = _turn(context, "Probably I'm good right now.")

    assert decision.should_close is True
    assert "current arrangement" not in decision.response_text
    assert "Porter Capital" in decision.response_text


def test_direct_explanation_questions_do_not_be_saved_as_an_industry_answer():
    pitch_context = PorterColdCallContext(stage=PorterColdCallStage.PITCH)

    pitch_question = _turn(
        pitch_context,
        "Yes, do you guys provide cash for invoices? That's what I mean.",
    )

    assert pitch_question.intent == PorterCallerIntent.MORE_INFORMATION
    assert pitch_context.stage == PorterColdCallStage.PITCH
    assert "working capital" in pitch_question.response_text.lower()

    industry_context = PorterColdCallContext(
        stage=PorterColdCallStage.INDUSTRY,
        awaiting_field="industry",
        last_agent_act="industry_question",
    )

    explanation = _turn(industry_context, "Hey, could you explain what you guys do?")
    follow_up = _turn(industry_context, "What are you talking about?")

    assert explanation.intent == PorterCallerIntent.MORE_INFORMATION
    assert follow_up.intent == PorterCallerIntent.MORE_INFORMATION
    assert industry_context.stage == PorterColdCallStage.INDUSTRY
    assert "industry" not in industry_context.captured_fields
    assert "working capital" in explanation.response_text.lower()
    assert "working capital" in follow_up.response_text.lower()


def test_unclear_discovery_has_bounded_repair_then_preserves_unknown():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.INDUSTRY,
        awaiting_field="industry",
        last_agent_act="industry_question",
    )

    first = _turn(context, "")
    second = _turn(context, "maybe")
    third = _turn(context, "hmm")

    assert first.response_text == "What type of business do you run?"
    assert second.response_text == "What type of business do you run?"
    assert "leave that unknown" in third.response_text
    assert third.should_close is False
    assert context.stage == PorterColdCallStage.ADVISOR_OFFER
    assert context.unclear_turn_count == 3


def test_valid_answer_resets_unclear_turn_count():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.INDUSTRY,
        awaiting_field="industry",
        last_agent_act="industry_question",
        unclear_turn_count=2,
    )

    decision = _turn(context, "trucking")

    assert decision.intent == PorterCallerIntent.ANSWER
    assert context.unclear_turn_count == 0


def test_industry_correction_updates_field_and_resumes_pending_question():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.EXISTING_FACTOR,
        awaiting_field="current_financing_solution",
        last_agent_act="existing_factor_question",
        captured_fields={"industry": "parking"},
    )

    correction = _turn(context, "Actually, it's trucking.")

    assert correction.intent == PorterCallerIntent.CORRECTION
    assert context.captured_fields["industry"] == "trucking"
    assert "covering" in correction.response_text
    assert context.stage == PorterColdCallStage.EXISTING_FACTOR


def test_email_correction_during_name_collection_resumes_name_question():
    context = PorterColdCallContext(
        stage=PorterColdCallStage.CONTACT_NAME,
        awaiting_field="full_name",
        last_agent_act="contact_name_question",
        captured_fields={"email": "old@example.com"},
    )

    correction = _turn(context, "Actually, my email is new@example.com.")

    assert correction.intent == PorterCallerIntent.CORRECTION
    assert context.captured_fields["email"] == "new@example.com"
    assert correction.response_text.endswith(CONTACT_NAME_QUESTION)
