from api.porter.llm import MockPorterLLMAdapter
from api.porter.local_web_call import run_porter_local_web_call_simulation
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.review import (
    get_porter_call_session_review,
    list_porter_call_sessions,
)


async def _create_reviewable_session(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)
    return await run_porter_local_web_call_simulation(
        async_session,
        lead_id=leads[0].id,
        user_turns=[
            "Yes, I have a minute.",
            "What are your rates?",
        ],
        llm_adapter=MockPorterLLMAdapter("Your rate will be 2%."),
    )


async def test_review_view_lists_call_sessions(async_session):
    result = await _create_reviewable_session(async_session)

    rows = await list_porter_call_sessions(async_session)

    assert any(row["id"] == result.summary.call_session_id for row in rows)
    assert rows[0]["company_name"]
    assert "policy_violation_count" in rows[0]


async def test_review_view_contains_ordered_transcript_and_outcome(async_session):
    result = await _create_reviewable_session(async_session)

    review = await get_porter_call_session_review(
        async_session,
        call_session_id=result.summary.call_session_id,
    )

    assert review["outcome"]["disposition"] == result.summary.disposition
    assert review["transcript"]
    assert [turn["id"] for turn in review["transcript"]] == sorted(
        turn["id"] for turn in review["transcript"]
    )


async def test_review_view_shows_policy_violations_and_qualification(async_session):
    result = await _create_reviewable_session(async_session)

    review = await get_porter_call_session_review(
        async_session,
        call_session_id=result.summary.call_session_id,
    )

    assert review["policy_violations"]
    assert review["policy_violations"][0]["violation_type"] == "rate_claim"
    assert review["qualification"] is not None
