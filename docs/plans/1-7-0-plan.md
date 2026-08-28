# 1.7.0 — plan

**Revision 2, 2026-08-27.** Adds the findings of the owner's architectural assessment of
`main` at `2448f5d1` (read the same evening; every claim acted on was re-verified against the
tree): six new issues (#1147–#1152), two existing ones sharpened (#154, #301), and three
placement changes (§7). Revision 1 was written while the 1.6.6 sets were closing (FastAPI+React
4 of 6, Next.js+TS in flight), from three inputs and nothing else: the ROADMAP's 1.7 identity (assigned
2026-08-07, `docs/plans/post-1-5-roadmap-reconciliation.md`), the 2026-08-21 open-issue sweep
(`docs/plans/issue-sweep-2026-08-21.md`, whose 1.7 slate this plan confirms and extends), and
the 1.6.3–1.6.6 verification-set records. **83 issues are open** at this writing (77 at rev 1,
plus the six the assessment produced); every one of
them is placed below — in a pack, at a gate, in 1.8's lane, or in verify-then-close — and the
owner's three asks shape the packs: **squash a lot of bugs, fix the thinking-token problem, and
harden for 1.8.**

**1.7 is an odd minor: feature-free by rule.** Its identity is *every port is actually a port* —
1.5 extracted structure inside the machinery; 1.7 fixes where the machinery meets the outside
world, so that the Atlas provider migration and 1.8's scorecard grade over seams that hold.
Substance gates the cut, not the clock; the cut criteria are in §6.

---

## 1. What 1.6 left on the table

Three facts from the records decide the shape of this plan.

**The correction loop's remaining reds are one class, and it is not a pack item.** Both 1.6.6
FastAPI+React rejections (rolls 3 and 6) and 1.6.5's roll 1 were a free-authored qa suite
asserting something the contract never said — a declared boolean is a name; a fetch spy must see
one particular URL — a correct dev repair rejected by that assertion, and no route to the
qa-owned file. The pack's six items held on every roll they were exercised on. What is left is
#1123 (scope the repair to the failing cases, add a machine signal), #1130 (route a qa-owned
defect to `qa.test_repair`), and the kind-gate finding from 1.6.6 roll 3 (a FastAPI+React
counterpart to #1094: an assertion contradicting a declared field kind is rejected at emission).

**The reasoning channel is the largest measured waste in the system, and it is invisible.**
#924's probe on the deployed qa brief: reasoning on, **5,727** completion tokens; reasoning off,
**413** — the same 8 fill fences, 13.9× the tokens; at a 2,500-token budget, 19,179 characters of
thinking and an empty response. #410 measured ~60% of an implementation run's generation time
bought thinking nobody can read: the Ollama adapter never sends `think`, reads only
`message.content`, and declares `THINKING_TOKENS: False`. Every completion-cap finding since
(#998, the 3-of-8 cap hits in 1.6.4, 1.6.5's E raising eve to 12,288) was treating this
symptom. The first fix (#925) was rejected because it was a boolean on a handler — a switch,
not a seam, and Ollama's shape leaking into a provider-neutral port. That is exactly a 1.7
question.

**The "generic" scaffold is stack #1.** `stack_nextjs_ts.py` exists and no stack-#1 module does;
a Next.js-shaped predicate written into a shared module discarded a green React suite (the
self-mocking finding, #1126), and the owner asked whether they must keep reminding us to stay
stack-aware. The answer is structural: #1131.

**The boundary is declared, not enforced.** The assessment's count: 32 port interfaces, a
forbidden-imports guard covering four directories, and one file of real architectural rules
for a 90,000-line hexagonal system. Verified on `2448f5d1`: four domain modules import
`adapters.*` outside any composition root — the orchestrator reaching for the NoOp
observability adapter, the config loader for the secrets factory, a cycles *route* constructing
`OllamaAdapter` directly, and a bootstrap check (#154, #301). The doctrine says guardrails over
discipline; the guard is what 1.7 owes.

---

## 2. The packs

Feature-free means every item below fixes, extracts, enforces, or measures something that
already exists. Each pack ends with **how we know it worked** — the verification story is part
of the pack, not an afterthought. The packs are named for their subject; the name is the
handle used in PR titles, the 1.7.x line table (§3.1) and the record:

| pack | the subject | why it is one pack | verified by |
|---|---|---|---|
| **Reasoning** | the model's reasoning channel — paid for, discarded, invisible | one fact (how much reasoning a task wants) with today five touchpoints and no port | rolls (one shakeout per stack + the #924 replay) and an adapter characterization suite |
| **Stack Seams** | what is stack-specific lives behind the stack seam; the loop's last red class lives at that seam | the 1.6.5/1.6.6 reds are one class, and F1 was a stack-shaped check in a shared file | rolls (the 1.6.6 reds replayed, then a counting set) and the structural guard |
| **Loop Honesty** | the correction loop keeps its own state and checks its own claims | every item is the loop discarding something it produced or trusting something it never verified | rolls (each item's originating roll replayed; the sets' texture fields) |
| **Boundaries** | vendor vocabulary and boundary conventions kept out of the domain | the 1.7 identity itself — every port is actually a port | CI: structural tests that fail on the leaked vocabulary |
| **Composition Root** | the runtime is wired through its factories, not around them | three issues that all alter initialization; one design note before code | CI: a bare import of `main` succeeds; the factories are the only constructors reachable |
| **Hardening** | what 1.8's scorecard and unattended campaigns need underneath | lineage, ops floor, CI truth, packaging fidelity — none of it feature-shaped | CI as the instrument: the integration job green on main, images running the deps the suite ran |

Reasoning, Stack Seams and Loop Honesty change what a cycle does and are the **measured packs**;
Boundaries, Composition Root and Hardening are provable without a cycle and ride as the
**CI-verified riders** (§3.1).

### 2.1 Pack **Reasoning** — the reasoning channel (the thinking-token problem)

The owner's second ask, and the pack with the widest blast radius: it touches every LLM call.

- **#927 — reasoning effort is contract-declared and provider-neutral.** The capability contract
  says whether its output is a *transcription* (fill slots, repair verdicts, a stored report) or
  an *argument* (authoring a manifest, a failure analysis); the port carries a level
  (`none | low | medium | high`), never a bool; adapters map down (Ollama: `none → think:false`,
  else `think:true`; an OpenAI-compatible surface → effort; Anthropic → a budget). It resolves
  through the chain that already exists (`agent_config_overrides` → capability default →
  model-spec clamp), one fact in one place.
- **#410 — the adapter reads the channel it pays for.** When thinking is on, `message.thinking`
  is captured and emitted to LangFuse under the redaction rules, so the spend is visible; the
  per-call `eval_count`-vs-content gap becomes a recorded number rather than a forensic one.
- **#924 (budget half)** — with `none` on the qa fill and repair paths, the completion cap
  stops being the story; 1.6.5's E (eve at 12,288) is re-examined once the channel is off where
  it should be, and lowered if the distribution says so.
- **#1145 — an unregistered model fails loudly, once.** Registry membership is a preflight
  fact; the three budget paths fall back the same way; `context_window=None` never reaches the
  prompt-size guard silently.
- **#901 — `top_p` beside `temperature`**, the half of the sampling pair the profiles expose
  and nothing can reach. **#930 — an agent boots logging the model it will actually use.**
- **#929 + #944 — extract the LLM call sequence (the duplication, not the thirteen sites) and
  delete the dead `LLMRouter`** whose docstring claims it is wired. This is the Atlas seam:
  after it, a provider is an adapter behind one port with a characterization suite, and the
  status vocabulary in the port is ours.

**How we know:** (1) the #924 probe replayed through the port — same brief, `none` vs `high`:
the 413/5,727 split reproduced from our own telemetry, thinking text present in LangFuse on
the `high` run; (2) one shakeout per stack with `none` on qa fill/repair and `high` on framing,
asserting fills-first still holds (Q0) and the qa primary distribution moves down; (3) the
adapter characterization suite runs in CI against a recorded Ollama transcript, so the mapping
cannot regress unobserved.

### 2.2 Pack **Stack Seams** — the stack seam and the correction loop's last red class

- **#1149 — harvest the rationale first.** `scaffold.py`'s comments are where the "why" of stack
  #1 lives (an 824-line `envelope_example` is embedded stack data in code form); a comment does
  not survive an extraction unless the refactorer reads it. The harvest into a durable home
  (the proposed design-decision register, or a SIP amendment section) is the precondition of
  every extraction in this release, and an extraction PR cites its register entry.
- **#1131 — extract `stack_fastapi_react.py`** from `scaffold.py` as a pure move (fixtures
  byte-identical, GENERATOR_VERSION unchanged), register through `ScaffoldStack`, and land the
  **structural guard**: no stack-shaped literal (`app/api/`, `.test.tsx`, `pytest`, `vitest`,
  `routes.py`…) outside a `stack_*` module or a stack-parameterised predicate. It would have
  failed on the commit that produced F1.
- **#1153 — the kind gate for free-authored suites** (filed from 1.6.6 roll 3): an assertion that
  contradicts a declared field kind (`removed: boolean` asserted equal to a name) is rejected at
  emission with the declared kind named — the #1094 rule, generalised from fills to any
  assertion the stack seam can bind to a declared field. On the evidence it flips roll 3
  outright.
- **#1130 — route a qa-owned defect to `qa.test_repair`** when the analysis implicates the qa
  file and no probe implicates the app (the 1.6.5 roll 3 `client.delete(json=)` shape: named by
  every analysis, never dispatched to). **#1123 — scope the qa repair to the failing cases and
  route on a DOM-anchor machine signal** rather than an LLM's opinion of a speculative assertion
  (1.6.6 roll 6: a correct app, audit PASS, exhausted by its own fetch-spy expectation).
- **#668 — the DOM testid contract gets its enforcement layer**, which #1123's signal needs;
  **#939 — `undefined_names` for the Next.js stack** (`.py`-only today); **#1022 — additive-suite
  containment** (every V7 counted red was an unconstrained additive test); **#1087 (stack-#1
  half) + #1112** — the store hands out tables for shapes no correct app writes.
- **#1122 — SIP-0104 shells and fill slots for stack #1** is *not* in this pack. It is a
  capability extension with a SIP behind it; it is the 1.8-lane consumer of #1131's seam, and
  it goes to its own design review with the Stack Blueprint rewrite (`project` note: rewrite
  against main after #1131).

**How we know:** the 1.6.6 record's two reds replayed — roll 3's stored suite through the kind
gate (rejected, boolean named), roll 3's analysis through the router (target = the qa file),
roll 6's suite through #1123's scoping (the failing case isolated) — before any new roll; then
a FastAPI+React counting set on the 1.6.6 protocol with the same R-predictions plus one per
item here. The structural guard is its own test.

### 2.3 Pack **Loop Honesty** — the correction loop keeps its own state and checks its own claims (bug squash, class by class)

The owner's first ask, taken as the sweep's 1.6.x leftovers that touch the loop and were
never scheduled, grouped by the mechanism each shares:

- **The repairer never sees the traceback (#788) — first, because it is one tuple.** The
  application's real traceback is captured (#687) and reaches the analyzer's evidence, but the
  repair prompt renders five evidence blocks (`repair_handlers.py:97`) and `app_tracebacks` is
  not one of them. A one-entry change with a clean prediction: repairs on runtime-error failures
  land more often when the repairer reads the error. The assessment's highest-information item
  per unit of effort, and this plan agrees.
- **The loop discards its own state:** #994 (rewind after a successful repair re-dispatches
  develop and drops the repaired tree), #995 (a timeout mid self-eval is banked as "zero
  chars", erasing the real history), #999 (fill-merge assertion-strength evidence computed then
  never persisted), #1110 (the aimed retry never echoes the #998 marker; LangFuse output capped
  at 10k chars), **#1148 (the fan-out execution paths do not write verification evidence to the
  ledger — the executor's own comment says so; parity before anyone reaches for parallelism,
  and Campaigns will).**
- **The analysis is trusted unchecked:** #968 (nothing checks the analyzer's claims against the
  source — three false diagnoses in one roll), #1054 (three repairs dispatched to qa on a
  dev-typed failure).
- **Two homes for one fact, still:** #1070 (the plan's restatement of success_status beside the
  manifest's field), **#1150 (`GATE_REJECTED_STATES` restates what the lifecycle transition
  table already encodes — derive it)**, #936/#933 (verify-then-close: the fill appendix vs `all()` and the plan
  authoring a deliverable that competes with fill mode — either fixed en route or they join
  this pack).
- **Budget shape:** #414 stays a *design* item (a severity-aware correction-budget reserve) —
  it goes to review, not to code, in this release.

**How we know:** each item lands with a replay of the roll that produced it (the per-round
evidence rule); the pack as a whole is measured by the same counting sets as Pack Stack Seams — the
texture fields "greens by repair vs by re-dispatch" and "refused vs applied patches" are the
readouts, and the bar is that no roll in the set ends for a reason the record cannot name.

### 2.4 Pack **Boundaries** — boundary and vocabulary leaks (the identity itself)

#377 (Prefect `State` in domain objects), #381 (its `TaskResult.status` twin), #305 Part B
(`runtime_status` always populated, `network_status` retired), #559 (residual `task_type ==`
sites → constants at the core), **#922 (three meanings of "capability" — must land before packs
freeze the word)**, #225 (Joi's id), #218/#219 (one URL-prefix standard; the unversioned chat
routes onto `/api/v1` — **and a test that enumerates the routes and asserts the lanes**, since
the standard is prose today). **#154 — the guard itself:** the forbidden-imports test extended
from four directories to every `src/squadops` package with a declared allowlist of composition
roots (~15 lines on the existing helper), and the four known domain→adapter sites moved — the
NoOp observability adapter beside the port it satisfies, the secrets factory out of the config
loader, the route-built `OllamaAdapter` through the factory (#301), the bootstrap check into
wiring. **Plus one test with no issue behind it:** identity/role independence — a profile with
permuted agent ids produces the same outcomes, so no behaviour keys on an instance id.
**How we know:** the structural tests the 1.5 line established
(`test_no_enum_shadow_comparisons` and kin) extended to each vocabulary; a grep that finds the
leaked vocabulary anywhere outside its adapter fails CI; the all-packages import guard is the
single highest-leverage rule the repo does not have.

### 2.5 Pack **Composition Root** — the runtime is wired through its factories (design gate before code)

#301 (main.py bypasses the llm/queue factories — provider selection is not a port until it
goes through them), #154 (adapter imports out of domain modules into bootstrap wiring), #286
(config loaded and validated at import time). These alter runtime initialization; a short
design note is reviewed before the first PR. **#1152 — the executor strangler's successor** sits
here too: #186 closed at 3,172 lines and the file is 4,349 today, `_execute_sequential` alone
411; the continuation is scoped to the two paths 1.7's loop work lands in, under #663's golden
harness (byte-identical on the 19 goldens before and after), extraction only, with #1149's
harvest done first. **How we know:** `python -c "import
squadops.api.runtime.main"` with no environment succeeds; the factories are the only
constructors reachable from main; the hex-arch audit compares vendor shape (port + NoOp +
factory), not file location.

### 2.6 Pack **Hardening** — what 1.8 needs underneath it

What 1.8's two headliners need under them, taken from the ROADMAP's own gating:

- **The scorecard grades over stable seams and complete lineage:** #575 (placeholder
  trace/span ids defeat propagation; truncated uuid4 ids discard entropy), #577 (one asyncpg
  pool factory with the JSONB codec — retire the `parse_jsonb` scatter), #576 (domain-error
  handlers — delete ~40 per-route envelope blocks), #578 (graphlib for the plan DAG, and DECIDE
  whether `depends_on` orders execution). #80 (framework version, git SHA, request profile on
  the Cycle record) ships *with* the scorecard per the sweep — but the record shape is settled
  here so 1.8 does not open a migration on day one.
- **Campaigns run unattended, so the ops floor must hold:** **#1147 (one setting bounds two
  different things — the agent's per-request LLM timeout and the orchestrator's wait for an
  entire task are the same 180 s; they cannot be tuned independently, so raising one to fit a
  six-minute emission blinds the other to a hung agent for the same span)**, #330 (Prefect loop
  services starve under heavy cycles — 12,613 s on a 60 s loop), #300 (migration applier advisory lock),
  #581 (compose healthchecks + `up --wait` replace sleep-and-poll), #560 (runtime-api log
  hygiene), #372 (Keycloak realm changes never reach existing realms — the #326 family), #352/
  #353 (prompt-registry staleness guard; manifest hashes stamped at build time), #574 (AMQP URL
  parsing), #567/#579 (pure extractions: the fenced-parser recognition engine, the frontmatter
  parser's five copies).
- **What CI actually tests is what ships:** #1099 + #242 (sixteen integration tests fail
  identically on main and nobody is told; serviceless integration tests run in CI), #1041 (CI
  tests a dependency set no image installs), #237 (Python 3.12 in production containers, then
  `requires-python`), #198 (FastAPI/Starlette ≥0.136 breaks the console — pin and fix), #157/
  #176 (coverage gaps; a small-model-runnable smoke integration test), #580 (retire the
  deprecated event-loop override).
- **Packaging fidelity:** **#1151 (release-cut steps 5 and 7 — the SIP sweep and the package
  capture — have no guard; a tag-push check that the package exists for the tag, and a sweep
  line the closure guard reads)**, #582 (`[project.dependencies]` empty — bare `pip install` broken),
  #637 (service images run locked deps the suite never exercises), #598 (the emitted container
  cannot build or run — verified by no criterion), #1135 (the release-package script credits
  `Closes` mentions in code spans), #1144 (24 live SIP proposals unindexed and the audit runs
  nowhere).

**How we know:** CI is the instrument — the integration job green on main, the images' locked
deps the ones the suite ran, `pip install squadops` from a clean venv boots the runtime API.
The cut's release package (step 7) is captured with #1135 fixed, on the first try.

### 2.7 Deferrals landing here, and design items routed to review

- **#820** — SIP-0103 §3.3's interface self-consistency proof (endpoints/params/testids mutual
  coherence), deferred from 1.6 by name.
- **#376** — SIP-0102 migration steps 3–7 (in-cycle final-state verification), deferred from 1.4.
- **Design, not code:** #414 (severity-aware correction-budget reserve), #557 (post-retest
  governance acceptance review), #1122 + the Stack Blueprint rewrite (1.8-lane consumers of
  #1131), #316 (request-profile taxonomy — moves with Campaign).

### 2.8 Explicitly not in 1.7

Feature-shaped work stays in the 1.8 lane: #950 (plan-gate review packet), #949
(feedback-scoped restart boundary), #194 (SIP-0093 B′ revision loop), #80 (ships with the
scorecard), #1039 (docs-site design pass — its own track), #1031 (manifest-authoring primer —
1.8 authoring work). Verify-then-close before the cut: #822 (S2 landed; confirm no live
remainder), #936, #933.

---

## 3. Sequencing

By dependency and by what each pack proves, never by date:

1. **Pack Reasoning first, alone.** It changes what every subsequent measurement means (a qa primary
   at 5,700 tokens today is mostly thinking). Land #927/#410 with the adapter suite, replay the
   #924 probe, run one shakeout per stack, and only then re-read every completion-budget
   number in the codebase (#924's budget half, 1.6.5's E).
2. **Harvest, then move (#1149 → #1131) before Pack Stack Seams' fixes** — the rationale comes
   out of `scaffold.py` into a durable home first; then the pure move; then the kind gate, #1130
   and #1123 are written into the stack seam, not into the file it is leaving. The structural
   guard lands with the move. The same order governs #1152's executor extraction later.
3. **Pack Loop Honesty in class-sized PRs**, each with its replay, interleaved with Pack Stack Seams; measured
   together by one FastAPI+React counting set and one Next.js regression arm on a frozen
   deploy — the 1.6.6 protocol, with a prediction per item.
4. **Pack Boundaries and Pack Composition Root** — B in parallel with 3 (they touch different files); C after its
   design note is reviewed, and after Pack Reasoning, because the composition root is where the LLM
   factory is wired.
5. **Pack Hardening continuously**, ops-rider quota per the standing 08-04 rule, with the CI items
   (#1099/#242/#1041/#237) *early* — they are what makes the rest of the release's greens mean
   something.
6. Verify-then-close, the release-package capture with #1135 fixed, the cut.

Two lanes as before: executor/handlers/framing surfaces and the loop (Packs Loop Honesty, Stack Seams' fixes, Composition Root) on
one; adapters, infra, CI, packaging (Pack Reasoning's adapter half, B, H) on the other. Pack Reasoning's port change
is the one item both lanes wait on.

---

## 3.1 The 1.7.x lines — what fits in one, and the breakdown

A line is one measured pack plus a rider, on the cadence the 1.6.x lines established (a day of
PRs, an overnight of rolls). The two kinds of fix have two different capacities, because they
are verified differently:

- **Roll-verified items** — anything that changes what a cycle does (loop, scaffold, prompts,
  checks). The limit is *attribution*, not code volume: each item needs its own falsifiable
  prediction readable from the record and a roll where it can fire. Calibration from the last
  three lines — 1.6.4: 6 items / 8 rolls; 1.6.5: 5 (+#772, #1120) / 12; 1.6.6: 6 / 8 — every
  red attributable to one item or to nothing in the pack. Past ~8, predictions share evidence
  and a red stops naming its cause. **6–8 per line**, measured by one 6+2 set (§4).
- **CI-verified items** — adapters, ports, vocabulary, infra, packaging, CI itself (Packs Boundaries, C,
  H). Proven by the suite, a structural guard, or a characterization test; the limit is review
  load and merge order. **10–15 per line**, riding beside a measured pack without touching its
  predictions.

| line | measured pack (roll-verified) | CI-verified rider |
|---|---|---|
| **1.7.1** | **Reasoning** — #927, #410, #924 (budget half), #1145, #930 — first and alone, because it changes what every later token number means | #901, #929, #944; the CI-truth items first: #1099, #242, #1041, #237 |
| **1.7.2** | **Stack Seams** — #1149 (harvest, precondition) then #1131 (move + guard), the kind gate (#1153, filed from 1.6.6 roll 3), #1130, #1123, #668, #939, #1022 | #1087 (stack-#1 half), #1112; packaging: #582, #637, #598, #1135, #1144, #1151 |
| **1.7.3** | **Loop Honesty, first half** — #788 (the traceback reaches the repairer), #994, #995, #999, #1110, #968 | **Boundaries** — #154 (the all-packages import guard + four moves), #377, #381, #305, #559, #922, #225, #218 (+ the route-lane test), #219, the identity-permutation test; riders #1148, #1150 |
| **1.7.4** | **Loop Honesty, second half** — #1054, #1070, with #936/#933 verified-then-closed | **Hardening (infra)** — #1147, #575, #577, #576, #578, #330, #300, #581, #560, #372, #352, #353, #574 |
| **1.7.5** | **Deferrals** — #820, #376 | **Composition Root** after its design note — #301, #286, #1152 (executor extraction under the goldens); extractions #567, #579; #198, #157, #176, #580 |

**The total: ~68 of the 83 open issues fixed across five lines** — 23 roll-verified, ~45
CI-verified (rev 2 adds #1147–#1152 as CI-verified riders and moves #154 into Boundaries).
The remaining 15: four at design review (#414, #557, #1122, #316), six held in the
1.8 lane (#950, #949, #194, #80, #1039, #1031), and five verify-then-close or folded (#822,
#936, #933 and the two the packs absorb). The counts per line are the honest ceiling, not a
target: a line closes when its pack's predictions all hold, and a falsified one costs a
1.7.x.1 before the next pack opens — the same rule the 1.6.x lines ran under. The line order
follows §3's dependencies; a line's rider may move to a neighbour without changing the packs.

---

## 4. The measurement

1.7 has no headline feature to measure, so it measures its own claim: *the seams hold*.

- **Two counting sets on one frozen deploy after Packs Reasoning, S and L land** — FastAPI+React N=6,
  Next.js+TS N=2 (the 1.6.6 sizing, for the same reasons), pre-registered with one falsifiable
  prediction per landed item: the reasoning level resolves per capability (read from LangFuse);
  no green suite is failed by a stack-shaped check; a kind-contradicting assertion is rejected at
  emission; a qa-owned defect reaches `qa.test_repair`; no roll ends for a reason the record
  cannot name.
- **Texture against 1.6.6**: 4 of 6 and 2 of 2 (if that is where the Next.js arm lands), with
  intervals and no bar; greens by repair vs by re-dispatch; qa primary completion tokens against
  1.6.6's `3233–6594` — the distribution Pack Reasoning is expected to move down, reported as measured.
- **CI as the second instrument**: the integration job, the adapter characterization suite,
  the structural guards — all green on the cut commit, and the cut says so.

---

## 5. What this plan does not decide

- **Whether Cross-Cycle Memory's Phase 1 rails ride 1.8 or 2.0** — a 1.8 plan-time decision, as
  the ROADMAP says; 1.7 only leaves the port boundary clean enough that it is an adapter swap.
- **The Atlas migration date.** Pack Reasoning makes it *possible* (one port, a characterization
  suite, our own status vocabulary); flipping the provider is its own decision with its own
  conformance run.
- **1.6.7.** If the Next.js arm of 1.6.6 closes with a finding that needs a fix before 1.7's
  packs open, it is one more narrow patch on the 1.6 line, and this plan waits for it.

---

## 6. Cut criteria

Substance, not the clock:

1. Packs Reasoning, S, B and C fully landed; Pack Loop Honesty and Pack Hardening at the ops-rider quota with every
   remaining item re-placed by name (nothing silently carried).
2. Both counting sets closed with no falsified prediction; the record written from per-round
   evidence.
3. CI green on main including the integration job, on Python 3.12, against the locked deps the
   images install.
4. Zero code drift between the measured deploy and the tag; the release package captured on
   the first try with the `Closes` column correct.
5. SIP promotion sweep: SIP-0104 stays `accepted` unless #1122 ships (it will not, in 1.7);
   any SIP whose implementation these packs complete is promoted at the cut.

---

## 7. Revision history

- **Rev 1 (2026-08-27)** — written from the 1.6.3–1.6.6 records, the 08-21 sweep and the
  ROADMAP's 1.7 identity, while the 1.6.6 Next.js arm was still running; issue placement
  against the 77 open at this writing. §3.1 (the 1.7.x line breakdown and the per-line
  capacity rule) added the same evening on the owner's ask; packs renamed from letters to
  their subjects, with the naming table in §2, on the owner's ask.
- **Rev 2 (2026-08-27, later)** — the owner's architectural assessment of `2448f5d1` read and
  its actionable claims re-verified against the tree. Filed #1147 (timeout seam), #1148
  (fan-out ledger parity), #1149 (rationale harvest before extraction), #1150 (gate-state
  constants), #1151 (cut-step guards), #1152 (executor strangler successor); the four
  domain→adapter sites and the all-packages guard recorded on #154, the route-built adapter on
  #301. Placement changes: #788 to Loop Honesty's first half (one tuple, highest information per
  effort); #218 carries a route-lane test; an identity-permutation test added to Boundaries with
  no issue behind it. Not adopted: the assessment's note of a hardcoded agent-name→role map in
  the entrypoint (checked — it is gone), and #194 / #1122 stay where rev 1 put them.
