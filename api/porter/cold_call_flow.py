from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping

from api.porter.delivery import (
    PorterAcknowledgement,
    pending_question,
    problem_summary,
    spoken_question,
    tailored_handoff,
)
from api.porter.cold_call_scripts import (
    ALREADY_HAS_FACTOR,
    BOOKING,
    COLD_CALL_PERMISSION,
    DISCLOSURE,
    EXIT,
    HAPPY_FACTOR_EXPLORE,
    NOT_INTERESTED,
    NOT_INTERESTED_CLOSE,
    PITCH,
    EXISTING_FACTOR_COMPARISON,
    PORTER_OPTION,
    QUALIFIER_FOLLOW_UP,
    QUALIFIER_OPENING,
    RATES,
    WARM_CLOSE,
    WRONG_NUMBER_CLOSE,
)


class PorterColdCallStage(StrEnum):
    CONNECTION_CHECK = "connection_check"
    IDENTITY_CONFIRMATION = "identity_confirmation"
    COMPANY_CONFIRMATION = "company_confirmation"
    OPENING = "opening"
    PITCH = "pitch"
    RELEVANCE = "relevance"
    PAYMENT_TIMING = "payment_timing"
    OPERATIONAL_IMPACT = "operational_impact"
    CURRENT_FUNDING = "current_funding"
    PROVIDER_LIMITATION = "provider_limitation"
    NEED_TIMING = "need_timing"
    DECISION_AUTHORITY = "decision_authority"
    PROBLEM_CONFIRMATION = "problem_confirmation"
    INDUSTRY = "industry"
    EXISTING_FACTOR = "existing_factor"
    FACTOR_SATISFACTION = "factor_satisfaction"
    FACTOR_EXPLORATION = "factor_exploration"
    CASH_FLOW_CHALLENGE = "cash_flow_challenge"
    MONTHLY_INVOICING_VOLUME = "monthly_invoicing_volume"
    ADVISOR_OFFER = "advisor_offer"
    BOOKING = "booking"
    FINAL_QUESTIONS = "final_questions"
    CONTACT_EMAIL = "contact_email"
    CONTACT_NAME = "contact_name"
    CONTACT_COMPANY = "contact_company"
    CALLBACK_DETAILS = "callback_details"
    CALLBACK_TODAY = "callback_today"
    CALLBACK_CONFIRMATION = "callback_confirmation"
    CONTACT_REFERRAL = "contact_referral"
    SAME_COMPANY_ROLE_CHECK = "same_company_role_check"
    ALTERNATE_CONTACT_NAME = "alternate_contact_name"
    REFERRAL_CONTACT_DETAILS = "referral_contact_details"
    NOT_INTERESTED_REASON = "not_interested_reason"
    COMPLETE = "complete"


class PorterCallerIntent(StrEnum):
    ANSWER = "answer"
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    GREETING = "greeting"
    IDENTITY = "identity"
    AI_DISCLOSURE = "ai_disclosure"
    MORE_INFORMATION = "more_information"
    RATES = "rates"
    FUNDING_SPEED = "funding_speed"
    FEES = "fees"
    TERMS = "terms"
    FACTORING_EXPLANATION = "factoring_explanation"
    INDUSTRY_ELIGIBILITY = "industry_eligibility"
    HUMAN_REQUEST = "human_request"
    WRONG_PERSON = "wrong_person"
    GATEKEEPER = "gatekeeper"
    VOICEMAIL = "voicemail"
    BUSY = "busy"
    STOP = "stop"
    NOT_INTERESTED = "not_interested"
    CALLBACK = "callback"
    SEND_INFORMATION = "send_information"
    SILENCE = "silence"
    CORRECTION = "correction"
    UNCLEAR = "unclear"


@dataclass
class PorterColdCallContext:
    stage: PorterColdCallStage = PorterColdCallStage.OPENING
    awaiting_field: str | None = None
    last_agent_act: str = "opener"
    unclear_turn_count: int = 0
    silence_turn_count: int = 0
    delivery_turn_count: int = 0
    last_acknowledgement: str | None = None
    lead_name: str | None = None
    lead_company: str | None = None
    captured_fields: dict[str, str] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "awaiting_field": self.awaiting_field,
            "last_agent_act": self.last_agent_act,
            "unclear_turn_count": self.unclear_turn_count,
            "silence_turn_count": self.silence_turn_count,
            "delivery_turn_count": self.delivery_turn_count,
            "last_acknowledgement": self.last_acknowledgement,
            "lead_name": self.lead_name,
            "lead_company": self.lead_company,
            "captured_fields": dict(self.captured_fields),
        }

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, object] | None) -> "PorterColdCallContext":
        payload = dict(metadata or {})
        stage_value = str(payload.get("stage") or PorterColdCallStage.OPENING.value)
        stage = (
            PorterColdCallStage(stage_value)
            if stage_value in PorterColdCallStage._value2member_map_
            else PorterColdCallStage.OPENING
        )
        captured = payload.get("captured_fields")
        return cls(
            stage=stage,
            awaiting_field=_optional_string(payload.get("awaiting_field")),
            last_agent_act=str(payload.get("last_agent_act") or "opener"),
            unclear_turn_count=max(int(payload.get("unclear_turn_count") or 0), 0),
            silence_turn_count=max(int(payload.get("silence_turn_count") or 0), 0),
            delivery_turn_count=max(int(payload.get("delivery_turn_count") or 0), 0),
            last_acknowledgement=_optional_string(payload.get("last_acknowledgement")),
            lead_name=_optional_string(payload.get("lead_name")),
            lead_company=_optional_string(payload.get("lead_company")),
            captured_fields={
                str(key): str(value)
                for key, value in dict(captured or {}).items()
                if value not in (None, "")
            },
        )


@dataclass(frozen=True)
class PorterColdCallDecision:
    response_text: str
    intent: PorterCallerIntent
    next_stage: PorterColdCallStage
    awaiting_field: str | None
    last_agent_act: str
    captured_updates: Mapping[str, str] = field(default_factory=dict)
    unclear_turn_count: int = 0
    silence_turn_count: int = 0
    acknowledgement: str | None = None
    should_close: bool = False

    def apply(self, context: PorterColdCallContext) -> None:
        context.stage = self.next_stage
        context.awaiting_field = self.awaiting_field
        context.last_agent_act = self.last_agent_act
        context.unclear_turn_count = self.unclear_turn_count
        context.silence_turn_count = self.silence_turn_count
        context.delivery_turn_count += 1
        if self.acknowledgement:
            context.last_acknowledgement = self.acknowledgement
        context.captured_fields.update(self.captured_updates)


CASH_FLOW_QUESTION = "During that wait, does it put pressure on payroll or other costs?"
CURRENT_FACTOR_CHALLENGE_QUESTION = (
    "What's the main thing you would want improved, if anything?"
)
MONTHLY_INVOICING_QUESTION = (
    "Roughly how much do you invoice in a typical month?"
)
PARTIAL_AMOUNT_CLARIFICATION = "About how many thousand per month?"
MONTHLY_VOLUME_UNIT_CLARIFICATION = (
    "Is that dollars, thousands, or millions per month?"
)
ADVISOR_OFFER = (
    "A quick 10-minute call with one of our financing advisors can give you a clearer "
    "look at whether Porter may fit. Could we set that up today?"
)
ADVISOR_EXPLANATION = (
    "A funding specialist would review the invoice setup and explain what may fit. "
    "Would a short review be useful?"
)
FACTOR_SATISFACTION_QUESTION = "Is the current factoring arrangement meeting your needs?"
BOOKING_CONFIRMATION = "You're set. A Porter funding specialist will follow up at the time we confirmed."
PHONE_QUESTION = "What's the best number or email for the advisor to use?"
FINAL_QUESTIONS_PROMPT = "Thanks — is there anything else you'd like to know before I let you go?"
CALLBACK_TIME_ONLY_QUESTION = "What day and time works best for the call?"
EMAIL_QUESTION = "What's the best business email for the confirmation?"
CONTACT_NAME_QUESTION = "What's your full name?"
COMPANY_NAME_QUESTION = "What company should I put with the appointment?"
CALLBACK_TIME_QUESTION = "What day and time would work better?"
CALLBACK_TODAY_QUESTION = "Would today work for a quick call?"
CALLBACK_TODAY_TIME_QUESTION = "What time today would work best for you?"
CALLBACK_CONFIRMATION = "Just to confirm, you'd like an advisor to call at the time you requested. Is that correct?"
CONTACT_REFERRAL_QUESTION = "Who handles invoice-financing decisions there?"
SAME_COMPANY_ROLE_QUESTION = (
    "Thanks for letting me know. Are you involved with financing or working-capital decisions there?"
)
ALTERNATE_CONTACT_NAME_QUESTION = "Got it. What's your name?"
REFERRAL_CONTACT_DETAILS_QUESTION = "Do you have their phone number or email?"
GATEKEEPER_QUESTION = "I'm calling about customer-payment timing. Who handles financing decisions there?"
VOICEMAIL_MESSAGE = (
    "Hi, this is Aiva, an automated assistant with Porter Capital. I'm calling about "
    "customer-payment timing. Porter can try again another time."
)
UNCLEAR_RETRY = "Let me put that another way."
CONNECTION_CLOSE = "I'm sorry, the connection isn't clear enough to continue. I'll end the call here."
NO_RESPONSE_CLOSE = "I'm not hearing anyone, so I'll end the call here."
SECOND_HELLO = "Hello?"
THIRD_HELLO = "Hello, can you hear me?"
OPENING_CLARIFICATION = "Would it be okay if I briefly explain why I called?"
OPENING_GREETING_RESPONSE = "This is Aiva, an automated assistant with Porter Capital. Can I briefly explain why I called?"
CALL_PURPOSE_ANSWER = (
    "Porter works with businesses that wait on customer invoices. Can I take 30 "
    "seconds to see if that's relevant here?"
)

IDENTITY_ANSWER = "I'm Aiva, an automated assistant calling on behalf of Porter Capital."
MORE_INFORMATION_ANSWER = (
    "Porter provides commercial working capital based on eligible invoices."
)
FACTORING_ANSWER = "Invoice factoring turns eligible unpaid business invoices into working capital."
FUNDING_SPEED_ANSWER = (
    "Once you're set up with Porter, funding is usually under 48 hours after you submit an invoice."
)
FEES_ANSWER = "Fees depend on how the program is structured and are reviewed in the proposal."
TERMS_ANSWER = (
    "Terms depend on the business setup. A funding specialist would need to review the details."
)
INDUSTRY_ANSWER = (
    "That depends on the details. A Porter funding specialist would need to review the fit."
)


def decide_porter_cold_call_turn(
    context: PorterColdCallContext,
    user_text: str,
) -> PorterColdCallDecision:
    normalized = _normalize(user_text)
    tokens = set(normalized.split())

    if normalized in {"silence", "no response"}:
        return _silence_decision(context)

    audio_delivery_recovery = _audio_delivery_recovery_confirmation(context, normalized)
    if audio_delivery_recovery is not None:
        return audio_delivery_recovery

    audio_delivery_problem = _audio_delivery_problem_decision(context, normalized)
    if audio_delivery_problem is not None:
        return audio_delivery_problem

    if context.stage == PorterColdCallStage.FINAL_QUESTIONS and _is_final_questions_decline(
        normalized
    ):
        return _warm_close_decision(context, original=user_text.strip())

    informational = _informational_decision(context, normalized, tokens)
    if informational is not None:
        return informational

    presence = _presence_check_decision(context, normalized)
    if presence is not None:
        return presence

    no_business = _no_business_decision(context, normalized)
    if no_business is not None:
        return no_business

    if (
        context.stage == PorterColdCallStage.ADVISOR_OFFER
        and _contains_any(normalized, ("why", "explain", "what would they do"))
    ):
        return _decision(
            context,
            response=ADVISOR_EXPLANATION,
            intent=PorterCallerIntent.MORE_INFORMATION,
            last_agent_act="advisor_explanation",
        )

    discovery_reason = _discovery_reason_decision(context, normalized)
    if discovery_reason is not None:
        return discovery_reason

    if context.stage in {
        PorterColdCallStage.FACTOR_EXPLORATION,
        PorterColdCallStage.ADVISOR_OFFER,
    } and (
        _is_negative(normalized)
        or _contains_any(normalized, ("not interested", "no thanks", "not right now"))
    ):
        return _warm_close_decision(context, original=user_text.strip())

    terminal = _terminal_or_callback_decision(context, normalized)
    if terminal is not None:
        return terminal

    if context.stage == PorterColdCallStage.ADVISOR_OFFER and (
        _is_affirmative(normalized)
        or _contains_any(normalized, ("connect me", "talk to", "speak with", "set it up"))
    ):
        return _stage_decision(context, user_text.strip(), normalized)

    correction = _correction_decision(context, user_text.strip(), normalized)
    if correction is not None:
        return correction

    return _stage_decision(context, user_text.strip(), normalized)


def _terminal_or_callback_decision(
    context: PorterColdCallContext,
    normalized: str,
) -> PorterColdCallDecision | None:
    if _contains_any(
        normalized,
        (
            "stop calling",
            "remove me",
            "do not call",
            "don t call",
            "dont call",
            "take me off your list",
            "take me off the list",
            "put me on your do not call list",
            "hang up",
        ),
    ):
        return _decision(
            context,
            response=EXIT,
            intent=PorterCallerIntent.STOP,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            should_close=True,
        )
    if _is_voicemail(normalized):
        return _decision(
            context,
            response=VOICEMAIL_MESSAGE,
            intent=PorterCallerIntent.VOICEMAIL,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            should_close=True,
        )
    if _is_wrong_number(normalized):
        return _decision(
            context,
            response=WRONG_NUMBER_CLOSE,
            intent=PorterCallerIntent.WRONG_PERSON,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            should_close=True,
        )
    if _is_wrong_person(normalized):
        if (
            context.stage == PorterColdCallStage.IDENTITY_CONFIRMATION
            and context.lead_company
        ):
            return _decision(
                context,
                response=_company_confirmation_prompt(context),
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.COMPANY_CONFIRMATION,
                awaiting="company_confirmation",
                last_agent_act="company_confirmation_question",
            )
        return _decision(
            context,
            response=CONTACT_REFERRAL_QUESTION,
            intent=PorterCallerIntent.WRONG_PERSON,
            stage=PorterColdCallStage.CONTACT_REFERRAL,
            awaiting="contact_referral",
            last_agent_act="contact_referral_question",
        )
    if _is_gatekeeper(normalized):
        return _decision(
            context,
            response=GATEKEEPER_QUESTION,
            intent=PorterCallerIntent.GATEKEEPER,
            stage=PorterColdCallStage.CONTACT_REFERRAL,
            awaiting="contact_referral",
            last_agent_act="contact_referral_question",
        )
    callback_intent = (
        None
        if context.stage
        in {
            PorterColdCallStage.BOOKING,
            PorterColdCallStage.CONTACT_EMAIL,
            PorterColdCallStage.CONTACT_NAME,
            PorterColdCallStage.CONTACT_COMPANY,
        }
        else _callback_or_busy_intent(normalized)
    )
    if callback_intent is not None:
        if _has_callback_details(normalized):
            return _decision(
                context,
                response=CALLBACK_CONFIRMATION,
                intent=callback_intent,
                stage=PorterColdCallStage.CALLBACK_CONFIRMATION,
                awaiting="callback_confirmation",
                last_agent_act="callback_confirmation_question",
                updates={"callback_request": normalized},
            )
        return _decision(
            context,
            response=CALLBACK_TIME_QUESTION,
            intent=callback_intent,
            stage=PorterColdCallStage.CALLBACK_DETAILS,
            awaiting="callback_request",
            last_agent_act="callback_time_question",
        )
    if (
        "email me" in normalized
        or (
            "send" in normalized
            and _contains_any(normalized, ("info", "information", "details"))
        )
    ):
        return _decision(
            context,
            response=(
                "Got it — one of our financing advisors can follow up with more information."
            ),
            intent=PorterCallerIntent.SEND_INFORMATION,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            updates={"send_information_request": normalized},
            should_close=True,
        )
    if _contains_any(normalized, ("not interested", "no thanks", "we are good")):
        return _not_interested_decision(context)
    return None


def _presence_check_decision(
    context: PorterColdCallContext,
    normalized: str,
) -> PorterColdCallDecision | None:
    if not _contains_any(
        normalized,
        ("are you there", "can you hear me", "are you still there"),
    ):
        return None
    if context.stage == PorterColdCallStage.CONNECTION_CHECK:
        return _decision(
            context,
            response=f"Yes, I can hear you. {_identity_confirmation_prompt(context)}",
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
            awaiting="identity_confirmation",
            last_agent_act="identity_confirmation_question",
        )
    return _decision(
        context,
        response=f"Yes, I'm here. {_pending_question(context)}",
        intent=PorterCallerIntent.ANSWER,
        last_agent_act="presence_check_answer",
    )


def _audio_delivery_problem_decision(
    context: PorterColdCallContext,
    normalized: str,
) -> PorterColdCallDecision | None:
    if not _contains_any(
        normalized,
        (
            "not audible",
            "can t hear you",
            "cant hear you",
            "cannot hear you",
            "can t hear",
            "cant hear",
            "cannot hear",
            "not hearing you",
            "no audio",
            "voice is not audible",
        ),
    ):
        return None
    if context.unclear_turn_count >= 1:
        return _decision(
            context,
            response="Sorry, it sounds like the connection isn't working. I won't keep you. Take care.",
            intent=PorterCallerIntent.UNCLEAR,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="audio_delivery_close",
            unclear_turn_count=context.unclear_turn_count + 1,
            should_close=True,
        )
    return _decision(
        context,
        response="Sorry about that. Can you hear me now?",
        intent=PorterCallerIntent.UNCLEAR,
        last_agent_act="audio_delivery_recovery",
        unclear_turn_count=context.unclear_turn_count + 1,
    )


def _audio_delivery_recovery_confirmation(
    context: PorterColdCallContext,
    normalized: str,
) -> PorterColdCallDecision | None:
    if context.last_agent_act != "audio_delivery_recovery":
        return None
    if not (
        _is_affirmative(normalized)
        or _contains_any(normalized, ("i can hear you", "can hear you now", "hear you now"))
    ):
        return None
    return _decision(
        context,
        response=f"Great. {_pending_question(context)}",
        intent=PorterCallerIntent.ANSWER,
        last_agent_act="audio_delivery_confirmed",
        unclear_turn_count=0,
    )


def _informational_decision(
    context: PorterColdCallContext,
    normalized: str,
    tokens: set[str],
) -> PorterColdCallDecision | None:
    response: str | None = None
    intent: PorterCallerIntent | None = None
    if _contains_any(
        normalized,
        (
            "need a real person",
            "want a real person",
            "talk to a real person",
            "speak to a real person",
            "talk with a person",
            "speak with a person",
        ),
    ):
        return _decision(
            context,
            response=BOOKING,
            intent=PorterCallerIntent.HUMAN_REQUEST,
            stage=PorterColdCallStage.BOOKING,
            awaiting="phone",
            last_agent_act="booking_question",
        )
    if _contains_any(normalized, ("are you ai", "are you an ai", "robot", "real person")):
        response, intent = DISCLOSURE, PorterCallerIntent.AI_DISCLOSURE
    elif _contains_any(normalized, ("who are you", "who is this", "who s this")):
        return _decision(
            context,
            response=f"{IDENTITY_ANSWER} {_identity_confirmation_prompt(context)}",
            intent=PorterCallerIntent.IDENTITY,
            stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
            awaiting="identity_confirmation",
            last_agent_act="identity_confirmation_question",
        )
    elif _asks_call_purpose(normalized, tokens):
        return _decision(
            context,
            response=CALL_PURPOSE_ANSWER,
            intent=PorterCallerIntent.MORE_INFORMATION,
            last_agent_act="permission_question",
        )
    elif bool(tokens & {"rate", "rates", "pricing", "price", "percentage"}) or (
        "cost" in tokens and _looks_like_question(normalized)
    ) or _contains_any(
        normalized,
        ("what are the grades", "grades do you", "what do you charge", "exact number", "calculate me"),
    ):
        response, intent = RATES, PorterCallerIntent.RATES
    elif _asks_about_funding_speed(normalized, tokens):
        response, intent = FUNDING_SPEED_ANSWER, PorterCallerIntent.FUNDING_SPEED
    elif _contains_any(normalized, ("fee", "fees")):
        response, intent = FEES_ANSWER, PorterCallerIntent.FEES
    elif _contains_any(normalized, ("selective", "full factoring", "contract", "terms")):
        response, intent = TERMS_ANSWER, PorterCallerIntent.TERMS
    elif _is_industry_eligibility_question(normalized, tokens):
        response, intent = INDUSTRY_ANSWER, PorterCallerIntent.INDUSTRY_ELIGIBILITY
    elif _asks_porter_explanation(normalized, tokens):
        response, intent = MORE_INFORMATION_ANSWER, PorterCallerIntent.MORE_INFORMATION
    elif _asks_what_factoring_is(normalized, tokens):
        response, intent = FACTORING_ANSWER, PorterCallerIntent.FACTORING_EXPLANATION
    elif _contains_any(
        normalized,
        ("talk to someone", "actual person", "advisor", "human", "representative"),
    ):
        return _decision(
            context,
            response=BOOKING,
            intent=PorterCallerIntent.HUMAN_REQUEST,
            stage=PorterColdCallStage.BOOKING,
            awaiting="phone",
            last_agent_act="booking_question",
        )

    if response is None or intent is None:
        return None
    response = _knowledge_answer_with_bridge(context, response)
    return _decision(
        context,
        response=response,
        intent=intent,
        last_agent_act="knowledge_answer",
    )


def _discovery_reason_decision(
    context: PorterColdCallContext,
    normalized: str,
) -> PorterColdCallDecision | None:
    if not _contains_any(normalized, ("why are you asking", "why do you ask", "why all this")):
        return None
    reasons = {
        PorterColdCallStage.INDUSTRY: (
            "Fair question — I'm only trying to see whether Porter would even be relevant "
            "to your business."
        ),
        PorterColdCallStage.EXISTING_FACTOR: (
            "Fair question — I'm just trying to understand whether Porter would be worth "
            "comparing with what you use now."
        ),
        PorterColdCallStage.FACTOR_SATISFACTION: (
            "Fair question — I'm only trying to see whether comparing Porter would be worth "
            "your time, not to push you to change anything."
        ),
        PorterColdCallStage.FACTOR_EXPLORATION: (
            "Fair question — I'm only checking whether a comparison would be worth your time."
        ),
        PorterColdCallStage.BOOKING: (
            "Just so an advisor can reach you at a time that works for you."
        ),
    }
    response = reasons.get(context.stage)
    if response is None:
        return None
    return _decision(
        context,
        response=response,
        intent=PorterCallerIntent.MORE_INFORMATION,
        last_agent_act="discovery_reason_answer",
    )


def _stage_decision(
    context: PorterColdCallContext,
    original: str,
    normalized: str,
) -> PorterColdCallDecision:
    stage = context.stage
    if stage == PorterColdCallStage.CONNECTION_CHECK:
        return _decision(
            context,
            response=_identity_confirmation_prompt(context),
            intent=(
                PorterCallerIntent.GREETING
                if _is_greeting(normalized)
                else PorterCallerIntent.ANSWER
            ),
            stage=PorterColdCallStage.IDENTITY_CONFIRMATION,
            awaiting="identity_confirmation",
            last_agent_act="identity_confirmation_question",
        )

    if stage == PorterColdCallStage.IDENTITY_CONFIRMATION:
        if _is_negative(normalized) or _identity_is_denied(normalized):
            return _decision(
                context,
                response=_company_confirmation_prompt(context),
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.COMPANY_CONFIRMATION,
                awaiting="company_confirmation",
                last_agent_act="company_confirmation_question",
            )
        if _identity_is_confirmed(context, normalized):
            return _decision(
                context,
                response=COLD_CALL_PERMISSION,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.OPENING,
                awaiting="permission",
                last_agent_act="permission_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.COMPANY_CONFIRMATION:
        if _is_negative(normalized) or _company_is_denied(normalized):
            return _decision(
                context,
                response=WRONG_NUMBER_CLOSE,
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                should_close=True,
            )
        if _is_affirmative(normalized) or _company_is_confirmed(context, normalized):
            return _decision(
                context,
                response=SAME_COMPANY_ROLE_QUESTION,
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.SAME_COMPANY_ROLE_CHECK,
                awaiting="financing_role",
                last_agent_act="same_company_role_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.SAME_COMPANY_ROLE_CHECK:
        if _is_affirmative(normalized) or _contains_any(
            normalized, ("i handle", "i am involved", "i'm involved", "i do", "that s me", "thats me")
        ):
            return _decision(
                context,
                response=ALTERNATE_CONTACT_NAME_QUESTION,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.ALTERNATE_CONTACT_NAME,
                awaiting="alternate_contact_name",
                last_agent_act="alternate_contact_name_question",
            )
        if _is_negative(normalized) or _contains_any(
            normalized, ("someone else", "not me", "owner", "my boss")
        ):
            return _decision(
                context,
                response=CONTACT_REFERRAL_QUESTION,
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.CONTACT_REFERRAL,
                awaiting="contact_referral",
                last_agent_act="contact_referral_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.ALTERNATE_CONTACT_NAME:
        if not _is_usable_free_text_answer(normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=COLD_CALL_PERMISSION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.OPENING,
            awaiting="permission",
            last_agent_act="permission_question",
            updates={"alternate_contact_name": original},
        )

    if stage == PorterColdCallStage.OPENING:
        if _is_greeting(normalized):
            return _decision(
                context,
                response=OPENING_GREETING_RESPONSE,
                intent=PorterCallerIntent.GREETING,
                stage=PorterColdCallStage.OPENING,
                last_agent_act="permission_question",
            )
        if _accepts_permission(normalized):
            return _decision(
                context,
                response=(
                    "Of course — I'll keep it brief. Porter helps businesses get cash from "
                    "invoices faster... simple as that. Does that sound relevant?"
                    if _has_limited_time(normalized)
                    else PITCH
                ),
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.PITCH,
                awaiting="pitch_check_in",
                last_agent_act="pitch",
            )
        if _is_negative(normalized):
            return _not_interested_decision(context)
        if context.unclear_turn_count > 0:
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=OPENING_CLARIFICATION,
            intent=PorterCallerIntent.UNCLEAR,
            stage=PorterColdCallStage.OPENING,
            last_agent_act="opening_clarification",
            unclear_turn_count=context.unclear_turn_count + 1,
        )

    if stage == PorterColdCallStage.PITCH:
        if _is_negative(normalized):
            return _not_interested_decision(context)
        factor_answer = _factor_status(normalized)
        if factor_answer is True and _mentions_factoring(normalized):
            return _decision(
                context,
                response=EXISTING_FACTOR_COMPARISON,
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
                updates={"current_financing_solution": original, "current_funding_method": "factor"},
            )
        funding_method = _current_funding_method(normalized)
        if funding_method is not None and funding_method not in {"factor", "other"}:
            return _decision(
                context,
                response=PORTER_OPTION,
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
                updates={"current_financing_solution": original, "current_funding_method": funding_method},
            )
        if _accepts_permission(normalized):
            return _decision(
                context,
                response=ADVISOR_OFFER,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
            )
        if _requests_short_version(normalized):
            return _decision(
                context,
                response=(
                    "Sure — we help businesses get cash from invoices faster... simple as "
                    "that. Does that sound relevant?"
                ),
                intent=PorterCallerIntent.MORE_INFORMATION,
                stage=PorterColdCallStage.PITCH,
                awaiting="pitch_check_in",
                last_agent_act="compact_pitch",
            )
        if context.unclear_turn_count == 0:
            return _decision(
                context,
                response=(
                    "I mean, we help businesses get working capital against unpaid "
                    "invoices. Does that sound relevant at all?"
                ),
                intent=PorterCallerIntent.UNCLEAR,
                stage=PorterColdCallStage.PITCH,
                awaiting="pitch_check_in",
                last_agent_act="pitch_clarification",
                unclear_turn_count=1,
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.RELEVANCE:
        if _payment_gap_status(normalized) is False:
            return _decision(
                context,
                response=(
                    "Understood. It sounds like customer-payment timing isn't "
                    "creating a need right now. Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="no_current_need_close",
                updates={"payment_timing": original, "next_action": "not_interested"},
                should_close=True,
            )
        if _is_negative(normalized):
            return _decision(
                context,
                response=(
                    "Understood. It sounds like there isn't a current need. "
                    "Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="no_current_need_close",
                updates={"invoice_funding_need": "no"},
                should_close=True,
            )
        customer_type = _customer_type(normalized)
        if customer_type is None:
            return _repeat_pending_question(context)
        if customer_type == "consumer":
            return _decision(
                context,
                response=(
                    "Thanks for explaining that. Porter focuses on invoices to "
                    "businesses or government customers, so this doesn't sound like "
                    "the right fit today."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="not_qualified_close",
                updates={"customer_type": customer_type, "next_action": "disqualified"},
                should_close=True,
            )
        return _decision(
            context,
            response=pending_question(PorterColdCallStage.CURRENT_FUNDING.value),
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.EXISTING_FACTOR,
            awaiting="current_financing_solution",
            last_agent_act="existing_factor_question",
            updates={
                "customer_type": customer_type,
            },
        )

    if stage == PorterColdCallStage.PAYMENT_TIMING:
        gap = _payment_gap_status(normalized)
        if gap is None:
            return _repeat_pending_question(context)
        if gap is False:
            return _decision(
                context,
                response=(
                    "Understood. It sounds like customer-payment timing isn't "
                    "creating a need right now. Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="no_current_need_close",
                updates={"payment_timing": original},
                should_close=True,
            )
        plan = spoken_question(
            pending_question(PorterColdCallStage.OPERATIONAL_IMPACT.value),
            kind=PorterAcknowledgement.NEUTRAL,
            previous=context.last_acknowledgement,
            turn_index=context.delivery_turn_count,
        )
        return _decision(
            context,
            response=plan.text,
            acknowledgement=plan.acknowledgement,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.OPERATIONAL_IMPACT,
            awaiting="operational_impact",
            last_agent_act="operational_impact_question",
            updates={"payment_timing": original},
        )

    if stage == PorterColdCallStage.OPERATIONAL_IMPACT:
        impact = _operational_impact_status(normalized)
        if impact is None:
            return _repeat_pending_question(context)
        if impact is False:
            return _decision(
                context,
                response=(
                    "Understood. It sounds like the wait isn't creating an "
                    "operational need right now. Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="no_current_need_close",
                updates={"operational_impact": original},
                should_close=True,
            )
        impact_text = (
            original
            if _is_usable_free_text_answer(normalized)
            else "Customer-payment timing creates pressure on operating costs."
        )
        updates = {
            "operational_impact": impact_text,
            "cash_flow_challenge": impact_text,
            "invoice_funding_need": "yes",
        }
        if context.captured_fields.get("current_financing_solution"):
            fields = {**context.captured_fields, **updates}
            return _decision(
                context,
                response=tailored_handoff(fields),
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
                updates=updates,
            )
        plan = spoken_question(
            pending_question(PorterColdCallStage.CURRENT_FUNDING.value),
            kind=PorterAcknowledgement.NEUTRAL,
            previous=context.last_acknowledgement,
            turn_index=context.delivery_turn_count,
        )
        return _decision(
            context,
            response=plan.text,
            acknowledgement=plan.acknowledgement,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.CURRENT_FUNDING,
            awaiting="current_financing_solution",
            last_agent_act="current_funding_question",
            updates=updates,
        )

    if stage == PorterColdCallStage.CURRENT_FUNDING:
        if _payment_gap_status(normalized) is False:
            return _decision(
                context,
                response=(
                    "Understood. It sounds like customer-payment timing isn't "
                    "creating a need right now. Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="no_current_need_close",
                updates={"payment_timing": original, "next_action": "not_interested"},
                should_close=True,
            )
        method = _current_funding_method(normalized)
        if method is None:
            return _repeat_pending_question(context)
        updates = {
            "current_financing_solution": original,
            "current_funding_method": method,
        }
        return _decision(
            context,
            response=PORTER_OPTION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.ADVISOR_OFFER,
            awaiting="advisor_offer",
            last_agent_act="advisor_offer_question",
            updates=updates,
        )

    if stage == PorterColdCallStage.PROVIDER_LIMITATION:
        funding_method = context.captured_fields.get("current_funding_method")
        if _is_satisfied_answer(normalized, funding_method):
            return _decision(
                context,
                response=(
                    "Understood. It sounds like the current approach is covering "
                    "the need. Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="existing_solution_satisfied_close",
                updates={"provider_limitation": "none"},
                should_close=True,
            )
        if not _is_usable_free_text_answer(normalized) and not _is_negative(normalized):
            return _repeat_pending_question(context)
        limitation = (
            original
            if _is_usable_free_text_answer(normalized)
            else "The current approach does not fully cover the timing gap."
        )
        fields = {**context.captured_fields, "provider_limitation": limitation}
        return _decision(
            context,
            response=tailored_handoff(fields),
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.ADVISOR_OFFER,
            awaiting="advisor_offer",
            last_agent_act="advisor_offer_question",
            updates={"provider_limitation": limitation},
        )

    if stage == PorterColdCallStage.NEED_TIMING:
        timing = _need_timing(normalized)
        if timing is None:
            return _repeat_pending_question(context)
        if timing == "none":
            return _decision(
                context,
                response=(
                    "Understood. It sounds like this isn't something you need right "
                    "now. Thanks for taking the call."
                ),
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="no_current_need_close",
                updates={"need_timing": timing},
                should_close=True,
            )
        if timing == "later":
            return _decision(
                context,
                response=CALLBACK_TIME_QUESTION,
                intent=PorterCallerIntent.CALLBACK,
                stage=PorterColdCallStage.CALLBACK_DETAILS,
                awaiting="callback_request",
                last_agent_act="callback_time_question",
                updates={"need_timing": timing},
            )
        return _decision(
            context,
            response=pending_question(PorterColdCallStage.DECISION_AUTHORITY.value),
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.DECISION_AUTHORITY,
            awaiting="decision_authority",
            last_agent_act="decision_authority_question",
            updates={"need_timing": timing},
        )

    if stage == PorterColdCallStage.DECISION_AUTHORITY:
        if _is_affirmative(normalized) or _contains_any(
            normalized, ("i am", "i would", "i handle", "part of", "involved")
        ):
            fields = {**context.captured_fields, "decision_authority": original}
            return _decision(
                context,
                response=problem_summary(fields),
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.PROBLEM_CONFIRMATION,
                awaiting="problem_confirmation",
                last_agent_act="problem_confirmation_question",
                updates={"decision_authority": original},
            )
        if _is_negative(normalized) or _contains_any(
            normalized, ("not me", "someone else", "my boss", "owner")
        ):
            return _decision(
                context,
                response=CONTACT_REFERRAL_QUESTION,
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.CONTACT_REFERRAL,
                awaiting="contact_referral",
                last_agent_act="contact_referral_question",
                updates={"decision_authority": original},
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.PROBLEM_CONFIRMATION:
        if _is_affirmative(normalized):
            return _decision(
                context,
                response=tailored_handoff(context.captured_fields),
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
                updates={"problem_confirmed": "yes"},
            )
        if _is_negative(normalized):
            plan = spoken_question(
                "Which part did I get wrong?",
                kind=PorterAcknowledgement.CORRECTION,
                previous=context.last_acknowledgement,
                turn_index=context.delivery_turn_count,
            )
            return _decision(
                context,
                response=plan.text,
                acknowledgement=plan.acknowledgement,
                intent=PorterCallerIntent.CORRECTION,
                last_agent_act="problem_correction_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.INDUSTRY:
        if not _is_usable_industry_answer(normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=QUALIFIER_OPENING,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.EXISTING_FACTOR,
            awaiting="current_financing_solution",
            last_agent_act="existing_factor_question",
            updates={"industry": original},
        )

    if stage == PorterColdCallStage.EXISTING_FACTOR:
        factor_answer = _factor_status(normalized)
        if factor_answer is True:
            return _decision(
                context,
                response=EXISTING_FACTOR_COMPARISON,
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
                updates={
                    "current_financing_solution": original,
                    "current_funding_method": "factor",
                },
            )
        if factor_answer is False:
            return _decision(
                context,
                response=pending_question("funding_method"),
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.CURRENT_FUNDING,
                awaiting="current_financing_solution",
                last_agent_act="current_funding_question",
                updates={"current_financing_solution": original},
            )
        if _is_likely_industry_correction(normalized):
            return _decision(
                context,
                response=QUALIFIER_FOLLOW_UP.format(
                    natural_reaction=_natural_industry_reaction(original)
                ),
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.EXISTING_FACTOR,
                awaiting="current_financing_solution",
                last_agent_act="existing_factor_question",
                updates={"industry": original},
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.FACTOR_SATISFACTION:
        if _is_affirmative(normalized) or "happy" in normalized:
            return _decision(
                context,
                response=HAPPY_FACTOR_EXPLORE,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.FACTOR_EXPLORATION,
                awaiting="factor_exploration",
                last_agent_act="factor_exploration_question",
                updates={"factor_satisfaction": original},
            )
        if _is_negative(normalized) or _contains_any(normalized, ("unhappy", "could be better", "not really")):
            return _decision(
                context,
                response=CURRENT_FACTOR_CHALLENGE_QUESTION,
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.PROVIDER_LIMITATION,
                awaiting="provider_limitation",
                last_agent_act="provider_limitation_question",
                updates={"factor_satisfaction": original},
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.FACTOR_EXPLORATION:
        if _accepts_exploration(normalized):
            return _decision(
                context,
                response=BOOKING,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.BOOKING,
                awaiting="phone",
                last_agent_act="booking_question",
                updates={"factor_exploration": original},
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.CASH_FLOW_CHALLENGE:
        if not _is_usable_free_text_answer(normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=pending_question(PorterColdCallStage.CURRENT_FUNDING.value),
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.CURRENT_FUNDING,
            awaiting="current_financing_solution",
            last_agent_act="current_funding_question",
            updates={
                "operational_impact": original,
                "cash_flow_challenge": original,
            },
        )

    if stage == PorterColdCallStage.MONTHLY_INVOICING_VOLUME:
        pending_amount = context.captured_fields.get("_monthly_volume_amount")
        if pending_amount and normalized in {"dollars", "thousand", "thousands", "million", "millions"}:
            return _decision(
                context,
                response=ADVISOR_OFFER,
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.ADVISOR_OFFER,
                awaiting="advisor_offer",
                last_agent_act="advisor_offer_question",
                updates={"monthly_invoicing_volume": f"{pending_amount} {original}"},
            )
        if _monthly_volume_needs_unit(original, normalized):
            return _decision(
                context,
                response=MONTHLY_VOLUME_UNIT_CLARIFICATION,
                intent=PorterCallerIntent.UNCLEAR,
                last_agent_act="monthly_invoicing_question",
                updates={"_monthly_volume_amount": original},
                unclear_turn_count=context.unclear_turn_count + 1,
            )
        if _is_partial_monthly_volume(normalized):
            return _decision(
                context,
                response=PARTIAL_AMOUNT_CLARIFICATION,
                intent=PorterCallerIntent.UNCLEAR,
                last_agent_act="monthly_invoicing_question",
                unclear_turn_count=context.unclear_turn_count + 1,
            )
        if not _is_usable_monthly_volume(original, normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=problem_summary(
                {**context.captured_fields, "monthly_invoicing_volume": original}
            ),
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.PROBLEM_CONFIRMATION,
            awaiting="problem_confirmation",
            last_agent_act="problem_confirmation_question",
            updates={"monthly_invoicing_volume": original},
        )

    if stage == PorterColdCallStage.ADVISOR_OFFER:
        if _is_affirmative(normalized) or _contains_any(
            normalized, ("connect me", "talk to", "speak with", "set it up")
        ):
            return _decision(
                context,
                response=BOOKING,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.BOOKING,
                awaiting="phone",
                last_agent_act="booking_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.BOOKING:
        if _is_negative(normalized) or _contains_any(
            normalized,
            ("can t book", "cant book", "cannot book", "don t book", "dont book"),
        ):
            return _warm_close_decision(context, original=original)
        updates: dict[str, str] = {}
        has_phone = bool(context.captured_fields.get("phone")) or _has_phone_details(original, normalized)
        has_email = bool(context.captured_fields.get("email")) or _has_email_details(original, normalized)
        if _has_phone_details(original, normalized):
            updates["phone"] = original
        if _has_email_details(original, normalized):
            updates["email"] = original
        if not has_phone and not has_email:
            return _decision(
                context,
                response=PHONE_QUESTION,
                intent=PorterCallerIntent.UNCLEAR,
                stage=PorterColdCallStage.BOOKING,
                awaiting="phone",
                last_agent_act="phone_question",
                updates=updates,
                unclear_turn_count=context.unclear_turn_count + 1,
            )
        return _decision(
            context,
            response=CALLBACK_TODAY_QUESTION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.CALLBACK_TODAY,
            awaiting="callback_day",
            last_agent_act="callback_today_question",
            updates=updates,
        )

    if stage == PorterColdCallStage.CALLBACK_TODAY:
        if _is_final_questions_decline(normalized):
            return _warm_close_decision(context, original=original)
        if _has_callback_details(normalized):
            return _decision(
                context,
                response=CALLBACK_CONFIRMATION,
                intent=PorterCallerIntent.CALLBACK,
                stage=PorterColdCallStage.CALLBACK_CONFIRMATION,
                awaiting="callback_confirmation",
                last_agent_act="callback_confirmation_question",
                updates={"callback_request": original},
            )
        if _is_affirmative(normalized) or "today" in normalized:
            return _decision(
                context,
                response=CALLBACK_TODAY_TIME_QUESTION,
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.CALLBACK_DETAILS,
                awaiting="callback_request",
                last_agent_act="callback_time_question",
                updates={"callback_day": "today"},
            )
        if _is_negative(normalized) or _contains_any(normalized, ("another day", "tomorrow", "next week")):
            return _decision(
                context,
                response=CALLBACK_TIME_QUESTION,
                intent=PorterCallerIntent.CALLBACK,
                stage=PorterColdCallStage.CALLBACK_DETAILS,
                awaiting="callback_request",
                last_agent_act="callback_time_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.FINAL_QUESTIONS:
        if _is_final_questions_decline(normalized):
            return _warm_close_decision(context, original=original)
        if _contains_any(normalized, ("yes", "yeah", "i have a question", "one question")):
            return _decision(
                context,
                response="Sure — what would you like to know?",
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.FINAL_QUESTIONS,
                awaiting="final_questions",
                last_agent_act="final_questions_prompt",
            )
        return _decision(
            context,
            response="No problem. Is there anything else you'd like to know before I let you go?",
            intent=PorterCallerIntent.UNCLEAR,
            stage=PorterColdCallStage.FINAL_QUESTIONS,
            awaiting="final_questions",
            last_agent_act="final_questions_prompt",
            unclear_turn_count=context.unclear_turn_count + 1,
        )

    if stage == PorterColdCallStage.CONTACT_EMAIL:
        if not _has_email_details(original, normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=CONTACT_NAME_QUESTION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.CONTACT_NAME,
            awaiting="full_name",
            last_agent_act="contact_name_question",
            updates={"email": original},
        )

    if stage == PorterColdCallStage.CONTACT_NAME:
        if not _has_full_name(normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=COMPANY_NAME_QUESTION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.CONTACT_COMPANY,
            awaiting="company_name",
            last_agent_act="company_name_question",
            updates={"full_name": original},
        )

    if stage == PorterColdCallStage.CONTACT_COMPANY:
        if not _is_usable_industry_answer(normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=BOOKING_CONFIRMATION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            updates={"company_name": original},
            should_close=True,
        )

    if stage == PorterColdCallStage.CALLBACK_DETAILS:
        callback_text = original
        if context.captured_fields.get("callback_day") == "today" and _has_time_only(normalized):
            callback_text = f"today at {original}"
        if not _has_callback_details(_normalize(callback_text)):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=CALLBACK_CONFIRMATION,
            intent=PorterCallerIntent.CALLBACK,
            stage=PorterColdCallStage.CALLBACK_CONFIRMATION,
            awaiting="callback_confirmation",
            last_agent_act="callback_confirmation_question",
            updates={"callback_request": callback_text},
        )

    if stage == PorterColdCallStage.CALLBACK_CONFIRMATION:
        if _is_affirmative(normalized):
            return _decision(
                context,
                response=FINAL_QUESTIONS_PROMPT,
                intent=PorterCallerIntent.AFFIRMATIVE,
                stage=PorterColdCallStage.FINAL_QUESTIONS,
                awaiting="final_questions",
                last_agent_act="final_questions_prompt",
            )
        if _is_negative(normalized) or _contains_any(normalized, ("change", "actually", "instead")):
            return _decision(
                context,
                response=CALLBACK_TIME_QUESTION,
                intent=PorterCallerIntent.CORRECTION,
                stage=PorterColdCallStage.CALLBACK_DETAILS,
                awaiting="callback_request",
                last_agent_act="callback_time_question",
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.CONTACT_REFERRAL:
        if _company_is_denied(normalized):
            return _decision(
                context,
                response=WRONG_NUMBER_CLOSE,
                intent=PorterCallerIntent.WRONG_PERSON,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                should_close=True,
            )
        if _is_negative(normalized) or _contains_any(
            normalized, ("don t know", "dont know", "not sure")
        ):
            return _decision(
                context,
                response="Got it — thanks for your time. Have a good one.",
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                should_close=True,
            )
        if not _is_usable_free_text_answer(normalized):
            return _repeat_pending_question(context)
        return _decision(
            context,
            response=REFERRAL_CONTACT_DETAILS_QUESTION,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.REFERRAL_CONTACT_DETAILS,
            awaiting="contact_referral_details",
            last_agent_act="contact_referral_details_question",
            updates={"contact_referral": original},
        )

    if stage == PorterColdCallStage.REFERRAL_CONTACT_DETAILS:
        if _has_phone_details(original, normalized) or _has_email_details(original, normalized):
            return _decision(
                context,
                response="Thanks for pointing me in the right direction. Have a good one.",
                intent=PorterCallerIntent.ANSWER,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                updates={"contact_referral_details": original},
                should_close=True,
            )
        if _is_negative(normalized) or _contains_any(normalized, ("don t have", "dont have", "not sure")):
            return _decision(
                context,
                response="No problem. Thanks for your time. Have a good one.",
                intent=PorterCallerIntent.NEGATIVE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                should_close=True,
            )
        return _repeat_pending_question(context)

    if stage == PorterColdCallStage.NOT_INTERESTED_REASON:
        return _decision(
            context,
            response=NOT_INTERESTED_CLOSE,
            intent=PorterCallerIntent.ANSWER,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            updates={"not_interested_reason": original},
            should_close=True,
        )

    return _decision(
        context,
        response=EXIT,
        intent=PorterCallerIntent.UNCLEAR,
        stage=PorterColdCallStage.COMPLETE,
        last_agent_act="close",
        should_close=True,
    )


def _repeat_pending_question(
    context: PorterColdCallContext,
    *,
    intent: PorterCallerIntent = PorterCallerIntent.UNCLEAR,
) -> PorterColdCallDecision:
    next_unclear_count = context.unclear_turn_count + 1
    if context.stage == PorterColdCallStage.CONNECTION_CHECK:
        if next_unclear_count >= 3:
            return _decision(
                context,
                response=NO_RESPONSE_CLOSE,
                intent=intent,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                unclear_turn_count=next_unclear_count,
                should_close=True,
            )
        return _decision(
            context,
            response=SECOND_HELLO if next_unclear_count == 1 else THIRD_HELLO,
            intent=intent,
            last_agent_act="connection_check",
            unclear_turn_count=next_unclear_count,
        )

    if next_unclear_count >= 3 and context.stage in {
        PorterColdCallStage.IDENTITY_CONFIRMATION,
        PorterColdCallStage.COMPANY_CONFIRMATION,
        PorterColdCallStage.OPENING,
        PorterColdCallStage.PITCH,
        PorterColdCallStage.ADVISOR_OFFER,
        PorterColdCallStage.BOOKING,
        PorterColdCallStage.CONTACT_EMAIL,
        PorterColdCallStage.CONTACT_NAME,
        PorterColdCallStage.CONTACT_COMPANY,
        PorterColdCallStage.CALLBACK_DETAILS,
        PorterColdCallStage.CALLBACK_TODAY,
        PorterColdCallStage.CALLBACK_CONFIRMATION,
        PorterColdCallStage.CONTACT_REFERRAL,
        PorterColdCallStage.SAME_COMPANY_ROLE_CHECK,
        PorterColdCallStage.ALTERNATE_CONTACT_NAME,
        PorterColdCallStage.REFERRAL_CONTACT_DETAILS,
        PorterColdCallStage.NOT_INTERESTED_REASON,
    }:
        return _decision(
            context,
            response=CONNECTION_CLOSE,
            intent=intent,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            unclear_turn_count=next_unclear_count,
            should_close=True,
        )
    if next_unclear_count >= 3:
        return _decision(
            context,
            response=(
                "No problem. We can leave that unknown. Would you like to speak "
                "with a Porter funding specialist?"
            ),
            intent=intent,
            stage=PorterColdCallStage.ADVISOR_OFFER,
            awaiting="advisor_offer",
            last_agent_act="advisor_offer_question",
            unclear_turn_count=next_unclear_count,
        )
    response = _pending_question(context, attempt=next_unclear_count)
    return _decision(
        context,
        response=response,
        intent=intent,
        last_agent_act="rephrased_question",
        unclear_turn_count=next_unclear_count,
    )


def _silence_decision(context: PorterColdCallContext) -> PorterColdCallDecision:
    next_silence_count = context.silence_turn_count + 1
    if context.stage == PorterColdCallStage.CONNECTION_CHECK:
        if next_silence_count >= 3:
            return _decision(
                context,
                response=NO_RESPONSE_CLOSE,
                intent=PorterCallerIntent.SILENCE,
                stage=PorterColdCallStage.COMPLETE,
                last_agent_act="close",
                silence_turn_count=next_silence_count,
                should_close=True,
            )
        return _decision(
            context,
            response=SECOND_HELLO if next_silence_count == 1 else THIRD_HELLO,
            intent=PorterCallerIntent.SILENCE,
            last_agent_act="connection_check",
            silence_turn_count=next_silence_count,
        )
    if next_silence_count == 1:
        return _decision(
            context,
            response="Take your time.",
            intent=PorterCallerIntent.SILENCE,
            last_agent_act="silence_wait",
            silence_turn_count=next_silence_count,
        )
    if next_silence_count == 2:
        return _decision(
            context,
            response=_pending_question(context, attempt=1),
            intent=PorterCallerIntent.SILENCE,
            last_agent_act="silence_rephrase",
            silence_turn_count=next_silence_count,
        )
    if context.stage in {
        PorterColdCallStage.OPENING,
        PorterColdCallStage.IDENTITY_CONFIRMATION,
        PorterColdCallStage.COMPANY_CONFIRMATION,
    }:
        return _decision(
            context,
            response=NO_RESPONSE_CLOSE,
            intent=PorterCallerIntent.SILENCE,
            stage=PorterColdCallStage.COMPLETE,
            last_agent_act="close",
            silence_turn_count=next_silence_count,
            should_close=True,
        )
    return _decision(
        context,
        response=(
            "No problem. We can leave that unknown. Would you like to speak with "
            "a Porter funding specialist?"
        ),
        intent=PorterCallerIntent.SILENCE,
        stage=PorterColdCallStage.ADVISOR_OFFER,
        awaiting="advisor_offer",
        last_agent_act="advisor_offer_question",
        silence_turn_count=next_silence_count,
    )


def _not_interested_decision(
    context: PorterColdCallContext,
) -> PorterColdCallDecision:
    return _decision(
        context,
        response=NOT_INTERESTED,
        intent=PorterCallerIntent.NOT_INTERESTED,
        stage=PorterColdCallStage.NOT_INTERESTED_REASON,
        awaiting="not_interested_reason",
        last_agent_act="not_interested_reason_question",
        updates={"next_action": "not_interested"},
    )


def _no_business_decision(
    context: PorterColdCallContext,
    normalized: str,
) -> PorterColdCallDecision | None:
    has_no_business = _contains_any(
        normalized,
        (
            "no business",
            "not a business owner",
            "i don t have a business",
            "i do not have a business",
            "we don t have a business",
            "we do not have a business",
            "i don t own a business",
            "i do not own a business",
        ),
    ) or (
        "business" in normalized.split()
        and _contains_any(
            normalized,
            (
                "i don t have any kind",
                "i do not have any kind",
                "we don t have any kind",
                "we do not have any kind",
            ),
        )
    )
    if not has_no_business:
        return None
    return _decision(
        context,
        response="Got it — then this isn't relevant right now. Thanks for letting me know. Take care.",
        intent=PorterCallerIntent.NEGATIVE,
        stage=PorterColdCallStage.COMPLETE,
        last_agent_act="no_business_close",
        updates={"business_status": "no_business", "next_action": "not_interested"},
        should_close=True,
    )


def _warm_close_decision(
    context: PorterColdCallContext,
    *,
    original: str,
) -> PorterColdCallDecision:
    return _decision(
        context,
        response=WARM_CLOSE,
        intent=PorterCallerIntent.NEGATIVE,
        stage=PorterColdCallStage.COMPLETE,
        last_agent_act="close",
        updates=(
            {} if context.stage == PorterColdCallStage.FINAL_QUESTIONS
            else {"factor_exploration": original}
        ),
        should_close=True,
    )


def _correction_decision(
    context: PorterColdCallContext,
    original: str,
    normalized: str,
) -> PorterColdCallDecision | None:
    if "?" in original:
        return None
    if not normalized.startswith((
        "actually",
        "correction",
        "i said",
        "that should be",
        "no my",
    )):
        return None

    field: str | None = None
    value = original.strip().rstrip(".!?")
    if _has_email_details(original, normalized):
        field = "email"
    elif _has_phone_details(original, normalized):
        field = "phone"
    elif _contains_any(normalized, ("my name", "name is")):
        field = "full_name"
    elif _contains_any(normalized, ("company is", "company name")):
        field = "company_name"
    elif _contains_any(normalized, ("industry", "trucking", "parking", "staffing", "manufacturing")):
        field = "industry"
    elif _has_callback_details(normalized):
        field = "best_callback_time"
    elif _mentions_financial_pressure(normalized):
        field = "operational_impact"
    elif _payment_gap_status(normalized) is not None:
        field = "payment_timing"
    elif _current_funding_method(normalized) is not None:
        field = "current_financing_solution"

    if field is None or field == context.awaiting_field:
        return None
    value = _clean_correction_value(value)
    updates = {field: value}
    if context.stage == PorterColdCallStage.PROBLEM_CONFIRMATION:
        return _decision(
            context,
            response=problem_summary({**context.captured_fields, **updates}),
            intent=PorterCallerIntent.CORRECTION,
            stage=context.stage,
            awaiting=context.awaiting_field,
            last_agent_act="problem_summary_corrected",
            updates=updates,
        )
    return _decision(
        context,
        response=(
            "Got it — I've updated that. "
            f"{_concise_pending_question(context.stage)}"
        ),
        intent=PorterCallerIntent.CORRECTION,
        stage=context.stage,
        awaiting=context.awaiting_field,
        last_agent_act="correction_acknowledged",
        updates=updates,
    )


def _clean_correction_value(value: str) -> str:
    cleaned = value.strip()
    lowered = cleaned.lower()
    for prefix in (
        "actually, my email is ",
        "actually my email is ",
        "actually, my name is ",
        "actually my name is ",
        "actually, our company is ",
        "actually our company is ",
        "actually, the company is ",
        "actually the company is ",
        "actually, it's ",
        "actually it's ",
        "actually, it is ",
        "actually it is ",
        "actually, ",
        "actually ",
        "correction, ",
        "correction ",
        "no, my ",
        "no my ",
    ):
        if lowered.startswith(prefix):
            return cleaned[len(prefix) :].strip()
    return cleaned


def _concise_pending_question(stage: PorterColdCallStage) -> str:
    return pending_question(_delivery_stage_name(stage))


def _pending_question(context: PorterColdCallContext, *, attempt: int = 0) -> str:
    return pending_question(
        _delivery_stage_name(context.stage),
        attempt=attempt,
        lead_name=context.lead_name,
        lead_company=context.lead_company,
    )


def _delivery_stage_name(stage: PorterColdCallStage) -> str:
    aliases = {
        PorterColdCallStage.PITCH: "pitch_check_in",
        PorterColdCallStage.INDUSTRY: "industry",
        PorterColdCallStage.EXISTING_FACTOR: "current_funding",
        PorterColdCallStage.CASH_FLOW_CHALLENGE: "operational_impact",
        PorterColdCallStage.MONTHLY_INVOICING_VOLUME: "monthly_invoicing_volume",
        PorterColdCallStage.CONTACT_EMAIL: "email",
        PorterColdCallStage.CONTACT_NAME: "full_name",
        PorterColdCallStage.CONTACT_COMPANY: "company_name",
        PorterColdCallStage.CALLBACK_DETAILS: "callback",
        PorterColdCallStage.CALLBACK_TODAY: "callback_today",
        PorterColdCallStage.CALLBACK_CONFIRMATION: "callback_confirmation",
        PorterColdCallStage.CONTACT_REFERRAL: "contact_referral",
        PorterColdCallStage.SAME_COMPANY_ROLE_CHECK: "same_company_role_check",
        PorterColdCallStage.ALTERNATE_CONTACT_NAME: "alternate_contact_name",
        PorterColdCallStage.REFERRAL_CONTACT_DETAILS: "referral_contact_details",
    }
    return aliases.get(stage, stage.value)


def _knowledge_answer_with_bridge(
    context: PorterColdCallContext,
    answer: str,
) -> str:
    if context.stage in {
        PorterColdCallStage.COMPLETE,
        PorterColdCallStage.BOOKING,
        PorterColdCallStage.FINAL_QUESTIONS,
    } or "?" in answer:
        return answer
    bridge = _pending_question(context)
    return f"{answer} {bridge}"


def _identity_confirmation_prompt(context: PorterColdCallContext) -> str:
    if context.lead_name and context.lead_company:
        return f"Hey — is this {context.lead_name} with {context.lead_company}?"
    if context.lead_name:
        return f"Hey — is this {context.lead_name}?"
    if context.lead_company:
        return f"Hey — am I speaking with someone at {context.lead_company}?"
    return "Hey — am I speaking with the person who handles financing there?"


def _identity_retry_prompt(context: PorterColdCallContext) -> str:
    if context.lead_name:
        return f"Sorry — I just need to confirm... is this {context.lead_name}?"
    return "Sorry — I just need to confirm... am I speaking with the right person?"


def _company_confirmation_prompt(context: PorterColdCallContext) -> str:
    if context.lead_company:
        return f"Got it — did I at least reach {context.lead_company}?"
    return "Got it — did I reach the right company?"


def _identity_is_confirmed(
    context: PorterColdCallContext,
    normalized: str,
) -> bool:
    if (
        _is_affirmative(normalized)
        or normalized == "speaking"
        or normalized.startswith("speaking ")
        or normalized.startswith("this is ")
        or normalized in {"s", "sis", "that s me", "that is me"}
    ):
        return True
    if not context.lead_name:
        return False
    normalized_name = _normalize(context.lead_name)
    first_name = normalized_name.split()[0] if normalized_name else ""
    return bool(first_name and first_name in normalized.split())


def _identity_is_denied(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "this isn t",
            "this is not",
            "not speaking",
            "not me",
            "you have the wrong person",
        ),
    )


def _company_is_denied(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "not from",
            "wrong company",
            "never heard of",
            "isn t this company",
            "is not this company",
        ),
    )


def _company_is_confirmed(
    context: PorterColdCallContext,
    normalized: str,
) -> bool:
    if not context.lead_company:
        return False
    company_words = {
        word
        for word in _normalize(context.lead_company).split()
        if len(word) > 3 and word not in {"group", "company"}
    }
    return bool(company_words & set(normalized.split())) and not _company_is_denied(
        normalized
    )


def _decision(
    context: PorterColdCallContext,
    *,
    response: str,
    intent: PorterCallerIntent,
    stage: PorterColdCallStage | None = None,
    awaiting: str | None = None,
    last_agent_act: str,
    updates: Mapping[str, str] | None = None,
    unclear_turn_count: int = 0,
    silence_turn_count: int = 0,
    acknowledgement: str | None = None,
    should_close: bool = False,
) -> PorterColdCallDecision:
    next_stage = stage or context.stage
    next_awaiting = awaiting if stage is not None else context.awaiting_field
    return PorterColdCallDecision(
        response_text=response,
        intent=intent,
        next_stage=next_stage,
        awaiting_field=next_awaiting,
        last_agent_act=last_agent_act,
        captured_updates=dict(updates or {}),
        unclear_turn_count=unclear_turn_count,
        silence_turn_count=silence_turn_count,
        acknowledgement=acknowledgement,
        should_close=should_close,
    )


def _is_voicemail(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "leave a message",
            "after the tone",
            "after the beep",
            "you have reached",
            "not available to take your call",
            "mailbox is full",
        ),
    )


def _is_wrong_person(normalized: str) -> bool:
    return _contains_any(
        normalized,
        ("wrong person", "doesn t work here", "does not work here"),
    )


def _is_wrong_number(normalized: str) -> bool:
    return _contains_any(normalized, ("wrong number", "don t call this number"))


def _is_gatekeeper(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "how can i direct your call",
            "who are you trying to reach",
            "which department are you calling",
            "i can transfer you",
        ),
    )


def _asks_call_purpose(normalized: str, tokens: set[str]) -> bool:
    return _contains_any(
        normalized,
        (
            "why are you calling",
            "why did you call",
            "what is this about",
            "what s this about",
            "what is this regarding",
            "what s this regarding",
            "what are you calling about",
            "reason for the call",
        ),
    ) or bool(tokens & {"call", "calling"}) and bool(
        tokens & {"about", "for", "reason", "why"}
    )


def _asks_porter_explanation(normalized: str, tokens: set[str]) -> bool:
    return _contains_any(
        normalized,
        (
            "know more",
            "tell me more",
            "more about",
            "what do you do",
            "what do you guys do",
            "what is porter",
            "what are you talking about",
            "what do you mean",
            "provide cash for invoices",
            "provide cash against invoices",
        ),
    ) or (
        "explain" in tokens
        and (
            "what" in tokens
            or "mean" in tokens
            or {"you", "guys"}.issubset(tokens)
        )
    )


def _is_greeting(normalized: str) -> bool:
    return normalized in {"hello", "hi", "hey", "good morning", "good afternoon"}


def _callback_or_busy_intent(normalized: str) -> PorterCallerIntent | None:
    if _contains_any(
        normalized,
        (
            "i m busy",
            "im busy",
            "busy right now",
            "bad time",
            "not a good time",
            "in a meeting",
            "walking into a meeting",
        ),
    ):
        return PorterCallerIntent.BUSY
    if _contains_any(normalized, ("call me later", "call back", "call me back")):
        return PorterCallerIntent.CALLBACK
    return None


def _has_callback_details(normalized: str) -> bool:
    has_day = _contains_any(
        normalized,
        (
            "today",
            "tomorrow",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "next week",
        ),
    )
    has_time = _contains_any(
        normalized,
        ("morning", "afternoon", "evening", "noon", "midnight", "o clock", "oclock"),
    ) or bool(set(normalized.split()) & {"am", "pm"})
    return has_day and has_time


def _has_time_only(normalized: str) -> bool:
    return _contains_any(
        normalized,
        ("morning", "afternoon", "evening", "noon", "midnight", "o clock", "oclock"),
    ) or bool(set(normalized.split()) & {"am", "pm"})


def _has_phone_details(original: str, normalized: str) -> bool:
    digits = "".join(character for character in original if character.isdigit())
    return len(digits) >= 10 or _contains_any(
        normalized, ("this number", "same number", "number you called")
    )


def _has_email_details(original: str, normalized: str) -> bool:
    lowered = original.lower()
    return (
        ("@" in lowered and "." in lowered.split("@", 1)[-1])
        or (" at " in lowered and " dot " in lowered)
        or _contains_any(normalized, ("no email", "don t have email", "dont have email"))
    )


def _has_full_name(normalized: str) -> bool:
    return _is_usable_free_text_answer(normalized) and len(normalized.split()) >= 2


def _asks_about_funding_speed(normalized: str, tokens: set[str]) -> bool:
    return (
        _contains_any(normalized, ("how fast", "how soon", "how long", "how much time", "funding speed", "24", "48"))
        or bool(tokens & {"fund", "funding"})
        and bool(tokens & {"take", "time", "when", "long", "soon", "fast"})
    )


def _asks_what_factoring_is(normalized: str, tokens: set[str]) -> bool:
    if not bool(tokens & {"factor", "factoring"}):
        return False
    return _looks_like_question(normalized) or _contains_any(
        normalized,
        (
            "factoring mean",
            "explain factoring",
            "understand factoring",
            "not familiar with factoring",
        ),
    )


def _is_industry_eligibility_question(
    normalized: str,
    tokens: set[str],
) -> bool:
    if tokens & {"eligible", "eligibility", "qualify", "qualified"}:
        return True
    return bool(tokens & {"construction", "trucking"}) and _looks_like_question(
        normalized
    )


def _looks_like_question(normalized: str) -> bool:
    return normalized.startswith(
        (
            "what ",
            "how ",
            "why ",
            "who ",
            "can ",
            "do ",
            "does ",
            "is ",
            "are ",
            "and what ",
        )
    ) or _contains_any(
        normalized,
        (
            "could you explain",
            "can you explain",
            "would you explain",
            "what are you talking about",
            "what do you mean",
        ),
    )


def _factor_status(normalized: str) -> bool | None:
    if _is_negative(normalized):
        return False
    if _contains_any(
        normalized,
        (
            "no factor",
            "not factoring",
            "do not factor",
            "don t factor",
            "dont factor",
            "handle it ourselves",
            "different way",
            "none",
            "ourselves",
        ),
    ):
        return False
    if _contains_any(
        normalized,
        (
            "we factor",
            "we are factoring",
            "factor invoices",
            "factor our invoices",
            "doing invoice factoring",
            "doing the invoice factoring",
            "invoice factoring",
            "have a factor",
            "current factor",
            "already factor",
            "invoice factory",
            "invoice factories",
        ),
    ):
        return True
    if "factoring" in normalized.split() and _contains_any(
        normalized, ("we re doing", "we are doing", "doing what")
    ):
        return True
    factor_tokens = {"factor", "factoring", "factory", "factories"}
    if factor_tokens & set(normalized.split()) and not _looks_like_question(normalized):
        return True
    if _is_affirmative(normalized):
        return True
    return None


def _mentions_factoring(normalized: str) -> bool:
    return bool({"factor", "factoring", "factory", "factories"} & set(normalized.split()))


def _customer_type(normalized: str) -> str | None:
    if _is_affirmative(normalized):
        return "business"
    if _contains_any(
        normalized,
        (
            "consumers",
            "consumer customers",
            "individual customers",
            "general public",
            "patients",
        ),
    ):
        return "consumer"
    serves_businesses = _contains_any(
        normalized,
        (
            "businesses",
            "business customers",
            "commercial customers",
            "companies",
            "b2b",
        ),
    )
    serves_government = _contains_any(
        normalized,
        ("government", "public agencies", "municipalities"),
    )
    if serves_businesses and serves_government:
        return "mixed"
    if serves_government:
        return "government"
    if serves_businesses:
        return "business"
    return None


def _payment_gap_status(normalized: str) -> bool | None:
    if _contains_any(
        normalized,
        (
            "pay immediately",
            "paid immediately",
            "same day",
            "up front",
            "upfront",
            "prepaid",
            "cash on delivery",
            "no wait",
        ),
    ):
        return False
    if _contains_any(
        normalized,
        (
            "net 30",
            "net 45",
            "net 60",
            "net 90",
            "days",
            "weeks",
            "months",
            "payment terms",
            "wait",
            "slow to pay",
        ),
    ):
        return True
    return None


def _operational_impact_status(normalized: str) -> bool | None:
    if _contains_any(
        normalized,
        (
            "no pressure",
            "not an issue",
            "doesn t affect",
            "does not affect",
            "doesn t create",
            "does not create",
            "not really",
        ),
    ) or _is_negative(normalized):
        return False
    if _is_affirmative(normalized) or _mentions_financial_pressure(normalized):
        return True
    return True if _is_usable_free_text_answer(normalized) else None


def _mentions_financial_pressure(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "payroll",
            "inventory",
            "materials",
            "operating costs",
            "cash flow",
            "pressure",
            "tight",
            "difficult",
            "new work",
            "growth",
        ),
    )


def _current_funding_method(normalized: str) -> str | None:
    factor = _factor_status(normalized)
    if factor is True:
        return "factor"
    if _contains_any(
        normalized,
        ("line of credit", "credit line", "bank loan", "bank financing"),
    ):
        return "bank_line"
    if _contains_any(
        normalized,
        (
            "cash reserves",
            "internal cash",
            "own cash",
            "internally",
            "self fund",
            "ourselves",
        ),
    ):
        return "internal_cash"
    if factor is False or _contains_any(
        normalized,
        ("no financing", "nothing", "don t fund", "dont fund"),
    ):
        return "none"
    return "other" if _is_usable_free_text_answer(normalized) else None


def _is_satisfied_answer(normalized: str, funding_method: str | None) -> bool:
    if funding_method == "factor":
        return _is_negative(normalized) or _contains_any(
            normalized, ("nothing", "no change", "works well")
        )
    return _is_affirmative(normalized) or _contains_any(
        normalized,
        ("covers it", "covers the gap", "meeting our needs", "works well"),
    )


def _need_timing(normalized: str) -> str | None:
    if _contains_any(
        normalized,
        ("later", "next month", "next quarter", "in the future", "not yet"),
    ):
        return "later"
    if _contains_any(
        normalized,
        ("don t need", "dont need", "no need", "not interested", "not right now"),
    ) or _is_negative(normalized):
        return "none"
    if _contains_any(
        normalized,
        ("right now", "now", "today", "soon", "immediately", "currently"),
    ) or _is_affirmative(normalized):
        return "now"
    return None


def _is_affirmative(normalized: str) -> bool:
    return normalized in {"yes", "yeah", "yep", "sure", "okay", "ok", "go ahead", "mhm", "mm hmm"} or normalized.startswith(
        ("yes ", "yeah ", "sure ", "okay ", "ok ")
    )


def _accepts_permission(normalized: str) -> bool:
    return _is_affirmative(normalized) or _mentions_available_seconds(normalized) or _contains_any(
        normalized,
        (
            "i have 30 seconds",
            "i have 20 seconds",
            "20 seconds",
            "twenty seconds",
            "30 seconds",
            "thirty seconds",
            "you can continue",
            "go ahead",
            "go then",
            "keep going",
            "go on",
            "let s talk",
        ),
    )


def _mentions_available_seconds(normalized: str) -> bool:
    if "second" not in normalized:
        return False
    tokens = set(normalized.split())
    return any(token.isdigit() for token in tokens) or bool(
        tokens
        & {
            "ten",
            "fifteen",
            "twenty",
            "thirty",
            "forty",
            "fortyfive",
            "fifty",
            "sixty",
        }
    )


def _requests_short_version(normalized: str) -> bool:
    return _contains_any(
        normalized,
        (
            "make it short",
            "keep it short",
            "short version",
            "brief version",
            "be brief",
        ),
    )


def _has_limited_time(normalized: str) -> bool:
    return "second" in normalized and bool(
        set(normalized.split()) & {"10", "15", "20", "ten", "fifteen", "twenty"}
    )


def _accepts_exploration(normalized: str) -> bool:
    return _is_affirmative(normalized) or _contains_any(
        normalized,
        (
            "would like to explore",
            "open to seeing",
            "let s explore",
            "let us explore",
            "worth a look",
            "go ahead",
            "go then",
            "keep going",
        ),
    )


def _is_negative(normalized: str) -> bool:
    return normalized in {"no", "nope", "not really"} or normalized.startswith("no ")


def _is_final_questions_decline(normalized: str) -> bool:
    return _is_negative(normalized) or _contains_any(
        normalized,
        (
            "no questions",
            "that s all",
            "thats all",
            "nothing else",
            "all set",
            "i m good",
            "im good",
            "we re good",
            "were good",
            "good right now",
        ),
    )


def _is_usable_free_text_answer(normalized: str) -> bool:
    if not normalized or _looks_like_question(normalized):
        return False
    if normalized in {"yes", "yeah", "no", "nope", "okay", "ok", "maybe", "hmm"}:
        return False
    if _contains_any(normalized, ("need more of", "more of what", "something")):
        return False
    return len(normalized.split()) >= 2


def _is_partial_monthly_volume(normalized: str) -> bool:
    tokens = set(normalized.split())
    return bool(tokens & {"thousand", "million"}) and not (
        any(character.isdigit() for character in normalized)
        or bool(
            tokens
            & {
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
                "ten",
                "twenty",
                "thirty",
                "forty",
                "fifty",
                "hundred",
            }
        )
    )


def _monthly_volume_needs_unit(original: str, normalized: str) -> bool:
    has_amount = any(character.isdigit() for character in original) or bool(
        set(normalized.split())
        & {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "hundred"}
    )
    has_unit = bool(
        set(normalized.split())
        & {"dollar", "dollars", "thousand", "thousands", "million", "millions"}
    ) or "$" in original
    return has_amount and not has_unit


def _is_usable_monthly_volume(original: str, normalized: str) -> bool:
    if any(character.isdigit() for character in original):
        return True
    tokens = set(normalized.split())
    number_words = {
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "hundred",
    }
    return bool(tokens & number_words) and bool(tokens & {"thousand", "million"})


def _is_usable_industry_answer(normalized: str) -> bool:
    if not normalized or _looks_like_question(normalized):
        return False
    if normalized in {
        "yes",
        "yeah",
        "no",
        "nope",
        "okay",
        "ok",
        "maybe",
        "hmm",
        "know",
    }:
        return False
    return not _contains_any(
        normalized,
        ("something", "not sure", "don t know", "dont know", "can t say"),
    )


def _natural_industry_reaction(original: str) -> str:
    cleaned = original.strip().rstrip(".!?")
    lowered = cleaned.lower()
    for prefix in (
        "we are in the ",
        "we are in ",
        "we're in the ",
        "we're in ",
        "i am in the ",
        "i am in ",
        "i'm in the ",
        "i'm in ",
        "our business is ",
    ):
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
            break
    normalized = _normalize(cleaned)
    if "it consulting" in normalized:
        return "IT consulting"
    categories = []
    for phrase, reaction in (
        ("trucking", "trucking"),
        ("transportation", "transportation"),
        ("staffing", "staffing"),
        ("manufacturing", "manufacturing"),
        ("distribution", "distribution"),
        ("government contracting", "government contracting"),
        ("consulting", "consulting"),
    ):
        if phrase in normalized:
            categories.append(reaction)
    unique_categories = list(dict.fromkeys(categories))
    if len(unique_categories) == 1:
        return unique_categories[0]
    if not unique_categories and cleaned and len(cleaned.split()) <= 3:
        return cleaned.removeprefix("a ").strip()
    return "that helps"


def _is_likely_industry_correction(normalized: str) -> bool:
    return (
        len(normalized.split()) == 1
        and normalized not in {"factor", "factoring", "factory", "know", "no"}
        and _is_usable_industry_answer(normalized)
    )


def _normalize(text: str) -> str:
    lowered = text.lower()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in lowered).split()
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
