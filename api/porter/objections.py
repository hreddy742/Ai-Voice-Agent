from dataclasses import dataclass
from enum import StrEnum

from api.porter.policy import PorterPolicyEngine
from api.porter.state_machine import PorterConversationState, PorterDisposition


class PorterObjectionType(StrEnum):
    NOT_INTERESTED = "not_interested"
    CALL_ME_LATER = "call_me_later"
    SEND_INFO = "send_info"
    ALREADY_HAVE_FUNDING = "already_have_funding"
    RATES = "rates"
    FUNDING_SPEED = "funding_speed"
    IS_THIS_A_LOAN = "is_this_a_loan"
    IS_THIS_FACTORING = "is_this_factoring"
    WHO_ARE_YOU = "who_are_you"
    HOW_GOT_NUMBER = "how_got_number"
    CAN_EMAIL_ME = "can_email_me"
    ANGRY_RESPONSE = "angry_response"
    GATEKEEPER = "gatekeeper"
    VOICEMAIL = "voicemail"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PorterObjectionHandlingResult:
    objection_type: PorterObjectionType
    response_text: str
    next_state: PorterConversationState
    disposition: PorterDisposition | None = None
    human_handoff_required: bool = False
    callback_requested: bool = False
    send_info_requested: bool = False
    should_end_conversation: bool = False


class PorterObjectionHandler:
    def __init__(self, policy_engine: PorterPolicyEngine | None = None) -> None:
        self._policy_engine = policy_engine or PorterPolicyEngine()

    def handle(self, user_text: str) -> PorterObjectionHandlingResult:
        objection_type = classify_porter_objection(user_text)
        result = _RESULTS[objection_type]
        policy_result = self._policy_engine.check_response(result.response_text)
        if not policy_result.allowed:
            return PorterObjectionHandlingResult(
                objection_type=objection_type,
                response_text=policy_result.safe_text,
                next_state=PorterConversationState.OBJECTION_HANDLING,
                human_handoff_required=True,
            )
        return result


def classify_porter_objection(user_text: str) -> PorterObjectionType:
    text = _normalize(user_text)
    if not text:
        return PorterObjectionType.UNKNOWN
    if _contains_any(text, ("voicemail", "leave a message", "after the tone")):
        return PorterObjectionType.VOICEMAIL
    if _contains_any(text, ("who is calling", "who are you", "what company")):
        return PorterObjectionType.WHO_ARE_YOU
    if _contains_any(text, ("how did you get", "where did you get", "my number")):
        return PorterObjectionType.HOW_GOT_NUMBER
    if _contains_any(text, ("angry", "stop calling", "never call", "remove me", "do not call")):
        return PorterObjectionType.ANGRY_RESPONSE
    if _contains_any(text, ("not interested", "no thanks", "we are good")):
        return PorterObjectionType.NOT_INTERESTED
    if _contains_any(text, ("gatekeeper", "not available", "not in", "assistant speaking")):
        return PorterObjectionType.GATEKEEPER
    if _contains_any(text, ("call me later", "call back", "tomorrow", "next week")):
        return PorterObjectionType.CALL_ME_LATER
    if _contains_any(text, ("email me", "send email")):
        return PorterObjectionType.CAN_EMAIL_ME
    if _contains_any(text, ("send info", "send information", "send me information")):
        return PorterObjectionType.SEND_INFO
    if _contains_any(text, ("already have funding", "have a lender", "current factor")):
        return PorterObjectionType.ALREADY_HAVE_FUNDING
    if _contains_any(text, ("rate", "rates", "fee", "fees", "cost")):
        return PorterObjectionType.RATES
    if _contains_any(text, ("how fast", "how quickly", "same day", "tomorrow funding")):
        return PorterObjectionType.FUNDING_SPEED
    if _contains_any(text, ("is this a loan", "loan?")):
        return PorterObjectionType.IS_THIS_A_LOAN
    if _contains_any(text, ("is this factoring", "what is factoring")):
        return PorterObjectionType.IS_THIS_FACTORING
    return PorterObjectionType.UNKNOWN


_RESULTS: dict[PorterObjectionType, PorterObjectionHandlingResult] = {
    PorterObjectionType.NOT_INTERESTED: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.NOT_INTERESTED,
        response_text="I understand. I can close this out for local review.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.NOT_INTERESTED,
        should_end_conversation=True,
    ),
    PorterObjectionType.CALL_ME_LATER: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.CALL_ME_LATER,
        response_text="No problem. I can mark this for a callback.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.CALLBACK_REQUESTED,
        callback_requested=True,
        should_end_conversation=True,
    ),
    PorterObjectionType.SEND_INFO: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.SEND_INFO,
        response_text="I can mark that you requested information for the Porter team.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.SEND_INFO,
        send_info_requested=True,
        should_end_conversation=True,
    ),
    PorterObjectionType.ALREADY_HAVE_FUNDING: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.ALREADY_HAVE_FUNDING,
        response_text="Understood. If useful, a Porter specialist can review whether there is a better fit.",
        next_state=PorterConversationState.NEXT_ACTION,
    ),
    PorterObjectionType.RATES: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.RATES,
        response_text="Rates depend on qualification and review.",
        next_state=PorterConversationState.OBJECTION_HANDLING,
    ),
    PorterObjectionType.FUNDING_SPEED: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.FUNDING_SPEED,
        response_text="Timing depends on the business details, receivables, and Porter review.",
        next_state=PorterConversationState.OBJECTION_HANDLING,
    ),
    PorterObjectionType.IS_THIS_A_LOAN: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.IS_THIS_A_LOAN,
        response_text="Porter may discuss factoring or working-capital options depending on review.",
        next_state=PorterConversationState.OBJECTION_HANDLING,
    ),
    PorterObjectionType.IS_THIS_FACTORING: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.IS_THIS_FACTORING,
        response_text="Factoring can turn qualifying unpaid B2B invoices into working capital after review.",
        next_state=PorterConversationState.OBJECTION_HANDLING,
    ),
    PorterObjectionType.WHO_ARE_YOU: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.WHO_ARE_YOU,
        response_text="I am a local Porter Capital validation agent calling about possible business funding needs.",
        next_state=PorterConversationState.PERMISSION_CHECK,
    ),
    PorterObjectionType.HOW_GOT_NUMBER: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.HOW_GOT_NUMBER,
        response_text="I only have local lead context for this test and can mark this for human review.",
        next_state=PorterConversationState.HUMAN_HANDOFF,
        disposition=PorterDisposition.HUMAN_HANDOFF,
        human_handoff_required=True,
    ),
    PorterObjectionType.CAN_EMAIL_ME: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.CAN_EMAIL_ME,
        response_text="I can mark that you requested information, but I will not send email from this local test.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.SEND_INFO,
        send_info_requested=True,
        should_end_conversation=True,
    ),
    PorterObjectionType.ANGRY_RESPONSE: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.ANGRY_RESPONSE,
        response_text="Understood. I will end this local test interaction.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.NOT_INTERESTED,
        should_end_conversation=True,
    ),
    PorterObjectionType.GATEKEEPER: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.GATEKEEPER,
        response_text="I can note that the contact was not available and avoid sharing sensitive details.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.GATEKEEPER,
        should_end_conversation=True,
    ),
    PorterObjectionType.VOICEMAIL: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.VOICEMAIL,
        response_text="I can mark this local test as voicemail without leaving a production message.",
        next_state=PorterConversationState.CLOSE,
        disposition=PorterDisposition.VOICEMAIL,
        should_end_conversation=True,
    ),
    PorterObjectionType.UNKNOWN: PorterObjectionHandlingResult(
        objection_type=PorterObjectionType.UNKNOWN,
        response_text="I can send this to the Porter team for review.",
        next_state=PorterConversationState.OBJECTION_HANDLING,
        human_handoff_required=True,
    ),
}


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())
