import pytest
from sqlalchemy import select

from api.db.models import PorterCallSessionModel, PorterPolicyViolationModel
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.policy import (
    SAFE_APPROVAL_REPLACEMENT,
    SAFE_FUNDING_REPLACEMENT,
    SAFE_LEGAL_REPLACEMENT,
    SAFE_RATE_REPLACEMENT,
    SAFE_REVIEW_REPLACEMENT,
    PorterPolicyEngine,
)


@pytest.mark.parametrize(
    ("text", "violation_type", "replacement"),
    [
        ("Your rate will be 2%.", "rate_claim", SAFE_RATE_REPLACEMENT),
        ("You are approved.", "approval_promise", SAFE_APPROVAL_REPLACEMENT),
        (
            "We can definitely fund you.",
            "definite_funding_claim",
            SAFE_FUNDING_REPLACEMENT,
        ),
        (
            "Funding is guaranteed.",
            "guaranteed_funding_claim",
            SAFE_FUNDING_REPLACEMENT,
        ),
        ("No review is needed.", "no_review_claim", SAFE_REVIEW_REPLACEMENT),
        ("This is legally risk-free.", "legal_or_compliance_claim", SAFE_LEGAL_REPLACEMENT),
        (
            "Porter already approved your business.",
            "porter_already_reviewed_claim",
            SAFE_REVIEW_REPLACEMENT,
        ),
        ("Absolutely, we can help.", "forbidden_corporate_tone", "Yeah, let me keep it simple."),
    ],
)
def test_forbidden_porter_claims_are_blocked(text, violation_type, replacement):
    result = PorterPolicyEngine().check_response(text)

    assert result.allowed is False
    assert result.safe_text == replacement
    assert len(result.violations) == 1
    assert result.violations[0].violation_type == violation_type
    assert result.violations[0].blocked_text == text
    assert result.violations[0].safe_replacement == replacement


@pytest.mark.parametrize(
    "text",
    [
        "Rates typically run somewhere between 0.2 and 2 percent.",
        "Right, I can't confirm approval without one of our financing advisors reviewing the details.",
        "Got it — that depends on the business details and one of our financing advisors reviewing it.",
        "Got it — I can send this to the Porter team for review.",
        "Sure, one of our financing advisors can follow up with you.",
    ],
)
def test_safe_porter_explanations_pass(text):
    result = PorterPolicyEngine().check_response(text)

    assert result.allowed is True
    assert result.safe_text == text
    assert result.violations == ()


def test_multiple_violations_return_deduped_safe_replacements():
    result = PorterPolicyEngine().check_response(
        "You are approved and funding is guaranteed. Your rate will be 2%."
    )

    assert result.allowed is False
    assert [violation.violation_type for violation in result.violations] == [
        "rate_claim",
        "approval_promise",
        "guaranteed_funding_claim",
    ]
    assert result.safe_text == (
        f"{SAFE_RATE_REPLACEMENT} {SAFE_APPROVAL_REPLACEMENT} "
        f"{SAFE_FUNDING_REPLACEMENT}"
    )


async def test_policy_violation_is_logged(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)
    call_session = PorterCallSessionModel(
        lead=leads[0],
        destination_phone=leads[0].phone,
        status="created",
        prompt_version="porter-local-v1",
        knowledge_base_version="porter-kb-v1",
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    async_session.add(call_session)
    await async_session.flush()

    engine = PorterPolicyEngine()
    result = engine.check_response("You are approved.")
    logged = await engine.log_violations(
        async_session, call_session_id=call_session.id, result=result
    )
    await async_session.commit()

    rows = (
        await async_session.execute(
            select(PorterPolicyViolationModel).where(
                PorterPolicyViolationModel.call_session_id == call_session.id
            )
        )
    ).scalars().all()

    assert len(logged) == 1
    assert len(rows) == 1
    assert rows[0].violation_type == "approval_promise"
    assert rows[0].blocked_text == "You are approved."
    assert rows[0].safe_replacement == SAFE_APPROVAL_REPLACEMENT


async def test_no_policy_violation_logs_nothing(async_session):
    leads = await load_mock_porter_leads(async_session, replace=True)
    call_session = PorterCallSessionModel(
        lead=leads[0],
        destination_phone=leads[0].phone,
        status="created",
        prompt_version="porter-local-v1",
        knowledge_base_version="porter-kb-v1",
        human_review_required=True,
        crm_sync_status="not_ready",
    )
    async_session.add(call_session)
    await async_session.flush()

    engine = PorterPolicyEngine()
    result = engine.check_response(
        "Rates typically run somewhere between 0.2 and 2 percent."
    )
    logged = await engine.log_violations(
        async_session, call_session_id=call_session.id, result=result
    )
    await async_session.commit()

    assert logged == []
