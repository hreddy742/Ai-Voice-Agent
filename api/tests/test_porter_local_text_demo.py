from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select

from api.db.models import (
    PorterCallOutcomeModel,
    PorterPolicyViolationModel,
    PorterQualificationAnswerModel,
    PorterTranscriptTurnModel,
)
from api.porter.llm import PorterLLMMessage, PorterLLMResponse
from api.porter.local_text_demo import ScriptedUserTurn, run_local_text_conversation
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.policy import PorterPolicyEngine


@dataclass
class _StaticLLMAdapter:
    response_text: str = "I can send this to the Porter team for review."
    model: str = "test-local-llm"

    async def generate(
        self,
        messages: Sequence[PorterLLMMessage],
    ) -> PorterLLMResponse:
        policy_result = PorterPolicyEngine().check_response(self.response_text)
        return PorterLLMResponse(
            raw_text=self.response_text,
            safe_text=policy_result.safe_text,
            allowed=policy_result.allowed,
            model=self.model,
            policy_result=policy_result,
            raw_response={"model": self.model, "message": {"content": self.response_text}},
        )


async def _mock_lead_id(async_session) -> int:
    leads = await load_mock_porter_leads(async_session, replace=True)
    return leads[0].id


def _happy_path_turns() -> list[ScriptedUserTurn]:
    return [
        ScriptedUserTurn("Yes, I have a minute."),
        ScriptedUserTurn("Yes, go ahead."),
        ScriptedUserTurn("Yes, connect me with an advisor."),
        ScriptedUserTurn("Call me at 205-555-0100."),
        ScriptedUserTurn("Today."),
        ScriptedUserTurn("3 pm."),
        ScriptedUserTurn("Yes, that's correct."),
        ScriptedUserTurn("No, that's all."),
    ]


async def test_full_happy_path_conversation_stores_transcript_and_outcome(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=_happy_path_turns(),
        llm_adapter=_StaticLLMAdapter(),
    )
    await async_session.commit()

    outcome = await async_session.scalar(
        select(PorterCallOutcomeModel).where(
            PorterCallOutcomeModel.call_session_id == summary.call_session_id
        )
    )
    qualification = await async_session.scalar(
        select(PorterQualificationAnswerModel).where(
            PorterQualificationAnswerModel.call_session_id == summary.call_session_id
        )
    )
    turns = (
        await async_session.execute(
            select(PorterTranscriptTurnModel).where(
                PorterTranscriptTurnModel.call_session_id == summary.call_session_id
            )
        )
    ).scalars().all()

    assert summary.disposition == "callback_requested"
    assert summary.qualification_status == "partially_qualified"
    assert outcome.disposition == "callback_requested"
    assert qualification.raw_answers["phone"] == "Call me at 205-555-0100."
    assert qualification.raw_answers["callback_request"] == "today at 3 pm."
    assert len(turns) == summary.transcript_turn_count
    assert all(turn.conversation_state for turn in turns)


async def test_rate_question_is_blocked_and_logged(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=[ScriptedUserTurn("What rate can you give me?")],
        llm_adapter=_StaticLLMAdapter("Your rate will be 2%."),
    )
    await async_session.commit()

    violations = (
        await async_session.execute(
            select(PorterPolicyViolationModel).where(
                PorterPolicyViolationModel.call_session_id == summary.call_session_id
            )
        )
    ).scalars().all()
    assistant_turns = (
        await async_session.execute(
            select(PorterTranscriptTurnModel).where(
                PorterTranscriptTurnModel.call_session_id == summary.call_session_id,
                PorterTranscriptTurnModel.speaker == "assistant",
            )
        )
    ).scalars().all()

    assert summary.policy_violation_count >= 1
    assert any(v.violation_type == "rate_claim" for v in violations)
    assert all("2%" not in turn.text for turn in assistant_turns)


async def test_approval_question_is_blocked(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=[ScriptedUserTurn("Am I approved?")],
        llm_adapter=_StaticLLMAdapter("You are approved."),
    )
    await async_session.commit()

    violations = (
        await async_session.execute(
            select(PorterPolicyViolationModel).where(
                PorterPolicyViolationModel.call_session_id == summary.call_session_id
            )
        )
    ).scalars().all()

    assert any(v.violation_type == "approval_promise" for v in violations)


async def test_callback_is_captured(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=[ScriptedUserTurn("Call me later tomorrow.")],
        llm_adapter=_StaticLLMAdapter(),
    )

    assert summary.disposition == "callback_requested"
    assert summary.next_action == "callback_requested"


async def test_send_info_is_captured_without_sending(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=[ScriptedUserTurn("Can you email me information?")],
        llm_adapter=_StaticLLMAdapter(),
    )

    assert summary.disposition == "send_info"
    assert summary.next_action == "send_info"


async def test_human_handoff_is_captured(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=[ScriptedUserTurn("I want to talk to a human specialist.")],
        llm_adapter=_StaticLLMAdapter(),
    )

    assert summary.disposition == "human_handoff"
    assert summary.next_action == "human_handoff"
    assert summary.human_review_required is True


async def test_final_outcome_validates_against_schema(async_session):
    summary = await run_local_text_conversation(
        async_session,
        lead_id=await _mock_lead_id(async_session),
        user_turns=[ScriptedUserTurn("Not interested.")],
        llm_adapter=_StaticLLMAdapter(),
    )
    await async_session.commit()

    outcome = await async_session.scalar(
        select(PorterCallOutcomeModel).where(
            PorterCallOutcomeModel.call_session_id == summary.call_session_id
        )
    )

    assert outcome.disposition == "not_interested"
    assert outcome.call_summary
