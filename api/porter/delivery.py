"""Controlled spoken delivery for Porter cold-call decisions."""

from dataclasses import dataclass
from enum import StrEnum


class PorterAcknowledgement(StrEnum):
    NEUTRAL = "neutral"
    HARDSHIP = "hardship"
    CORRECTION = "correction"
    SATISFIED = "satisfied"
    SKEPTICAL = "skeptical"


@dataclass(frozen=True)
class PorterSpeechPlan:
    text: str
    acknowledgement: str | None = None


ACKNOWLEDGEMENTS: dict[PorterAcknowledgement, tuple[str, ...]] = {
    PorterAcknowledgement.NEUTRAL: ("Okay.", "Understood.", "That makes sense."),
    PorterAcknowledgement.HARDSHIP: ("I understand.", "I hear you."),
    PorterAcknowledgement.CORRECTION: ("Thanks for correcting me.", "Understood."),
    PorterAcknowledgement.SATISFIED: ("Understood.", "Good to know."),
    PorterAcknowledgement.SKEPTICAL: ("That's a fair question.", "I understand."),
}


PENDING_QUESTIONS: dict[str, tuple[str, ...]] = {
    "identity_confirmation": (
        "Is this {lead_name}?",
        "I just want to make sure I reached {lead_name}. Is that you?",
    ),
    "company_confirmation": (
        "Did I reach {lead_company}?",
        "Let me check the company instead. Is this {lead_company}?",
    ),
    "opening": (
        "Can I take about 30 seconds to see if this is relevant?",
        "Would it be okay if I briefly explain why I called?",
    ),
    "pitch_check_in": (
        "Does that sound relevant to your business?",
        "Is that something you deal with at all?",
    ),
    "industry": (
        "What kind of business are you in?",
        "What type of business do you run?",
    ),
    "relevance": (
        "Do you mainly bill other businesses or government customers?",
        "Are your customers mostly businesses or government customers?",
        "When you invoice, is that mainly to businesses or government customers?",
    ),
    "payment_timing": (
        "After you send an invoice, how long do customers usually take to pay?",
        "Let me put that more simply. Do customers pay right away, or on terms like 30 or 45 days?",
        "For example, is payment normally due now, in 30 days, or later?",
    ),
    "operational_impact": (
        "What's the main issue the wait creates for you?",
        "Does the wait affect payroll, growth, or something else?",
        "What would getting paid sooner make easier?",
    ),
    "current_funding": (
        "Are you already factoring those invoices, or covering the wait another way?",
    ),
    "funding_method": (
        "What are you using instead — internal cash, a credit line, or something else?",
        "How are you covering the wait for payment right now?",
    ),
    "provider_limitation": (
        "What's the main thing you would want improved, if anything?",
        "Is there anything about the current setup that makes the timing gap harder?",
        "What is the current arrangement not covering for you?",
    ),
    "monthly_invoicing_volume": (
        "Roughly how much do you invoice in a typical month?",
        "Is the monthly invoice volume closer to tens of thousands or hundreds of thousands?",
    ),
    "factor_satisfaction": (
        "Is the current factoring arrangement meeting your needs?",
        "Are you comfortable with the service and structure you have now?",
    ),
    "factor_exploration": (
        "Would you be open to a brief comparison with Porter?",
        "Would it be useful to see how another option compares?",
    ),
    "need_timing": (
        "Is this something you're looking at now, or later on?",
        "When would you want the timing gap addressed?",
        "Is there an upcoming point when this becomes more important?",
    ),
    "decision_authority": (
        "Would you be involved in reviewing an option like this?",
        "Are you part of the decision on working-capital options?",
    ),
    "problem_confirmation": (
        "Did I understand that correctly?",
        "Is that an accurate summary?",
    ),
    "advisor_offer": (
        "Would you like to speak with a Porter funding specialist?",
        "Would a short review with a funding specialist be useful?",
    ),
    "booking": (
        "What day and time works best for a funding specialist to call?",
        "When would be a convenient time for that call?",
    ),
    "phone": (
        "What's the best number for the specialist to use?",
        "Which phone number should the specialist call?",
    ),
    "email": (
        "What's the best business email for the confirmation?",
        "Which email should we use for the confirmation?",
    ),
    "full_name": (
        "What's your full name?",
        "What name should I put on the appointment?",
    ),
    "company_name": (
        "What company should I put with the appointment?",
        "Which company name should the specialist have?",
    ),
    "callback": (
        "What day and time would work better?",
        "When should Porter call you back?",
    ),
    "callback_today": (
        "Would today work for a quick call?",
    ),
    "callback_confirmation": (
        "Just to confirm, you'd like an advisor to call at the time you requested. Is that correct?",
    ),
    "same_company_role_check": (
        "Are you involved with financing or working-capital decisions there?",
    ),
    "alternate_contact_name": (
        "What's your name?",
    ),
    "referral_contact_details": (
        "Do you have their phone number or email?",
    ),
    "contact_referral": (
        "Who handles invoice-financing decisions there?",
        "Who would be the right person for a conversation about customer-payment timing?",
    ),
    "not_interested_reason": (
        "Is that because there isn't a current need, or because you already have it covered?",
        "Is the issue timing, or is this simply not relevant?",
    ),
}


def acknowledgement(
    kind: PorterAcknowledgement,
    *,
    previous: str | None,
    turn_index: int,
) -> str:
    choices = ACKNOWLEDGEMENTS[kind]
    for offset in range(len(choices)):
        candidate = choices[(turn_index + offset) % len(choices)]
        if candidate != previous:
            return candidate
    return choices[0]


def spoken_question(
    question: str,
    *,
    kind: PorterAcknowledgement | None = None,
    previous: str | None = None,
    turn_index: int = 0,
) -> PorterSpeechPlan:
    if kind is None:
        return PorterSpeechPlan(text=question)
    prefix = acknowledgement(kind, previous=previous, turn_index=turn_index)
    return PorterSpeechPlan(text=f"{prefix} {question}", acknowledgement=prefix)


def pending_question(
    stage: str,
    *,
    attempt: int = 0,
    lead_name: str | None = None,
    lead_company: str | None = None,
) -> str:
    questions = PENDING_QUESTIONS.get(stage, ("Could you say that another way?",))
    question = questions[min(max(attempt, 0), len(questions) - 1)]
    return question.format(
        lead_name=lead_name or "the person I was trying to reach",
        lead_company=lead_company or "the company I was trying to reach",
    )


def problem_summary(fields: dict[str, str]) -> str:
    statements: list[str] = []
    payment = _payment_phrase(fields.get("payment_timing"))
    impact = _impact_phrase(
        fields.get("operational_impact") or fields.get("cash_flow_challenge")
    )
    method = _method_phrase(fields.get("current_financing_solution"))
    if payment:
        statements.append(f"your customers usually pay {payment}")
    if impact:
        statements.append(impact)
    if method:
        statements.append(method)
    if not statements:
        return "Let me make sure I understood the timing gap. Did I get that right?"
    return f"Let me make sure I have this right. {_join_statements(statements)}. Is that accurate?"


def tailored_handoff(fields: dict[str, str]) -> str:
    raw_impact = (
        fields.get("operational_impact") or fields.get("cash_flow_challenge") or ""
    ).lower()
    provider_limitation = fields.get("provider_limitation", "").lower()
    if provider_limitation:
        return (
            "Porter can review whether a different setup could address what you want improved. "
            "Would you like to speak with a funding specialist?"
        )
    if "payroll" in raw_impact:
        focus = "the gap between customer payment and payroll"
    elif "inventory" in raw_impact:
        focus = "the timing pressure around inventory costs"
    elif "material" in raw_impact:
        focus = "the timing pressure around material costs"
    elif "growth" in raw_impact or "new work" in raw_impact:
        focus = "the payment timing that can limit new work"
    else:
        focus = "the payment-timing gap you described"
    if raw_impact:
        return (
            f"Based on what you described, Porter can review whether eligible invoices could help with {focus}. "
            "Would you like to speak with a funding specialist?"
        )
    return (
        "Based on what you described, Porter can review whether eligible invoices could help with the payment timing. "
        "Would you like to speak with a funding specialist?"
    )


def contains_multiple_questions(text: str) -> bool:
    return text.count("?") > 1


def _payment_phrase(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _clean_fact(value)
    for prefix in (
        "our customers pay in ",
        "customers pay in ",
        "they pay in ",
        "it takes ",
        "about ",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            if "pay in" in prefix:
                cleaned = f"in {cleaned}"
            elif prefix == "about ":
                cleaned = f"about {cleaned}"
            break
    if cleaned and cleaned[0].isdigit() and " " in cleaned:
        cleaned = f"in {cleaned}"
    return cleaned or None


def _impact_phrase(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if "payroll" in lowered:
        return "that puts pressure on payroll"
    if "inventory" in lowered:
        return "that makes inventory harder to cover"
    if "material" in lowered:
        return "that makes material costs harder to cover"
    if "growth" in lowered or "new work" in lowered or "new client" in lowered:
        return "that can limit new work"
    if "cash flow" in lowered or "cashflow" in lowered:
        return "that creates a cash-flow gap"
    cleaned = _clean_fact(value, limit=10)
    return f"that means {cleaned}" if cleaned else None


def _method_phrase(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if "factor" in lowered or "factory" in lowered:
        return "you're using a factoring company today"
    if "bank" in lowered or "credit line" in lowered or "line of credit" in lowered:
        return "you're using a credit line today"
    if "internal" in lowered or "our own cash" in lowered or "cash reserves" in lowered:
        return "you're covering it with internal cash"
    if "none" in lowered or lowered.strip() in {"no", "nothing"}:
        return "you don't have a separate funding method in place"
    return None


def _clean_fact(value: str, *, limit: int = 12) -> str:
    cleaned = " ".join(value.strip().rstrip(".!?").split())
    words = cleaned.split()
    if len(words) > limit:
        cleaned = " ".join(words[:limit])
    return cleaned


def _join_statements(statements: list[str]) -> str:
    if len(statements) == 1:
        return statements[0].capitalize()
    return f"{', '.join(statements[:-1]).capitalize()}, and {statements[-1]}"
