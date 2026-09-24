from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterLeadModel

MOCK_LEAD_SOURCE = "porter_mock_fixture"


@dataclass(frozen=True)
class MockPorterLead:
    company_name: str
    industry: str
    location: str
    contact_name: str
    phone: str
    email: str
    website: str
    evidence_summary: str
    evidence_url: str
    funding_signal_type: str
    lead_source: str
    lead_score_before_call: float
    notes: str

    def to_model(self) -> PorterLeadModel:
        return PorterLeadModel(**self.__dict__)


MOCK_PORTER_LEADS: tuple[MockPorterLead, ...] = (
    MockPorterLead(
        company_name="Fake Summit Staffing Group LLC",
        industry="Staffing and recruiting",
        location="Birmingham, AL",
        contact_name="Morgan Test",
        phone="+15550101001",
        email="morgan.test@summit-staffing.example.invalid",
        website="https://summit-staffing.example.invalid",
        evidence_summary=(
            "Fake fixture: hiring posts and payroll-heavy staffing model suggest "
            "possible short-term payroll funding pressure."
        ),
        evidence_url="https://signals.example.invalid/summit-staffing-payroll",
        funding_signal_type="payroll_pressure",
        lead_source=MOCK_LEAD_SOURCE,
        lead_score_before_call=88.0,
        notes="Synthetic staffing lead for local-only testing.",
    ),
    MockPorterLead(
        company_name="Fake Northstar Components Inc.",
        industry="Manufacturing",
        location="Greenville, SC",
        contact_name="Riley Test",
        phone="+15550101002",
        email="riley.test@northstar-components.example.invalid",
        website="https://northstar-components.example.invalid",
        evidence_summary=(
            "Fake fixture: announced a large customer order that may create a "
            "working-capital gap before receivables are collected."
        ),
        evidence_url="https://signals.example.invalid/northstar-large-order",
        funding_signal_type="large_customer_order",
        lead_source=MOCK_LEAD_SOURCE,
        lead_score_before_call=84.0,
        notes="Synthetic manufacturer lead for local-only testing.",
    ),
    MockPorterLead(
        company_name="Fake Blue Ridge Distribution Co.",
        industry="Wholesale distribution",
        location="Knoxville, TN",
        contact_name="Casey Test",
        phone="+15550101003",
        email="casey.test@blue-ridge-distribution.example.invalid",
        website="https://blue-ridge-distribution.example.invalid",
        evidence_summary=(
            "Fake fixture: distributor sells to B2B buyers with likely invoice "
            "timing mismatch between shipments and customer payment."
        ),
        evidence_url="https://signals.example.invalid/blue-ridge-ar-timing",
        funding_signal_type="ar_timing_signal",
        lead_source=MOCK_LEAD_SOURCE,
        lead_score_before_call=79.0,
        notes="Synthetic A/R timing lead for local-only testing.",
    ),
    MockPorterLead(
        company_name="Fake Atlas Field Services LLC",
        industry="B2B field services",
        location="Dallas, TX",
        contact_name="Jordan Test",
        phone="+15550101004",
        email="jordan.test@atlas-field-services.example.invalid",
        website="https://atlas-field-services.example.invalid",
        evidence_summary=(
            "Fake fixture: rapid regional expansion and new commercial contracts "
            "suggest growth-driven working capital needs."
        ),
        evidence_url="https://signals.example.invalid/atlas-growth-signal",
        funding_signal_type="growth_working_capital",
        lead_source=MOCK_LEAD_SOURCE,
        lead_score_before_call=76.0,
        notes="Synthetic B2B services lead for local-only testing.",
    ),
    MockPorterLead(
        company_name="Fake Maple Street Cafe LLC",
        industry="Consumer retail food service",
        location="Mobile, AL",
        contact_name="Taylor Test",
        phone="+15550101005",
        email="taylor.test@maple-street-cafe.example.invalid",
        website="https://maple-street-cafe.example.invalid",
        evidence_summary=(
            "Fake fixture: mostly consumer payments, limited B2B invoices, and no "
            "clear receivables signal."
        ),
        evidence_url="https://signals.example.invalid/maple-street-unqualified",
        funding_signal_type="unqualified_consumer_retail",
        lead_source=MOCK_LEAD_SOURCE,
        lead_score_before_call=22.0,
        notes="Synthetic unqualified lead for local-only testing.",
    ),
)


def get_mock_porter_leads() -> tuple[MockPorterLead, ...]:
    return MOCK_PORTER_LEADS


async def load_mock_porter_leads(
    session: AsyncSession, *, replace: bool = False
) -> Sequence[PorterLeadModel]:
    if replace:
        await session.execute(
            delete(PorterLeadModel).where(
                PorterLeadModel.lead_source == MOCK_LEAD_SOURCE
            )
        )
        await session.flush()

    loaded: list[PorterLeadModel] = []
    for fixture in MOCK_PORTER_LEADS:
        existing = await session.scalar(
            select(PorterLeadModel).where(
                PorterLeadModel.lead_source == fixture.lead_source,
                PorterLeadModel.website == fixture.website,
            )
        )
        if existing is not None:
            loaded.append(existing)
            continue

        lead = fixture.to_model()
        session.add(lead)
        loaded.append(lead)

    await session.flush()
    return loaded
