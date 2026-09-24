from dataclasses import dataclass
from typing import Mapping, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterCallSessionModel, PorterKnowledgeBaseChunkModel


PORTER_KB_VERSION = "porter-kb-v4-approved-estimates"
SAFE_UNKNOWN_ANSWER = "Got it — let me get one of our financing advisors to dig into that with you."
SAFE_RATE_ANSWER = (
    "Rates typically run between 0.2 and 2 percent, depending on invoice volume and "
    "customers. Porter builds the actual number after reviewing the business."
)
SAFE_INDUSTRY_HANDOFF_ANSWER = (
    "Yeah, that depends on the details — let me get one of our financing "
    "advisors to look at that with you."
)


@dataclass(frozen=True)
class PorterKnowledgeSeedChunk:
    source_title: str
    chunk_index: int
    chunk_text: str
    topics: tuple[str, ...]
    source_url: str | None = None

    def to_model(self, version: str = PORTER_KB_VERSION) -> PorterKnowledgeBaseChunkModel:
        return PorterKnowledgeBaseChunkModel(
            knowledge_base_version=version,
            source_title=self.source_title,
            source_url=self.source_url,
            chunk_index=self.chunk_index,
            chunk_text=self.chunk_text,
            chunk_metadata={"topics": list(self.topics), "approved": True},
        )


@dataclass(frozen=True)
class PorterKnowledgeAnswer:
    answer_text: str
    knowledge_base_version: str
    chunk_ids: tuple[int, ...]
    source_titles: tuple[str, ...]
    needs_human_handoff: bool = False


PORTER_CAPITAL_KNOWLEDGE = """
COMPANY OVERVIEW
Porter Capital is an invoice factoring company based in Birmingham, Alabama.
We help B2B businesses turn unpaid invoices into working capital instead of
waiting weeks or months to get paid.

WHO WE SERVE
We work with all kinds of B2B businesses that invoice other businesses or
government clients. Staffing, transportation, manufacturing, distribution,
tech, government contracting, and a broad range of similar B2B companies.
Do not proactively mention industry exclusions. If asked directly about a
specific industry's eligibility, route to a human advisor rather than
confirming or denying fit. Never say Porter excludes trucking or construction.
Porter actively works with transportation and has a dedicated freight funding
division. For construction specifically, route to a human advisor if it comes up.

RATES
Honestly, it kind of depends on a few things — how much you're invoicing,
who your customers are, stuff like that. Rates typically run somewhere
between 0.2 and 2 percent, but we'd actually build a custom number for you
once we know more about your business. Aiva may state this range.
Never give a specific number, percentage, or estimate beyond this stated range.

FUNDING SPEED
Once you're set up with us, funding is usually under 48 hours after you submit
an invoice. This applies to ongoing funding speed once a client is set up.

PRELIMINARY FUNDING ILLUSTRATIONS
John approved two preliminary illustrations: eligible accounts receivable
multiplied by 90 percent, and annual revenue multiplied by 10 percent. These are
illustrations for advisor review only. Never present either result as approval,
a guarantee, a commitment, a credit decision, a final proposal, or funding that
is available to the prospect.

FEES
Fees really depend on how the program ends up being structured for you.
That's something we'd go over in the actual proposal, not something I can
throw a number at you right now. No specific fee amounts.

CONTRACT TERMS
That kind of thing varies depending on the situation. One of our advisors can
walk through what the options would actually look like. No specific terms,
lengths, or commitments.

SELECTIVE VS FULL FACTORING
That depends on the setup. Get the prospect talking to someone who can dig
into that with them. Do not explain the difference.

DIFFERENTIATION
Porter has been doing this for decades and has funded billions to businesses
around the country. The people prospects work with can make decisions fast and
solve problems in real time. Porter is big on service, with a dedicated person
who knows the business instead of a random queue.

INTERESTED PROSPECT
Schedule a call with one of our financing advisors and collect contact
information. Never promise approval, pricing, funding amounts, or timing beyond
the approved funding-speed statement. Collect full name, company name, phone,
email, best time to call, estimated monthly invoicing volume, industry, current
financing solution if any, and biggest cash flow challenge.

COMPLIANCE
Never say guaranteed approval, guaranteed funding, guaranteed rate, we are
cheaper than everyone else, we can fund anyone, or anything that sounds like a
financial guarantee.

TONE
Be professional, conversational, consultative, respectful of time, and focused
on understanding the business before discussing options. Use contractions.
Use natural connectors like Yeah, Right, Got it, Oh, So, and Sure. Never use
Hello, Absolutely, Certainly, Wonderful, Leverage, Solutions, Utilize,
Transparent, Outstanding, Facilitate, or Endeavor. One thought per response.
Mirror the prospect's own words.
"""


APPROVED_PORTER_KB_CHUNKS: tuple[PorterKnowledgeSeedChunk, ...] = (
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - company overview",
        chunk_index=0,
        topics=("company_overview", "invoice_factoring", "factoring"),
        chunk_text=(
            "Porter Capital is an invoice factoring company based in Birmingham, "
            "Alabama. We help B2B businesses turn unpaid invoices into working "
            "capital instead of waiting weeks or months to get paid."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - who we serve",
        chunk_index=0,
        topics=("industries", "b2b_invoices", "advisor_handoff"),
        chunk_text=(
            "Porter works with B2B businesses that invoice other businesses or "
            "government clients, including staffing, transportation, manufacturing, "
            "distribution, tech, government contracting, and a broad range of similar "
            "B2B companies. If asked about a specific industry's eligibility, route "
            "to a human advisor rather than confirming or denying fit."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - rates",
        chunk_index=0,
        topics=("rates", "pricing"),
        chunk_text=(
            "Rates kind of depend on how much the prospect is invoicing and who "
            "their customers are. Rates typically run somewhere between 0.2 and "
            "2 percent, but Porter builds a custom number once it knows more "
            "about the business. Do not give a specific number beyond this range."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - funding speed",
        chunk_index=0,
        topics=("funding_speed", "invoices"),
        chunk_text=(
            "Once a client is set up with Porter, ongoing funding is usually under "
            "48 hours after they submit an invoice."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John confirmation - preliminary funding illustrations",
        chunk_index=0,
        topics=("funding_estimate", "advisor_handoff", "compliance"),
        chunk_text=(
            "John approved two preliminary funding illustrations: eligible accounts "
            "receivable multiplied by 90 percent, and annual revenue multiplied by "
            "10 percent. Either result is an illustration for advisor review only, "
            "not approval, a guarantee, a commitment, a credit decision, a final "
            "proposal, or available funding."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - fees",
        chunk_index=0,
        topics=("fees", "proposal", "advisor_handoff"),
        chunk_text=(
            "Fees depend on how the program is structured. Porter would go over "
            "that in the actual proposal, not throw out a number during the call. "
            "No specific fee amounts."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - contract terms",
        chunk_index=0,
        topics=("contract_terms", "advisor_handoff"),
        chunk_text=(
            "Contract terms vary depending on the situation. One of our financing "
            "advisors can walk the prospect through what the options would look like. "
            "No specific terms, lengths, or commitments."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - selective vs full factoring",
        chunk_index=0,
        topics=("selective_factoring", "full_factoring", "advisor_handoff"),
        chunk_text=(
            "Selective versus full factoring depends on the prospect's setup. Get "
            "them talking to someone who can dig into that with them. Do not explain "
            "the difference."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - differentiation",
        chunk_index=0,
        topics=("differentiation", "service", "experience"),
        chunk_text=(
            "Porter has been doing this for decades and has funded billions to "
            "businesses around the country. The people prospects work with can make "
            "decisions fast and solve problems in real time. Porter is big on service, "
            "with a dedicated person who knows the business."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - interested prospect",
        chunk_index=0,
        topics=("interested", "advisor_handoff", "qualification_fields"),
        chunk_text=(
            "When a prospect is interested, schedule a call with one of our financing "
            "advisors and collect full name, company name, phone, email, best time "
            "to call, estimated monthly invoicing volume, industry, current financing "
            "solution if any, and biggest cash flow challenge."
        ),
    ),
    PorterKnowledgeSeedChunk(
        source_title="John questionnaire - compliance and tone",
        chunk_index=0,
        topics=("compliance", "tone", "forbidden_language"),
        chunk_text=(
            "Never say guaranteed approval, guaranteed funding, guaranteed rate, "
            "we are cheaper than everyone else, or we can fund anyone. Use a "
            "professional, conversational, consultative tone with contractions, "
            "natural connectors, one thought per response, and no scripted corporate "
            "phrases."
        ),
    ),
)


TOPIC_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "company_overview": ("porter", "company", "based", "birmingham", "alabama"),
    "invoice_factoring": ("invoice factoring", "factoring", "invoice", "invoices"),
    "ar_factoring": ("a/r", "ar ", "accounts receivable", "receivables"),
    "b2b_invoices": ("b2b", "business", "government", "client", "customer"),
    "industries": (
        "industry",
        "industries",
        "staffing",
        "transportation",
        "trucking",
        "freight",
        "manufacturing",
        "distribution",
        "tech",
        "government",
        "construction",
    ),
    "rates": ("rate", "rates", "pricing", "percent", "percentage"),
    "fees": ("fee", "fees", "cost"),
    "funding_speed": ("speed", "fast", "quick", "24", "48", "fund"),
    "funding_estimate": (
        "estimate",
        "funding amount",
        "how much",
        "accounts receivable",
        "annual revenue",
        "90 percent",
        "10 percent",
    ),
    "contract_terms": ("contract", "term", "terms", "commitment", "length"),
    "selective_factoring": ("selective", "spot", "choose invoices"),
    "full_factoring": ("full factoring", "all invoices"),
    "differentiation": ("different", "why porter", "decades", "billions"),
    "service": ("service", "dedicated", "rep", "advisor"),
    "interested": ("interested", "next step", "follow up", "call"),
    "qualification_fields": ("name", "email", "phone", "volume", "cash flow"),
    "advisor_handoff": ("advisor", "human", "specialist"),
    "compliance": ("guarantee", "guaranteed", "approval", "cheaper", "fund anyone"),
    "tone": ("tone", "say", "sound"),
}


async def seed_porter_knowledge_base(
    session: AsyncSession,
    *,
    version: str = PORTER_KB_VERSION,
    replace: bool = False,
) -> Sequence[PorterKnowledgeBaseChunkModel]:
    if replace:
        await session.execute(
            delete(PorterKnowledgeBaseChunkModel).where(
                PorterKnowledgeBaseChunkModel.knowledge_base_version == version
            )
        )
        await session.flush()

    existing_rows = (
        await session.execute(
            select(PorterKnowledgeBaseChunkModel).where(
                PorterKnowledgeBaseChunkModel.knowledge_base_version == version
            )
        )
    ).scalars().all()
    existing_by_key = {
        (row.source_title, row.chunk_index): row for row in existing_rows
    }

    loaded: list[PorterKnowledgeBaseChunkModel] = []
    for fixture in APPROVED_PORTER_KB_CHUNKS:
        existing = existing_by_key.get((fixture.source_title, fixture.chunk_index))
        if existing is not None:
            loaded.append(existing)
            continue

        model = fixture.to_model(version)
        session.add(model)
        loaded.append(model)

    await session.flush()
    return loaded


async def retrieve_porter_knowledge(
    session: AsyncSession,
    query: str,
    *,
    version: str = PORTER_KB_VERSION,
    limit: int = 3,
) -> Sequence[PorterKnowledgeBaseChunkModel]:
    if limit <= 0:
        return []

    rows = (
        await session.execute(
            select(PorterKnowledgeBaseChunkModel).where(
                PorterKnowledgeBaseChunkModel.knowledge_base_version == version
            )
        )
    ).scalars().all()

    scored = [
        (score_knowledge_chunk(query, row), row)
        for row in rows
        if score_knowledge_chunk(query, row) > 0
    ]
    scored.sort(key=lambda item: (-item[0], item[1].source_title, item[1].chunk_index))
    return [row for _, row in scored[:limit]]


async def answer_from_porter_knowledge(
    session: AsyncSession,
    query: str,
    *,
    version: str = PORTER_KB_VERSION,
) -> PorterKnowledgeAnswer:
    if _is_rate_question(query):
        chunks = await retrieve_porter_knowledge(session, "rates safety", version=version)
        return _build_answer(
            SAFE_RATE_ANSWER,
            version=version,
            chunks=chunks,
        )

    if _is_specific_industry_question(query):
        chunks = await retrieve_porter_knowledge(session, "industry advisor", version=version)
        return _build_answer(
            SAFE_INDUSTRY_HANDOFF_ANSWER,
            version=version,
            chunks=chunks,
            needs_human_handoff=True,
        )

    if _is_unsupported_question(query):
        return PorterKnowledgeAnswer(
            answer_text=SAFE_UNKNOWN_ANSWER,
            knowledge_base_version=version,
            chunk_ids=(),
            source_titles=(),
            needs_human_handoff=True,
        )

    chunks = await retrieve_porter_knowledge(session, query, version=version)
    if not chunks:
        return PorterKnowledgeAnswer(
            answer_text=SAFE_UNKNOWN_ANSWER,
            knowledge_base_version=version,
            chunk_ids=(),
            source_titles=(),
            needs_human_handoff=True,
        )

    answer_text = " ".join(chunk.chunk_text for chunk in chunks)
    return _build_answer(answer_text, version=version, chunks=chunks)


async def mark_call_session_knowledge_version(
    session: AsyncSession,
    *,
    call_session_id: int,
    version: str = PORTER_KB_VERSION,
) -> PorterCallSessionModel:
    call_session = await session.get(PorterCallSessionModel, call_session_id)
    if call_session is None:
        raise ValueError(f"Porter call session {call_session_id} was not found.")
    call_session.knowledge_base_version = version
    await session.flush()
    return call_session


def score_knowledge_chunk(query: str, chunk: PorterKnowledgeBaseChunkModel) -> int:
    normalized = _normalize(query)
    if not normalized:
        return 0

    metadata = chunk.chunk_metadata or {}
    topics = tuple(metadata.get("topics") or ())
    topic_score = 0
    for topic in topics:
        keywords = TOPIC_KEYWORDS.get(str(topic), ())
        topic_score += sum(3 for keyword in keywords if keyword in normalized)

    text_score = sum(
        1 for token in set(normalized.split()) if len(token) > 3 and token in chunk.chunk_text.lower()
    )
    return topic_score + text_score


def _build_answer(
    answer_text: str,
    *,
    version: str,
    chunks: Sequence[PorterKnowledgeBaseChunkModel],
    needs_human_handoff: bool = False,
) -> PorterKnowledgeAnswer:
    return PorterKnowledgeAnswer(
        answer_text=answer_text,
        knowledge_base_version=version,
        chunk_ids=tuple(chunk.id for chunk in chunks if chunk.id is not None),
        source_titles=tuple(dict.fromkeys(chunk.source_title for chunk in chunks)),
        needs_human_handoff=needs_human_handoff,
    )


def _is_rate_question(query: str) -> bool:
    normalized = _normalize(query)
    return any(word in normalized for word in ("rate", "rates", "fee", "fees", "cost"))


def _is_specific_industry_question(query: str) -> bool:
    normalized = _normalize(query)
    industry_words = (
        "trucking",
        "transportation",
        "freight",
        "construction",
        "staffing",
        "manufacturing",
        "distribution",
        "tech",
        "government contractor",
        "government contracting",
    )
    eligibility_words = ("eligible", "qualify", "work with", "serve", "industry", "industries")
    return any(word in normalized for word in industry_words) and any(
        word in normalized for word in eligibility_words
    )


def _is_unsupported_question(query: str) -> bool:
    normalized = _normalize(query)
    unsupported_markers = (
        "lease",
        "legal",
        "tax",
        "accounting",
        "investment advice",
        "personal loan",
        "consumer",
    )
    return any(marker in normalized for marker in unsupported_markers)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())
