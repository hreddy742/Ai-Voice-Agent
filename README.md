# Porter Capital AI Voice Agent

A local-first outbound sales voice agent for invoice-factoring / accounts-receivable-financing lead
outreach, built as a deterministic conversation system rather than an LLM improvising a sales call.
The agent runs a real, testable state machine through opener → pitch → objection handling →
qualification → booking/exit, with a hard compliance layer, a citation-backed knowledge base, and a
full evaluation harness — all under [`api/porter/`](api/porter/).

**Status — local simulation only, not production calling.** No real telephony provider is wired in, no
Salesforce sync exists yet, and the knowledge base is placeholder-approved starter content. See
[Status and known limitations](#status-and-known-limitations) below before assuming this places real
calls.

## What this actually does

- Places (in the current build, simulates) an outbound call, runs a structured sales conversation,
  qualifies the prospect, and books a callback with a human advisor — or logs a clear reason why it
  didn't.
- Every conversational turn is routed through an explicit state machine, not free-form LLM reasoning
  about what to say next — the LLM composes the reply *within* a state the code already picked.
- Every factoring/financing claim the agent can make comes from a retrieval-scored knowledge base with
  traceable source chunks — never invented rates or terms.
- A policy/guardrail layer rejects unsafe claims (guaranteed approval, exact rates, "no risk", hiding
  that it's an AI) before they can be spoken, and logs every violation caught.

## Architecture

| Area | What it does | Code |
|---|---|---|
| Conversation engine | Deterministic sales state machine (greeting → qualifying → pitching ⇄ objection handling → scheduling → closing) | [`api/porter/state_machine.py`](api/porter/state_machine.py), [`api/porter/cold_call_flow.py`](api/porter/cold_call_flow.py) |
| Compliance & policy | Guardrails against unsafe claims (guaranteed approval, exact rates, "no risk", hiding AI identity, etc.), logged violations | [`api/porter/policy.py`](api/porter/policy.py) |
| Knowledge base | Approved-answer retrieval for factoring/AR-financing questions, traceable chunk IDs, no invented rates | [`api/porter/knowledge_base.py`](api/porter/knowledge_base.py) |
| Objection handling | Scripted objection responses tied to conversation state | [`api/porter/objections.py`](api/porter/objections.py) |
| Voice pipeline | STT / TTS / VAD adapter boundaries (faster-whisper, Silero, local TTS) | [`api/porter/stt.py`](api/porter/stt.py), [`api/porter/tts.py`](api/porter/tts.py), [`api/porter/vad.py`](api/porter/vad.py) |
| Live & local calling | Real audio pipeline route plus a local text/web-call simulator for fast iteration without a phone line | [`api/porter/live_voice.py`](api/porter/live_voice.py), [`api/porter/local_web_call.py`](api/porter/local_web_call.py), [`api/porter/local_text_demo.py`](api/porter/local_text_demo.py) |
| Evaluation harness | Golden-conversation, hallucination/policy-bypass, objection-scenario, and latency test suites | [`api/porter/evaluation.py`](api/porter/evaluation.py) |
| Call review | Backend + UI for reviewing transcripts, outcomes, and policy violations per call | [`api/porter/review.py`](api/porter/review.py), [`ui/src/app/porter/page.tsx`](ui/src/app/porter/page.tsx), [`ui/src/components/porter/PorterConsole.tsx`](ui/src/components/porter/PorterConsole.tsx) |
| Data model | Postgres schema for Porter leads, call sessions, suppression/DNC, and call-to-destination binding | [`api/alembic/versions/`](api/alembic/versions/) (`add_porter_schema`, `add_porter_lead_suppression`, `bind_porter_call_to_destination`, `add_porter_phone_suppressions`) |

That's ~330KB of original code across 23 files under `api/porter/` (`cold_call_flow.py` alone is ~97KB),
plus a full design-doc trail in [`docs/developer/`](docs/developer/): conversation design (v2, 53KB),
evaluation suite, telephony readiness/human-likeness assessment, knowledge base design, local LLM/STT/TTS
adapter notes, mock-lead design, objection handling, live-call validation, review view, sales playbook,
Salesforce sync design, and VAD/interruption handling.

**Test coverage:** 23 dedicated test files under [`api/tests/test_porter_*.py`](api/tests/) covering the
state machine, policy engine, KB, objections, evaluation harness, live-voice route, and DB schema.
Non-DB tests run standalone; DB-backed tests need the bundled Postgres/Redis/MinIO stack
(`docker compose up postgres redis minio`).

## Status and known limitations

From [`docs/developer/porter-production-readiness-report.mdx`](docs/developer/porter-production-readiness-report.mdx):

- The knowledge base is placeholder-approved starter content, not the real, legally-reviewed Porter
  Capital product terms.
- Kokoro, faster-whisper, and Silero are wired as adapter boundaries, not installed production engines.
- The "live" web-call bridge is a local simulation bridge, not a deep Pipecat WebRTC runtime.
- No real telephony provider is configured — nothing in this repo places or receives an actual phone
  call today.
- No Salesforce sync is implemented.
- Before any real outbound call: TCPA review, DNC policy, state call-recording consent rules, AI-voice
  disclosure approval, a data retention policy, an opt-out process, and a human review policy are all
  required and not yet in place.

Local dev entry points: [`scripts/start_porter_local.cmd`](scripts/start_porter_local.cmd),
[`scripts/start_porter_stack.ps1`](scripts/start_porter_stack.ps1),
[`scripts/start_porter_ui.cmd`](scripts/start_porter_ui.cmd).

## Built on Dograh

The underlying voice infrastructure — the LiveKit/Pipecat-based call pipeline, the drag-and-drop workflow
builder, telephony provider adapters, and the Next.js dashboard shell — comes from
[dograh-hq/dograh](https://github.com/dograh-hq/dograh), an open-source (BSD 2-Clause) self-hostable
voice-agent platform. This repo forks that platform and adds the Porter Capital sales-agent layer
described above on top of it under `api/porter/` and `ui/src/components/porter/`.

The unmodified upstream Dograh README (setup instructions, their feature list, their positioning vs.
Vapi/Retell) is preserved at [`docs/UPSTREAM_DOGRAH_README.md`](docs/UPSTREAM_DOGRAH_README.md) rather
than duplicated here. The [`LICENSE`](LICENSE) file is Dograh's original BSD 2-Clause license
(Copyright Zansat Technologies Private Limited) and applies to the parts of this codebase that are
unmodified upstream Dograh code.

## Setup

Base platform setup follows upstream Dograh — see
[`docs/UPSTREAM_DOGRAH_README.md`](docs/UPSTREAM_DOGRAH_README.md#-get-started) for the Docker quick
start. For the Porter-specific stack:

```bash
docker compose up postgres redis minio
scripts\start_porter_stack.ps1   # or start_porter_local.cmd
```
