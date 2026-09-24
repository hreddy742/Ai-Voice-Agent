from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import (
    PorterCallOutcomeModel,
    PorterCallSessionModel,
    PorterQualificationAnswerModel,
    PorterTranscriptTurnModel,
)
from api.porter.cold_call_flow import (
    PorterCallerIntent,
    PorterColdCallContext,
    PorterColdCallStage,
)
from api.porter.state_machine import PorterDisposition


TERMINAL_CALL_STATUSES = frozenset({"completed", "failed", "needs_review"})


@dataclass(frozen=True)
class PorterCallFinalizationResult:
    call_session_id: int
    status: str
    disposition: PorterDisposition
    qualification_status: str


async def finalize_porter_call(
    session: AsyncSession,
    *,
    call_session_id: int,
    context: PorterColdCallContext | None = None,
    disposition: PorterDisposition | None = None,
    completion_reason: str,
    status: str = "completed",
) -> PorterCallFinalizationResult:
    if status not in TERMINAL_CALL_STATUSES:
        raise ValueError(f"Unsupported terminal Porter call status: {status}")

    call_session = await session.scalar(
        select(PorterCallSessionModel)
        .where(PorterCallSessionModel.id == call_session_id)
        .with_for_update()
    )
    if call_session is None:
        raise ValueError(f"Porter call session {call_session_id} was not found.")

    resolved_context = context or await load_porter_cold_call_context(
        session,
        call_session_id=call_session_id,
    )
    resolved_disposition = disposition or infer_porter_disposition(resolved_context)
    qualification_status = porter_qualification_status(resolved_context)

    if call_session.status not in TERMINAL_CALL_STATUSES:
        call_session.status = status
    if call_session.ended_at is None:
        call_session.ended_at = datetime.now(UTC)

    await _upsert_qualification(
        session,
        call_session_id=call_session_id,
        context=resolved_context,
    )
    await _upsert_outcome(
        session,
        call_session_id=call_session_id,
        context=resolved_context,
        disposition=resolved_disposition,
        qualification_status=qualification_status,
        completion_reason=completion_reason,
    )
    await session.flush()
    return PorterCallFinalizationResult(
        call_session_id=call_session_id,
        status=call_session.status,
        disposition=resolved_disposition,
        qualification_status=qualification_status,
    )


async def load_porter_cold_call_context(
    session: AsyncSession,
    *,
    call_session_id: int,
) -> PorterColdCallContext:
    rows = (
        await session.execute(
            select(PorterTranscriptTurnModel)
            .where(PorterTranscriptTurnModel.call_session_id == call_session_id)
            .order_by(
                PorterTranscriptTurnModel.timestamp.desc(),
                PorterTranscriptTurnModel.id.desc(),
            )
        )
    ).scalars().all()
    for row in rows:
        metadata = row.raw_metadata or {}
        cold_call_metadata = metadata.get("cold_call_context")
        if isinstance(cold_call_metadata, dict):
            return PorterColdCallContext.from_metadata(cold_call_metadata)
    return PorterColdCallContext()


def porter_disposition_for_intent(
    *,
    current: PorterDisposition,
    intent: PorterCallerIntent,
    context: PorterColdCallContext,
) -> PorterDisposition:
    if intent == PorterCallerIntent.CALLBACK:
        context.captured_fields["next_action"] = "callback_requested"
        return PorterDisposition.CALLBACK_REQUESTED
    if intent == PorterCallerIntent.BUSY:
        context.captured_fields["next_action"] = "callback_requested"
        return PorterDisposition.CALLBACK_REQUESTED
    if intent == PorterCallerIntent.VOICEMAIL:
        context.captured_fields["next_action"] = "voicemail"
        return PorterDisposition.VOICEMAIL
    if intent == PorterCallerIntent.GATEKEEPER:
        context.captured_fields["next_action"] = "contact_referral"
        return PorterDisposition.GATEKEEPER
    if intent == PorterCallerIntent.WRONG_PERSON:
        context.captured_fields["next_action"] = "contact_referral"
        return PorterDisposition.DISQUALIFIED
    if intent == PorterCallerIntent.SEND_INFORMATION:
        context.captured_fields["next_action"] = "send_info"
        return PorterDisposition.SEND_INFO
    if intent == PorterCallerIntent.HUMAN_REQUEST:
        context.captured_fields["next_action"] = "human_handoff"
        return PorterDisposition.HUMAN_HANDOFF
    if intent == PorterCallerIntent.STOP:
        context.captured_fields["next_action"] = "do_not_call"
        return PorterDisposition.NOT_INTERESTED
    if intent == PorterCallerIntent.NOT_INTERESTED:
        context.captured_fields["next_action"] = "not_interested"
        return PorterDisposition.NOT_INTERESTED
    if intent == PorterCallerIntent.SILENCE and context.stage == PorterColdCallStage.COMPLETE:
        context.captured_fields["next_action"] = "no_answer"
        return PorterDisposition.NO_ANSWER
    if current != PorterDisposition.UNKNOWN:
        return current
    return infer_porter_disposition(context)


def infer_porter_disposition(context: PorterColdCallContext) -> PorterDisposition:
    next_action = context.captured_fields.get("next_action")
    action_dispositions = {
        "callback_requested": PorterDisposition.CALLBACK_REQUESTED,
        "send_info": PorterDisposition.SEND_INFO,
        "human_handoff": PorterDisposition.HUMAN_HANDOFF,
        "do_not_call": PorterDisposition.NOT_INTERESTED,
        "not_interested": PorterDisposition.NOT_INTERESTED,
        "no_answer": PorterDisposition.NO_ANSWER,
        "voicemail": PorterDisposition.VOICEMAIL,
        "contact_referral": PorterDisposition.DISQUALIFIED,
        "disqualified": PorterDisposition.DISQUALIFIED,
        "advisor_callback": PorterDisposition.INTERESTED,
    }
    if next_action in action_dispositions:
        return action_dispositions[next_action]
    if (
        context.stage == PorterColdCallStage.COMPLETE
        and context.captured_fields.get("company_name")
    ):
        context.captured_fields["next_action"] = "advisor_callback"
        return PorterDisposition.INTERESTED
    return PorterDisposition.UNKNOWN


def porter_qualification_status(context: PorterColdCallContext) -> str:
    required = (
        "customer_type",
        "invoice_funding_need",
        "current_financing_solution",
        "operational_impact",
        "phone",
        "email",
        "full_name",
        "company_name",
    )
    completed = sum(1 for field in required if context.captured_fields.get(field))
    if completed == len(required):
        return "qualified_pending_review"
    if completed:
        return "partially_qualified"
    return "unqualified"


async def _upsert_qualification(
    session: AsyncSession,
    *,
    call_session_id: int,
    context: PorterColdCallContext,
) -> None:
    fields = context.captured_fields
    qualification = await session.scalar(
        select(PorterQualificationAnswerModel).where(
            PorterQualificationAnswerModel.call_session_id == call_session_id
        )
    )
    if qualification is None:
        qualification = PorterQualificationAnswerModel(call_session_id=call_session_id)
        session.add(qualification)

    qualification.funding_need = _optional_string(fields.get("cash_flow_challenge"))
    qualification.existing_factor_or_lender = _optional_string(
        fields.get("current_financing_solution")
    )
    qualification.raw_answers = {
        **dict(qualification.raw_answers or {}),
        **{key: value for key, value in fields.items() if not key.startswith("_")},
    }


async def _upsert_outcome(
    session: AsyncSession,
    *,
    call_session_id: int,
    context: PorterColdCallContext,
    disposition: PorterDisposition,
    qualification_status: str,
    completion_reason: str,
) -> None:
    outcome = await session.scalar(
        select(PorterCallOutcomeModel).where(
            PorterCallOutcomeModel.call_session_id == call_session_id
        )
    )
    if outcome is None:
        outcome = PorterCallOutcomeModel(
            call_session_id=call_session_id,
            disposition=disposition.value,
            call_summary=(
                f"Porter call finalized via {completion_reason}. "
                f"Qualification status: {qualification_status}."
            ),
            objections=[],
        )
        session.add(outcome)
    elif (
        outcome.disposition == PorterDisposition.UNKNOWN.value
        and disposition != PorterDisposition.UNKNOWN
    ):
        outcome.disposition = disposition.value

    outcome.next_action = _optional_string(context.captured_fields.get("next_action"))
    outcome.human_handoff_reason = (
        "Caller requested a financing advisor."
        if disposition == PorterDisposition.HUMAN_HANDOFF
        else None
    )


def _optional_string(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
