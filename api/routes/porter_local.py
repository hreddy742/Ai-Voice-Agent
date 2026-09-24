import asyncio
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

from api.db import db_client
from api.db.models import UserModel
from api.porter.call_finalization import finalize_porter_call
from api.porter.live_voice import (
    PorterLiveVoiceError,
    PorterLiveVoiceNoSpeechError,
    PorterLiveVoiceTurnResult,
    PorterVoiceOpenerResult,
    prewarm_default_stt_model,
    run_porter_live_voice_turn,
    run_porter_voice_opener,
)
from api.porter.local_web_call import (
    local_web_call_result_to_dict,
    run_porter_local_web_call_simulation,
)
from api.porter.llm import MockPorterLLMAdapter, OllamaLLMAdapter
from api.porter.mock_leads import load_mock_porter_leads
from api.porter.pcm_stream import PorterPCMStreamBuffer, PorterPCMStreamError, write_pcm16_wav
from api.porter.review import (
    get_porter_call_session_review,
    list_porter_call_sessions,
)
from api.porter.runtime import (
    PorterRuntimeReadiness,
    PorterVoiceRuntimeWarmResult,
    inspect_porter_voice_runtime,
    prewarm_porter_voice_scripts,
)
from api.porter.tts import PorterTTSError
from api.services.auth.depends import get_user, get_user_ws


router = APIRouter(prefix="/porter-local", tags=["porter-local"])


class PorterLocalWebCallSimulationRequest(BaseModel):
    lead_id: int | None = None
    user_turns: list[str] = Field(min_length=1)
    synthesize_audio: bool = True
    use_live_llm: bool = False
    mock_llm_response: str = "I can send this to the Porter team for review."


class PorterLocalWebCallSimulationResponse(BaseModel):
    summary: dict[str, Any]
    assistant_audio_count: int
    transcript: list[dict[str, Any]]
    telephony_enabled: bool
    crm_sync_enabled: bool
    email_enabled: bool
    sms_enabled: bool


class PorterCallSessionListResponse(BaseModel):
    sessions: list[dict[str, Any]]


class PorterCallSessionReviewResponse(BaseModel):
    session: dict[str, Any]


class PorterLiveVoiceTurnResponse(BaseModel):
    call_session_id: int
    lead_id: int
    attempt_id: str
    destination_phone: str
    user_text: str
    assistant_text: str
    assistant_audio_base64: str
    assistant_audio_content_type: str
    audio_streamed: bool
    vad: dict[str, Any]
    stt: dict[str, Any]
    tts: dict[str, Any]
    llm: dict[str, Any]
    timings_ms: dict[str, float]
    transcript: list[dict[str, Any]]
    should_close: bool


class PorterVoiceOpenerResponse(BaseModel):
    call_session_id: int
    lead_id: int
    attempt_id: str
    destination_phone: str
    assistant_text: str
    assistant_audio_base64: str
    assistant_audio_content_type: str
    tts: dict[str, Any]
    transcript: list[dict[str, Any]]


class PorterRuntimeComponentResponse(BaseModel):
    name: str
    provider: str
    model: str
    ready: bool
    production_recommended: bool
    details: dict[str, Any]


class PorterRuntimeReadinessResponse(BaseModel):
    ready: bool
    fast_voice_mode: bool
    default_voice: str
    recommended_target_ms: int
    notes: list[str]
    components: list[PorterRuntimeComponentResponse]


class PorterVoiceRuntimeWarmRequest(BaseModel):
    voice: str | None = None
    script_names: list[str] | None = None


class PorterVoiceScriptWarmResponse(BaseModel):
    script_name: str
    text: str
    cache_hit: bool
    elapsed_ms: float
    tts: dict[str, Any]


class PorterVoiceRuntimeWarmResponse(BaseModel):
    voice: str
    warmed_count: int
    cache_hit_count: int
    total_elapsed_ms: float
    scripts: list[PorterVoiceScriptWarmResponse]


@router.websocket("/voice-stream")
async def porter_voice_stream(
    websocket: WebSocket,
    lead_id: int | None = None,
    _: UserModel = Depends(get_user_ws),
) -> None:
    await websocket.accept()
    asyncio.create_task(_prewarm_porter_stt_after_opener())
    pcm = PorterPCMStreamBuffer()
    call_session_id: int | None = None
    try:
        try:
            async with db_client.async_session() as session:
                opener = await run_porter_voice_opener(session, lead_id=lead_id)
                await session.commit()
                call_session_id = opener.call_session_id
        except Exception:
            logger.exception("Porter voice stream opener failed")
            await websocket.send_json(
                {
                    "type": "error",
                    "payload": {
                        "code": "opener_failed",
                        "message": "Aiva could not open the call.",
                        "retryable": True,
                    },
                }
            )
            await websocket.close(code=1011)
            return

        await websocket.send_json(
            {"type": "opener", "payload": _voice_opener_result_to_response(opener).model_dump(mode="json")}
        )

        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                await _finalize_porter_voice_call(
                    call_session_id,
                    completion_reason="websocket_disconnect",
                )
                return
            if audio := message.get("bytes"):
                try:
                    pcm.append(audio)
                except PorterPCMStreamError as exc:
                    pcm.reset()
                    await websocket.send_json(
                        {
                            "type": "error",
                            "payload": {
                                "code": "invalid_audio_turn",
                                "message": str(exc),
                                "retryable": True,
                            },
                        }
                    )
                continue

            raw_text = message.get("text")
            if not raw_text:
                continue
            try:
                command = json.loads(raw_text)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "code": "invalid_command",
                            "message": "Invalid voice stream command.",
                            "retryable": True,
                        },
                    }
                )
                continue
            command_type = command.get("type")
            if command_type == "cancel-turn":
                pcm.reset()
                continue
            if command_type == "end-call":
                await _finalize_porter_voice_call(
                    call_session_id,
                    completion_reason="explicit_end_call",
                )
                await websocket.close(code=1000)
                return
            if command_type == "silence-turn":
                pcm.reset()
                async with db_client.async_session() as session:
                    turn = await run_porter_live_voice_turn(
                        session,
                        call_session_id=opener.call_session_id,
                        user_text_override="[silence]",
                        event_source="browser_silence",
                        on_tts_audio_chunk=lambda pcm16, sample_rate: _send_tts_audio_chunk(
                            websocket, pcm16, sample_rate
                        ),
                    )
                    await session.commit()
                await websocket.send_json(
                    {"type": "turn", "payload": _live_voice_result_to_response(turn).model_dump(mode="json")}
                )
                if turn.should_close:
                    await websocket.close(code=1000)
                    return
                continue
            if command_type != "commit-turn":
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "code": "unknown_command",
                            "message": "Unknown Porter voice stream command.",
                            "retryable": True,
                        },
                    }
                )
                continue

            try:
                audio = pcm.commit()
                with TemporaryDirectory(prefix="porter-pcm-stream-") as temp_dir:
                    audio_path = Path(temp_dir) / "caller.wav"
                    write_pcm16_wav(audio, audio_path)
                    async with db_client.async_session() as session:
                        turn = await run_porter_live_voice_turn(
                            session,
                            audio_path=audio_path,
                            call_session_id=opener.call_session_id,
                            on_tts_audio_chunk=lambda pcm16, sample_rate: _send_tts_audio_chunk(
                                websocket, pcm16, sample_rate
                            ),
                        )
                        await session.commit()
                await websocket.send_json(
                    {"type": "turn", "payload": _live_voice_result_to_response(turn).model_dump(mode="json")}
                )
                if turn.should_close:
                    await websocket.close(code=1000)
                    return
            except (PorterPCMStreamError, PorterLiveVoiceNoSpeechError) as exc:
                await websocket.send_json({"type": "error", "payload": {"message": str(exc)}})
            except PorterLiveVoiceError as exc:
                await websocket.send_json(
                    {"type": "error", "payload": {"message": str(exc), "retryable": True}}
                )
    except WebSocketDisconnect:
        if call_session_id is not None:
            try:
                await _finalize_porter_voice_call(
                    call_session_id,
                    completion_reason="websocket_disconnect",
                )
            except Exception:
                logger.exception("Failed to finalize disconnected Porter voice stream")
        return
    except Exception:
        logger.exception("Unexpected Porter voice stream failure")
        if call_session_id is not None:
            try:
                await _finalize_porter_voice_call(
                    call_session_id,
                    completion_reason="websocket_error",
                    status="failed",
                )
            except Exception:
                logger.exception("Failed to finalize errored Porter voice stream")
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            return


async def _finalize_porter_voice_call(
    call_session_id: int,
    *,
    completion_reason: str,
    status: str = "completed",
) -> None:
    async with db_client.async_session() as session:
        await finalize_porter_call(
            session,
            call_session_id=call_session_id,
            completion_reason=completion_reason,
            status=status,
        )
        await session.commit()


async def _prewarm_porter_stt_after_opener() -> None:
    try:
        await prewarm_default_stt_model()
    except Exception:
        logger.warning("Porter STT prewarm failed; it will retry on the first caller turn.")


@router.get("/voice-runtime/readiness", response_model=PorterRuntimeReadinessResponse)
async def get_porter_voice_runtime_readiness(
    _: UserModel = Depends(get_user),
) -> PorterRuntimeReadinessResponse:
    return _runtime_readiness_to_response(inspect_porter_voice_runtime())


@router.post("/voice-runtime/prewarm", response_model=PorterVoiceRuntimeWarmResponse)
async def prewarm_porter_voice_runtime(
    request: PorterVoiceRuntimeWarmRequest,
    _: UserModel = Depends(get_user),
) -> PorterVoiceRuntimeWarmResponse:
    try:
        result = await prewarm_porter_voice_scripts(
            voice=request.voice,
            script_names=tuple(request.script_names) if request.script_names else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PorterTTSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PorterLiveVoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _runtime_warm_result_to_response(result)


@router.post("/voice-opener", response_model=PorterVoiceOpenerResponse)
async def create_porter_voice_opener(
    lead_id: int | None = Form(default=None),
    voice: str | None = Form(default=None),
    _: UserModel = Depends(get_user),
) -> PorterVoiceOpenerResponse:
    try:
        async with db_client.async_session() as session:
            result = await run_porter_voice_opener(
                session, lead_id=lead_id, voice=voice
            )
            await session.commit()
            return _voice_opener_result_to_response(result)
    except PorterLiveVoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/web-call-simulations",
    response_model=PorterLocalWebCallSimulationResponse,
)
async def create_porter_local_web_call_simulation(
    request: PorterLocalWebCallSimulationRequest,
    _: UserModel = Depends(get_user),
) -> PorterLocalWebCallSimulationResponse:
    try:
        async with db_client.async_session() as session:
            lead_id = request.lead_id
            if lead_id is None:
                leads = await load_mock_porter_leads(session)
                lead_id = leads[0].id
            result = await run_porter_local_web_call_simulation(
                session,
                lead_id=lead_id,
                user_turns=request.user_turns,
                llm_adapter=(
                    OllamaLLMAdapter()
                    if request.use_live_llm
                    else MockPorterLLMAdapter(request.mock_llm_response)
                ),
                synthesize_audio=request.synthesize_audio,
            )
            await session.commit()
            return PorterLocalWebCallSimulationResponse(
                **local_web_call_result_to_dict(result)
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/voice-turns", response_model=PorterLiveVoiceTurnResponse)
async def create_porter_live_voice_turn(
    audio: UploadFile = File(...),
    call_session_id: int | None = Form(default=None),
    lead_id: int | None = Form(default=None),
    voice: str | None = Form(default=None),
    _: UserModel = Depends(get_user),
) -> PorterLiveVoiceTurnResponse:
    if audio.content_type not in {
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=415,
            detail="Porter live voice currently accepts browser-recorded WAV audio.",
        )

    with TemporaryDirectory(prefix="porter-live-upload-") as temp_dir:
        audio_path = Path(temp_dir) / "caller.wav"
        contents = await audio.read()
        if len(contents) > 8 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio upload is too large.")
        audio_path.write_bytes(contents)

        try:
            async with db_client.async_session() as session:
                result = await run_porter_live_voice_turn(
                    session,
                    audio_path=audio_path,
                    call_session_id=call_session_id,
                    lead_id=lead_id,
                    voice=voice,
                )
                await session.commit()
                return _live_voice_result_to_response(result)
        except PorterLiveVoiceNoSpeechError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PorterLiveVoiceError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected Porter voice turn failure")
            if call_session_id is not None:
                try:
                    await _finalize_porter_voice_call(
                        call_session_id,
                        completion_reason="voice_turn_error",
                        status="failed",
                    )
                except Exception:
                    logger.exception("Failed to finalize errored Porter voice turn")
            raise HTTPException(
                status_code=503,
                detail="Aiva could not complete the voice turn.",
            ) from exc


@router.get("/call-sessions", response_model=PorterCallSessionListResponse)
async def list_porter_local_call_sessions(
    limit: int = 25,
    _: UserModel = Depends(get_user),
) -> PorterCallSessionListResponse:
    async with db_client.async_session() as session:
        return PorterCallSessionListResponse(
            sessions=await list_porter_call_sessions(session, limit=limit)
        )


@router.get(
    "/call-sessions/{call_session_id}",
    response_model=PorterCallSessionReviewResponse,
)
async def get_porter_local_call_session_review(
    call_session_id: int,
    _: UserModel = Depends(get_user),
) -> PorterCallSessionReviewResponse:
    async with db_client.async_session() as session:
        review = await get_porter_call_session_review(
            session,
            call_session_id=call_session_id,
        )
        if review is None:
            raise HTTPException(status_code=404, detail="Porter call session not found")
        return PorterCallSessionReviewResponse(session=review)


def _live_voice_result_to_response(
    result: PorterLiveVoiceTurnResult,
) -> PorterLiveVoiceTurnResponse:
    return PorterLiveVoiceTurnResponse(
        call_session_id=result.call_session_id,
        lead_id=result.lead_id,
        attempt_id=result.attempt_id,
        destination_phone=result.destination_phone,
        user_text=result.user_text,
        assistant_text=result.assistant_text,
        assistant_audio_base64=result.assistant_audio_base64,
        assistant_audio_content_type=result.assistant_audio_content_type,
        audio_streamed=result.audio_streamed,
        vad=result.vad,
        stt=result.stt,
        tts=result.tts,
        llm=result.llm,
        timings_ms=result.timings_ms,
        transcript=list(result.transcript),
        should_close=result.should_close,
    )


async def _send_tts_audio_chunk(
    websocket: WebSocket,
    pcm16: bytes,
    sample_rate: int,
) -> None:
    await websocket.send_json(
        {
            "type": "audio-chunk",
            "payload": {
                "pcm16_base64": base64.b64encode(pcm16).decode("ascii"),
                "sample_rate": sample_rate,
            },
        }
    )


def _voice_opener_result_to_response(
    result: PorterVoiceOpenerResult,
) -> PorterVoiceOpenerResponse:
    return PorterVoiceOpenerResponse(
        call_session_id=result.call_session_id,
        lead_id=result.lead_id,
        attempt_id=result.attempt_id,
        destination_phone=result.destination_phone,
        assistant_text=result.assistant_text,
        assistant_audio_base64=result.assistant_audio_base64,
        assistant_audio_content_type=result.assistant_audio_content_type,
        tts=result.tts,
        transcript=list(result.transcript),
    )


def _runtime_readiness_to_response(
    result: PorterRuntimeReadiness,
) -> PorterRuntimeReadinessResponse:
    return PorterRuntimeReadinessResponse(
        ready=result.ready,
        fast_voice_mode=result.fast_voice_mode,
        default_voice=result.default_voice,
        recommended_target_ms=result.recommended_target_ms,
        notes=list(result.notes),
        components=[
            PorterRuntimeComponentResponse(
                name=component.name,
                provider=component.provider,
                model=component.model,
                ready=component.ready,
                production_recommended=component.production_recommended,
                details=component.details,
            )
            for component in result.components
        ],
    )


def _runtime_warm_result_to_response(
    result: PorterVoiceRuntimeWarmResult,
) -> PorterVoiceRuntimeWarmResponse:
    return PorterVoiceRuntimeWarmResponse(
        voice=result.voice,
        warmed_count=result.warmed_count,
        cache_hit_count=result.cache_hit_count,
        total_elapsed_ms=result.total_elapsed_ms,
        scripts=[
            PorterVoiceScriptWarmResponse(
                script_name=script.script_name,
                text=script.text,
                cache_hit=script.cache_hit,
                elapsed_ms=script.elapsed_ms,
                tts=script.tts,
            )
            for script in result.scripts
        ],
    )
