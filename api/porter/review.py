from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.db.models import PorterCallSessionModel


async def list_porter_call_sessions(
    session: AsyncSession,
    *,
    limit: int = 25,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    rows = (
        await session.execute(
            select(PorterCallSessionModel)
            .options(
                selectinload(PorterCallSessionModel.lead),
                selectinload(PorterCallSessionModel.outcome),
                selectinload(PorterCallSessionModel.policy_violations),
            )
            .order_by(PorterCallSessionModel.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_session_summary(row) for row in rows]


async def get_porter_call_session_review(
    session: AsyncSession,
    *,
    call_session_id: int,
) -> dict[str, Any] | None:
    row = await session.scalar(
        select(PorterCallSessionModel)
        .where(PorterCallSessionModel.id == call_session_id)
        .options(
            selectinload(PorterCallSessionModel.lead),
            selectinload(PorterCallSessionModel.transcript_turns),
            selectinload(PorterCallSessionModel.qualification_answers),
            selectinload(PorterCallSessionModel.outcome),
            selectinload(PorterCallSessionModel.policy_violations),
            selectinload(PorterCallSessionModel.agent_events),
        )
    )
    if row is None:
        return None
    return {
        **_session_summary(row),
        "transcript": [
            {
                "id": turn.id,
                "speaker": turn.speaker,
                "text": turn.text,
                "conversation_state": turn.conversation_state,
                "timestamp": turn.timestamp.isoformat(),
                "raw_metadata": turn.raw_metadata,
            }
            for turn in row.transcript_turns
        ],
        "qualification": _qualification(row),
        "outcome": _outcome(row),
        "policy_violations": [
            {
                "id": violation.id,
                "violation_type": violation.violation_type,
                "blocked_text": violation.blocked_text,
                "safe_replacement": violation.safe_replacement,
                "created_at": violation.created_at.isoformat(),
            }
            for violation in row.policy_violations
        ],
        "agent_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "event_payload": event.event_payload,
                "created_at": event.created_at.isoformat(),
            }
            for event in row.agent_events
        ],
    }


def _session_summary(row: PorterCallSessionModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "lead_id": row.lead_id,
        "attempt_id": row.attempt_id,
        "destination_phone": row.destination_phone,
        "company_name": row.lead.company_name if row.lead else None,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "prompt_version": row.prompt_version,
        "knowledge_base_version": row.knowledge_base_version,
        "human_review_required": row.human_review_required,
        "crm_sync_status": row.crm_sync_status,
        "disposition": row.outcome.disposition if row.outcome else None,
        "policy_violation_count": len(row.policy_violations),
    }


def _qualification(row: PorterCallSessionModel) -> dict[str, Any] | None:
    qualification = row.qualification_answers
    if qualification is None:
        return None
    return {
        "funding_need": qualification.funding_need,
        "funding_amount": qualification.funding_amount,
        "monthly_revenue": qualification.monthly_revenue,
        "invoices_b2b": qualification.invoices_b2b,
        "has_outstanding_ar": qualification.has_outstanding_ar,
        "has_payroll_need": qualification.has_payroll_need,
        "has_purchase_order_need": qualification.has_purchase_order_need,
        "existing_factor_or_lender": qualification.existing_factor_or_lender,
        "urgency": qualification.urgency,
        "callback_time": (
            qualification.callback_time.isoformat()
            if qualification.callback_time
            else None
        ),
        "raw_answers": qualification.raw_answers,
    }


def _outcome(row: PorterCallSessionModel) -> dict[str, Any] | None:
    outcome = row.outcome
    if outcome is None:
        return None
    return {
        "disposition": outcome.disposition,
        "call_summary": outcome.call_summary,
        "objections": outcome.objections,
        "next_action": outcome.next_action,
        "human_handoff_reason": outcome.human_handoff_reason,
        "created_at": outcome.created_at.isoformat(),
    }
