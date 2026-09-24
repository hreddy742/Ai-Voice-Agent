from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PorterTranscriptTurnModel
from api.porter.llm import PorterLLMAdapter
from api.porter.local_text_demo import (
    PorterTextConversationSummary,
    ScriptedUserTurn,
    run_local_text_conversation,
)
from api.porter.tts import SafeTTSAdapter, StubTTSAdapter, TTSAdapter, TTSRequest


@dataclass(frozen=True)
class PorterLocalWebCallResult:
    summary: PorterTextConversationSummary
    assistant_audio_count: int
    transcript: tuple[dict[str, object], ...]
    telephony_enabled: bool = False
    crm_sync_enabled: bool = False
    email_enabled: bool = False
    sms_enabled: bool = False


async def run_porter_local_web_call_simulation(
    session: AsyncSession,
    *,
    lead_id: int,
    user_turns: Sequence[str],
    llm_adapter: PorterLLMAdapter | None = None,
    tts_adapter: TTSAdapter | None = None,
    synthesize_audio: bool = True,
) -> PorterLocalWebCallResult:
    if not user_turns:
        raise ValueError("At least one user turn is required.")

    summary = await run_local_text_conversation(
        session,
        lead_id=lead_id,
        user_turns=[ScriptedUserTurn(text=turn) for turn in user_turns],
        llm_adapter=llm_adapter,
    )

    transcript_rows = (
        await session.execute(
            select(PorterTranscriptTurnModel)
            .where(PorterTranscriptTurnModel.call_session_id == summary.call_session_id)
            .order_by(PorterTranscriptTurnModel.timestamp, PorterTranscriptTurnModel.id)
        )
    ).scalars().all()

    assistant_audio_count = 0
    if synthesize_audio:
        adapter = SafeTTSAdapter(tts_adapter or StubTTSAdapter())
        with TemporaryDirectory(prefix="porter-local-web-call-") as temp_dir:
            for index, turn in enumerate(transcript_rows):
                if turn.speaker != "assistant":
                    continue
                await adapter.synthesize(
                    TTSRequest(
                        text=turn.text,
                        output_path=Path(temp_dir) / f"assistant-{index}.wav",
                    )
                )
                assistant_audio_count += 1

    return PorterLocalWebCallResult(
        summary=summary,
        assistant_audio_count=assistant_audio_count,
        transcript=tuple(_turn_to_dict(turn) for turn in transcript_rows),
    )


def _turn_to_dict(turn: PorterTranscriptTurnModel) -> dict[str, object]:
    return {
        "id": turn.id,
        "speaker": turn.speaker,
        "text": turn.text,
        "conversation_state": turn.conversation_state,
        "timestamp": turn.timestamp.isoformat(),
        "raw_metadata": turn.raw_metadata,
    }


def local_web_call_result_to_dict(result: PorterLocalWebCallResult) -> dict[str, object]:
    return {
        "summary": asdict(result.summary),
        "assistant_audio_count": result.assistant_audio_count,
        "transcript": list(result.transcript),
        "telephony_enabled": result.telephony_enabled,
        "crm_sync_enabled": result.crm_sync_enabled,
        "email_enabled": result.email_enabled,
        "sms_enabled": result.sms_enabled,
    }
