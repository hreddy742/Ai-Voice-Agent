from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterTranscriptTurnModel
from api.porter.policy import PorterPolicyEngine


class PorterConversationState(StrEnum):
    OPENING = "opening"
    PERMISSION_CHECK = "permission_check"
    REASON_FOR_CALL = "reason_for_call"
    FUNDING_NEED = "funding_need"
    INVOICE_AR_FIT = "invoice_ar_fit"
    PAYROLL_PO_WORKING_CAPITAL = "payroll_po_working_capital"
    REVENUE_AND_AMOUNT = "revenue_and_amount"
    TIMING = "timing"
    EXISTING_FUNDING = "existing_funding"
    OBJECTION_HANDLING = "objection_handling"
    NEXT_ACTION = "next_action"
    HUMAN_HANDOFF = "human_handoff"
    CLOSE = "close"


class PorterDisposition(StrEnum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CALLBACK_REQUESTED = "callback_requested"
    SEND_INFO = "send_info"
    HUMAN_HANDOFF = "human_handoff"
    DISQUALIFIED = "disqualified"
    VOICEMAIL = "voicemail"
    GATEKEEPER = "gatekeeper"
    NO_ANSWER = "no_answer"
    UNKNOWN = "unknown"


TERMINAL_DISPOSITIONS = frozenset(disposition.value for disposition in PorterDisposition)

STATE_REQUIRED_FIELDS: Mapping[PorterConversationState, tuple[str, ...]] = {
    PorterConversationState.FUNDING_NEED: ("funding_need",),
    PorterConversationState.INVOICE_AR_FIT: ("invoices_b2b", "has_outstanding_ar"),
    PorterConversationState.PAYROLL_PO_WORKING_CAPITAL: (
        "has_payroll_need",
        "has_purchase_order_need",
    ),
    PorterConversationState.REVENUE_AND_AMOUNT: (
        "monthly_revenue",
        "funding_amount",
    ),
    PorterConversationState.TIMING: ("urgency",),
    PorterConversationState.EXISTING_FUNDING: ("existing_factor_or_lender",),
    PorterConversationState.NEXT_ACTION: ("next_action",),
}


ADVANCE_STATE: Mapping[PorterConversationState, PorterConversationState] = {
    PorterConversationState.OPENING: PorterConversationState.PERMISSION_CHECK,
    PorterConversationState.PERMISSION_CHECK: PorterConversationState.REASON_FOR_CALL,
    PorterConversationState.REASON_FOR_CALL: PorterConversationState.FUNDING_NEED,
    PorterConversationState.FUNDING_NEED: PorterConversationState.INVOICE_AR_FIT,
    PorterConversationState.INVOICE_AR_FIT: PorterConversationState.PAYROLL_PO_WORKING_CAPITAL,
    PorterConversationState.PAYROLL_PO_WORKING_CAPITAL: PorterConversationState.REVENUE_AND_AMOUNT,
    PorterConversationState.REVENUE_AND_AMOUNT: PorterConversationState.TIMING,
    PorterConversationState.TIMING: PorterConversationState.EXISTING_FUNDING,
    PorterConversationState.EXISTING_FUNDING: PorterConversationState.NEXT_ACTION,
    PorterConversationState.OBJECTION_HANDLING: PorterConversationState.NEXT_ACTION,
    PorterConversationState.NEXT_ACTION: PorterConversationState.CLOSE,
    PorterConversationState.HUMAN_HANDOFF: PorterConversationState.CLOSE,
    PorterConversationState.CLOSE: PorterConversationState.CLOSE,
}


@dataclass(frozen=True)
class PorterStateMachineResult:
    current_state: PorterConversationState
    next_state: PorterConversationState
    disposition: PorterDisposition | None = None
    required_fields: tuple[str, ...] = ()
    reason: str = "advance"
    human_handoff_required: bool = False
    policy_safe_text: str | None = None
    policy_violation_types: tuple[str, ...] = ()

    @property
    def is_terminal(self) -> bool:
        return self.next_state == PorterConversationState.CLOSE


@dataclass
class PorterConversationContext:
    state: PorterConversationState = PorterConversationState.OPENING
    captured_fields: dict[str, object] = field(default_factory=dict)


class PorterSalesStateMachine:
    def __init__(self, policy_engine: PorterPolicyEngine | None = None) -> None:
        self._policy_engine = policy_engine or PorterPolicyEngine()

    def transition(
        self,
        context: PorterConversationContext,
        user_text: str,
        *,
        agent_draft: str | None = None,
    ) -> PorterStateMachineResult:
        normalized = _normalize(user_text)
        policy_result = (
            self._policy_engine.check_response(agent_draft) if agent_draft else None
        )

        if policy_result is not None and not policy_result.allowed:
            return PorterStateMachineResult(
                current_state=context.state,
                next_state=PorterConversationState.OBJECTION_HANDLING,
                required_fields=STATE_REQUIRED_FIELDS.get(
                    PorterConversationState.OBJECTION_HANDLING, ()
                ),
                reason="policy_violation",
                policy_safe_text=policy_result.safe_text,
                policy_violation_types=tuple(
                    violation.violation_type for violation in policy_result.violations
                ),
            )

        routed = self._route_special_intent(context.state, normalized)
        if routed is not None:
            return routed

        missing_fields = _missing_required_fields(context)
        if missing_fields and not _is_affirmative_or_informative(normalized):
            return PorterStateMachineResult(
                current_state=context.state,
                next_state=context.state,
                required_fields=missing_fields,
                reason="needs_clarification",
            )

        next_state = ADVANCE_STATE[context.state]
        return PorterStateMachineResult(
            current_state=context.state,
            next_state=next_state,
            required_fields=STATE_REQUIRED_FIELDS.get(next_state, ()),
            reason="advance",
        )

    def _route_special_intent(
        self,
        state: PorterConversationState,
        normalized: str,
    ) -> PorterStateMachineResult | None:
        if _contains_any(normalized, ("human", "person", "representative", "specialist")):
            return PorterStateMachineResult(
                current_state=state,
                next_state=PorterConversationState.HUMAN_HANDOFF,
                disposition=PorterDisposition.HUMAN_HANDOFF,
                reason="human_requested",
                human_handoff_required=True,
            )

        if _contains_any(normalized, ("not interested", "stop calling", "remove me")):
            return PorterStateMachineResult(
                current_state=state,
                next_state=PorterConversationState.CLOSE,
                disposition=PorterDisposition.NOT_INTERESTED,
                reason="not_interested",
            )

        if _contains_any(normalized, ("send info", "send me information", "email me")):
            return PorterStateMachineResult(
                current_state=state,
                next_state=PorterConversationState.CLOSE,
                disposition=PorterDisposition.SEND_INFO,
                reason="send_info_requested",
            )

        if _contains_any(normalized, ("call me later", "call back", "tomorrow", "next week")):
            return PorterStateMachineResult(
                current_state=state,
                next_state=PorterConversationState.CLOSE,
                disposition=PorterDisposition.CALLBACK_REQUESTED,
                reason="callback_requested",
            )

        if _contains_any(normalized, ("rate", "rates", "fee", "fees", "approved", "approval")):
            return PorterStateMachineResult(
                current_state=state,
                next_state=PorterConversationState.OBJECTION_HANDLING,
                reason="sensitive_question",
            )

        if normalized.strip(".!?,") in {"hello", "hi", "hey"}:
            return PorterStateMachineResult(
                current_state=state,
                next_state=state,
                required_fields=STATE_REQUIRED_FIELDS.get(state, ()),
                reason="greeting",
            )

        if _is_informational_question(normalized):
            return PorterStateMachineResult(
                current_state=state,
                next_state=state,
                required_fields=STATE_REQUIRED_FIELDS.get(state, ()),
                reason="informational_question",
            )

        if normalized.strip(".!?,") in {"i want you", "want you"}:
            return PorterStateMachineResult(
                current_state=state,
                next_state=state,
                required_fields=STATE_REQUIRED_FIELDS.get(state, ()),
                reason="needs_clarification",
            )

        if state == PorterConversationState.NEXT_ACTION and _contains_any(
            normalized, ("yes", "okay", "ok", "interested", "sounds good")
        ):
            return PorterStateMachineResult(
                current_state=state,
                next_state=PorterConversationState.CLOSE,
                disposition=PorterDisposition.INTERESTED,
                reason="interested",
            )

        return None


async def record_porter_transcript_turn(
    session: AsyncSession,
    *,
    call_session_id: int,
    speaker: str,
    text: str,
    state: PorterConversationState,
    raw_metadata: Mapping[str, object] | None = None,
    timestamp: datetime | None = None,
) -> PorterTranscriptTurnModel:
    turn = PorterTranscriptTurnModel(
        call_session_id=call_session_id,
        speaker=speaker,
        text=text,
        conversation_state=state.value,
        timestamp=timestamp or datetime.now(UTC),
        raw_metadata=dict(raw_metadata or {}),
    )
    session.add(turn)
    await session.flush()
    return turn


def _missing_required_fields(
    context: PorterConversationContext,
) -> tuple[str, ...]:
    required = STATE_REQUIRED_FIELDS.get(context.state, ())
    return tuple(field for field in required if context.captured_fields.get(field) in (None, ""))


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _is_affirmative_or_informative(text: str) -> bool:
    if not text:
        return False
    if _contains_any(text, ("yes", "yeah", "yep", "no", "not sure", "maybe")):
        return True
    return len(text.split()) >= 3


def _is_informational_question(text: str) -> bool:
    if _contains_any(
        text,
        (
            "who are you",
            "who is this",
            "what is porter",
            "what do you do",
            "tell me more",
            "know more",
            "what do you mean",
            "mean by what part",
            "what part do you mean",
        ),
    ):
        return True

    normalized = " ".join(
        "".join(character if character.isalnum() else " " for character in text).split()
    )
    tokens = set(normalized.split())
    if "funding" in tokens and bool(tokens & {"take", "time", "when", "long", "soon", "fast"}):
        return True

    asks_about_factoring = (
        bool(tokens & {"factor", "factoring"})
        and not normalized.startswith(
            (
                "we factor",
                "already have a factor",
                "current factor",
                "no current factor",
                "no factor",
                "we do not factor",
                "we dont factor",
            )
        )
    )
    return asks_about_factoring


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())
