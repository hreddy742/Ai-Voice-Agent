# Porter Phase 1 Controlled Internal Live-Call Validation

Status: In progress

Date: 2026-07-14

Scope: Phase 1 conversational-delivery validation using the unchanged local voice runtime. External prospect dialing and production calling are prohibited.

## Runtime Readiness

| Check | Result |
|---|---|
| API | Live on `http://localhost:18000` |
| Porter console | Live on `http://localhost:3020/porter` |
| STT | `faster-whisper`, `base.en` |
| TTS | `kokoro-onnx`, default voice `af_heart` |
| Conversation routing | `deterministic-router`, `porter-fast-local` |
| Fast mode | On |
| Runtime readiness | 100% |
| Safety readiness | 67%; provider actions still require approval |
| Data readiness | 33%; knowledge and CRM remain placeholders |
| Initial prewarm | 8/14 cache hits, 20,324 ms |
| Immediate repeated prewarm | 14/14 cache hits, 117 ms |

## Scenario Matrix

| # | Scenario | Tester | Start/end | Complete | Expected outcome | Actual outcome | Disposition | Score | Result | Defect layer |
|---:|---|---|---|---|---|---|---|---:|---|---|
| 1 | Weekly payroll and 45-day terms | Pending | Pending | Pending | Qualified next step | Pending | Pending | Pending | Pending | Pending |
| 2 | Uses internal cash | Pending | Pending | Pending | Conditional discovery | Pending | Pending | Pending | Pending | Pending |
| 3 | Uses bank line | Pending | Pending | Pending | Conditional discovery | Pending | Pending | Pending | Pending | Pending |
| 4 | Satisfied with existing factor | Pending | Pending | Pending | Comparison offer or clean exit | Pending | Pending | Pending | Pending | Pending |
| 5 | Dissatisfied with existing factor | Pending | Pending | Pending | Tailored next step | Pending | Pending | Pending | Pending | Pending |
| 6 | No current funding need | Pending | Pending | Pending | No-current-need close | Pending | Pending | Pending | Pending | Pending |
| 7 | Early rate question | Pending | Pending | Pending | Approved 0.2-2% answer, resume | Pending | Pending | Pending | Pending | Pending |
| 8 | Funding amount question | Pending | Pending | Pending | No invented amount; human review | Pending | Pending | Pending | Pending | Pending |
| 9 | Funding-speed question | Pending | Pending | Pending | Approved under-48-hour answer after setup and invoice submission | Pending | Pending | Pending | Pending | Pending |
| 10 | Guaranteed approval question | Pending | Pending | Pending | No guarantee | Pending | Pending | Pending | Pending | Pending |
| 11 | What Porter does | Pending | Pending | Pending | Concise factual answer | Pending | Pending | Pending | Pending | Pending |
| 12 | AI identity question | Pending | Pending | Pending | Truthful disclosure | Pending | Pending | Pending | Pending | Pending |
| 13 | Immediate human request | Pending | Pending | Pending | Honor request | Pending | Pending | Pending | Pending | Pending |
| 14 | Interrupts opening | Pending | Pending | Pending | Answer interruption, no restart | Pending | Pending | Pending | Pending | Pending |
| 15 | Interrupts discovery | Pending | Pending | Pending | Answer interruption, resume | Pending | Pending | Pending | Pending | Pending |
| 16 | Corrects lead data | Pending | Pending | Pending | Update confirmed fact | Pending | Pending | Pending | Pending | Pending |
| 17 | Does not understand | Pending | Pending | Pending | Rephrase | Pending | Pending | Pending | Pending | Pending |
| 18 | Silence after question | Pending | Pending | Pending | Gradual recovery | Pending | Pending | Pending | Pending | Pending |
| 19 | Busy | Pending | Pending | Pending | Callback path | Pending | Pending | Pending | Pending | Pending |
| 20 | Send information | Pending | Pending | Pending | Send-info disposition | Pending | Pending | Pending | Pending | Pending |
| 21 | Not interested | Pending | Pending | Pending | One clarification | Pending | Pending | Pending | Pending | Pending |
| 22 | Repeated refusal | Pending | Pending | Pending | Stop selling and close | Pending | Pending | Pending | Pending | Pending |
| 23 | Do not call | Pending | Pending | Pending | Immediate suppression and close | Pending | Pending | Pending | Pending | Pending |
| 24 | Wrong person | Pending | Pending | Pending | Referral or clean close | Pending | Pending | Pending | Pending | Pending |
| 25 | Wrong number | Pending | Pending | Pending | Apology and close | Pending | Pending | Pending | Pending | Pending |
| 26 | Gatekeeper | Pending | Pending | Pending | Role-based routing | Pending | Pending | Pending | Pending | Pending |
| 27 | Voicemail | Pending | Pending | Pending | Approved voicemail outcome | Pending | Pending | Pending | Pending | Pending |
| 28 | Financial hardship | Pending | Pending | Pending | Appropriate acknowledgement | Pending | Pending | Pending | Pending | Pending |
| 29 | Scheduled-call confirmation | Pending | Pending | Pending | Explicit confirmation | Pending | Pending | Pending | Pending | Pending |
| 30 | Simulated live-transfer request | Pending | Pending | Pending | Human-handoff outcome | Pending | Pending | Pending | Pending | Pending |

## Per-Call Evidence

For every completed call, attach or reference the persisted session transcript and record:

- Tester role and speaking conditions.
- Start and end timestamps.
- Expected and actual outcome.
- Persisted disposition.
- Reviewer score out of 100.
- Ratings from 1-5 for naturalness, responsiveness, turn-taking, voice quality, perceived latency, trustworthiness, and usability.
- End-of-speech to first-audio latency.
- Barge-in stop latency when applicable.
- Overlap, premature-response, silence, and clipping counts.
- TTS cache status and generation delay.
- Phase 1 defects and runtime defects separately.

## Current Runtime Observation

The first prewarm required 20,324 ms with six uncached scripts. The repeated fully cached prewarm required 117 ms. This is evidence of substantial uncached full-WAV synthesis delay. It is recorded for Phase 2 consideration and must not be changed during this validation.

## Invalidated Calls

### Session 2183

- Started: 2026-07-14 20:41:41 UTC.
- Ended: 2026-07-14 20:43:12 UTC.
- Persisted outcome: `unknown`.
- Not counted as a Phase 1 validation call.
- Reason: the local API process had not reloaded the completed Phase 1 modules and used the former industry-first flow.
- Observed STT uncertainty: `I'm going to stop in business`, `redo factor invoices`, and `need more of`.
- Corrective action: restarted only `porter-api-ui-smoke` and verified that accepted permission now advances to `relevance` with the new business/government customer question.
- Phase 1 correction: presence checks such as `Are you there?` are now answered directly before identity confirmation resumes.
- Phase 1 correction: incomplete fragments such as `need more of` are rephrased and are not stored as confirmed facts.
- Verification: 56 focused conversational tests passed after the corrections.
- Audio stack changes: none.
