# Porter Capital Cold-Call Conversation Design v2

Status: Design recommendation only. No agent implementation is changed by this document.

## Evidence labels used throughout

- **[OD] Observational data:** large recorded-call datasets, generally vendor-published and non-randomized.
- **[BS] Buyer survey:** self-reported buyer preferences; useful directionally, not proof of conversion lift.
- **[SF] Sales framework:** established sales-practice logic, not Porter-specific experimental evidence.
- **[PL] Porter logic:** derived from Porter's locked knowledge, stated business objective, and current call behavior.
- **[IV] Internal validation:** requires approval or facts from Porter management, sales, underwriting, compliance, or counsel.

## 1. Executive assessment of the current pattern

The current flow is orderly and safer than a free-form sales bot, but it is structurally a fixed qualification form:

`connect -> identify -> ask permission -> explain Porter -> industry -> factor status -> satisfaction -> cash-flow challenge -> volume -> advisor -> contact details`

That pattern is **qualification-led, not diagnosis-led**. It asks for industry, financing status, challenge, and volume before it has established that the prospect has commercial invoices, waits for payment, or experiences a meaningful timing gap. In practice, that causes repeated questions, irrelevant factor branches, abrupt escalation to volume, and poor handling when a prospect asks a question instead of supplying the expected field. **[PL]**

The correct redesign is not a longer script. It is a smaller mandatory core plus conditional branches:

`identify -> disclose -> relevant context -> permission -> relevance gate -> adaptive discovery -> confirm problem -> tailored Porter value -> qualify -> low-risk next step -> confirm -> close`

The conversation should earn each question. A maximum of four adaptive discovery questions should normally be enough before a problem summary or exit. **[SF][PL]**

Important compliance boundary: the call-flow design cannot by itself make automated outbound calling lawful. The FCC has treated AI-generated voices as artificial voices under the TCPA, while the FTC has expanded B2B protections against material misrepresentations and added recordkeeping requirements. Porter counsel must approve audience, consent basis, disclosure wording, states, number types, calling hours, recording, and suppression rules before production dialing. **[IV]**

## 2. What is correct in the current pattern

1. **Connection check:** Retain a short connection check and bounded silence recovery. **[PL]**
2. **Identity confirmation:** Useful when lead identity is reliable, but it must tolerate wrong-person and bad-data paths. **[PL]**
3. **Cold-call permission:** Keep a direct time-boxed request. Gong's proprietary observational data associates permission-based openers with better outcomes than some alternatives, but the result is not causal or factoring-specific. **[OD]**
4. **Current funding method:** This is useful after a payment-timing problem is established. **[SF][PL]**
5. **Current-provider satisfaction:** Useful only when a current factor or lender exists. **[PL]**
6. **Cash-flow consequence:** Essential, but the present generic wording should become a contextual impact question. **[SF][PL]**
7. **Approximate invoice volume:** Potentially useful for routing and human preparation, but only late and conditionally. **[PL][IV]**
8. **Human-advisor next step:** Correct objective; the cold call should sell a review, not underwriting or a financing commitment. **[PL]**
9. **Contact confirmation after interest:** Correct in principle, provided only operationally necessary fields are confirmed. **[PL]**
10. **Knowledge boundaries:** The locked rate range, ongoing funding-speed statement, no guarantees, and industry-eligibility deferral are appropriate safety constraints. **[PL]**

## 3. What is structurally weak

1. **Generic explanation arrives before relevance.** The prospect hears a product category before the agent knows whether commercial receivables or a payment gap exists. **[PL]**
2. **Industry is a universal gate.** Industry alone neither proves B2B invoicing nor proves need. It is low-value when enrichment already knows it and high-friction when STT mishears it. **[PL]**
3. **The factor question is premature and binary.** It narrows the conversation to factoring before establishing how customers pay or how the gap is currently funded. It misses bank lines, internal cash, and no-financing situations. **[PL]**
4. **Satisfaction is treated as qualification.** A satisfied factor user may still compare options, but only with permission; a non-factor user should never enter this branch. **[PL]**
5. **The generic cash-flow question is too broad.** It invites vague answers and can feel presumptive. The question should follow a confirmed payment pattern. **[SF][PL]**
6. **Volume follows mechanically.** Asking a financial-scale question immediately after a weak or misunderstood answer feels like an application. **[PL]**
7. **No explicit problem summary.** The agent does not prove it listened before pitching the specialist. **[SF]**
8. **No explicit customer-type/payment-term gate.** The current flow can qualify a company without knowing whether it invoices businesses or consumers, or whether payment delay exists. **[PL]**
9. **No timing or authority check.** It can book a meeting without knowing whether a need is current or whether the contact participates in the decision. **[PL]**
10. **Question repetition is the fallback.** When an answer is ambiguous, corrective, or a product question, the state machine often repeats the pending question instead of resolving meaning and adapting. **[PL]**
11. **Information requests close too early.** "Send information" should identify what is wanted, confirm an approved delivery method, and obtain follow-up permission. **[PL]**
12. **No explicit "no need" route.** A prospect can be pushed toward challenge and volume even when there is no current or foreseeable need. **[PL]**

## 4. What is missing

- Reliable pre-call context and a confidence level for each enrichment fact. **[PL]**
- A clear automated-assistant disclosure approved for the campaign. **[IV]**
- Customer type: business/government versus consumer. **[PL]**
- Confirmation that the company issues commercial invoices. **[PL]**
- Typical payment period or payment behavior. **[PL]**
- Whether payroll, materials, inventory, operations, or growth costs occur before payment. **[PL]**
- The operational consequence of that timing gap. **[SF][PL]**
- Current funding method beyond factoring. **[PL]**
- Limitations of the current method, asked only when relevant. **[SF][PL]**
- Current or upcoming timing of need. **[PL]**
- Decision involvement or access to the decision-maker. **[PL]**
- A concise problem confirmation before a Porter value statement. **[SF]**
- Separate routes for live transfer, scheduled review, approved information, future follow-up, and no next step. **[PL]**
- Explicit conflict repair for uncertain STT and bad enrichment. **[PL]**
- Outcome-specific closing and CRM dispositions. **[PL]**

## 5. Stages to keep, remove, move, or make conditional

| Current stage | Decision | Required change | Evidence |
|---|---|---|---|
| Connection check | Keep | Bound to three attempts; then technical/no-response close | [PL] |
| Identity confirmation | Keep, conditional | Use full name/company only when data confidence is high | [PL] |
| Cold-call permission | Keep | Combine with truthful context and approved AI disclosure | [OD][PL][IV] |
| Generic Porter explanation | Remove as universal | Replace with one relevance hypothesis; explain Porter after need is confirmed | [SF][PL] |
| Industry | Move/conditional | Prefer pre-call enrichment; confirm only if unknown, conflicting, or needed for human context | [PL] |
| Current factoring status | Move/expand | Ask current funding method after a payment gap is established | [PL] |
| Factor satisfaction | Conditional | Only for an existing-factor branch | [PL] |
| Cash-flow challenge | Keep, rewrite/move | Ask consequence after customer type and payment timing | [SF][PL] |
| Monthly invoice volume | Move/conditional | Ask late, use a range, and skip if the specialist can collect it | [PL][IV] |
| Advisor offer | Keep | Tie it to the prospect's stated problem and readiness | [SF][PL] |
| Contact details | Keep, conditional | Confirm only after next-step consent and only missing operational fields | [PL] |
| Outcome and close | Keep, expand | Use outcome-specific language, permissions, and suppression | [PL][IV] |

Questions that most resemble an interrogation when asked universally are industry, factoring status, satisfaction, cash-flow challenge, and exact monthly volume. They become reasonable only after the preceding answer creates a clear reason to ask. **[PL]**

## 6. Comparison table: current flow versus recommended flow

| Dimension | Current flow | Recommended flow |
|---|---|---|
| Opening | Identity plus generic cold-call permission | Truthful identity/disclosure plus verified or carefully qualified context and permission |
| Relevance | Assumed from lead list | Confirmed through commercial invoices and payment timing |
| Product timing | Porter/factoring before discovery | Brief problem hypothesis first; Porter value after confirmed need |
| Industry | Mandatory caller question | Use enrichment; confirm only if uncertain or materially useful |
| Discovery | Same sequence for most callers | Slot-based, one question at a time, skip known or irrelevant slots |
| Funding method | Factoring yes/no | Internal cash, bank line, factor, other, or none |
| Problem | Generic cash-flow challenge | Specific operational effect of payment timing |
| Listening proof | None | Prospect-language summary and confirmation |
| Volume | Mandatory before advisor | Conditional, approximate, and late |
| Authority | Missing | Confirm decision involvement before booking/transfer |
| Objections | Script/keyword branches | Acknowledge -> clarify -> answer -> confirm -> advance/exit |
| Information request | Often closes immediately | Clarify requested content, approved send, and follow-up permission |
| Qualification | Fields completed | Fit + need + timing + appropriate contact + willingness |
| Ending | General close | Outcome-specific wording, action, permission, and disposition |

## 7. Final recommended Porter call pattern

`Pre-call eligibility/suppression -> Connection and routing -> Identity and approved disclosure -> Context-led permission -> Commercial-invoice relevance gate -> Payment-timing discovery -> Operational impact -> Current funding branch -> Timing and authority -> Problem confirmation -> Tailored Porter value -> Qualification decision -> Low-risk next step -> Operational confirmation -> Clean close -> CRM outcome`

Default opening: **context-led permission opener**, because it combines transparency, relevance, and a small commitment. Permission-based opening has directional observational support; tailoring is a Porter-specific recommendation whose lift must be A/B tested. **[OD][PL][IV]**

### Opening options

| Approach | Porter use | Assessment |
|---|---|---|
| Generic company introduction | Prohibit as default | Honest but gives no reason to listen |
| Permission-only opener | Fallback | Respectful, but relevance is deferred |
| Context-led permission opener | Default | Best balance of truth, relevance, and low commitment |
| Industry-specific problem opener | Use when industry is reliable | Useful if phrased as a possibility, not a claimed fact |
| Trigger-specific opener | Preferred when verified | Highest relevance; prohibited if the trigger is guessed |

**High-confidence trigger:** "Hi, this is Aiva, an automated assistant with Porter Capital. I noticed [verified trigger]. That can sometimes create a gap between operating costs and customer payment. Can I take 30 seconds to see if that's relevant for you?" **[PL][IV]**

**Probable context:** "Hi, this is Aiva, an automated assistant with Porter Capital. We often speak with [industry] businesses that invoice commercial customers and wait to get paid. I don't know if that applies to you. Can I ask one quick question?" **[PL]**

**No reliable trigger:** "Hi, this is Aiva, an automated assistant with Porter Capital. We work with businesses that invoice other businesses or government customers and wait to get paid. Can I ask one quick question to see if this is relevant?" **[PL][IV]**

Prohibit: fake familiarity; invented business events; "we know you have cash-flow problems"; implied preapproval; fake urgency; "did I catch you at a bad time?" as the default; and joking that the prospect can hang up. **[OD][PL]**

## 8. Detailed stage-by-stage specification

### Stage 1: Pre-call relevance and suppression

**Purpose:** Prevent obviously irrelevant, suppressed, or legally unapproved calls.

**Agent action:** Use only approved lead segments. Assign confidence to name, company, industry, trigger, phone type, timezone, and decision role. Never convert a probable enrichment fact into a spoken fact.

**Recommended wording:** None; this stage occurs before connection.

**Data required:** Number, suppression status, legal campaign approval, local time, source, available contact/company context, confidence by field.

**Branch conditions:** Approved lead -> Stage 2. Uncertain fit but permitted -> call with neutral context. Suppressed or legally blocked -> no call.

**Skip conditions:** Never.

**Failure or exit conditions:** DNC match, invalid consent basis where required, disallowed calling window, or prohibited segment. **[PL][IV]**

### Stage 2: Connection and recipient routing

**Purpose:** Determine whether a person, gatekeeper, wrong party, voicemail, or silence answered.

**Agent action:** Say "Hello?" once; allow up to two natural retries. Route before pitching.

**Recommended wording:** Correct contact uncertain: "Hi, is this [name]?" Gatekeeper: "I'm trying to reach the person who handles cash-flow or invoice-financing decisions. Could you point me in the right direction?"

**Data required:** Contact name, company, role, and confidence.

**Branch conditions:** Correct contact -> Stage 3. Gatekeeper -> request role/name or transfer. Wrong person at company -> request correct role once. Wrong number -> apologize and close. Voicemail -> approved voicemail policy only.

**Skip conditions:** Skip identity confirmation if the recipient identifies themselves unambiguously.

**Failure or exit conditions:** Three silence attempts, hostile recipient, wrong number, or no routing information. **[PL][IV]**

### Stage 3: Identity and automated-assistant disclosure

**Purpose:** State who is calling, for whom, and the approved nature of the caller without deception.

**Agent action:** Use Porter's legally approved disclosure exactly. Do not claim to be human.

**Recommended wording:** "Hi, this is Aiva, an automated assistant with Porter Capital."

**Data required:** Approved disclosure version and campaign jurisdiction.

**Branch conditions:** AI question -> answer directly and offer a human. Human request -> Stage 12. Identity concern -> give approved Porter verification details or human route.

**Skip conditions:** The disclosure itself should not be skipped; it may be combined with Stage 4 if approved.

**Failure or exit conditions:** Recipient refuses automated interaction or requests a human who cannot be connected; schedule or close per preference. **[PL][IV]**

### Stage 4: Context-led permission

**Purpose:** Give a credible reason for the interruption and earn a small amount of attention.

**Agent action:** Select the highest-trust context tier available. Keep the request to one breath.

**Recommended wording:** "We work with businesses that invoice commercial customers and wait to get paid. Can I take 30 seconds to see if that's relevant for you?"

**Data required:** Verified trigger, reliable industry, or neutral Porter context.

**Branch conditions:** Yes/go ahead -> Stage 5. Busy -> exact callback option. No/not interested -> one respectful clarification only if it is not a DNC request. Requests purpose -> answer briefly, then ask permission once.

**Skip conditions:** If the prospect immediately states a relevant need or asks for a specialist, acknowledge and advance.

**Failure or exit conditions:** Clear refusal after one response, repeated refusal, DNC, or hostility. **[OD][PL]**

### Stage 5: Commercial-invoice relevance gate

**Purpose:** Establish basic relevance before discussing factoring or collecting financial-scale data.

**Agent action:** Confirm the smallest missing eligibility fact: commercial/government customers and invoicing.

**Recommended wording:** "Do you mainly invoice other businesses or government customers?" If customer type is reliable: "And are those customers usually paying you after the work is delivered?"

**Data required:** Customer type and invoicing evidence from enrichment or conversation.

**Branch conditions:** Commercial/government invoices -> Stage 6. Consumer-only/no invoicing -> likely no fit; close or human review if uncertain. Mixed -> ask whether commercial invoices are material.

**Skip conditions:** Skip a field already stated clearly; confirm only if consequential uncertainty remains.

**Failure or exit conditions:** No commercial invoices, no willingness to clarify, or industry-specific eligibility uncertainty requiring a specialist. **[PL][IV]**

### Stage 6: Payment timing and operational impact

**Purpose:** Determine whether a real receivables timing problem exists.

**Agent action:** Ask payment timing first, then one consequence question only if delay exists.

**Recommended wording:** "How long do those customers usually take to pay?" Then: "What does that wait make harder... payroll, taking on work, or something else?"

**Data required:** Customer type/invoicing, any known payment terms, and the prospect's words.

**Branch conditions:** Delay plus impact -> Stage 7. Delay without impact -> ask whether a future growth event could change that; otherwise no-current-need close. Immediate payment/no gap -> close. Unclear terms -> one confirmation.

**Skip conditions:** Skip payment terms if explicitly supplied in the same answer. Skip impact if the prospect already described it.

**Failure or exit conditions:** No payment gap, no operational effect, refusal to discuss, or repeated incomprehension. **[SF][PL]**

### Stage 7: Current working-capital method

**Purpose:** Understand how the confirmed gap is handled and branch without assuming factoring.

**Agent action:** Ask neutrally after the problem is real.

**Recommended wording:** "How are you covering that gap today... internal cash, a bank line, factoring, or something else?"

**Data required:** Confirmed payment gap and impact.

**Branch conditions:** Internal cash -> ask whether it limits growth only if impact suggests it. Bank line -> ask whether availability is sufficient. Factor -> ask what works and what they would improve. None -> ask whether they are actively exploring options.

**Skip conditions:** Skip if already stated. Skip provider limitations when the current method fully works and the prospect declines comparison.

**Failure or exit conditions:** Fully satisfied/no openness -> clean close. Complex terms or provider dispute -> human route, not advice. **[SF][PL]**

### Stage 8: Timing, approximate scale, and decision involvement

**Purpose:** Distinguish immediate opportunities from nurture and prepare an appropriate handoff without underwriting.

**Agent action:** Ask timing first. Ask approximate commercial invoice volume only if Porter confirms it is needed for routing. Confirm decision involvement before scheduling or transfer.

**Recommended wording:** "Is this something you're looking at now, or more of a later-in-the-year issue?" Conditional volume: "For context, is monthly commercial invoicing closer to tens of thousands, hundreds of thousands, or more?" Authority: "Would you be involved in reviewing an option like this?"

**Data required:** Problem, current method, need timing, volume if required, role.

**Branch conditions:** Now + involved -> Stage 9. Later -> future follow-up. Not involved -> correct-contact route. Unknown volume -> do not block unless Porter sets a hard routing rule.

**Skip conditions:** Skip volume when unnecessary, refused, unreliable, or better handled by a specialist. Skip authority if role is reliably known and confirmed naturally.

**Failure or exit conditions:** No need, no access to decision process, or unwillingness to take a next step. **[PL][IV]**

### Stage 9: Problem confirmation

**Purpose:** Demonstrate listening and validate the business problem before explaining Porter.

**Agent action:** Summarize only confirmed facts in the prospect's language and ask for correction.

**Recommended wording:** "So your customers usually pay in about 45 days, but payroll comes first, and that gets tight when you add new clients. Did I get that right?"

**Data required:** Payment timing, consequence, current method, and any correction.

**Branch conditions:** Confirmed -> Stage 10. Corrected -> update facts and restate once. Rejected -> return to the single misunderstood point or exit.

**Skip conditions:** For a direct human request or simple factual question, do not force a summary first.

**Failure or exit conditions:** Contradictory high-impact facts after one repair -> human review or no qualification. **[SF][PL]**

### Stage 10: Tailored Porter value

**Purpose:** Connect Porter only to the problem the prospect confirmed.

**Agent action:** Use one relevant Porter fact, not the full pitch. Mention invoice factoring here when the prospect understands the context; explain it plainly if asked.

**Recommended wording:** "That's the kind of payment-timing gap Porter can review using eligible receivables. One of our financing advisors can look at whether it fits your setup."

**Data required:** Confirmed problem and approved Porter knowledge.

**Branch conditions:** Interest -> Stage 11. Product/rate/speed question -> answer from locked knowledge, then return. Skepticism -> trust branch. No interest -> close.

**Skip conditions:** Skip the value statement if the prospect only wants a human or has clearly declined.

**Failure or exit conditions:** Any request requiring rates beyond 0.2-2%, funding amount, approval, terms, fees, or industry eligibility -> specialist, with no invented answer. **[PL]**

### Stage 11: Qualification decision

**Purpose:** Choose the correct next step, not maximize meetings at any cost.

**Agent action:** Evaluate fit, need, timing, decision access, and willingness.

**Recommended wording:** No additional scripted question unless a single decisive item is missing.

**Data required:** Commercial invoices, payment timing, impact, current method, timing, authority/access, and consent to next step.

**Branch conditions:** Qualified-now -> live transfer or schedule. May-fit/later -> scheduled or future follow-up. Needs human eligibility review -> human escalation. No fit/no need -> clean close.

**Skip conditions:** Direct human request bypasses normal qualification, but the handoff must label missing fields.

**Failure or exit conditions:** Never mark qualified solely because all form fields are present. **[PL][IV]**

### Stage 12: Low-risk next step

**Purpose:** Secure the smallest useful commitment.

**Agent action:** Offer one next step appropriate to readiness, with an alternative only if useful.

**Recommended wording:** "Would it make sense to spend 15 minutes with a financing advisor to see whether the setup fits? I can connect you now, or find a better time."

**Data required:** Availability, specialist routing rules, and prospect preference.

**Branch conditions:** Transfer -> live-transfer close. Schedule -> Stage 13. Information -> approved-send route plus explicit follow-up permission. Later -> future follow-up. No -> close.

**Skip conditions:** DNC, hostile, unqualified, or clear refusal.

**Failure or exit conditions:** Do not claim a transfer, email, or appointment succeeded until it is operationally confirmed. **[SF][PL]**

### Stage 13: Operational confirmation and contact details

**Purpose:** Confirm only what is required to execute the agreed next step.

**Agent action:** Reuse reliable lead data. Confirm date, time, timezone, channel, destination, and permission. Ask no duplicate fields.

**Recommended wording:** "I have [email/phone] for you. Is that still the best way to reach you?" and "That's Tuesday at 2 p.m. Central, correct?"

**Data required:** Existing name, role, company, phone, email, timezone, and chosen action.

**Branch conditions:** Confirmed -> Stage 14. Correction -> update and reconfirm once. Missing required field -> ask only that field.

**Skip conditions:** Live transfer may need no additional contact collection. No-next-step outcomes need none.

**Failure or exit conditions:** No confirmed channel/time or no follow-up permission means no appointment or marketing follow-up may be recorded as confirmed. **[PL][IV]**

### Stage 14: Clean ending and outcome recording

**Purpose:** End with accurate expectations and a usable disposition.

**Agent action:** State the agreed action, avoid new selling, thank the prospect, and record outcome, permissions, suppression, and handoff facts.

**Recommended wording:** Use the outcome-specific matrix in Section 12.

**Data required:** Outcome, commitments, permission, suppression, and handoff summary.

**Branch conditions:** Record exactly one primary disposition plus secondary context.

**Skip conditions:** Never.

**Failure or exit conditions:** A call is incomplete until the disposition and any suppression or promised action are recorded. **[PL][IV]**

### Discovery-field rules

| Field | Mandatory? | May infer? | Confirm? | Skip when | Placement reason |
|---|---|---|---|---|---|
| Customer type | Yes for qualification | Yes, cautiously | If uncertain | Clearly stated | Basic commercial fit before financial questions |
| Payment terms | Yes for need | Enrichment is hypothesis only | Yes through conversation | Already stated | Establishes whether a timing gap exists |
| Operational impact | Yes for active need | No | Reflect back | No gap or already stated | Lets prospect define consequence |
| Current funding method | Conditional after gap | May infer, do not trust silently | Ask/confirm | No gap or already stated | Enables relevant branch |
| Provider limitations | Conditional | No | Reflect back | No provider, fully satisfied, or refusal | Prevents competitor fishing |
| Invoice volume | Conditional, Porter to confirm | May use range | Only if routing requires | No need, refusal, specialist can collect | Financial question should come late |
| Timing/urgency | Yes for disposition | No | Confirm callback timing | Explicitly stated | Separates now, later, and no need |
| Decision authority | Yes before booked next step | May infer from role | Light confirmation | Reliable and naturally confirmed | Avoids unproductive handoffs |

Do not collect on the initial call: SSN, tax ID, passwords, payment-card data, full bank account/routing credentials, login codes, full customer lists, invoice-level documents, personal guarantees, ownership schedules, financial statements, legal documents, or underwriting documentation. Do not provide legal, tax, accounting, or investment advice. **[PL][IV]**

## 9. Full branching decision tree

```text
PRECALL
  suppressed/unapproved -> DO NOT CALL
  approved -> CONNECT

CONNECT
  silence -> retry up to 3 -> technical/no-response close
  voicemail -> approved voicemail or disposition
  gatekeeper -> ask for responsible role -> transfer/referral/callback/close
  wrong number -> apologize -> suppress bad number -> close
  wrong person at company -> request correct contact once -> referral/close
  correct contact -> DISCLOSE + CONTEXT + PERMISSION

PERMISSION
  yes -> RELEVANCE
  busy -> confirm callback date/time/timezone -> schedule callback
  no/not interested -> acknowledge -> one optional reason clarification
      timing -> callback only with permission
      no need -> no-current-need close
      cold-call refusal -> refusal close
  DNC -> confirm suppression -> end immediately
  hostile -> one de-escalation -> end

RELEVANCE
  commercial/government invoices -> PAYMENT TIMING
  consumer-only/no invoices -> unqualified or human review if uncertain
  bad enrichment -> apologize, update, use neutral question
  incomplete/conflicting -> one concise confirmation -> human review if consequential

PAYMENT TIMING
  meaningful wait -> IMPACT
  prompt payment/no gap -> no-current-need close
  asks what factoring is -> plain approved explanation -> resume
  cannot understand -> two repairs -> technical close/human option

IMPACT
  operational effect -> CURRENT METHOD
  no effect -> check future timing once -> nurture or close
  does not need funding -> no-current-need close

CURRENT METHOD
  internal cash -> ask whether it constrains operations/growth
      no limitation -> satisfied/no-need close
      limitation -> TIMING
  bank line -> ask whether availability/timing covers the gap
      sufficient/satisfied -> optional compare once, then close
      insufficient/restricted -> TIMING
  factor -> ask what works and what they would improve
      satisfied -> optional comparison once; decline -> close
      dissatisfied/bad experience/expensive -> clarify one issue -> TIMING
  none -> ask whether options are being considered -> TIMING or close

INTERRUPTING INTENTS (may occur at any stage)
  rates -> approved 0.2-2% general range + custom explanation -> resume/offer human
  funding amount -> no promise; advisor reviews setup -> human route
  speed -> once set up, usually under 48 hours after invoice submission -> resume
  guarantee -> explicitly no guarantee -> human route or resume
  legitimacy -> approved company facts + official verification/human option
  are you AI -> direct disclosure + human option
  human request -> transfer or schedule immediately
  send information -> clarify topic -> approved material + follow-up permission
  DNC -> suppress and terminate, overriding every state

TIMING + AUTHORITY
  ready now + involved -> optional volume -> CONFIRM PROBLEM
  ready now + not involved -> referral/human route
  later -> exact future callback with permission
  no current need -> future permission or clean close

CONFIRM PROBLEM
  confirmed -> TAILORED VALUE
  corrected -> update and restate once
  rejected/unclear -> resolve one fact or exit

TAILORED VALUE + NEXT STEP
  qualified and ready -> live transfer if available; otherwise schedule
  qualified but later -> schedule/future follow-up
  may fit, eligibility uncertain -> human review
  asks for information -> approved send + explicit follow-up permission
  declines -> clean close
```

This tree covers all requested scenarios. A DNC request, explicit human request, identity correction, or material product question has priority over the current discovery stage. **[PL][IV]**

## 10. Objection-handling matrix

Reusable loop: `pause -> acknowledge -> clarify once -> respond only to the real issue -> confirm -> advance or exit`. Maximum is normally one clarifying attempt and two total objection turns. DNC is not an objection and receives no rebuttal. **[SF][PL]**

| Category | Likely meaning | Acknowledge | Clarify | Approved response direction | Max | Return / escalate / end | CRM |
|---|---|---|---|---|---:|---|---|
| Dismissive: "not interested" | Interruption, no relevance, or reflex | "Fair enough." | "Is it mainly timing, no need, or that it's a cold call?" | Address only selected reason | 1 | Return if invited; otherwise end | `not_interested` + reason |
| Timing: "busy" | Cannot engage now | "I understand." | "Would later today or another day be better?" | Confirm exact callback only | 1 | Schedule or end | `callback_requested` |
| No need | No gap or no priority | "Got it." | "Is that because customer payments already line up with your costs?" | Validate no-need; do not force pain | 1 | Future permission or end | `no_current_need` |
| Cost / too expensive | Prior experience or price sensitivity | "That makes sense." | "Was the concern the rate, extra fees, or the overall structure?" | Give only approved 0.2-2% general range if asked; custom review | 1 | Human if interested; else end | `cost_objection` |
| Existing bank | Current solution may be enough | "Good, you already have something in place." | "Does the available line cover the gap when volume grows?" | Position review only if limitation exists | 1 | Return, optional compare, or end | `existing_bank` |
| Existing factor | Incumbent provider | "That makes sense." | "What works well, and is there anything you'd change?" | Never attack competitor; compare only with permission | 1 | Dissatisfied -> discovery; satisfied -> one optional compare then end | `existing_factor_satisfied/dissatisfied` |
| Trust / legitimacy | Scam concern or unfamiliar brand | "That's a fair question." | "Would official company information or a human conversation be more useful?" | Approved Porter facts, official site, Birmingham location, human verification | 1 | Human route or end | `trust_objection` |
| Product question | Wants facts before discovery | "Sure." | Clarify only if question is ambiguous | Locked KB answer; rates/speed boundaries; defer terms/eligibility/amount | 1 | Resume or human | `product_question` + topic |
| Human request | Rejects bot or wants expertise | "Of course." | Ask only now versus scheduled | Transfer or schedule without further qualification | 0 | Escalate immediately | `human_requested` |
| Compliance / DNC | Revokes contact | "Understood. I'll mark this number so Porter doesn't call again." | None | Suppress; no pitch, reason question, or confirmation loop | 0 | End immediately | `do_not_call` |

Special handling: a bad prior factoring experience is a trust/provider objection. Acknowledge the experience, ask what specifically went wrong, and only connect Porter's approved service differentiator to that issue. Do not promise Porter will eliminate it. **[PL]**

## 11. Human-handoff criteria and summary format

### Offer an immediate live transfer when

- The prospect explicitly asks for a human.
- The prospect has commercial receivables, a present timing problem, and wants to explore now.
- The question concerns specific rates, funding amount, terms, fees, selective/full factoring, eligibility, or a complex incumbent arrangement.
- A trust concern would be better resolved by a person.
- Eligibility is uncertain and the prospect wants an answer. **[PL][IV]**

### Offer a scheduled specialist call when

- The prospect appears relevant and interested but is unavailable.
- The appropriate specialist is unavailable.
- The prospect wants a later discussion and confirms date, time, timezone, and contact channel. **[PL]**

### Offer approved information when

- The prospect requests a specific approved resource.
- The delivery address is confirmed.
- The system can actually send it.
- Follow-up permission and timing are explicit. Sending information alone is not permission for indefinite follow-up. **[PL][IV]**

### Offer future follow-up when

- The prospect may fit but has no present need.
- A known event may create future need.
- The prospect explicitly approves a concrete follow-up window. **[PL]**

### Offer no next step when

- DNC, repeated refusal, hostility, wrong number, no commercial invoices, no need and no follow-up permission, or a fully satisfactory existing solution with no interest in comparing. **[PL]**

### Minimum handoff summary

```yaml
contact:
  name: confirmed-or-unknown
  company: confirmed-or-unknown
  role: confirmed-or-unknown
  decision_involvement: decision_maker | participant | referrer | unknown
fit:
  customer_type: business | government | mixed | unknown
  commercial_invoices: yes | no | unknown
  typical_payment_timing: prospect-words-or-unknown
need:
  operational_effect: prospect-words-or-none
  current_funding_method: internal_cash | bank_line | factor | other | none | unknown
  provider_limitation: prospect-words-or-none
  approximate_invoice_volume: range-or-unknown
  timing: now | dated_future | no_current_need | unknown
conversation:
  main_objection: category-and-words-or-none
  reason_for_accepting_handoff: prospect-words
commitment:
  next_step: live_transfer | scheduled_call | info_followup | future_followup
  confirmed_time_timezone_channel: value-or-not-applicable
  promises_made: exact-operational-commitments-only
```

Unknown values must remain unknown. Never fill gaps with enrichment guesses. **[PL]**

## 12. Call-ending and CRM-disposition matrix

| Outcome | Final agent wording | CRM disposition | Follow-up | Future contact | Suppress? |
|---|---|---|---|---|---|
| Live transfer | "Thanks. I'm connecting you with a financing advisor now, and I'll pass along what you shared." | `live_transfer` | Transfer and summary | As agreed | No |
| Scheduled appointment | "You're set for [date] at [time] [timezone] by [channel]. The advisor will review [purpose]. Thanks for your time." | `appointment_booked` | Calendar/confirmation | Yes, for appointment | No |
| Information + follow-up | "I'll send the approved information to [email], and we'll follow up on [date/time]. Is that correct?" | `info_followup_authorized` | Send only if confirmed; scheduled follow-up | Only as confirmed | No |
| Future opportunity | "Understood. I'll note [time/event] and have the team check back then. Thanks for being clear with me." | `future_followup` | Dated task | Yes, within permission | No |
| No current need | "Got it. It sounds like the timing gap isn't creating a need right now. Thanks for your time." | `no_current_need` | None unless invited | Only if separately permitted | No |
| Existing solution satisfies | "Good to hear it's working for you. I won't keep you. Thanks for the time." | `existing_solution_satisfied` | None | Only if separately permitted | No |
| Not qualified | "Thanks for explaining it. Based on what you've shared, this doesn't sound like the right conversation for Porter today." | `not_qualified` | None or human review if uncertainty remains | Policy-dependent | No |
| Wrong person | "Thanks. Who would be the right person for invoice-financing decisions?" If no referral: "No problem. Thanks for your help." | `wrong_person` | Referral task if supplied | Business-contact policy | No |
| Wrong number | "Sorry about that. I have the wrong number. Thanks for letting me know." | `wrong_number` | Correct data | No to that number | Yes for bad number |
| Clear refusal | "Understood. I won't keep you. Thanks for your time." | `not_interested` | None | Campaign policy unless DNC | No |
| DNC request | "Understood. I'll mark this number so Porter doesn't call again. Goodbye." | `do_not_call` | Immediate suppression | No | Yes |
| Hostile termination | "I understand. I'll end the call now." | `hostile_termination` | None; review if necessary | No immediate retry | Policy-dependent |
| Technical failure | "I'm sorry, the connection isn't clear enough to continue. I'll end the call here." | `technical_failure` | Retry only under approved policy | Policy-dependent | No |
| Human escalation | "Of course. I can connect you now or arrange a time for a financing advisor to call. Which works better?" | `human_escalation` | Transfer/schedule | As agreed | No |

Legal/compliance must define whether an entity-specific DNC request is applied at number, person, company, campaign, or all-Porter scope. The safe product behavior is immediate suppression at the broadest approved scope, with no rebuttal. **[IV]**

## 13. Evaluation rubric and automatic failures

### 100-point call score

| Dimension | Points | Full-credit standard |
|---|---:|---|
| Opening relevance | 8 | Context is truthful, concise, and confidence-appropriate |
| Permission handling | 6 | Permission is clear; refusal/busy responses are respected |
| Discovery quality | 12 | Establishes customer type, payment timing, impact, and only relevant branches |
| Listening | 10 | Uses supplied facts, reflects prospect language, and repairs corrections |
| Question efficiency | 8 | One question per turn, no repeats, no unnecessary fields |
| Problem identification | 10 | Identifies a concrete payment-timing consequence or correctly finds none |
| Adaptation | 10 | Skips known fields and routes bank/factor/internal-cash/no-need paths correctly |
| Objection handling | 10 | Acknowledges, clarifies once, answers the real issue, advances or exits |
| Porter value explanation | 8 | Uses one approved fact tied to the confirmed problem |
| Qualification accuracy | 8 | Correct fit/need/timing/authority decision; uncertainty is preserved |
| Human handoff quality | 5 | Correct route and concise factual summary |
| Closing quality | 3 | Confirms action and ends cleanly without reopening sales |
| CRM disposition accuracy | 2 | Outcome, permission, commitments, and suppression are correct |
| **Total** | **100** | |

Suggested acceptance threshold: 85 overall, no automatic failure, at least 70% in every dimension. This threshold is an initial QA proposal and requires calibration against Porter-reviewed calls. **[IV]**

### Automatic failures

- False or implied funding promise.
- Invented pricing, fee, term, timing, funding amount, or eligibility.
- Ignoring or arguing with a DNC request.
- Misrepresenting Aiva as human or concealing identity when asked.
- Continuing sales pressure after repeated refusal.
- Asking for prohibited sensitive information.
- Giving unauthorized legal, tax, accounting, underwriting, or financial advice.
- Fabricating a lead fact, trigger, prior contact, or customer statement.
- Creating or claiming an appointment, transfer, email, or callback without confirmation.
- Criticizing a bank, factor, or competitor without substantiated approved evidence.
- Marking a lead qualified when the decisive facts are unknown or contradictory.
- Failing to record required suppression. **[PL][IV]**

## 14. Evidence strength and limitations

1. **Permission-based opening [OD]:** Gong publishes analyses of large call datasets and reports stronger outcomes for permission-based openers. This is proprietary observational data. Selection bias, customer mix, seller quality, definitions of success, and product category may confound results. It does not prove the same lift for Porter or an AI caller.
2. **Buyer receptiveness [BS]:** RAIN Group's prospecting research surveyed 488 buyers and 489 sellers across industries and reports broad willingness to engage with proactive sellers. It is self-reported, vendor-published, older, and not specific to invoice factoring or automated voices.
3. **Problem-led discovery and summaries [SF]:** Consultative and problem-discovery frameworks support asking about situation, impact, and need before a tailored value statement. These are practice frameworks, not direct experimental proof of Porter's conversion rate.
4. **Conditional questions [PL]:** Skipping irrelevant and already-answered questions follows basic conversation coherence and directly addresses failures observed in Porter's current deterministic flow. Porter must validate conversion and qualification effects through transcript review and controlled tests.
5. **Rates, speed, claims, and industry handling [PL]:** These come from Porter's locked John-questionnaire knowledge, not external research. They remain authoritative only while that internal source is approved and current.
6. **Legal/compliance [IV]:** FTC and FCC sources establish material regulatory risk, but this document is not legal advice. B2B status does not justify assuming every call, number, state, recording practice, or AI-voice use is permitted.

Sources:

- [Gong, How to master cold calls](https://www.gong.io/resources/guides/how-to-master-cold-calls)
- [Gong, best and worst cold-call openers](https://www.gong.io/blog/the-best-and-worst-cold-call-openers-backed-by-data-from-300m-calls)
- [RAIN Group study summary: 488 buyers and 489 sellers](https://customerthink.com/new-rain-group-center-for-sales-research-study-debunks-common-myths-about-sales-prospecting/)
- [FTC Telemarketing Sales Rule](https://www.ftc.gov/legal-library/browse/rules/telemarketing-sales-rule)
- [FTC 2024 B2B telemarketing protections and recordkeeping update](https://www.ftc.gov/news-events/news/press-releases/2024/03/ftc-implements-new-protections-businesses-against-telemarketing-fraud-affirms-protections-against-ai)
- [FCC statement on AI-generated voices and the TCPA](https://docs.fcc.gov/public/attachments/DOC-400393A1.pdf)
- [Porter Capital official site](https://portercap.com/)

## 15. Specific questions Porter management must answer before implementation

1. What exact customer types, invoice characteristics, geographies, and minimum/maximum ranges define a potentially suitable lead?
2. Which facts are absolute disqualifiers, and which require a financing-advisor review?
3. Is approximate monthly commercial invoice volume required on the cold call, merely useful, or specialist-only?
4. What volume bands, if any, are approved for routing without suggesting eligibility?
5. Which pre-call triggers may be spoken, and what source/confidence threshold makes each trigger "verified"?
6. Which industry/payment-cycle hypotheses are approved, including any "30 to 60 day" wording?
7. What exact AI/automated-assistant, sales-purpose, recording, and consent disclosures are required by campaign and jurisdiction?
8. Which number types, states, time windows, consent sources, and dialing methods are approved by counsel?
9. What is the scope and retention policy for DNC suppression?
10. What official facts may Aiva use for legitimacy, and should the public "over $10B" claim replace or remain behind the conservative locked "billions" wording?
11. What approved information can actually be emailed, and what workflow confirms successful sending?
12. What are live-transfer hours, queues, fallback behavior, and maximum transfer wait?
13. What appointment duration, calendars, timezone rules, and confirmation channel are approved?
14. What constitutes qualified-now, nurture, no-need, and unqualified in CRM?
15. Is decision authority mandatory, or is an influencer/referrer acceptable for a specialist call?
16. Which current-bank/factor comparison statements are approved?
17. How many objection attempts and future follow-ups are permitted by policy?
18. Which handoff fields are truly required versus merely desirable?
19. How should mixed B2B/B2C companies be routed?
20. Who owns weekly transcript review, score calibration, false-positive qualification review, and script approval?

## 16. Final implementation-ready call-flow specification

### Conversation slots

```yaml
identity:
  recipient_match: confirmed | wrong_person | gatekeeper | wrong_number | unknown
  disclosure_complete: true | false
permission:
  status: granted | busy | refused | dnc | unknown
relevance:
  customer_type: business | government | mixed | consumer | unknown
  commercial_invoices: yes | no | unknown
  payment_timing: value | unknown
need:
  timing_gap: yes | no | unknown
  operational_effect: value | none | unknown
  current_method: internal_cash | bank_line | factor | other | none | unknown
  current_method_issue: value | none | unknown
  need_timing: now | later | none | unknown
qualification:
  invoice_volume_band: value | declined | unknown
  decision_involvement: decision_maker | participant | referrer | not_involved | unknown
  eligibility: potential_fit | no_fit | human_review | unknown
next_step:
  type: live_transfer | appointment | information | future_followup | none
  channel: phone | email | other | unknown
  date_time_timezone: value | not_applicable | unknown
  permission_confirmed: true | false
control:
  objection_count: integer
  repair_count: integer
  dnc: true | false
  disposition: value | unknown
```

### Intent priority

Process each caller turn in this order:

1. DNC/stop request.
2. Hostility or safety issue.
3. Human request.
4. Identity, company, or lead-data correction.
5. Direct Porter/product question.
6. Busy/callback or information request.
7. Objection.
8. Answer to the current stage.
9. Ambiguity/repair.

Higher-priority intents suspend the normal stage. A factual answer should return to the last meaningful stage only if the prospect has not refused and the question still matters. **[PL]**

### State transitions

| State | Required entry condition | Ask/action | Success transition | Alternate transition |
|---|---|---|---|---|
| `precall` | Campaign-approved record | Validate suppression/context confidence | `connect` | `no_call` |
| `connect` | Call answered | Identify recipient type | `disclose` | gatekeeper/wrong/silence outcomes |
| `disclose` | Correct or willing contact | Identity + approved automation disclosure | `permission` | human/decline |
| `permission` | Disclosure complete | Context-led small request | `relevance` | busy/refusal/DNC |
| `relevance` | Permission granted | Ask smallest missing commercial-invoice fact | `payment_timing` | no-fit/human-review |
| `payment_timing` | Commercial invoices possible | Ask timing, then impact if needed | `current_method` | no-need/repair |
| `current_method` | Real gap/impact | Ask how gap is covered; branch | `timing_authority` | satisfied/no-need/human |
| `timing_authority` | Potential need | Ask timing, conditional volume, involvement | `problem_confirm` | future/referral/close |
| `problem_confirm` | Enough facts to summarize | Reflect and verify | `value` | correction/repair |
| `value` | Problem confirmed | One tailored Porter statement | `qualification` | product question/decline |
| `qualification` | Fit/need/timing facts | Select appropriate outcome | `next_step` | close/human-review |
| `next_step` | Prospect willing | Transfer, schedule, send, or future follow-up | `confirm` | decline close |
| `confirm` | Operational action chosen | Confirm only required missing fields | `close` | correction/no confirmation |
| `close` | Outcome known | Exact ending + disposition + permission/suppression | complete | never reopen discovery |

### Hard conversation rules

1. Ask one question per turn.
2. Never repeat a question verbatim after an ambiguous answer; acknowledge and narrow it.
3. Do not ask a slot already supplied clearly.
4. Do not ask industry solely because it is the next state.
5. Do not mention factoring as the presumed solution before commercial invoices and a potential timing gap are established, unless the prospect asks directly.
6. Do not ask current factor satisfaction unless `current_method == factor`.
7. Do not ask provider limitations unless a provider/method exists and the prospect is open to discussing it.
8. Do not ask volume before relevance and impact; do not block a human request on volume.
9. Do not collect contact details before agreement to a specific next step.
10. Preserve unknowns; never turn uncertainty into a positive qualification.
11. Use at most four adaptive discovery questions before summarizing, proposing a next step, or exiting.
12. Use at most one clarifying question per objection and two objection turns total.
13. Use at most two comprehension repairs after connection; then end or offer a human channel.
14. DNC terminates immediately and overrides every other state.
15. The close confirms the action; it does not restart the pitch. **[PL][IV]**

### Qualification decision

```text
QUALIFIED_NOW when:
  commercial invoices are confirmed or highly credible,
  a payment-timing problem and operational effect are confirmed,
  need is current,
  the contact is involved or can bring the right person,
  and the prospect agrees to a specialist conversation.

QUALIFIED_LATER when:
  potential fit is credible,
  a future need/event is identified,
  and a specific follow-up is explicitly permitted.

HUMAN_REVIEW when:
  industry eligibility, structure, rates, amount, terms, or conflicting fit facts
  cannot be resolved from approved knowledge.

NO_CURRENT_NEED when:
  commercial relevance may exist but no meaningful timing problem or priority exists.

NO_FIT when:
  no material commercial/government invoices exist, subject to Porter's approved rules.

STOP when:
  DNC, repeated refusal, hostility, wrong number, or prohibited collection occurs.
```

This specification replaces universal field completion with explicit state, slot, priority, and exit rules. It should be implemented only after the Section 15 decisions are approved, then validated with scripted branch tests, transcript scoring, and a controlled human-reviewed pilot. **[PL][IV]**
