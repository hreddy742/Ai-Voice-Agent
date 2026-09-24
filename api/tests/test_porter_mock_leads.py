from sqlalchemy import func, select

from api.db.models import PorterCallSessionModel, PorterLeadModel
from api.porter.mock_leads import (
    MOCK_LEAD_SOURCE,
    get_mock_porter_leads,
    load_mock_porter_leads,
)


def test_mock_porter_leads_cover_required_scenarios():
    leads = get_mock_porter_leads()
    signal_types = {lead.funding_signal_type for lead in leads}

    assert len(leads) == 5
    assert {
        "payroll_pressure",
        "large_customer_order",
        "ar_timing_signal",
        "growth_working_capital",
        "unqualified_consumer_retail",
    } == signal_types


def test_mock_porter_leads_are_complete_and_clearly_fake():
    for lead in get_mock_porter_leads():
        assert lead.company_name.startswith("Fake ")
        assert lead.contact_name.endswith(" Test")
        assert lead.phone.startswith("+15550101")
        assert lead.email.endswith(".example.invalid")
        assert ".example.invalid" in lead.website
        assert ".example.invalid" in lead.evidence_url
        assert "Fake fixture:" in lead.evidence_summary
        assert lead.lead_source == MOCK_LEAD_SOURCE
        assert lead.lead_score_before_call >= 0
        assert lead.notes.startswith("Synthetic ")


async def test_mock_porter_leads_load_idempotently(async_session):
    first_load = await load_mock_porter_leads(async_session)
    await async_session.commit()
    second_load = await load_mock_porter_leads(async_session)
    await async_session.commit()

    total = await async_session.scalar(
        select(func.count(PorterLeadModel.id)).where(
            PorterLeadModel.lead_source == MOCK_LEAD_SOURCE
        )
    )

    assert len(first_load) == 5
    assert len(second_load) == 5
    assert total == 5


async def test_mock_porter_leads_replace_existing_fixture_rows(async_session):
    await load_mock_porter_leads(async_session)
    await async_session.commit()

    lead = await async_session.scalar(
        select(PorterLeadModel).where(PorterLeadModel.lead_source == MOCK_LEAD_SOURCE)
    )
    lead.company_name = "Mutated Fixture Lead"
    await async_session.commit()

    await load_mock_porter_leads(async_session, replace=True)
    await async_session.commit()

    names = (
        await async_session.execute(
            select(PorterLeadModel.company_name)
            .where(PorterLeadModel.lead_source == MOCK_LEAD_SOURCE)
            .order_by(PorterLeadModel.id)
        )
    ).scalars().all()

    assert "Mutated Fixture Lead" not in names
    assert len(names) == 5


async def test_mock_porter_leads_can_link_to_call_sessions(async_session):
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
    await async_session.commit()

    refreshed = await async_session.get(PorterCallSessionModel, call_session.id)

    assert refreshed.lead.lead_source == MOCK_LEAD_SOURCE
    assert refreshed.lead.funding_signal_type == "payroll_pressure"
