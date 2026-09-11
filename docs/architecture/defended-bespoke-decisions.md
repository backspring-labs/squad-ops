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

## 26. The acceptance verdict names the workspace tree it verified against

The repair-acceptance verdict carries the identity of the workspace tree
`verify_patched_artifacts` computed and verified against (#734 Slice A), so a record can say
which tree a patch was judged on rather than inferring it from timestamps. *Lives in:* block
7 (accept).

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
never as authority (#1054). Two ownership vetoes ride the dispatch: a step under a foreign
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
