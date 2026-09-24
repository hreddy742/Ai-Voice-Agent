import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterPolicyViolationModel
from api.porter.cold_call_scripts import (
    ALREADY_HAS_FACTOR,
    BOOKING,
    COLD_CALL_PERMISSION,
    DISCLOSURE,
    EXIT,
    HAPPY_FACTOR_EXPLORE,
    NOT_INTERESTED,
    NOT_INTERESTED_CLOSE,
    OPENER,
    PITCH,
    QUALIFIER_OPENING,
    RATES,
    WARM_CLOSE,
    WRONG_NUMBER_CLOSE,
)


SAFE_RATE_REPLACEMENT = "Rates depend on qualification and review."
SAFE_APPROVAL_REPLACEMENT = (
    "Right, I can't confirm approval without one of our financing advisors reviewing the details."
)
SAFE_FUNDING_REPLACEMENT = (
    "Got it — that depends on the business details and one of our financing advisors reviewing it."
)
SAFE_REVIEW_REPLACEMENT = "Got it — I can send this to the Porter team for review."
SAFE_LEGAL_REPLACEMENT = (
    "Right, I can't give legal advice or make a guarantee there."
)


@dataclass(frozen=True)
class PolicyRule:
    violation_type: str
    pattern: re.Pattern[str]
    safe_replacement: str


@dataclass(frozen=True)
class PolicyViolation:
    violation_type: str
    blocked_text: str
    safe_replacement: str


@dataclass(frozen=True)
class PolicyCheckResult:
    allowed: bool
    original_text: str
    safe_text: str
    violations: tuple[PolicyViolation, ...]


class PorterPolicyEngine:
    def __init__(self, rules: Iterable[PolicyRule] | None = None) -> None:
        self._rules = tuple(rules or DEFAULT_POLICY_RULES)

    def check_response(self, text: str) -> PolicyCheckResult:
        if text in APPROVED_COLD_CALL_SCRIPTS:
            return PolicyCheckResult(
                allowed=True,
                original_text=text,
                safe_text=text,
                violations=(),
            )
        violations = tuple(self._find_violations(text))
        if not violations:
            return PolicyCheckResult(
                allowed=True,
                original_text=text,
                safe_text=text,
                violations=(),
            )

        safe_text = " ".join(
            dict.fromkeys(violation.safe_replacement for violation in violations)
        )
        return PolicyCheckResult(
            allowed=False,
            original_text=text,
            safe_text=safe_text,
            violations=violations,
        )

    async def log_violations(
        self,
        session: AsyncSession,
        *,
        call_session_id: int,
        result: PolicyCheckResult,
    ) -> Sequence[PorterPolicyViolationModel]:
        logged: list[PorterPolicyViolationModel] = []
        for violation in result.violations:
            model = PorterPolicyViolationModel(
                call_session_id=call_session_id,
                violation_type=violation.violation_type,
                blocked_text=violation.blocked_text,
                safe_replacement=violation.safe_replacement,
            )
            session.add(model)
            logged.append(model)
        await session.flush()
        return logged

    def _find_violations(self, text: str) -> Iterable[PolicyViolation]:
        for rule in self._rules:
            if rule.pattern.search(text):
                yield PolicyViolation(
                    violation_type=rule.violation_type,
                    blocked_text=text,
                    safe_replacement=rule.safe_replacement,
                )


def _rule(violation_type: str, pattern: str, replacement: str) -> PolicyRule:
    return PolicyRule(
        violation_type=violation_type,
        pattern=re.compile(pattern, re.IGNORECASE),
        safe_replacement=replacement,
    )


DEFAULT_POLICY_RULES: tuple[PolicyRule, ...] = (
    _rule(
        "rate_claim",
        r"\b(rate|fee|factoring fee|discount rate)\b[^.?!]{0,80}\b("
        r"(?!0\.2\s*(?:-|to)\s*2\s*(?:%|percent))"
        r"\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*(?:percent|points?)\b"
        r")",
        SAFE_RATE_REPLACEMENT,
    ),
    _rule(
        "approval_promise",
        r"\b(you(?:'re| are)?|your business(?: is)?)\s+("
        r"approved|preapproved|pre-approved|qualified|accepted"
        r")\b",
        SAFE_APPROVAL_REPLACEMENT,
    ),
    _rule(
        "definite_funding_claim",
        r"\b(we|porter)\s+(can|will|definitely can|absolutely can)\s+"
        r"(fund|finance|approve)\b|\bwe can definitely fund\b",
        SAFE_FUNDING_REPLACEMENT,
    ),
    _rule(
        "guaranteed_funding_claim",
        r"\b(guaranteed funding|funding is guaranteed|guarantee(?:d)? "
        r"(?:approval|funding)|100%\s+(?:approved|guaranteed))\b",
        SAFE_FUNDING_REPLACEMENT,
    ),
    _rule(
        "no_review_claim",
        r"\b(no review is needed|without (?:any )?review|no underwriting "
        r"(?:needed|required)|skip (?:the )?review)\b",
        SAFE_REVIEW_REPLACEMENT,
    ),
    _rule(
        "legal_or_compliance_claim",
        r"\b(legally risk[- ]free|risk[- ]free legally|compliance is guaranteed|"
        r"this is legal advice|no legal risk|fully compliant guaranteed)\b",
        SAFE_LEGAL_REPLACEMENT,
    ),
    _rule(
        "forbidden_corporate_tone",
        r"\b(Absolutely|Certainly|Wonderful|Leverage|Solutions|Utilize|Transparent|"
        r"Outstanding|Facilitate|Endeavor)\b",
        "Yeah, let me keep it simple.",
    ),
    _rule(
        "porter_already_reviewed_claim",
        r"\b(porter|we)\s+(already|has already|have already)\s+"
        r"(reviewed|approved|underwritten)\b",
        SAFE_REVIEW_REPLACEMENT,
    ),
)


APPROVED_COLD_CALL_SCRIPTS = frozenset(
    {
        OPENER,
        COLD_CALL_PERMISSION,
        PITCH,
        QUALIFIER_OPENING,
        ALREADY_HAS_FACTOR,
        NOT_INTERESTED,
        RATES,
        BOOKING,
        DISCLOSURE,
        EXIT,
        HAPPY_FACTOR_EXPLORE,
        WARM_CLOSE,
        NOT_INTERESTED_CLOSE,
        WRONG_NUMBER_CLOSE,
    }
)
