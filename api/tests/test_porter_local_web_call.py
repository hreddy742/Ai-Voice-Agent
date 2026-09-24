from api.porter.llm import MockPorterLLMAdapter
from api.porter.cold_call_scripts import RATES
from api.porter.local_web_call import run_porter_local_web_call_simulation
from api.porter.mock_leads import load_mock_porter_leads


async def test_local_web_call_simulation_uses_lead_context_and_persists(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)

    result = await run_porter_local_web_call_simulation(
        async_session,
        lead_id=leads[0].id,
        user_turns=[
            "Yes, I have a minute.",
            "We need payroll funding.",
            "Call me later tomorrow.",
        ],
        llm_adapter=MockPorterLLMAdapter(
            "Porter may be able to help depending on review."
        ),
    )

    assert result.telephony_enabled is False
    assert result.crm_sync_enabled is False
    assert result.email_enabled is False
    assert result.sms_enabled is False
    assert result.summary.lead_id == leads[0].id
    assert result.summary.disposition == "callback_requested"
    assert result.transcript
    assert result.assistant_audio_count > 0


async def test_local_web_call_simulation_refuses_exact_rates(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)

    result = await run_porter_local_web_call_simulation(
        async_session,
        lead_id=leads[0].id,
        user_turns=["What are your rates?"],
        llm_adapter=MockPorterLLMAdapter("Your rate will be 2%."),
    )

    assistant_text = " ".join(
        str(turn["text"]) for turn in result.transcript if turn["speaker"] == "assistant"
    )

    assert "2%" not in assistant_text
    assert RATES in assistant_text
    assert result.summary.policy_violation_count >= 1


async def test_local_web_call_simulation_captures_core_qualification_fields(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)

    result = await run_porter_local_web_call_simulation(
        async_session,
        lead_id=leads[0].id,
        user_turns=[
            "Yes, I have a minute.",
            "Yes, we want invoices paid sooner.",
            "We cover it with internal cash.",
            "Waiting on invoices makes payroll difficult.",
            "Yes, connect me with an advisor.",
            "Call me at 205-555-0100 Friday morning.",
            "alex@example.com",
            "Alex Morgan",
            "Morgan Technology Group",
        ],
        llm_adapter=MockPorterLLMAdapter(
            "I can send this to the Porter team for review."
        ),
        synthesize_audio=False,
    )

    assert result.summary.disposition == "interested"
    assert result.summary.customer_type == "business"
    assert result.summary.invoice_funding_need == "yes"
    assert result.summary.cash_flow_challenge == (
        "Waiting on invoices makes payroll difficult."
    )
    assert result.summary.current_financing_solution == "We cover it with internal cash."
