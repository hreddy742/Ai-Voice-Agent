from sqlalchemy import func, select

from api.db.models import (
    PorterCallOutcomeModel,
    PorterCallSessionModel,
    PorterQualificationAnswerModel,
)
from api.porter.call_finalization import finalize_porter_call
from api.porter.cold_call_flow import PorterColdCallContext, PorterColdCallStage
from api.porter.live_voice import run_porter_voice_opener
from api.porter.state_machine import PorterDisposition, record_porter_transcript_turn
from api.porter.tts import StubTTSAdapter


async def test_finalization_is_idempotent(db_session):
    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(session, tts_adapter=StubTTSAdapter())
        context = PorterColdCallContext(
            stage=PorterColdCallStage.COMPLETE,
            captured_fields={
                "industry": "IT consulting",
                "cash_flow_challenge": "Slow customer payments",
                "next_action": "advisor_callback",
            },
        )

        first = await finalize_porter_call(
            session,
            call_session_id=opener.call_session_id,
            context=context,
            disposition=PorterDisposition.INTERESTED,
            completion_reason="test_close",
        )
        call = await session.get(PorterCallSessionModel, opener.call_session_id)
        first_ended_at = call.ended_at
        second = await finalize_porter_call(
            session,
            call_session_id=opener.call_session_id,
            context=context,
            disposition=PorterDisposition.INTERESTED,
            completion_reason="duplicate_close",
        )

        outcome_count = await session.scalar(
            select(func.count(PorterCallOutcomeModel.id)).where(
                PorterCallOutcomeModel.call_session_id == opener.call_session_id
            )
        )
        qualification_count = await session.scalar(
            select(func.count(PorterQualificationAnswerModel.id)).where(
                PorterQualificationAnswerModel.call_session_id == opener.call_session_id
            )
        )

    assert first.status == "completed"
    assert second.status == "completed"
    assert call.ended_at == first_ended_at
    assert outcome_count == 1
    assert qualification_count == 1


async def test_finalization_reconstructs_latest_cold_call_context(db_session):
    async with db_session.async_session() as session:
        opener = await run_porter_voice_opener(session, tts_adapter=StubTTSAdapter())
        context = PorterColdCallContext(
            stage=PorterColdCallStage.EXISTING_FACTOR,
            captured_fields={
                "industry": "Staffing",
                "current_financing_solution": "Bank line",
            },
        )
        await record_porter_transcript_turn(
            session,
            call_session_id=opener.call_session_id,
            speaker="assistant",
            text="And how do you handle invoices today?",
            state=context.stage,
            raw_metadata={"cold_call_context": context.to_metadata()},
        )

        result = await finalize_porter_call(
            session,
            call_session_id=opener.call_session_id,
            completion_reason="explicit_end_call",
        )
        qualification = await session.scalar(
            select(PorterQualificationAnswerModel).where(
                PorterQualificationAnswerModel.call_session_id == opener.call_session_id
            )
        )
        outcome = await session.scalar(
            select(PorterCallOutcomeModel).where(
                PorterCallOutcomeModel.call_session_id == opener.call_session_id
            )
        )

    assert result.qualification_status == "partially_qualified"
    assert qualification.raw_answers["industry"] == "Staffing"
    assert qualification.existing_factor_or_lender == "Bank line"
    assert outcome.disposition == "unknown"

