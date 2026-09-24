import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import db_client
from api.db.models import (
    PorterCallSessionModel,
    PorterLeadModel,
)
from api.porter.call_finalization import (
    finalize_porter_call,
    porter_disposition_for_intent,
)
from api.porter.cold_call_flow import (
    PorterCallerIntent,
    PorterColdCallContext,
    PorterColdCallStage,
    decide_porter_cold_call_turn,
)
from api.porter.cold_call_scripts import OPENER, PORTER_AGENT_INSTRUCTIONS
from api.porter.knowledge_base import (
    PORTER_KB_VERSION,
    SAFE_UNKNOWN_ANSWER,
    answer_from_porter_knowledge,
    seed_porter_knowledge_base,
)
from api.porter.llm import OllamaLLMAdapter, PorterLLMAdapter, PorterLLMMessage
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.policy import PorterPolicyEngine
from api.porter.state_machine import (
    PorterConversationContext,
    PorterConversationState,
    PorterDisposition,
    PorterSalesStateMachine,
    record_porter_transcript_turn,
)
from api.porter.suppression import (
    is_porter_phone_suppressed,
    normalize_porter_phone,
    suppress_porter_phone,
)


PROMPT_VERSION = "porter-local-text-v2"


@dataclass(frozen=True)
class ScriptedUserTurn:
    text: str


@dataclass(frozen=True)
class PorterTextConversationSummary:
    call_session_id: int
    lead_id: int
    disposition: str
    qualification_status: str
    funding_need: str | None
    funding_amount: str | None
    monthly_revenue: str | None
    urgency: str | None
    next_action: str | None
    human_review_required: bool
    policy_violation_count: int
    transcript_turn_count: int
    industry: str | None
    current_financing_solution: str | None
    factor_satisfaction: str | None
    cash_flow_challenge: str | None
    monthly_invoicing_volume: str | None
    best_callback_number_and_time: str | None
    phone: str | None
    email: str | None
    full_name: str | None
    company_name: str | None
    customer_type: str | None
    payment_timing: str | None
    operational_impact: str | None
    need_timing: str | None
    decision_authority: str | None
    invoice_funding_need: str | None


async def run_local_text_conversation(
    session: AsyncSession,
    *,
    lead_id: int,
    user_turns: Sequence[ScriptedUserTurn],
    llm_adapter: PorterLLMAdapter | None = None,
    policy_engine: PorterPolicyEngine | None = None,
) -> PorterTextConversationSummary:
    if not user_turns:
        raise ValueError("At least one user turn is required.")

    policy_engine = policy_engine or PorterPolicyEngine()
    lead = await session.get(PorterLeadModel, lead_id)
    if lead is None:
        raise ValueError(f"Porter lead {lead_id} was not found.")
    destination_phone = normalize_porter_phone(lead.phone)
    if lead.do_not_call or await is_porter_phone_suppressed(session, destination_phone):
        raise ValueError(f"Porter phone {destination_phone} is suppressed.")

    await seed_porter_knowledge_base(session)
    call_session = PorterCallSessionModel(
        lead_id=lead.id,
        destination_phone=destination_phone,
        status="in_progress",
        started_at=datetime.now(UTC),
        prompt_version=PROMPT_VERSION,
        knowledge_base_version=PORTER_KB_VERSION,
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    session.add(call_session)
    await session.flush()

    context = PorterColdCallContext()
    policy_violation_count = 0
    transcript_turn_count = 0

    await record_porter_transcript_turn(
        session,
        call_session_id=call_session.id,
        speaker="assistant",
        text=OPENER,
        state=PorterConversationState.OPENING,
        raw_metadata={"cold_call_context": context.to_metadata()},
    )
    transcript_turn_count += 1

    final_disposition = PorterDisposition.UNKNOWN
    for scripted_turn in user_turns:
        decision = decide_porter_cold_call_turn(context, scripted_turn.text)
        decision_policy = policy_engine.check_response(decision.response_text)
        approved_text = decision_policy.safe_text
        policy_violation_count += len(decision_policy.violations)
        await policy_engine.log_violations(
            session,
            call_session_id=call_session.id,
            result=decision_policy,
        )
        await record_porter_transcript_turn(
            session,
            call_session_id=call_session.id,
            speaker="user",
            text=scripted_turn.text,
            state=_legacy_state_for_cold_call_stage(context.stage),
            raw_metadata={
                "classified_intent": decision.intent.value,
                "captured_updates": dict(decision.captured_updates),
            },
        )
        transcript_turn_count += 1

        probe_metadata: dict[str, object] = {}
        if llm_adapter is not None:
            probe = await _generate_agent_text(
                session,
                llm_adapter=llm_adapter,
                lead=lead,
                state=_legacy_state_for_cold_call_stage(context.stage),
                user_text=scripted_turn.text,
            )
            policy_violation_count += len(probe.policy_result.violations)
            await policy_engine.log_violations(
                session,
                call_session_id=call_session.id,
                result=probe.policy_result,
            )
            probe_metadata = _assistant_metadata(
                probe,
                approved_text=approved_text,
            )

        spoken_policy_metadata: dict[str, object] = {
            "spoken_policy_allowed": decision_policy.allowed,
            "spoken_policy_violation_types": [
                violation.violation_type for violation in decision_policy.violations
            ],
        }
        if not decision_policy.allowed and decision.response_text != approved_text:
            spoken_policy_metadata["policy_original_text"] = decision.response_text

        decision.apply(context)
        final_disposition = porter_disposition_for_intent(
            current=final_disposition,
            intent=decision.intent,
            context=context,
        )
        if decision.intent == PorterCallerIntent.STOP:
            await suppress_porter_phone(
                session,
                lead=lead,
                call_session_id=call_session.id,
            )

        await record_porter_transcript_turn(
            session,
            call_session_id=call_session.id,
            speaker="assistant",
            text=approved_text,
            state=_legacy_state_for_cold_call_stage(context.stage),
            raw_metadata={
                **probe_metadata,
                **spoken_policy_metadata,
                "classified_intent": decision.intent.value,
                "cold_call_context": context.to_metadata(),
            },
        )
        transcript_turn_count += 1

        if decision.should_close:
            break

    if (
        final_disposition == PorterDisposition.UNKNOWN
        and context.stage == PorterColdCallStage.NOT_INTERESTED_REASON
    ):
        final_disposition = PorterDisposition.NOT_INTERESTED

    finalization = await finalize_porter_call(
        session,
        call_session_id=call_session.id,
        context=context,
        disposition=final_disposition,
        completion_reason="local_text_conversation",
    )
    final_disposition = finalization.disposition

    return PorterTextConversationSummary(
        call_session_id=call_session.id,
        lead_id=lead.id,
        disposition=final_disposition.value,
        qualification_status=finalization.qualification_status,
        funding_need=None,
        funding_amount=None,
        monthly_revenue=None,
        urgency=None,
        next_action=_as_optional_str(context.captured_fields.get("next_action")),
        human_review_required=bool(call_session.human_review_required),
        policy_violation_count=policy_violation_count,
        transcript_turn_count=transcript_turn_count,
        industry=_as_optional_str(context.captured_fields.get("industry")),
        current_financing_solution=_as_optional_str(
            context.captured_fields.get("current_financing_solution")
        ),
        factor_satisfaction=_as_optional_str(
            context.captured_fields.get("factor_satisfaction")
        ),
        cash_flow_challenge=_as_optional_str(
            context.captured_fields.get("cash_flow_challenge")
        ),
        monthly_invoicing_volume=_as_optional_str(
            context.captured_fields.get("monthly_invoicing_volume")
        ),
        best_callback_number_and_time=_as_optional_str(
            context.captured_fields.get("best_callback_number_and_time")
        ),
        phone=_as_optional_str(context.captured_fields.get("phone")),
        email=_as_optional_str(context.captured_fields.get("email")),
        full_name=_as_optional_str(context.captured_fields.get("full_name")),
        company_name=_as_optional_str(context.captured_fields.get("company_name")),
        customer_type=_as_optional_str(context.captured_fields.get("customer_type")),
        payment_timing=_as_optional_str(context.captured_fields.get("payment_timing")),
        operational_impact=_as_optional_str(
            context.captured_fields.get("operational_impact")
        ),
        need_timing=_as_optional_str(context.captured_fields.get("need_timing")),
        decision_authority=_as_optional_str(
            context.captured_fields.get("decision_authority")
        ),
        invoice_funding_need=_as_optional_str(
            context.captured_fields.get("invoice_funding_need")
        ),
    )


async def _generate_agent_text(
    session: AsyncSession,
    *,
    llm_adapter: PorterLLMAdapter,
    lead: PorterLeadModel,
    state: PorterConversationState,
    user_text: str,
):
    kb_answer = await answer_from_porter_knowledge(session, user_text or lead.evidence_summary)
    messages = [
        PorterLLMMessage(
            role="system",
            content=PORTER_AGENT_INSTRUCTIONS,
        ),
        PorterLLMMessage(
            role="user",
            content=(
                f"Lead: {lead.company_name}; signal: {lead.funding_signal_type}; "
                f"state: {state.value}; user said: {user_text or '[opening]'}; "
                f"approved knowledge: {kb_answer.answer_text}; "
                "Respond in one concise spoken sentence. If the approved knowledge "
                "does not answer it, route to one of our financing advisors."
            ),
        ),
    ]
    response = await llm_adapter.generate(messages)
    response.raw_response.setdefault("porter_kb", {})
    response.raw_response["porter_kb"] = {
        "chunk_ids": list(kb_answer.chunk_ids),
        "source_titles": list(kb_answer.source_titles),
        "knowledge_base_version": kb_answer.knowledge_base_version,
        "needs_human_handoff": kb_answer.needs_human_handoff,
    }
    if not response.safe_text.strip():
        response.raw_response["message"] = {"content": SAFE_UNKNOWN_ANSWER}
    return response


def _legacy_state_for_cold_call_stage(
    stage: PorterColdCallStage,
) -> PorterConversationState:
    return {
        PorterColdCallStage.CONNECTION_CHECK: PorterConversationState.OPENING,
        PorterColdCallStage.IDENTITY_CONFIRMATION: PorterConversationState.OPENING,
        PorterColdCallStage.COMPANY_CONFIRMATION: PorterConversationState.OPENING,
        PorterColdCallStage.SAME_COMPANY_ROLE_CHECK: PorterConversationState.OPENING,
        PorterColdCallStage.ALTERNATE_CONTACT_NAME: PorterConversationState.OPENING,
        PorterColdCallStage.OPENING: PorterConversationState.OPENING,
        PorterColdCallStage.PITCH: PorterConversationState.REASON_FOR_CALL,
        PorterColdCallStage.RELEVANCE: PorterConversationState.INVOICE_AR_FIT,
        PorterColdCallStage.PAYMENT_TIMING: PorterConversationState.FUNDING_NEED,
        PorterColdCallStage.OPERATIONAL_IMPACT: PorterConversationState.FUNDING_NEED,
        PorterColdCallStage.CURRENT_FUNDING: PorterConversationState.EXISTING_FUNDING,
        PorterColdCallStage.PROVIDER_LIMITATION: PorterConversationState.OBJECTION_HANDLING,
        PorterColdCallStage.NEED_TIMING: PorterConversationState.TIMING,
        PorterColdCallStage.DECISION_AUTHORITY: PorterConversationState.FUNDING_NEED,
        PorterColdCallStage.PROBLEM_CONFIRMATION: PorterConversationState.FUNDING_NEED,
        PorterColdCallStage.INDUSTRY: PorterConversationState.FUNDING_NEED,
        PorterColdCallStage.EXISTING_FACTOR: PorterConversationState.EXISTING_FUNDING,
        PorterColdCallStage.FACTOR_SATISFACTION: PorterConversationState.OBJECTION_HANDLING,
        PorterColdCallStage.FACTOR_EXPLORATION: PorterConversationState.OBJECTION_HANDLING,
        PorterColdCallStage.CASH_FLOW_CHALLENGE: PorterConversationState.FUNDING_NEED,
        PorterColdCallStage.MONTHLY_INVOICING_VOLUME: PorterConversationState.REVENUE_AND_AMOUNT,
        PorterColdCallStage.ADVISOR_OFFER: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.BOOKING: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.FINAL_QUESTIONS: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CONTACT_EMAIL: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CONTACT_NAME: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CONTACT_COMPANY: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CALLBACK_DETAILS: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CALLBACK_TODAY: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CALLBACK_CONFIRMATION: PorterConversationState.NEXT_ACTION,
        PorterColdCallStage.CONTACT_REFERRAL: PorterConversationState.HUMAN_HANDOFF,
        PorterColdCallStage.REFERRAL_CONTACT_DETAILS: PorterConversationState.HUMAN_HANDOFF,
        PorterColdCallStage.NOT_INTERESTED_REASON: PorterConversationState.OBJECTION_HANDLING,
        PorterColdCallStage.COMPLETE: PorterConversationState.CLOSE,
    }[stage]


def _capture_fields(context: PorterConversationContext, text: str) -> None:
    lowered = text.lower()
    if context.state == PorterConversationState.FUNDING_NEED:
        context.captured_fields["funding_need"] = text
    elif context.state == PorterConversationState.INVOICE_AR_FIT:
        context.captured_fields["invoices_b2b"] = _mentions_any(
            lowered, ("b2b", "business", "commercial")
        )
        context.captured_fields["has_outstanding_ar"] = _mentions_any(
            lowered, ("invoice", "receivable", "a/r", "ar")
        )
    elif context.state == PorterConversationState.PAYROLL_PO_WORKING_CAPITAL:
        context.captured_fields["has_payroll_need"] = "payroll" in lowered
        context.captured_fields["has_purchase_order_need"] = _mentions_any(
            lowered, ("purchase order", "po", "large order")
        )
    elif context.state == PorterConversationState.REVENUE_AND_AMOUNT:
        context.captured_fields["monthly_revenue"] = _extract_money_phrase(text, "revenue")
        context.captured_fields["funding_amount"] = _extract_money_phrase(text, "need")
    elif context.state == PorterConversationState.TIMING:
        context.captured_fields["urgency"] = text
    elif context.state == PorterConversationState.EXISTING_FUNDING:
        context.captured_fields["existing_factor_or_lender"] = text
    elif context.state == PorterConversationState.NEXT_ACTION:
        context.captured_fields["next_action"] = text

    if "call me later" in lowered or "call back" in lowered:
        context.captured_fields["next_action"] = "callback_requested"
    if (
        ("send" in lowered or "email" in lowered)
        and ("info" in lowered or "information" in lowered or "email" in lowered)
    ):
        context.captured_fields["next_action"] = "send_info"
    if "human" in lowered or "person" in lowered or "specialist" in lowered:
        context.captured_fields["next_action"] = "human_handoff"


def _assistant_metadata(
    response,
    *,
    approved_text: str | None = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "model": response.model,
        "allowed": response.allowed,
        "policy_violation_types": [
            violation.violation_type for violation in response.policy_result.violations
        ],
        "kb_chunk_ids": _extract_chunk_ids(response.raw_response),
    }
    if (
        approved_text is not None
        and not response.allowed
        and response.raw_text != approved_text
    ):
        metadata["policy_original_text"] = response.raw_text
    return metadata


def _extract_chunk_ids(raw_response: dict) -> list[int]:
    porter_kb = raw_response.get("porter_kb") or {}
    return list(porter_kb.get("chunk_ids") or [])


def _mentions_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _extract_money_phrase(text: str, hint: str) -> str:
    words = text.replace(",", "").split()
    money_words = [
        word for word in words if "$" in word or word.lower().endswith(("k", "m"))
    ]
    if money_words:
        return " ".join(money_words[:2])
    return text if hint in text.lower() else ""


def _as_optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


async def _resolve_lead_id(session: AsyncSession, lead_id: int | None) -> int:
    if lead_id is not None:
        return lead_id
    leads = await load_mock_porter_leads(session)
    return leads[0].id


async def _interactive_main(lead_id: int | None) -> PorterTextConversationSummary:
    async with db_client.async_session() as session:
        resolved_lead_id = await _resolve_lead_id(session, lead_id)
        user_turns = []
        print("Porter local text demo. Type 'done' to finish the scripted input.")
        while True:
            text = input("user> ").strip()
            if text.lower() == "done":
                break
            if text:
                user_turns.append(ScriptedUserTurn(text=text))
        summary = await run_local_text_conversation(
            session,
            lead_id=resolved_lead_id,
            user_turns=user_turns,
        )
        await session.commit()
        print(summary)
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Porter local text demo.")
    parser.add_argument("--lead-id", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(_interactive_main(args.lead_id))


if __name__ == "__main__":
    main()
