# Porter Human-Like Telephony Assessment

Status: Inspection and implementation proposal only. No Porter behavior or runtime code was changed.

Assessment date: 2026-07-14

## Executive conclusion

The current Porter agent is not yet consistently human-like. It has several useful foundations: deterministic business-state control, direct-question interception, bounded call opening, a client-side barge-in detector, local Kokoro TTS, cached approved scripts, and explicit policy checks. However, naturalness is limited by four combined causes:

1. The business-state engine frequently emits fixed, context-insensitive scripts and repeats pending questions.
2. There is no distinct conversational-delivery layer between a business decision and spoken output.
3. Kokoro generates complete WAV files before playback; internal pause segments are concatenated and are not streamed to the caller.
4. Turn endpointing, echo-sensitive browser VAD, and full-response buffering add latency and make interruptions only partially reliable.

Prompt or script changes alone can improve wording, acknowledgement, question count, and reformulation. They cannot solve full-WAV buffering, slow uncached synthesis, delayed endpointing, echo, or reliable cancellation.

## Human-like telephony behavior assessment

### 1. Why the current agent sounds robotic

- Most common paths return fixed strings from `cold_call_scripts.py` and `cold_call_flow.py`.
- The state machine expects one field and often calls `_repeat_pending_question()` when speech is ambiguous.
- The first unclear answer normally repeats the same prompt; the second falls back to a generic "I didn't catch that."
- Acknowledgements such as "Got it," "Yeah," and "That helps" are attached to stages, not selected from the meaning or emotional weight of the prospect's answer.
- The current qualification sequence remains survey-like: industry, factor status, satisfaction, challenge, volume, advisor.
- TTS pauses are controlled primarily by literal ellipses and em dashes.
- Every response is rendered as one complete WAV and played as one uninterrupted audio source unless the browser stops it.

### 2. Root causes

| Cause | Current contribution | Assessment |
|---|---|---|
| Prompt/script wording | High | Fixed phrases, generic acknowledgements, and long explanations are directly audible |
| State logic | High | Expected-field routing and question repetition cause questionnaire behavior |
| TTS voice quality | Medium | Kokoro is usable, but one voice and fixed speed cannot express all required delivery styles |
| Prosody controls | High | Only marker pauses exist; no SSML, pitch, emotion, style, or per-turn speed policy |
| Response length | Medium/high | Average is acceptable, but long outliers substantially exceed the desired turn length |
| Turn detection | High | Browser RMS endpointing and a fixed 550 ms silence threshold add delay and may misread hesitation |
| Barge-in | Medium/high | Client playback can stop, but behavior is not end-to-end instrumented or acoustically validated |
| Audio buffering | High | First audio waits for the entire TTS WAV, especially costly for uncached responses |
| STT | Medium | Clean test speech worked, but turn-based `base.en` CPU transcription is not streaming |

### 3. Current average response length

The latest 200 persisted assistant turns were inspected:

| Metric | Result |
|---|---:|
| Assistant turns sampled | 200 |
| Average words per turn | 17.56 |
| Median words per turn | 13 |
| Maximum words in one turn | 66 |
| Estimated average duration at 150 words/minute | 7.02 seconds |
| Estimated longest duration at 150 words/minute | 26.4 seconds |

The average fits the requested 8-15 second ceiling, but the 66-word outlier does not. Current approved source strings average roughly 16 words, while rate and disclosure answers are approximately 12-15 seconds before TTS pauses.

### 4. Natural streaming and chunking

Current response audio is **not streamed in natural speech chunks**.

- `_split_spoken_segments()` divides text at `...` and em dashes.
- Kokoro synthesizes each segment and inserts silence samples.
- The segments are concatenated into one WAV.
- The backend base64-encodes the complete WAV.
- The browser decodes the complete WAV and starts one `AudioBufferSourceNode`.

Therefore, chunking currently affects pauses inside a completed file, not time to first audio, cancellation of unsynthesized content, or responsive turn delivery.

### 5. Barge-in support

Status: **partially implemented, not production-proven**.

- The browser records while Aiva is speaking.
- Barge-in is disabled for the first 800 ms of playback.
- After arming, RMS must exceed `0.075` for eight animation frames.
- Eight frames are roughly 130 ms at 60 Hz, so the earliest possible stop is about 930 ms after playback starts. After the arming window, detection is roughly 130 ms plus capture and scheduling delay.
- On detection, the browser stops the current audio source and retains microphone pre-roll.
- The captured caller turn is sent after endpoint silence.
- The Porter VAD event helpers are not wired into this browser path, so interruption-stop latency and interruption outcomes are not persisted.
- There is no automated acoustic test proving that caller speech stops playback without false triggers from speaker echo.

The current design can stop already-downloaded playback. It cannot cancel TTS generation because generation is complete before playback begins.

### 6. Direct questions and qualification interruption

Status: **mostly supported**.

`_informational_decision()` executes before the normal stage handler and recognizes AI identity, caller identity, call purpose, rates, funding speed, fees, terms, industry eligibility, general information, factoring explanation, and human requests. It answers these before normal discovery.

Remaining weaknesses:

- Intent recognition is phrase-based and misses paraphrases.
- After the answer, a simple affirmative can call `_repeat_pending_question()` and restore a robotic pending prompt.
- The bridge back to discovery is usually absent or generic.
- Some answers use wording that does not meet the new mandatory AI disclosure.

### 7. Fixed repeated phrases

The 200-turn sample shows material repetition:

| Phrase | Occurrences |
|---|---:|
| `Hello?` | 19 |
| Legacy long cold-call opener | 14 |
| Fixed Morgan Test identity question | 13 |
| `Got it. I can send this to the Porter team.` | 11 |
| `Sure - what part are you trying to figure out first?` | 10 |
| Existing-factor satisfaction script | 6 |

Some records are from earlier versions, but the source still relies on fixed phrase families with little contextual selection.

### 8. Multiple questions per turn

Most current scripted turns contain one question mark, but several turns combine explanation, acknowledgement, and a compound choice in ways that feel like more than one task. The booking line asks for both number and time in one turn. The qualification follow-up asks whether the prospect factors or handles invoices another way, which is one conceptual question but cognitively broad.

The one-primary-question rule is not enforced structurally. It currently depends on script discipline.

### 9. Available TTS prosody controls

| Control | Current state |
|---|---|
| Voice selection | Supported through `PORTER_VOICE_NAME`; default `af_heart` |
| Speaking rate | Kokoro supports a speed argument, but Porter hard-codes `speed=1.0` |
| Explicit pause | Supported only for `...` (320 ms) and em dash (180 ms) |
| SSML | Not supported in the Porter adapter |
| Pitch | Not supported |
| Emotion/style | Not supported |
| Volume/stress | Not supported |
| Sentence chunk delivery | Not supported; complete WAV only |
| Per-emotion delivery profile | Not supported |

The em-dash pause is currently shorter than the specified 300-600 ms normal conversational pause. The marker model also cannot distinguish question-yield, reflection, disclosure, correction, and confirmation pauses.

### 10. Pronunciation hints

Status: **not implemented**.

There is no pronunciation lexicon, phoneme override, name confidence, spoken email formatter, currency verbalizer, timezone formatter, or correction memory in the Porter path. Kokoro creates phonemes automatically, but the agent cannot supply an approved pronunciation hint or remember a caller's correction.

### 11. Minimum safe changes required

1. Add a small delivery layer that receives a safe business decision and returns a controlled speech plan: chunks, pause class, acknowledgement family, one primary question, and pronunciation-ready text.
2. Replace verbatim question repetition with a two-step rephrasing ladder, then preserve unknown or offer a human.
3. Use contextual acknowledgements and a small controlled variation history; never vary compliance meaning.
4. Implement the exact approved automated-assistant disclosure.
5. Split compound contact collection into one operational field per turn.
6. Stream sentence-sized audio chunks and begin playback after the first chunk rather than after the complete WAV.
7. Make chunk generation and playback cancellable when barge-in occurs.
8. Instrument endpoint-to-first-audio, barge-in stop, overlap, agent audio duration, and longest monologue.
9. Add gradual silence recovery based on conversation state rather than repeating the current prompt.
10. Add pronunciation confirmation and safe spoken formatting for names, email, money, dates, times, and percentages.

### 12. Problems prompting cannot solve

- The 550 ms end-of-turn silence threshold.
- Full-WAV TTS buffering.
- Uncached Kokoro synthesis time.
- Failure to cancel unsynthesized or in-flight audio.
- Acoustic echo and false barge-in triggers.
- Fixed speaking rate and unavailable pitch/emotion controls.
- STT errors and non-streaming transcription.
- Audio clipping, device behavior, or network delay.
- Reliable pronunciation without a formatting/lexicon mechanism.

## Measured runtime behavior

### Cached end-to-end backend probe

A clean synthesized `Hello` was passed through the actual Porter VAD, faster-whisper STT, deterministic state router, cached Kokoro response, persistence, and WAV response path.

| Component | Measured time |
|---|---:|
| VAD | 0.17 ms |
| STT | 380.44 ms |
| DB context | 8.92 ms |
| Deterministic decision | 0.05 ms |
| Cached TTS lookup | 8.25 ms |
| Persistence | 2.91 ms |
| Backend total after committed audio | 406.16 ms |

The reply audio was 4.34 seconds long. This probe used a clean generated sample and a cached reply, so it is a best-case backend measurement, not a production microphone benchmark.

### Perceived-latency estimate

The browser waits 550 ms of silence before committing a normal caller turn. Therefore:

`550 ms endpointing + 406 ms cached backend + WebSocket/base64/decode = roughly 1 second or more before first audio`

The current 500 ms target cannot be met as end-of-speech-to-first-audio with this architecture, even when response audio is cached.

### Uncached Kokoro measurements

After model loading, full-WAV synthesis on CPU measured:

| Response | Words | Synthesis | Audio duration |
|---|---:|---:|---:|
| Simple payment-timing question | 10 | 2.16 s | 3.11 s |
| Contextual impact question | 17 | 3.67 s | 5.78 s |
| Problem summary | 23 | 4.21 s | 6.93 s |

These measurements confirm that controlled wording alone cannot provide low perceived latency for uncached contextual turns. Streaming the first completed sentence/chunk is required.

### Required metrics not currently available

| Metric | Current status |
|---|---|
| End-of-user-speech to first audio | Not measured directly; estimated above |
| Interruption-stop latency | Not persisted; static estimate only |
| Average agent turn duration | Not stored; estimated from word count |
| Agent/prospect overlap frequency | Not measured |
| Longest uninterrupted monologue | 66 words in sampled transcripts; audio duration not stored per turn |

## Prompt-level versus runtime-level improvements

| Improvement | Script/delivery logic | Runtime required |
|---|:---:|:---:|
| Short spoken syntax | Yes | No |
| One primary question | Yes | No |
| Contextual acknowledgement | Yes | No |
| Rephrase instead of repeat | Yes | No |
| Exact AI disclosure | Yes | No |
| Controlled phrase variation | Yes | No |
| Emotional alignment | Yes | Optional speed support |
| Natural problem summary | Yes | No |
| Contextual handoff bridge | Yes | No |
| Gradual silence wording | Yes | Silence event timing already exists but needs tuning |
| Meaningful pause classes | Delivery plan | Yes, TTS/chunk playback |
| Low first-audio latency | No | Yes |
| Reliable barge-in | No | Yes |
| Echo resistance | No | Yes and acoustic calibration |
| Pronunciation hints | Formatting logic | TTS adapter support where available |
| Pitch/emotion/stress | No | Different TTS capability or provider support |

## Behavioral test gap assessment

| # | Required behavior | Current status | Evidence |
|---:|---|---|---|
| 1 | Opening delivered in natural chunks | Fail | Identity stages are separate, but each response is one complete WAV |
| 2 | One primary question | Partial | Usually true; not structurally validated and booking asks number plus time |
| 3 | Stop/change course on interruption | Partial | Browser stops playback; no integrated behavioral test or server cancellation |
| 4 | Direct questions before discovery | Pass/partial | Informational routing precedes stage routing; resume bridge is weak |
| 5 | Contextual acknowledgements | Fail | Mostly stage-fixed acknowledgements |
| 6 | No `perfect/great` for hardship | Partial | `BOOKING` uses `Great`; hardship path says `That helps` before volume |
| 7 | No repeated acknowledgement | Fail | No acknowledgement-history control |
| 8 | Rephrase misunderstood questions | Fail | First repair usually repeats pending prompt |
| 9 | No verbatim misunderstood repeat | Fail | `_repeat_pending_question()` does exactly this |
| 10 | Natural prospect summary | Fail | No pre-value problem-summary state |
| 11 | Value tied to confirmed facts | Fail | Advisor offer is generic |
| 12 | No long generic explanation | Partial | Most current scripts are short; historical and rate/disclosure outliers remain |
| 13 | No stacked questions | Partial | No validator; contact collection can stack number/time |
| 14 | No filler overuse | Pass | No systematic filler injection |
| 15 | No random `um/uh` | Pass | Not generated by approved deterministic scripts |
| 16 | Never claims human | Pass | Current scripts identify Aiva as AI when asked |
| 17 | Clear AI identity answer | Partial | Direct answer exists but does not match the new mandatory wording |
| 18 | More concise when busy | Partial | Callback branch is brief, but no general busy delivery profile |
| 19 | De-escalates anger | Fail/not covered | No explicit hostile-intent branch in the current cold-call state machine |
| 20 | Stops after DNC | Pass | STOP closes, finalizes, and suppresses the lead |
| 21 | Natural human-handoff bridge | Partial | Advisor offer has a bridge; early human request jumps to booking |
| 22 | Outcome-specific closing | Partial | Several specific closes exist; coverage is incomplete |
| 23 | Precise conversational appointment confirmation | Fail | Date/time/timezone/channel confirmation is incomplete |
| 24 | Unknown remains unknown | Partial | Some unclear turns close, but repeated prompts can force low-quality data |
| 25 | Variation preserves compliance | Not implemented | No controlled variation system |
| 26 | No excessive enrichment disclosure | Partial | Name/company are spoken; no confidence/verbosity policy |
| 27 | Pause after questions and yield | Partial | Recording/yield exists; no explicit question-yield pause class |
| 28 | Do not prompt during normal thinking pauses | Partial | 6.5 s no-speech timeout is reasonable; 550 ms endpointing can cut hesitations |
| 29 | Gradual silence recovery | Fail | Repeats hello/pending questions rather than the required recovery ladder |
| 30 | Pronunciation uncertainty | Fail | No pronunciation confirmation or correction memory |

## Evaluation-rubric additions

Add 25 points to the existing 100-point business rubric, then report business and conversation scores separately rather than hiding one inside a combined number.

| Conversation dimension | Points |
|---|---:|
| Naturalness and conversational flow | 6 |
| Turn-taking and barge-in | 5 |
| Listening and course correction | 5 |
| Speech efficiency | 5 |
| Emotional appropriateness | 4 |
| **Conversation subtotal** | **25** |

Recommended release gate:

- Business/compliance score: at least 85/100.
- Conversation score: at least 21/25.
- No business or conversational automatic failure.
- Live acoustic benchmark passes on headset, laptop speakers, and moderate background noise.

The threshold requires calibration with Porter reviewers and real approved test calls.

## Automatic conversational failures

Use all failures from the requirement without weakening existing policy failures. In particular, fail the call review automatically when the agent:

- Claims to be human or denies automation.
- Ignores a direct question and continues the script.
- Continues speaking through a detected interruption.
- Repeats the same misunderstood question without reformulation.
- Asks multiple unrelated qualification questions in one turn.
- Celebrates financial hardship.
- Injects fake fillers or synthetic disfluency.
- Restarts an interrupted script from the beginning.
- Asks for information already supplied.
- Continues after DNC.
- Speaks unsupported personalization as fact.
- Changes compliance meaning through variation.
- Claims an unconfirmed transfer, email, or appointment.

## Minimal implementation proposal

### Phase 1: Conversational-delivery correctness

Goal: Fix robotic language and listening behavior without changing compliance, qualification standards, or the audio protocol.

1. Add one focused `api/porter/delivery.py` module.
2. Define a small `PorterSpeechPlan` containing safe text chunks, pause class, primary question, tone class, and semantic fixedness.
3. Keep `PorterColdCallDecision` responsible only for objective, state, captured data, and approved facts.
4. Map business decisions to controlled phrase families; track only the last acknowledgement to prevent consecutive repetition.
5. Add contextual acknowledgement categories: neutral, hardship, correction, satisfied, skeptical, busy, angry.
6. Add a two-step reformulation ladder per question objective; third failure preserves unknown or offers a human.
7. Replace the AI response with the exact approved automated-assistant wording.
8. Split number/time and other compound operational questions.
9. Add a problem-summary speech plan before value/handoff.
10. Add the 30 deterministic behavioral tests in a focused `test_porter_delivery.py`, plus affected state-machine tests.

This is the smallest useful separation between business logic and spoken delivery. A general NLG framework, emotion model, or new LLM is not needed.

### Phase 2: Chunked TTS and cancellable playback

Goal: Reduce perceived latency and make interruption behavior genuine.

1. Synthesize `PorterSpeechPlan` chunks independently.
2. Extend the WebSocket protocol with `assistant-start`, ordered `assistant-audio`, and `assistant-end` events.
3. Start browser playback as soon as the first chunk arrives.
4. Maintain a small playback queue and stop/clear it immediately on barge-in.
5. Cancel remaining chunk synthesis when interrupted or the call closes.
6. Do not restart the interrupted speech plan; process the caller turn and resume only the still-relevant objective.
7. Keep legally required disclosure chunks non-skippable only when counsel explicitly requires completion.

This phase is necessary for natural latency. Pre-caching alone cannot cover contextual summaries, names, objections, and confirmations.

### Phase 3: Turn tuning, pronunciation, and telemetry

Goal: Calibrate live behavior and make quality measurable.

1. Record user-endpoint timestamp, first-audio timestamp, barge-in detection, playback-stop, agent audio duration, and overlap.
2. Tune the 550 ms endpoint, 800 ms barge-in arm, RMS thresholds, frame count, and pre-roll using acoustic tests.
3. Add spoken formatters for currency, percentages, dates, times, time zones, phone numbers, and email addresses.
4. Add name/company pronunciation confirmation and correction memory for the call.
5. Expose Kokoro speaking rate as a bounded delivery setting, not an unrestricted script control.
6. Evaluate whether the selected Kokoro voice is sufficient after delivery and streaming fixes. Do not change TTS models before isolating those causes.

## Proposed validation sequence

1. Deterministic delivery-unit tests for all 30 requested behaviors.
2. Existing Porter policy, DNC, state-machine, finalization, and knowledge tests.
3. Audio tests verifying pause classes, chunk ordering, cancellation, and no playback after interruption.
4. Browser tests for microphone capture, echo cancellation, barge-in, playback queue, silence recovery, and appointment confirmation.
5. Benchmarks for cached and uncached turns using short question, objection, summary, and handoff responses.
6. Live approved test calls across headset, laptop speaker, quiet room, and moderate noise.
7. Human transcript/audio review using the separate 100-point business and 25-point conversation rubrics.

## Approval boundary

No behavioral code should be changed until Porter approves:

- The exact automated-assistant disclosure.
- The controlled phrase families and emotional acknowledgement policy.
- Which disclosures, if any, must continue through an interruption.
- The problem-summary wording and specialist title.
- Appointment fields and timezone behavior.
- Silence recovery wording.
- The live acoustic latency and overlap acceptance thresholds.

Recommended approval: implement Phase 1 first, run its complete behavioral and regression suite, then review transcripts before authorizing the audio-protocol work in Phase 2.
