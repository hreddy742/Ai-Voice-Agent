from api.db.models import PorterCallSessionModel
from api.porter.knowledge_base import (
    PORTER_KB_VERSION,
    SAFE_INDUSTRY_HANDOFF_ANSWER,
    SAFE_RATE_ANSWER,
    answer_from_porter_knowledge,
    mark_call_session_knowledge_version,
    retrieve_porter_knowledge,
    seed_porter_knowledge_base,
)
from api.porter.mock_leads import load_mock_porter_leads


async def test_factoring_question_retrieves_approved_chunk(async_session):
    await seed_porter_knowledge_base(async_session, replace=True)

    chunks = await retrieve_porter_knowledge(
        async_session,
        "How does invoice factoring work for B2B invoices?",
    )

    assert chunks
    assert chunks[0].knowledge_base_version == PORTER_KB_VERSION
    assert "factoring" in chunks[0].chunk_text.lower()
    assert chunks[0].chunk_metadata["approved"] is True


async def test_rate_question_returns_safe_answer_without_invented_rate(async_session):
    await seed_porter_knowledge_base(async_session, replace=True)

    answer = await answer_from_porter_knowledge(
        async_session,
        "What rate or fee would I get?",
    )

    assert answer.answer_text == SAFE_RATE_ANSWER
    assert "0.2 and 2 percent" in answer.answer_text
    assert "1 and 5 percent" not in answer.answer_text
    assert "6" not in answer.answer_text
    assert answer.chunk_ids
    assert "John questionnaire - rates" in answer.source_titles


async def test_specific_industry_question_routes_to_advisor(async_session):
    await seed_porter_knowledge_base(async_session, replace=True)

    answer = await answer_from_porter_knowledge(
        async_session,
        "Does Porter work with construction companies?",
    )

    assert answer.answer_text == SAFE_INDUSTRY_HANDOFF_ANSWER
    assert answer.needs_human_handoff is True
    assert "excludes" not in answer.answer_text.lower()


async def test_unknown_question_returns_safe_fallback(async_session):
    await seed_porter_knowledge_base(async_session, replace=True)

    answer = await answer_from_porter_knowledge(
        async_session,
        "Can you advise on unrelated commercial lease terms?",
    )

    assert answer.needs_human_handoff is True
    assert answer.answer_text == "Got it — let me get one of our financing advisors to dig into that with you."
    assert answer.chunk_ids == ()


async def test_kb_version_is_stored_on_call_session(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)
    call_session = PorterCallSessionModel(
        lead=leads[0],
        destination_phone=leads[0].phone,
        status="created",
        prompt_version="porter-local-v1",
        knowledge_base_version="pending",
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    async_session.add(call_session)
    await async_session.flush()

    updated = await mark_call_session_knowledge_version(
        async_session,
        call_session_id=call_session.id,
    )

    assert updated.knowledge_base_version == PORTER_KB_VERSION


async def test_generated_answers_include_traceable_chunk_ids(async_session):
    await seed_porter_knowledge_base(async_session, replace=True)

    answer = await answer_from_porter_knowledge(async_session, "How fast is funding?")

    assert answer.chunk_ids
    assert answer.source_titles
    assert answer.knowledge_base_version == PORTER_KB_VERSION
    assert "under 48 hours" in answer.answer_text.lower()
    assert "once a client is set up" in answer.answer_text.lower()


async def test_approved_estimate_methods_are_traceable_and_nonbinding(async_session):
    await seed_porter_knowledge_base(async_session, replace=True)

    answer = await answer_from_porter_knowledge(
        async_session,
        "How much funding could accounts receivable or annual revenue support?",
    )

    lowered = answer.answer_text.lower()
    assert "accounts receivable multiplied by 90 percent" in lowered
    assert "annual revenue multiplied by 10 percent" in lowered
    assert "advisor review only" in lowered
    assert "not approval" in lowered
    assert "John confirmation - preliminary funding illustrations" in answer.source_titles
