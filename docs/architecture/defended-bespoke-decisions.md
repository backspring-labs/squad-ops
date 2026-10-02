# ADR — Defended-Bespoke Architecture Decisions

**Status:** Accepted · **Established:** 2026-08-05 (1.5 Gate 1, #583) · **Source:**
the 2026-07-24 bespoke-inventions sweep (Tier 3), whose most repeated outcome was
*justified-LEAVE* — bespoke code a naive review (human or LLM) would flag as
reinventing a library or framework feature, that is deliberately correct here.

**Purpose:** pin these decisions once so they stop being re-litigated. Each entry is
the answer to "why doesn't this use X?" — settled, with the reasoning. A review that
wants to overturn one of these argues against the *why*, with new evidence; it does
not get to treat the bespoke shape itself as the defect. If a decision below stops
being true (a dependency gains the missing property, a constraint disappears), amend
this ADR in the same PR that changes the code.

---

## 1. Prefect is a passive UI tracker, not the orchestrator

Agents are distributed RabbitMQ request/reply workers. `@task`-wrapping queue
dispatch is not Prefect's execution model, and pretending otherwise would put a
second orchestrator in the loop. Deterministic task IDs and DB-backed resume
(SIP-0079) live outside Prefect on purpose; Prefect renders per-task progress
(SIP-0087) and nothing depends on it for correctness. The lane split is standing:
Console = cycle glue, Prefect = per-task visibility, LangFuse = LLM.

## 2. Reply router over `aio_pika.patterns.RPC`

SIP-0094's durable **shared per-agent reply queue** with `task_id` correlation
deliberately contradicts RPC's per-call exclusive queues. Per-call queues are exactly
the leaky pattern SIP-0094 retired: consumer-tag churn lost replies and leaked one
orphan queue per run. The router holds one long-lived subscription per agent and
resolves replies by `task_id`.

## 3. Hand-rolled publish-retry / resubscribe atop aio-pika

Each retry/resubscribe loop carries an issue-cited edge (`#245`-class) that
`RobustChannel` does not cover — recovery surfaces in `health()` instead of being
silently swallowed. Swapping to the library's recovery would reintroduce the failure
modes these loops were written against.

## 4. No tenacity / backoff library

Retry loops here are **domain classifications**, not exception predicates:
`outcome_class` routing, aimed re-rolls, correction decisions. A generic
retry-on-exception decorator collapses precisely the distinction the correction
protocol exists to make (transient vs product vs plan failure).

## 5. Run lifecycle FSM as transition tuples

The state machine validates `(current, target)` **values against persistence**, not
live objects — persistence-first, because the row is the truth and multiple processes
write it. FSM libraries bind transitions to live in-memory objects, which is the
wrong model for a lifecycle that must survive process death and be re-validated on
load.

## 6. `TaskEnvelope` frozen dataclasses + manual `to`/`from_dict`

A deliberate migration OFF pydantic. `from_dict` **drops unknown keys** by design —
that is rolling-deploy forward compatibility (an old agent reading a new envelope
keeps working, proven in v1.0.6). Frozen dataclasses + explicit codecs keep the A2A
message format (SIP-0031) a stable wire contract rather than a validation framework's
moving target.

## 7. Prompt renderer's minimal `{{var}}` substitution

`render_hash` provenance (#327 / SIP-0084) makes **byte-stable output load-bearing**:
prompt bytes are hashed for drift detection and fragment migrations are accepted only
on byte-equivalence (#452's standard). A real template engine (jinja2 filters,
whitespace control, autoescape) makes byte stability an accident instead of a
property.

## 8. Canonical-JSON sha256 idiom

Sorted-keys canonical serialization before hashing is what makes artifact/plan hashes
comparable across processes and releases (contract and manifest hash stability is a
release gate). A generic "hash the object" helper without the canonical form would
make every hash an implementation detail of dict ordering.

## 9. Checkpoint codec (SIP-0079)

Checkpoints are explicitly versioned payloads with their own codec rather than
pickled state: they must be readable by a *different, newer* process after a crash —
same forward-compat reasoning as entry 6, applied to resume.

## 10. Gate waits are DB polls

Human gate approval is a **crash-survivable wait**: the decision is a row, the waiter
polls it, and an orchestrator restart changes nothing. Event-driven gate delivery
would be faster and strictly less durable — the wait can outlive any process,
connection, or broker state.

## 11. Subprocess handling in test/probe runners

The runners manage spawn/timeout/kill directly (no plugin harness) because the
subject process is **untrusted squad output**: hard timeouts, exit-code semantics,
and output capture are the contract, and #498 added interpreter resolution strictly
after the safelist gate. A test-framework plugin would run untrusted code inside the
trusted process.

## 12. Secrets providers (SIP-0052)

`env` / `file` / `docker_secret` behind `SecretProvider` instead of a vault SDK: the
port is the abstraction, providers are deliberately dumb, and deployment profiles
choose. A vault dependency would invert that into infrastructure the smallest
profiles don't have.

## 13. Handler registry as a table

Capability handlers register in an explicit table rather than via decorators or
entry-point discovery: the registry is diffable, testable for drift (registry/event
parity tests), and load order is not import order. Implicit discovery is exactly how
handlers go silently missing in a container image.

## 14. Token file over keyring

The CLI stores its auth token in a file, not the OS keyring: agents and CI run
headless in containers where no keyring exists, and one code path that works
everywhere beats two paths where the privileged one is untestable in the environment
that matters.

## 15. `jose` over `PyJWT`

The auth boundary (SIP-0062) validates Keycloak JWTs via `jose` for its JWK-set
handling; the choice is pinned so dependency-hygiene passes don't "simplify" the auth
path into a subtly different validator.

---

*Entries 16–26 were harvested on 2026-09-09 from the comment rationale in
`DispatchedFlowExecutor._try_accept_patch` (`adapters/cycles/dispatched_flow_executor.py:3245–3755`)
before the 1.7.5 recovery extraction moves that code (#1149; the map is
`docs/plans/1-7-5-recovery-extraction-map.md` §4 step 1, and each entry names the block it
lives in so an extraction PR cites the entry rather than re-reading the comment). Keyed to
the decision, not the move: an entry that justifies two blocks is cited by both PRs.*

## 16. Repair verification uses the repairing step's grants, on the set that will be stored

The set a repair is verified on is the set storage will keep, and the grants it is verified
under are the **repairing** step's — named per artifact by the correction runner — never the
failed task's; an artifact that names no producer is refused loudly rather than judged under
the wrong grants silently (#1323, #1350). Twice the alternative shipped a defect: verifying on
the overlay *with* a file the producer could not write reported passed, storage dropped the
file, the failing row was superseded and the defect stayed in the tree (1.7.2 React roll 1,
`docker/serve.py`); judging a dev repair of a dev slot under the failed task's grants refused
it as a QA write (`cyc_375bdea6e140`). *Lives in:* block 1 (grants).

## 17. Patches are verified against the accepted workspace tree, which is never re-stored

The overlay's base is the accepted workspace, not the failed task's own files, because
`module_imports` and the #591 import pre-gate need the scaffold siblings present — in a
`routes.py`-only workspace both candidates were rejected and a correct repair could never be
accepted (fay-1, #643). The workspace rides as a separate base: `patched_artifacts` is what an
accepted patch re-stores (the #389 swap) and the tree must never be re-stored under the
repaired task's type. *Lives in:* block 2 (overlay).

## 18. File-owned criteria come from the canonical contract emission, and a rejection names its checks

The criteria owned by the files a repair rewrote are derived from the pinned contract
artifact (M0a: emission equals the pinned artifact), presence-keyed on the manifest like every
other manifest surface; a derivation failure disables the *gate*, never the verification
(#870). Every rejection names the failed checks with their reasons — "status=failed reason=
checks=7" forced a by-hand artifact replay to learn which check had rejected the patch
(pf-33), and the first attempt at naming them matched nothing because the rows are
`PatchCheckRecord` dataclasses, not dicts. *Lives in:* blocks 2 and 4.

## 19. The repair's own executed rows and own files, not the failed task's

What a repair executed on its own patch, in its own container, is carried on the protocol
result (#1229, #1256); reading the rows off the *failed* task's result found none in every
live round (`cyc_c6db3ffc1f4e`). The absent-file rule is keyed on the repair's own files, not
the overlay's, which carries the failed task's artifacts too (#1264) — a correct fix was
refused because `file_not_found` on another role's files counted as failure (#1259).
*Lives in:* block 3 (verification).

## 20. The deliverable set is the builder repair's blocking criterion

With the handoff's `sections_present` row retired (#1312), `required_files` evaluated on the
overlay is the builder repair's blocking criterion, guarded by the same predicate the spine
row uses (`emits_required_files`): a dev or qa repair is judged by its contract criteria, and
handing it a file list would charge it for files another role owns — the #1259 class.
*Lives in:* block 3.

## 21. "Nothing executed" is two absences with opposite remedies

`no_executed_blocking_checks` is produced by an absent *toolchain* and by an absent *file*
(every row skipping `file_not_found` because the repair wrote prose instead of the file), and
the two want opposite fixes, so the reason says which (#1276, #1273). The 1.7.1 Next.js roll 1
terminated under the toolchain wording for a file that was never written, and the R7 readout
could not tell the two apart because the line carried neither reason. *Lives in:* blocks 3
and 4.

## 22. A structurally unevaluable patch is decided by its retest, or terminated with a named reason — never rejected unheard

When a task's checks are structurally unevaluable (a frontend test file, where every AST
check skips by design), "unverifiable" is not caution, it is a deterministic deadlock: no
repair can ever produce an executed verdict, so the loop burns its whole budget rejecting
repairs unheard (pf-47, pf-49). So, for exactly those reasons and only with behavioural
evidence to re-run, the retest of the actual failing suite decides alone (`retest_decides`);
evaluator errors, parse failures and real check failures keep failing closed. A repair with
*no* behavioural evidence on a stack whose checks cannot execute here — a dev repair on stack
#2 at the runtime-api, which has no node — is the same deadlock: `cyc_05abfc7c1f00` spent all
three rounds re-dispatching an identical task after two identical unverifiable verdicts. That
is terminated with one named reason a reader can act on (#1221); the toolchain belonging
where the checks run is #1221's option C, deliberately after the cut. *Lives in:* blocks 3
and 5.

## 23. The retest is keyed on what the patch contains, not on the failed result's evidence

A behavioural-evidence-backed task re-executes the repaired suite before acceptance, and
fresh `test_result` supersedes the stale one (#456). The trigger is *is there a suite to run
in the patch*, asked through the stack's own declared conventions (#846) — not whether the
failed result already carried a `test_result`: a `qa.test` that failed at emission never had
one, so the repair that finally produced the suite was accepted on typed rows alone, no
retest ran, `tests_pass` and `frontend_build` ended `subject_missing`, and the run blocked
with the delivered app booting (React roll 2, `cyc_9c085ec2e9e5`, #1269). The owner ruled
2026-09-03 to key on the patch rather than on a per-task-type evidence-contract table,
because the artifacts already carry the fact and a table would be a second home for it.
`None` means no retest ran, distinct from a retest that produced no artifacts. Two details
the retest carries for the same reason: it needs the dispatch-time workspace
(`artifact_contents` is added by `_enrich_envelope`; built from the un-enriched envelope the
retest instant-failed input validation, 3.11), and it carries its own verdict *text* (roll
12's non-compiling repair died as "status=FAILED passed=False" and nothing downstream learned
it did not build, #870). *Lives in:* block 5 (retest).

## 24. The passing retest is what the task stores; the failed attempt's evidence never survives beside the patch

Fresh retest evidence *replaces*; with no retest the stale file is *dropped*, because the
corrected result already carries the patch verification's rows (#1111, generalised by #1318).
Twice the failed attempt's evidence was re-stored under the repaired task after the fix: the
failed run's `test_report.md` seconds *after* the passing retest banked its report (1.6.5
FastAPI+React roll 1), and the pre-patch typed-check evaluation eleven milliseconds before
the patch's own file landed — same `evaluated_at`, same workspace revision — so the next
analysis read the failure (1.7.2 roll 1). Gating supersession inside the retest branch was
the rejected shape: it covered only tasks with a suite, and a builder task has none. The
ledger supersedes on `(check_id, subject, criterion_id)`. *Lives in:* block 6.

## 25. Framework rows are owed by contract and re-derived from the patched set; an owed row no stage produced is reported, not refused

Every framework row a task type owes *by contract* — `required_files` for the type that
emits it, the test spine for the type that authors a suite (`framework_rows_owed`) — is
present in the corrected result or the patch is not accepted, re-derived from the **patched**
set through the handler's own rule and never invented for a task type that does not carry the
check (#1374). Two void counted rolls on two lines were one mechanism patched twice: this
seam composed the corrected result from the failed attempt's rows plus whatever the verifier
produced, so a framework row survived only if some earlier stage happened to write one —
#1318 re-derived `required_files` when the attempt *had* carried it (1.7.2 roll 1: a booting
app rejected on the pre-patch row), and #1364 found the next shape, a contentless attempt
carrying no rows at all (1.7.3 roll 1: a booting app read `blocked_unverified`). The contract
says what a task owes; its attempt's history does not. Two rules ride with it: `tests_pass`
presence means "the evidence the roll-up reads exists" (`verification_normalize` skips the
failure-only row and synthesises the check from `test_result` on a green run), because a
readout keyed on the key alone would refuse every retested qa patch; and an owed row that is
not producible at this seam is **reported** as `subject_missing`, not refused — every
measured instance is a `required_files` row the branch now derives unconditionally, and
refusing on the unmeasured half would change what a verdict means inside a measurement
window. Promotion to a refusal is a separate, deliberate call with evidence behind it.
*Lives in:* block 6.

## 26. The acceptance verdict names the base it landed on and the candidate it verified, and nothing is stored that is not that candidate

The repair-acceptance verdict carries the identity of the accepted workspace the patch landed on
(`workspace_revision_id`, #734 Slice A) and, since SIP-0107's first rollout step, the identity of
the candidate itself: that base with the patch's work product applied (`candidate_revision_id`,
§20), taken over repository state, so evidence artifacts the path supersedes by design do not
count (entry 24). Block 7 recomputes it over the set the corrected result will carry and refuses a
mismatch by failing the run; the storage seam checks that its own grant enforcement leaves an
accepted patch's set unchanged. The base alone named a tree nothing was verified on (SIP-0107
§3.6), and "verified set equals stored set" held only by call order (#1323). A mismatch fails the
run rather than re-dispatching, because no producer can cause one (the #1350 precedent), and an
ordinary correction round would bury the framework defect. *Lives in:* block 7 (accept), and
`_collect_artifacts_and_checkpoint`.

## 27. Every handled outcome stamps an attempt, and the facts that attempt exposed ride the next one

A re-dispatched task is a fresh emission with no memory. The Next.js shakeout
`cyc_9c379355b5e8` found a real defect (a route dropping a numeric `capacity`), had its
correct fix refused for an unrelated reason, re-authored the suite **without** the case and
shipped the defect green — the suite that shipped was not the suite that found it (#1260).
`#1123` already carried that fact to a qa *repair*; the re-dispatch carried nothing, so the
failing cases are threaded onto the envelope the retry loop re-dispatches, exactly as #566's
emission feedback is. The attempt counter itself (`prior_attempts`, #1304) is stamped on
every handled outcome rather than only on the retry branch: a re-dispatch from the
*correction* loop carried no marker at all, so an injected fault re-broke every repaired
emission and the loop could never be observed recovering. *Lives in:* outcome block 1.

## 28. The emission-retry marker rides exactly one dispatch

#566's marker is set for the retry it aims and **cleared** at the top of the next outcome,
not left on the envelope. Left set, every later dispatch of the same envelope from the
correction loop still carried it: the handler appended stale format feedback to a
repair-driven re-take, and the fault injector — which reads the marker as "this is an
emission retry" — re-applied an all-attempts fault to the recovery the diagnostic exists to
observe (deploy-A absent-suite diagnostic `cyc_1b3b225e593e`: the fault bit on all three
correction re-dispatches and the run exhausted its budget). The RETRYABLE branch sets it
again for a genuine emission retry. *Lives in:* outcome block 1.

## 29. An unclassified failure is classified by attempt count, and two task types never reach correction

D5: a result with no `outcome_class` is not "unknown, so correct it" — it is RETRYABLE until
this task's attempts reach `max_task_retries`, then SEMANTIC. The alternative rejected is
treating unclassified as semantic immediately, which sends a transport blip through the
correction protocol and spends a correction budget on nothing. D9: a definition-of-done task
failure aborts the run outright (`fails_without_correction`), because correcting the
statement of what "done" means is how a cycle talks itself into a lower bar. `BLOCKED` raises
rather than returning an action: it is a pause, not an outcome. *Lives in:* outcome block 2.

## 30. The run-level correction count is bumped before the dispatch it pays for, and the dispatched envelope is what the protocol gets

#374: the shared count is incremented on **this** correction before any repair dispatch, so a
patch that re-runs the check is bounded and each re-run gets a fresh `corr-`/`plan_delta-` id
keyed on the pre-increment value. The protocol is handed the *enriched* envelope, not the
base one: the correction runner forwards the failed task's typed-acceptance workspace to the
repair from `envelope.inputs` (#1229 rule B) and only the enriched envelope carries
`acceptance_workspace_files`, cut at dispatch (#643). Handed the base envelope, a repair
evaluated its patch in a patch-only tree, its frontend build skipped for want of a frontend,
and the verdict came back `unverifiable / no_executed_blocking_checks` — the 1.7.0 shape, on
the deploy built to end it (1.7.1 Next.js shakeout `cyc_3ac86805439f`). *Lives in:* outcome
block 3.

## 31. An emission containing nothing is not an attempt, and the refund that says so is bounded separately

#1053: arm B of the 2026-08-23 pair banked `repair_output.md` at **zero bytes** on two of
three rounds while its diagnosis stayed correct and stable, and each was billed as a spent
attempt — so the run reported an exhausted budget after one real try. The round is refunded
and re-taken. The refund allowance is its own counter, deliberately: taking it from the
correction pool the empty emission is failing to consume would be unbounded by construction,
and a producer that emits nothing every time must still terminate. Once spent, an empty round
is billed like any other. *Lives in:* outcome block 4.

## 32. The correction path is a four-way action, dispatched by `if`/`elif` and not by a table

`abort` / `rewind` / `patch` / `continue` are keyed on the *protocol's answer*, not on a task
type — so the identifier convention's "tables over chains" rule (which is about type-keyed
dispatch) does not apply, and a table here would add a lookup between the decision and the
action it names. `rewind` raises rather than discarding work: #994's guard is that a rewind
never discards an accepted repair, which is why the loop carries `has_accepted_repair` into
the protocol. `patch` is the only path that can end without a re-dispatch, because
re-dispatching a generative task re-rolls its artifacts and clobbers the repair (the
`cyc_6841d75f167c` oscillation). *Lives in:* outcome block 4.

## 33. Each correction step's outputs go in its own bucket, and the chain shares one correlation id

Issue #95: reusing one variable across `CORRECTION_TASK_STEPS` masked the analyzer's
`classification` and `analysis_summary` with defaults at PlanDelta time, because the
governance decision step that runs after it does not carry those fields forward. Each step's
outputs are captured in a named bucket keyed by `_CORRECTION_STEP_OUTPUT_BUCKET` — a table,
so a new step is a row rather than another `elif`. Every correction and repair envelope of
one chain carries the **same** `correlation_id`, minted once: a later step that minted its
own would compile, read fine, and break the lineage a trace is read by — visible in no test
and only in a trace. *Lives in:* protocol block 1 (diagnosis).

## 34. A deterministic policy guard bounds the model's correction path, and discloses the override

#447: `continue` may not discard a required check that executed and failed while this
chain's repair slot is unspent. The guard resolves the path, and where it overrides, the
model's original rationale **stays intact in the decision artifact** while the override is
disclosed in the `CORRECTION_DECIDED` event payload — a silent substitution would leave the
record saying the model chose what the guard chose. pf-45 added the rewind anchor: a
`work_product` rewind dies as a run failure with the repair budget unspent, so the guard
substitutes the patch the classification says is possible. #994 rides here too: a rewind
re-authors from the checkpoint and cannot preserve a repair that landed after it, so the
executor — the only place that knows a prior round of *this* task was accepted — threads
`has_accepted_repair` in. *Lives in:* protocol block 2 (resolution).

## 35. The plan delta is banked before the termination check, and the check runs before any repair

#435 (1.5 A4): progress-aware termination is placed **after** the delta is stored, so the
decision evidence survives the termination, and **before** any repair dispatch, so the
maximum budget is honoured. Either order inverted loses something that cannot be recovered:
terminate first and the round's reasoning is gone; dispatch first and the budget is spent on
a chain already known not to be progressing (#687, #431). *Lives in:* protocol block 3.

## 36. Repair-step selection is keyed on the failed task's type and the deterministic locus, never on the LLM's account

The LLM-emitted `affected_task_types` is free text and once routed a builder failure
(`affected_task_types: ["QA Handoff"]`) silently to the dev repair handler. Selection is
keyed on the failed task's `task_type` (authoritative) plus the deterministic failure locus
(#568): a task whose OWN artifact is missing or uncollectable is repaired by its own role
re-producing that artifact (`qa.test` → `qa.test_repair`), and the repair target is the
failed task's own contract rather than the subject-implementation surface — aiming a test
re-author at app source files is what `_resolve_repair_target` would otherwise do. The
decision's own account of what is affected is read **against** the conservative default,
never as authority (#1054) — and, in the one direction the default cannot take alone, two
model readings that agree the failed qa task's own suite is the defect and nothing else (the
analyzer's implicated files all its own, every label the lead wrote suite-side) promote a
failing assertion to the suite's author, with the target limited to the files named (#1581,
deploy C's React shakeout: the dev was sent to repair a routes.py every party had agreed was
correct). Two ownership vetoes ride the dispatch: a step under a foreign
role must not receive the failed task's own artifacts (#884, pre-dispatch) and must not
*land* them or anything on its test-collection surface (#1014, post-rebase). Both are
failure-isolated — an unresolvable pattern surface weakens the veto rather than crashing the
protocol. *Lives in:* protocol block 4 (repair).

## 37. "Did the repair emit a file" is the question, and the extractor's marker is the answer

#1273: the extraction **fallback** is not an emission. A repair returning prose and no fenced
block produces one non-empty `repair_output.md`, which counted as content — so the round was
spent rather than refunded, and the loop then terminated as `unverifiable` for a file that
was never written (Next.js roll 1, `cyc_9be98128f0e9`). Judged on emitted *content* rather
than artifact count (a zero-byte file is still a file, #1053) and with the fallback marker
excluded. `steps_ran` is not `bool(artifacts)`: a rewind or continue emits nothing
legitimately and must never be refunded. The signatures ride the `CORRECTION_COMPLETED`
event, not only a log line — "converged in 3" and "converged in 3 after two empty emissions"
must not read the same, and #998 adds *which* nothing, because the two shapes have opposite
remedies. *Lives in:* protocol block 5 (the emission judged).

## 38. A collaborator that borrows a method borrows it late

`CorrectionRepair` takes `CorrectionRunner._dispatch_protocol_step` as a **lambda**, not as
the bound method, and `PatchAcceptance` takes the executor's SIP-0100 helpers the same way.
A reference captured at construction keeps calling the original past any replacement — and
that seam is exactly what the correction-context golden patches to capture every envelope
crossing it, so an eagerly-captured reference would leave the repair dispatching for real
while the golden diffed the real envelope against the stub's. Found by that golden during
#1152 step 5, which is the only reason it was loud rather than silent. The pattern this
follows is `store_artifact=lambda *args, **kw: self._store_artifact(...)` on
`CorrectionRunner` itself (SIP-0097 §6.3, "executor residual, residual-but-watched"): a
collaborator holds no ports it does not own, and borrows the rest late. *Lives in:* the
executor's and the runner's constructors.

## 39. A self-evaluation pass re-asks on the whole transcript and validates the merged set, not the follow-up

The second call replays system, the original user prompt, the model's first response and the
follow-up prompt, with the first call's kwargs unchanged, and each pass re-validates the
**merged** artifact set (RC-7). A follow-up validated alone would pass on the one file it
re-emitted while the task stored a set that still failed; a re-ask without the first
response gives the model nothing to correct. Evaluator-error counts are shared across the
passes of one `handle()` and dropped after it (SIP-0092 M1.3, #670 / RC-9b), so a check whose
evaluator errors twice escalates within a task and never across tasks. The loop was copied
into both producing handlers; it is one method now so a third emission shape does not become
a third copy. *Lives in:* `_CycleTaskHandler._self_evaluate`.

## 40. The self-evaluation trigger names the checks that opened it, on the qa path

The self-evaluation branch is the sole trigger for a second model call, and nothing recorded
which check opened it: a roll's summary read 29/29 accepted while a whole extra generation —
3,574 tokens, 68% of the qa task's wall clock — was unreadable from stored state (#946). The
line names the failing checks, never a count, because `expected_artifacts` fails for a reason
fill mode makes invisible (#947). It is logged on the qa path only; the dev path never carried
it, and an extraction does not add it. *Lives in:* `QATestHandler.handle`, before the call.

## 41. A self-evaluation pass in fill mode goes through the same merge gate, and cannot rewrite a merged shell

A follow-up's fills are parsed, folded into the primary's fill emission and merged through the
same gate as the primary's — phantom tables (#1087) and declared element kinds (#1094)
included — rather than extracting as files named `slot-…` that the shell guard then discards
(1.6.5 C, #947). A follow-up file at a merged shell's path is dropped: in fill mode the slot
protocol is the only shell surface (SIP-0104 P3). What was applied and what was skipped
because the slot was already filled is banked per pass as `self_eval_fills`. *Lives in:*
`_ScaffoldFillShape`, the fill unit in `qa_test.py`.

## 42. Fill fences are stripped before file extraction, and the parse is logged before the merge

Under a verification scaffold the emission is parsed for fills first and the fill blocks are
stripped before `extract_fenced_files` runs, so the fill protocol and the additive-file surface
never compete for the same bytes. The parse is logged at the parse site — fills, duplicate
slots, extracted files, whether scaffold-bound — because three outcomes are indistinguishable
afterwards: emitted nothing, emitted fills that were refused, emitted a file instead of fills.
P3 renders a rejected fill as the same failing state as a missing one, and window rolls 3 and
5 were each diagnosed twice, wrongly, from the result instead of the emission (#924;
`test_emission_log.py` pins the order). A fills-only emission is authorship, not an emission
failure. *Lives in:* `_ScaffoldFillShape.split` and `QATestHandler.handle`'s parse log.

## 43. The scaffold evidence lands in `outputs`, after the probes, and is not a check row

SIP-0104 P5 classifies shell failures, correlates them with the probe rows and banks the summary
as `outputs["scaffold_evidence"]` — after the probes are appended, because correlation joins on
the shared criterion id. It is deliberately not a `validation_result.checks` row: roll 1
(`cyc_04d36309d793`) showed that `normalize_task_checks` records any row carrying a `status`,
so an informational row surfaced in the cycle outcome's `unverified` list with reason
`unspecified`. A diagnostic is not evidence and is not counted as one (SIP-0096 §6.1). The
fill-merge evidence rides beside it as a stored `evidence` artifact, because the same
measurement placed only in `execution_evidence` was persisted by nothing (#999). *Lives in:*
`_ScaffoldFillShape.append_evidence` and `QATestHandler._fill_merge_evidence_artifact`.

## 44. Which output a capability produces is the capability's own fact

`qa.test` has two outputs — whole files, or fills under a verification scaffold — and the
reasoning declaration is about the output (#1285; fill mode's level corrected by #1434). The
handler answers it through `_output_shape(inputs)` rather than shared code reading
`verification_scaffold` for every capability: reading it in the base broke the
manifest-authoring stage's enforced input contract. The same answer selects the shape that
parses, merges and evidences the emission, so the reasoning level and the parse can never
disagree about which output this is. *Lives in:* `QATestHandler._output_shape` and
`QATestHandler._SHAPES`.

## 45. An emission containing no fenced block fails with a marker that carries what was written

A producer's response with nothing extractable fails the task with `emission_failure`: its
length, the expected artifacts, the completion tokens against the cap, and the content itself
(#566, #1372). The executor turns the marker into an aimed retry that tells the model what it
wrote rather than asking again blind, and the correction loop's locus classifier reads it as a
producing-side signal. The full response is also stored as `build_warnings.md`, so the
emission survives the failed attempt. *Lives in:* `_CycleTaskHandler._no_fenced_blocks_result`.

## 46. Validation evidence rides the passing branch too

`validation_result` goes into `outputs` whether the task passed or failed. It was failure-only
on the dev surface (#597: a passing roll reported 3/6 criteria verified with 6/6 passing
evidence) and then, despite a comment saying otherwise, on the qa surface (#1271: React roll 5
rejected on the first attempt's six failed rows while the re-authored suite passed all eight),
because the ledger supersedes per `(check_id, subject)` and a check that only ever appears when
it fails can never be superseded by its own later pass. One helper now attaches it for both
handlers, so the two cannot diverge a third time. *Lives in:* `_CycleTaskHandler._attach_outcome`.

## 47. The framing gate returns its plan errors; the caller records the rejection

`_reject_invalid_plan_before_workload_gate` returns a list, and the sequencing loop records a
system `REJECTED` gate decision from it, which re-rolls framing for free (#464, #473). It used to
raise, and the orchestrator died silently mid-sequence (the 3.13 stall). A validator added here
adds a rejection reason; it never raises. *Lives in:* the framing gate's plan check (#1507 step 1).

## 48. Two plan nets, two error channels: pick the net by where the rejection must land

The inter-workload gate's check **returns** (a recorded re-roll), and the dispatch-time net in
`generate_task_plan` / `_reject_unsatisfiable_plan_at_gate` **raises** (a run failure). They are
separate on purpose (#663 D5): merging them would conflate #473's returns-vs-raises semantics.
A new rule goes on the net whose landing it needs, and on both when both apply; landing it on one
when both apply is the #718/#719 scar. `test_plan_gate_seams.py` pins both call sites.

## 49. A missing plan is rejected at the gate; an unreadable one defers

With `implementation_plan` on, a completed framing run with no plan artifact means plan authoring
collapsed, and approving it spends a whole implementation run before the SIP-0096 throttle catches
it at the end (#424). An artifact that exists but doesn't parse is different: the dispatch-time
net gives it a full diagnosis, so the gate defers. Exists-but-unreadable is not absent.

## 50. Whatever is provably unwinnable from the plan and manifest is rejected at the gate

Each validator the gate runs proves, in milliseconds, that a roll cannot pass on any content: an
unexecutable command check or directory-shaped artifact (#645), a dual-claimed artifact (#673), a
qa task that can never satisfy `tests_pass` (#715), a builder with no build profile (#426) or under
its required files (roll 15), a suite outside qa's namespace (#1587), a module the scaffold can't
provide (#671), a failing check on a frozen file (pf-42), a manifest the plan contradicts (#1013).
At the gate a re-roll costs minutes; the same defect found later costs a roll's correction budget.
The check only ever adds an earlier rejection, never a pass.

## 51. Bind mode binds the contract's criteria before validating the plan

In bind mode the contract's covered-file criteria are bound by id before the plan is validated
(#509), and dispatch applies the same normalization, so the validated plan and the executed plan
cannot drift. Bind mode requires an interface manifest, seeded or framing-emitted and hash-checked
(#494, #496), and a seeded contract that won't parse is a hard rejection, never a fall-through to
author mode (SIP-0098 §10).

## 52. Soft plan violations are logged at the gate, never fatal

A warning- or info-severity criterion can't block a build (RC-9), so it must not kill a cycle at
plan validation either; the gate logs every tolerated violation, including the derived-criteria
notes (#1254), so the pass is never silent. The rule is taught in the vocabulary and enforced by
the dispatch strip, and a framing re-roll for a row dispatch would drop costs half an hour for
nothing.

## 53. A resumed run is not marked running again

A run is moved to `running` only if it isn't already: the resume and retry routes mark it before
enqueuing it (#222/#256), and a `running → running` transition is illegal on a lifecycle-enforcing
registry, which made every resumed run fail instantly (#342). *Lives in:* `RunProvisioning.prepare`.

## 54. A run's plan, contract and manifest are loaded before its first dispatch

The implementation plan (SIP-0086/SIP-0092) and a bind-mode contract (SIP-0098 98.3) are loaded
together, before any task goes out, so the task plan is fully materialized and the executor stays
deterministic. The criteria proposer reads the operator-seeded manifest, never a framing run's own:
a framing run must not carry skeleton files (#496), a prompt describing the interface materializes
nothing, and bind mode already requires the seeded one (#494). Without it the proposer writes checks
against an invented interior of the frozen files (pf-42). *Lives in:* `RunProvisioning.prepare`.

## 55. Admission defers a run; it never fails one

A participant committed to, or about to start, a hard duty window (SIP-0089 §2.5), or holding a
conflicting focus lease (§3.5), pauses the run (`RUN_PAUSED`, resumable) rather than failing it, and
admission rolls back any agents it already recruited before deferring, so a paused run strands no
one in cycle mode. Both guards are opt-in: no assignment port, no guard; no coordinator, no
recruitment. *Lives in:* `RunAdmission.admit`.

## 56. What admits a participant releases it, whatever the run's outcome

The release runs in the run's `finally`, before anything that can raise, isolated per agent: a
stranded cycle lease blocks all of that agent's future recruitment (#233). A sweep then releases
anything still held under the run's `owner_ref`, because a recruitment replayed on resume (#288's
idempotent skip) leaves leases this admission never recorded (#373). *Lives in:*
`RunAdmission.release`.

## 57. The skeleton is seeded on a fresh run only, and the scaffold only on top of it

A resumed run's checkpoint already carries the original seed set; seeding again stores new ids that
land after the restored state, and last-writer-wins per filename hands every fill slot back to a
stub (#881). The test scaffold (SIP-0104) rides the same seed act and only on a seeded skeleton,
since its shells import against that tree. *Lives in:* `RunProvisioning.seed`.

## 58. A failed run finalizes with the state it reached

`RunInProgress` is mutable, unlike the cycle models: it is the running record of how far a run
got. `RunCompletion.finalize` receives the cycle, the plan and the contract a run had established
when it failed, and provisioning records each on the line after the line that establishes it. A
provisioning step that returned its results only at the end would hand finalization `None` where
the contract was already loaded — a behaviour change an extraction would hide (#1507 step 2).
*Lives in:* `RunProvisioning`, `RunAdmission`, and `execute_run`'s `finally`.

## 59. A system plan rejection re-rolls framing, and the re-roll revises

A plan the gate's check rejects is a stochastic framing fault — the rule the model tripped is in its
prompt already — so framing re-runs, bounded by `framing_max_rerolls`, rather than the cycle dying
(#522). The default is 2: it shipped as 0, which made the machinery dead code until a correct
refusal dead-ended a cycle (#1030). The re-roll carries what died and why into the new framing's
authoring prompts (#669): revise, don't re-dice. The rejection stays in `gate_decisions` as evidence
(#473). *Lives in:* `WorkloadGate.decide`.

## 60. The gate stops only when the design asks a question

A manifest that declares no unresolved decision has already passed the deterministic gates, and a
review that adds nothing manufactures the appearance of one (M4, #807). The question-free approval
is synthesized and runs through the same exhaustive dispatch a human's answer does, so a
pass-through cannot reach a path an approval would not; the questions themselves are the review
request (§5c.10). *Lives in:* `WorkloadGate.decide`.

## 61. Returned-for-revision revises, on the re-roll's own path

Revision is not approval: the sequence never advances on the un-revised plan (#466, the 3.10
false-approve). The revision runs on the same re-execution path a system re-roll takes (#811) — a
second loop beside a proven one is how they drift — with its own counter, bounded by
`manifest_max_attempts`, because a human's instruction is not a stochastic fault. It carries the
prior manifest (§5c.6's "revise, don't re-roll") and the superseded run whose prefix it restores.

## 62. The superseded run is cancelled first

A re-roll or a revision cancels the run it supersedes before creating the next, because the
positional run↔workload invariant is exactly one non-cancelled run per position (#257, D14).

## 63. An unrecognized gate decision stops the sequence

The dispatch over gate decisions is exhaustive: a value it doesn't know — a future policy, a typo —
is never read as an approval (#466). *Lives in:* `WorkloadGate.decide`.

## 64. Every way a cycle ends meets one completion boundary

`execute_cycle`'s endings — the single-workload fast path, a run that did not complete, the last
workload, and each way the gate stops the sequence — all reach `CycleCompletion.end`, which
produces one read-only `CycleEnd` naming why. It is the seam 2.0's continuation request enters
(the Campaign SIP's Appendix A). `execute_cycle` keeps the port's `None` return: changing a port
inside an extraction is out, and the view is observed at the boundary itself (#1507 step 3).

"A run that did not complete" is every status but `completed` (#1754). The loop once stopped only on
a failed or cancelled run, and read a paused one as completed: it gated it, rejected its empty plan
and cancelled it with each framing re-roll, so `runs resume` had nothing to re-enter. A paused run
now ends the sequence uncancelled, as `run_paused`. *Lives in:* `STOP_REASON_FOR_UNCOMPLETED_RUN`
(`src/squadops/cycles/cycle_end.py`).
