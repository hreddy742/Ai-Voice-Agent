"""Phone-level do-not-call enforcement for Porter."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterLeadModel, PorterPhoneSuppressionModel


def normalize_porter_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 10:
        digits = f"1{digits}"
    if not 8 <= len(digits) <= 15 or digits.startswith("0"):
        raise ValueError("Porter destination phone must be a valid E.164 number.")
    return f"+{digits}"


async def is_porter_phone_suppressed(session: AsyncSession, phone: str) -> bool:
    normalized = normalize_porter_phone(phone)
    return (
        await session.scalar(
            select(PorterPhoneSuppressionModel.id).where(
                PorterPhoneSuppressionModel.phone == normalized
            )
        )
    ) is not None


async def suppress_porter_phone(
    session: AsyncSession,
    *,
    lead: PorterLeadModel,
    call_session_id: int,
    reason: str = "caller_requested_do_not_call",
) -> PorterPhoneSuppressionModel:
    normalized = normalize_porter_phone(lead.phone)
    suppression = await session.scalar(
        select(PorterPhoneSuppressionModel).where(
            PorterPhoneSuppressionModel.phone == normalized
        )
    )
    now = datetime.now(UTC)
    if suppression is None:
        suppression = PorterPhoneSuppressionModel(
            phone=normalized,
            reason=reason,
            source_call_session_id=call_session_id,
            created_at=now,
            updated_at=now,
        )
        session.add(suppression)
    else:
        suppression.reason = reason
        suppression.source_call_session_id = call_session_id
        suppression.updated_at = now

    lead.do_not_call = True
    lead.suppressed_at = now
    lead.suppression_reason = reason
    await session.flush()
    return suppression
