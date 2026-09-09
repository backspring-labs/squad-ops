# 1.7.5 — plan

**Revision 4, 2026-09-09.** Written the morning the 1.7.4 line closed, from the 1.7.4 plan (rev
4 §6, §6a, §8), the 1.7.4 record (`docs/plans/1-7-4-verification-set-record.md` §2–§9), the
1.7.4 pre-registration §3a and §9, the 1.7.3 plan §6 and §8, the 1.7.0 plan §2.5, §3.1 (as
amended) and §6.2, the ROADMAP's 1.7 identity, and every open issue in the tracker on the
morning of writing; revised three times the same morning — rev 2 on the owner's two rulings and
the god-file measurement (#1443, #1444), rev 3 on the owner's written review of rev 2, rev 4 on
the owner's ruling that a 1.8 feature's design review is the 1.8 plan's step, not this line's (§10).

**1.7.5 closes 1.7 by making the remaining ports real at start-up and through the LLM call
path, while proving the recovery path still behaves after extraction.** Three prior lines made
the loop honest (1.7.2, 1.7.4) and the boundaries hold (1.7.3). What remains of "every port is
actually a port" is **three closure contracts**, each with its own invariant and its own proof:

| closure | contract | items | proof |
|---|---|---|---|
| **Start-up truth** | configuration and adapter selection happen at the composition root through ports and factories, never implicitly at import time | #286, #301, #637 | an architecture guard; a bare import with no environment; the lock-install import job |
| **Invocation truth** | every LLM invocation crosses one observable call path, so there is no successful model interaction the generation record cannot see | #929 with #1206 | a characterization proof against a recording port; the inverted seam test; records equal calls on a live pair |
| **Recovery structural integrity** | moving the recovery implementation does not change the recovery contract proven across 1.7.2–1.7.4 | #1152 with #1443 | byte-identical goldens and replays; the five fault diagnostics reaching their seams on the pinned deploy |

In front of them sits a small **measurement-correction prelude** — the four findings 1.7.4's
set handed forward plus what must land before the instrument is trusted — banked green on its
own deploy before any closure moves. Behind them rides a **hardening list** of four, none of
it in the runtime image's cycle path. The line is the 1.7.3 shape with a prelude, and its
attribution is structural: a red on deploy A belongs to the prelude tranche; a red on deploy B
belongs to the closures.

Rules carried from 1.7.3 and 1.7.4 without discount, and one added from the 1.7.4 record:

- **a measured tranche and a structural tranche do not share a deploy** — the prelude is banked
  on deploy A before the closures move on deploy B, and nothing that can move runtime
  behaviour rides beside the closures (§3.6 classifies the list to make that true);
- **every registered readout maps to a typed evidence field, checked against a real record,
  before the set opens** — and, new from the 1.7.4 record §9, **every field carries one of
  three states**: observed, asked-and-none, or unaskable with its reason (#1445); an empty
  field whose producer is structurally silent on a clean roll is not evidence;
- **no fault, no prediction** — a claim no counted roll is likely to reach is proven by a
  fault or a CI invariant and reported as texture; applied this time to the untouched-file
  rule as well as to the seams (§4);
- **the diagnostics run on the pinned deploy**, with no amendment: 1.7.4 skipped its step 10
  and said so; this line's recovery extraction is exactly what those diagnostics exercise, so
  a seam not reached on the pinned deploy is a closure finding, not a reachability that "was
  not in doubt".

---

## 1. What the 1.7.4 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| Functional App Yield 7 of 9 with zero intervention; every accepted roll credited all its criteria; both rejections named the criterion they lost | 1.7.4 record §1, §6 | the loop's honesty half is done; the line can be about structure rather than behaviour |
| the line's only bar breach came from the fill-mode reasoning declaration: across the five fill-mode qa rolls on the line, three produced a working suite in one emission at ~3,943 tokens and two produced sentences of intent (2 of 24 and 7 of 35 contentless), both recovered through correction rounds | record §3 (Q1), #1434 | **the fill-mode declaration is decided in this line** (§3.2, §8): the saving is a token cost, the failure is the bar |
| a repair's verification demoted nothing on the set but carried five `missing_tooling` skips on one roll; the registered condition says that roll's coverage is never quoted whole | record §5 (#1406) | **the framework half of #1406 lands in the prelude**, credit-restoring, and is proven by the absent-suite diagnostic rather than waited for (§4) |
| the diagnostics were not re-run on the pinned deploy; the four carried 1.7.3 invariants and the analyzer invariant rest on earlier deploys | record §4, §8 | **this line runs all five on its pinned deploy**; the recovery extraction is what they exercise |
| the handoff bar's readout was structurally empty on every roll — the framework's `required_files` row is filtered at `validation.py:252` and the other source reads log lines emitted only on the patch path | record §2, §9 | the three-state vocabulary (#1445) in the preamble; §4 applies it to every registered field before roll 1 |
| `container_packaging` reported a failing row on **five of nine** counted rolls (React 1, 3, 4, 5; Next.js 1 — `npm_ci_without_lockfile` on four, `debian_nginx_default_site_unremoved` on one), after four of nine on 1.7.3 and eight of nine on 1.7.2 | the counted records' `typed_checks.container_packaging_rows` | **promoting the check to blocking is the wrong shape** (§8, decision 1): the finding rate says the packaging is a deliverable the squad does not reliably author, and both accepted sandbox SIPs say it is a rendering, not an emission |
| three rider items whose PRs merged are still open — #330 (PR #1396), #372 (PR #1395), #352 (PR #1394) — and #157, which the 1.7.4 plan §6 declared closed-by-accretion, is open | the tracker, 2026-09-09 | verify-then-close at the head of the line with the record's own readings (§3.1) |
| the rider-then-pack structure behind a checkpoint pair attributed every red on the line; zero code drift deploy-to-tag | record §1, the cut | the same structure: one measured tranche per deploy, a checkpoint between (§7) |
| the Scoped Code Revision design review, which the 1.7.4 plan §7 step 2 said "opens beside this line", never opened — PR #1325 has zero reviews and zero comments | the PR, 2026-09-09 | **the review is the 1.8 plan's opening step, not this line's** — a 1.7 line does not carry a 1.8 feature's review (§6); the finding stands so the 1.8 plan names a reviewer instead of repeating "beside" |

---

## 2. Why this line, on the roadmap — the three closures

**Start-up truth.** "Every port is actually a port" is false at the composition roots today:
the runtime-api constructs its queue adapter directly at `src/squadops/api/runtime/main.py:310`
and its A2A client at `:496`, and the agent entrypoint constructs its queue adapter at
`src/squadops/agents/entrypoint.py:453` — while both roots already route the LLM through
`create_llm_provider` (#1157, the LLM half of #301). `get_queue_adapter` exists
(`adapters/comms/factory.py:40`) and already *requires* `comms.provider` (`:29–31`); nothing
calls it from a root. The config is loaded at module import (`main.py:57`), so
`import squadops.api.runtime.main` needs a secrets profile to succeed (#286). The principle
behind #286 is worth stating once because it generalizes past this FastAPI root: **importing
code defines behaviour; starting the application performs configuration and wiring.** The
ROADMAP names the composition-root cluster as load-bearing for the Atlas migration and for
1.8's scorecard; SIP-0106 §1.2f names #301 a *precondition* of any provider adoption. The
1.7.0 plan §6.2's third close criterion — CI green "against the locked deps the images
install" — has its deliverable here (#637), and no prior line took it.

**Invocation truth.** The observability port is bypassed at eight LLM call sites. By AST
count on the tree this plan was written against, `analyze_failure.py`,
`correction_decision.py` and `define_done.py` each make two LLM calls and record no generation;
`_plan_authoring.py` and `planning/review.py` one each; `develop.py` and `qa_test.py` record
their first call and not their self-eval second (#1206). The sequence around every call —
budget, prompt guard, call, content, duration, generation record — is copy-pasted, and the
1.7.4 shakeout pair read 26 LangFuse generations against 35 calls. #929's extraction of that
sequence onto the handler base is what makes a fourteenth dark site impossible rather than
guarded against. It is a port closure, not observability plumbing, and it is non-droppable
(§5): if capacity could close 1.7 without it, the release thesis would be false.

**Recovery structural integrity.** `_try_accept_patch` is the largest method in
`adapters/cycles/dispatched_flow_executor.py` — 511 lines at `:3245`, in a file of 4,933
(4,349 when #1152 was filed). **The correction runner is the fastest-growing file in the
tree** — `adapters/cycles/correction_runner.py` at 2,145 lines (1,461 at v1.6.0, 1,843 at
v1.7.0), with `run_correction_protocol` at 536 lines (`:1505`), because every Loop Honesty
pack row landed inside it (#1443). Both are on the path Scoped Code Revision — a 1.8 feature
— lands through, so extracting after 1.8 builds on top is the wrong order. The last two lines
built the fault diagnostics that exercise exactly these paths; this is the line where an
extraction under those diagnostics costs least and proves most. This closure is a different
invariant from the first — "moving the implementation does not change the contract" is not
"roots construct through factories" — and it has its own design artifact and proof (§3.5).
They share a release because both are structural debts blocking the next architecture, not
because they are the same architecture.

**What it does not do, stated here rather than implied.** It does not change the loop
(1.7.2's and 1.7.4's), the boundaries (1.7.3's) or the reasoning budget (1.7.0's), except
for the four 1.7.4 findings in the prelude and the fill-mode declaration. It does not adopt
Atlas (SIP-0106 §1.2a stands on its own measurements). It does not build the in-cycle image
build, the stack-rendered packaging, Scoped Code Revision, or any 1.8-lane item (§6). It does
not promote a SIP on the strength of its own work except by amendment (§3.9).

---

## 3. The content

### 3.1 Preconditions — before the first code PR, and before deploy A

**Verify-then-close, no code.** Five open issues whose evidence is already in the tree or the
1.7.4 record; each closes with a comment naming that evidence, or is re-placed here with what
is missing named:

| item | evidence in hand | what closes it |
|---|---|---|
| **#330** | 1.7.4 record §7: Prefect loop overruns **0 in every counted roll's window**, all nine, after PR #1396 | the record's reading cited in the closing comment |
| **#372** | record §7: deploy D `synced — added 0, skipped 11, overwritten 0` on both realms after deploy B added 2; converged and idempotent, after PR #1395 | as above |
| **#352** | PR #1394 landed the boot-time guard (an agent refuses to boot against a registry lacking an asset its image ships). **A unit test for the refusal was not found by name on the tree this plan was written against** — the closing step locates it or files the gap | the test named, or a gap issue |
| **#157** | the 1.7.4 plan §6 already states the evidence (every `api/routes/` module has a test file, twelve assert 401/403, `test_route_lanes.py` enumerates every router, the comms suite covers the failure modes, CI runs the integration lane); the issue was never closed | the §6 paragraph cited in the closing comment |
| **#376** | its four asks are shipped by later work: the post-correction retest exists (`task_plan.py:145` `retest_decides`, `dispatched_flow_executor.py:1622`), the repair verdict is aggregated (#374 closed 2026-07-11), `frontend_build` is a required framework check (`check_registry.py:59, :109`, stack-conditional at `:128`), and the narrative-override prohibition is implemented (`run_report_builder.py:68`, SIP-0096 §6.6(4)). **The 1.7.0 plan §2.7 mislabels it "SIP-0102 migration steps 3–7"; it is SIP-0096 Phase 2 field evidence.** SIP-0102's steps 3–7 are feature-shaped and stay with that SIP (§6) | closed as verified; the mislabel corrected in the 1.7.0 plan amendment this PR carries |

**Two design artifacts, two independent decisions, reviewed by the owner before the first
closure PR.** They may share one review PR; they are not one document, because the reason
`correction_runner.py` has the shape it will have must never require reading a
composition-root policy.

*The composition-root standard* — under `docs/architecture/`, in the shape `api-route-lanes.md`
set for #218: a document plus one enforcing test. It must answer, with a decision for each:

1. which modules are composition roots — the allowlist at
   `tests/unit/architecture/test_forbidden_imports.py:156` already names them (the runtime
   API's wiring, the agent entrypoint, the sandbox, the bootstrap package); the standard adopts
   that list as the definition rather than writing a second one;
2. the rule, as an architecture invariant: **every adapter binding performed by a composition
   root is delegated to the owning adapter package's approved factory; a factory takes config
   and a required selector; a root never instantiates a concrete vendor adapter** — #1157's
   precedent for the LLM, applied to the queue and the A2A client; the `comms.provider`
   selector is already required by the factory and becomes required at both roots (the
   owner's require-don't-default ruling, 2026-08-28);
3. an A2A factory of the same shape — one entry, a required selector — because the seam's
   consistency is the point, not the number of implementations behind it today;
4. #286's shape: **importing code defines behaviour; starting the application performs
   configuration and wiring.** An app factory (`create_app(config)`), with the runtime image's
   command moving to uvicorn's `--factory` form (`src/squadops/api/runtime/Dockerfile:64`;
   `docker-compose.yml` untouched — it names the image, not the module), so that a bare import
   of the module performs no config load and no secret resolution; the `_import_fastapi_app()`
   workaround in `tests/unit/cli/test_integration.py` is deleted, not kept;
5. the enforcing test, a composition-roots guard beside the existing ones in
   `tests/unit/architecture/`: every root imports with no environment; no root instantiates a
   vendor adapter class; every binding a root performs is delegated to the owning package's
   factory. **The test proves the invariant by AST today; the invariant is the rule, and the
   factory package's layout may evolve without amending the standard.**

*The recovery extraction map* — its own artifact, answering:

1. the methods that move — the executor's recovery path first (`_try_accept_patch` at `:3245`,
   `_handle_task_outcome` at `:2950`), the correction protocol **by protocol step** (analyze,
   decide, rewind-or-repair, retest — each already dispatched through
   `_dispatch_protocol_step` at `correction_runner.py:1268`), `_execute_sequential` (`:1565`)
   last; `execute_cycle` and `execute_run` named as *not* in this line's map;
2. the destination modules and the order;
3. the forbidden change: **no behavioural change rides an extraction PR** — a defect found
   while extracting is filed and fixed in its own PR, before or after, never inside;
4. the proof: byte-identical on the context-assembly, correction-context and plan-context
   goldens (`tests/unit/cycles/test_*_golden.py`) and on the `tests/fixtures/roll_replays`
   corpus before and after every PR; then the five diagnostics on the pinned deploy (§4);
5. the stop rule, and which part of the map is the close criterion's core (§3.5).

**#1149's harvest, first.** The rationale in the paths the map moves is harvested into
`docs/architecture/defended-bespoke-decisions.md` — an existing home for exactly this kind of
content, so no new register is invented while the Design Decision Register SIP is still
proposed — and each extraction PR cites the entries it moved. A precondition of the first
extraction PR, not of the line.

**#906 lands in the prelude.** The Next.js baseline stylesheet has been "post-window" through
three lines. It touches `stack_nextjs_ts.py` and a request template, so the #1438 drift guard
refuses a counted roll after it merges until a rebuild — which is why it lands in §3.2 before
deploy A, where the checkpoint pair reads it. If it is not ready by then it is closed or
re-placed by name, not carried a fourth time.

**Two host preconditions, required, before deploy A.** Both are changes to the physical box,
and the line's rule is that the measured host does not move between the checkpoint and the
counted set — so they move it *before* the checkpoint, and deploy A cannot start without them:

| precondition | who | what proves it |
|---|---|---|
| **the nightly database backup timer** (`scripts/dev/ops/install_backup_timer.sh`, needs sudo; outstanding since 2026-08-30) | the owner | `install_backup_timer.sh --status` shows the timer active, recorded in the pre-registration's deploy-A identity |
| **OOM containment** (#1178): `earlyoom` at a conservative threshold as the first choice (it keys on available memory, which is the thrash the box saw on 2026-08-29; `systemd-oomd` keys on PSI and cannot see a unified-memory GPU allocation), `MemoryMax=` on the serving unit as the bound, and a `doctor local-spark` check | the profile and doctor PR merges (CI); the owner applies it | `squadops doctor local-spark` green on the box, recorded beside the timer |

The deployment Postgres had no backups at all until #1181; the only dumps today are the ones
deploys take. That is why the timer is a gate and not a note.

### 3.2 The measurement-correction prelude — deploy A, behind a checkpoint pair

Nine PRs that change what a record reads, what a roll rejects on, or what an evidence line
says, plus the one non-prelude item that touches the deployed database and is classified here
so the record knows it moved. They are **not** CI-only in the 1.7.0 plan §3.1 sense, and they
cannot ride beside the closures: a red on deploy B must have one owner. In merge order:

| step | item | what lands | readout |
|---|---|---|---|
| 1 | **#1445** | the three-state evidence vocabulary in the driver's record schema — `observed(value)`, `asked_none`, `unaskable(reason)` — with every existing readout migrated onto it and every registered field declaring its unaskable state as a schema property | instrument — the pre-registration is written in it |
| 2 | **#1436** | the attempt is stamped where a failed emission's artifacts are banked (the #971 seam), so the record reports emissions and artifacts as separate, both true | instrument — the L1 count's producer; the driver's grouping key moves to it and is re-checked on the pair |
| 3 | **#1197** | the sandbox environment image retagged for what it is (Python 3.12, Node 20, npm 10, serving both stacks); `environment.py:97, :141` and `build_sandbox_env_image.sh:10` agree; the old tag retired | texture: the boot-audit evidence line carries the new name; the contract hash changes on both stacks **here**, never mid-set |
| 4 | **#906** | the Next.js baseline stylesheet | read on the pair's Next.js half: boot audit and UI reach unchanged |
| 5 | **#1428** | the run-level roll-up owes only the checks its run's task types can subject — `framework_rows_owed()`'s rule (1.7.4 pack row 2) applied at the run level; `frontend_build` stays stack-conditional | texture: no framing run reports `blocked_unverified`; a genuine harness failure on a framing run is visible again |
| 6 | **#820** | `PROOF_INTERFACE_COHERENT` in `cycles/manifest_gates.py` beside the existing proofs (`:35–48`): path-parameter naming consistent across endpoints, declared testids correspond to what endpoints and views promise — string coherence over the manifest's own declarations, no PRD semantics, no LLM. **Reporting-only** | texture: findings per roll by class; promotion is a later deliberate call |
| 7 | **#668** (second half) | a check that a suite's `apiFetch` mock honours the frozen client surface — behind the stack seam (the client is stack #1's), validated on the 34 stored `../api`-mocking suites as its replay set and on the fay-14 suite it must flag. **Reporting-only** | texture: findings per roll; the replay set's result in the PR's Evidence |
| 8 | **#1406** (framework half) | **the untouched-file rule**: an environment skip (`missing_tooling`) on a criterion whose named file the patch did not touch does not erase that criterion's earlier executed-and-passed row — the patch's file set is already known per repair (#1323/#1350). Credit-restoring only; the seam table (emission / agent-side repair / verifier / gate / retest) in the PR | **a seam invariant, not a live hypothesis** (§4): proven on the absent-suite diagnostic and by the stored 1.7.4 case as a CI fixture; live occurrences read from #1407's readout as texture. The record computes every coverage figure under this rule and says so |
| 9 | **#1434** | the fill-mode declaration for `qa.test` and `qa.test_repair` moves from `NONE` to `LOW` in `REASONING_BY_OUTPUT_SHAPE` (`reasoning_policy.py:112`); the mechanism (#1285) stays | **the line's one live hypothesis — the fill declaration** (§4) |
| — | **#1180** | a `squadops_test` role whose grants make the deployment database unreachable (`REVOKE CONNECT … FROM PUBLIC` is the hole), created by the bootstrap path and the compose Postgres init (`infra/00-create-databases.sh`, mounted at `docker-compose.yml:40`) so a fresh environment has it without a manual step; a `doctor` check that verifies the **negative** — the test role cannot connect to the deployment database; the #1099 guard stays as defence in depth. **The compose init edit needs the owner's explicit OK, recorded on the PR** | **classified: the one item on deploy A outside the prelude that touches the deployed database.** Its failure signature (a connection or grant error at start-up) is distinct from every prelude readout, which is what keeps the pair attributable |

**Why `LOW` and not a revert.** The port's own vocabulary (`src/squadops/llm/models.py:10`)
defines `NONE` as "the level for a transcription — an output the prompt already contains". A
fill is synthesis under a scaffold, not a transcription: the model reads the scaffold and
writes bodies. `NONE` was a category error on the policy's own definition, and the line
measured its cost: #1268 read `think:false` at one usable emission in six on the authoring
shape; the 1.7.4 line read it at three clean in five on the fill shape, with the two failures
costing two and five correction rounds. `LOW` is the minimum honest declaration, and on
Ollama's boolean wire it maps to `think:true` (`adapters/llm/ollama.py:139, :225`), #1268's
six-in-six. The token saving #924 measured is given up on this provider and kept as a
declaration a provider with an effort dial can honour. **The owner overrules** (§8, decision 2).

**What the pair proves.** A red on deploy A belongs to this tranche — the prelude or the
database role — and is identified per PR by its signature: the prelude's readouts are named
fields, the role's failure is a start-up error. The fill hypothesis gets its first reading
here and its counted reading on deploy B.

### 3.3 Start-up truth — Composition Roots

After the composition-root standard is reviewed (§3.1). One PR each, in this order, because
#637's import job needs #286's bare import.

| step | item | what lands | how CI proves it |
|---|---|---|---|
| 1 | **#286** | the app factory; the module-level `load_config` at `main.py:57` gone; the Dockerfile CMD in `--factory` form; the test-side import workaround deleted | `python -c "import squadops.api.runtime.main"` with no environment succeeds, as a test; the composition-roots guard |
| 2 | **#301** | the queue half at **both** roots (`main.py:310`, `entrypoint.py:453`) delegated to `get_queue_adapter`; the A2A client through a factory of the same shape; `comms.provider` required at both roots; no vendor adapter class instantiated in either root | the composition-roots guard; the #154 allowlist test unchanged |
| 3 | **#637** | a CI job that installs `requirements/api.lock` and `requirements/agent.lock` into fresh venvs and imports both composition roots — the registration-time DOA class #636 found. **This row is the lock-and-import closure and nothing else**: the console's unconstrained `fastapi` pin (`console/app/requirements.txt:1`, installed at `console/Dockerfile:58` with no `-c`) is a second dependency-governance defect, the console has no lock file, and it is fixed with the console's own row (#198, §3.6), not here | the job, red on a root that fails to import under the locks; it is the deliverable for the 1.7.0 plan §6.2 criterion 3 |

**Non-droppable.** These three are the close criterion's first half (§3.9).

### 3.4 Invocation truth — the Observability Port

| item | what lands | how it is proven |
|---|---|---|
| **#929 with #1206** | the LLM call sequence — budget → prompt guard → call → content → duration → generation record — extracted onto `_CycleTaskHandler` as one method; the eight dark sites (`analyze_failure.py` ×2, `correction_decision.py` ×2, `define_done.py` ×2, `_plan_authoring.py`, `planning/review.py`) and the two unrecorded self-eval second calls (`develop.py`, `qa_test.py`) record through it; handlers keep prompt construction and response parsing; designed together, as the 1.7.1 plan §2.4 required | **extraction only — no semantic change in the extraction PR.** *Behaviour preservation:* a characterization test per migrated site against a recording fake port — the same messages, the same request kwargs including the reasoning declaration, the same returned content, the same task result, plus exactly one generation record per call where before there were zero. *Structural:* `test_every_llm_seam_captures_what_it_emitted` **inverts** to "no handler calls the port directly", and a generation-record twin counts records against calls per file and fails on a gap. *Live, completeness only:* the shakeout pair's LangFuse generation count equals its LLM-call count (1.7.4's pair read 26 of 35) — this reading proves the port sees everything; it does not stand in for the characterization proof |

**Non-droppable.** The line's preamble names the observability port as one of two remaining
violations of the 1.7 identity; a 1.7 that closes without it has a false thesis.

### 3.5 Recovery structural integrity — the extraction

After the recovery extraction map is reviewed and #1149's harvest has landed (§3.1). One PR
per step of the map.

| item | what lands | how it is proven |
|---|---|---|
| **#1152 with #1443** | the extraction in the map's order: the executor's recovery path (`_try_accept_patch`, `_handle_task_outcome`), the correction protocol by step, `_execute_sequential` last; **one extraction class, one proof**; each PR cites the #1149 entries it moved | byte-identical on the three goldens and the replay corpus before and after every PR; the five diagnostics on the pinned deploy reaching their seams (§4) — the seams the moved code owns |

**The core and the tail, for the close criterion.** The map's **recovery-path portion** — the
executor's accept-patch and outcome handling, and the correction protocol by step — is the
close criterion's core: it is what the five diagnostics prove and what Scoped Code Revision
lands through. `_execute_sequential` is the **tail**. If the shakeout budget (§4) is spent
before the map is complete, the tail is re-placed by name into the 1.8 plan's rider with the
map attached and §3.8's count incremented — a plan-management disposition that **does not**
satisfy the close criterion for the core. A core left incomplete stops the line, not the plan.

### 3.6 The hardening list — CI-verified, in neither deploy's cycle path

Four items, one PR each, riding beside the closures because none of them enters the runtime
image's cycle path: three are tests, and one changes the console container, which is deployed
but is not on the path a cycle runs or the driver reads. That classification is what lets
§7's attribution claim for deploy B stand.

| step | item | what lands | how CI proves it | in the image? |
|---|---|---|---|---|
| 1 | **#198** | the console router include graph flattened so a router is mounted once; `console/app/requirements.txt` constrained to the lock set; the `<0.136` cap in `tests/requirements.txt:37` lifted | `tests/unit/console/` green on the current lock's fastapi (`0.135.4`) and on the first release past `0.136`, in the #637 job | the console container only — not the cycle path |
| 2 | **#580** | the session-scoped `event_loop` override (`tests/conftest.py:39`) and the duplicate marker registrations (`:54–60`) retired; pyproject is the one marker registry | the whole regression suite, not the affected subset — the loop-scope change can surface cross-test loop assumptions | no |
| 3 | **#1182** | an architecture test asserting no file under `tests/` names the deployment database in a connection string — broader than `*.py` (the `.env` and `.md` literals #1099 found outranked the corrected default), matching the database *name* not one URL | the test itself, beside the existing guards | no |
| 4 | **#176** | the framework smoke integration test: the pipeline invariants (create → dispatch → framing → gate → handoff → correction → persistence) asserted over a cycle's artifacts and run state, runnable on the `smoke` squad, **explicitly decoupled from terminal `completed`** on content-gated paths | a `pytest` smoke marker against a small-model squad, in the integration lane | no |

**Re-placed out of this list at rev 3, proactively rather than under capacity pressure** (§5,
§6): #579 (the frontmatter parser — five sites, on every prompt render) and #353 (the
manifest hash stamped at build — a SIP-0084 governance change on the agent's boot path). Both
are legitimate debts on their fifth plan; neither is central to a closure contract or to
measured verdict correctness, and both can move runtime behaviour, which is exactly what the
list must not do beside the closures. §3.8's count says so.

### 3.7 The ops rider — live reads, not CI

| item | what | read where |
|---|---|---|
| **#1177** | the Atlas A/B replay scripts routed through `arm.sh` so the rig cannot put both arms in the Spark's unified memory; the host reserve restored. Its scripts live in `~/atlas/scripts`, outside the repo | on the box, after the counted set (§7 step 12); a stated precondition of #1408 |
| **#300** (carried reading) | the 1.7.4 record §7 read the advisory-lock key loaded and the acquisition path unexercised (no migration ran) | stays "loaded, not exercised" unless a migration lands in this line; the record says which |

### 3.8 The count this line owes the record

Counted from the plans' own placement sections; the 1.5-era items enter at the 1.5 plan's
capacity roll, where the post-1.5 reconciliation classified them.

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #301, #286 | 1.5.0 (capacity roll), 1.7.0 (§2.5, the row then called 1.7.4), 1.7.3 §6, 1.7.4 §6, 1.7.5 | **5** each |
| #567, #579 | 1.5.0, 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **5** each — both re-placed to the 1.8 rider (§6): #567 at rev 2, #579 at rev 3 |
| #820, #376 | 1.6.0 (deferred by name), 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **5** each — #376 closes as verified, not as built |
| #929 (+#1206) | 1.7.0 (rider), 1.7.1 §2.4, 1.7.3 §6, 1.7.4 §6, 1.7.5 | **5** — non-droppable here |
| #353 | 1.7.0, 1.7.2, 1.7.3, 1.7.4 (not landed, pre-registration §9), 1.7.5 | **5** — re-placed to the 1.8 rider at rev 3 (§6) |
| #198, #176, #580 | 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **4** each |
| #1152, #1149 | 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **4** each |
| #637, #598, #668 | 1.7.1, (lost), 1.7.4 §6a, 1.7.5 | **3** each — #598 re-placed by recommendation (§8) |
| #1180, #1182, #1197 | 1.7.3 §6, 1.7.4 §6, 1.7.5 | **3** each |
| #1177, #1178 | 1.7.3 §6 (parked), 1.7.4 §6a, 1.7.5 | **3** each |
| #1406, #1428, #1434, #1436 | 1.7.4 (§6a or the record), 1.7.5 | **2** each |
| #1443, #1444, #1445 | 1.7.5 (filed with rev 2 and rev 3) | **1** each |

Five items are on their fifth plan, and two of them leave this line by decision rather than
land. That is the §3.6 principle of every 1.7 plan actually removing work: repeated deferral
raises the requirement to dispose of each item by explicit decision, and it does not override
experiment isolation — which is why the two that can move runtime behaviour beside the
closures are re-placed rather than carried.

### 3.9 The cut criterion — the 1.7.0 plan §6.2, criterion by criterion, plus the three gates

The line closes when the 1.7.0 plan §6.2 holds. Each criterion has a deliverable in this
plan; the record reads them one at a time:

| §6.2 criterion | this line's deliverable |
|---|---|
| 1. Composition Root fully landed; Hardening's remainder re-placed by name | **Start-up truth (§3.3) and invocation truth (§3.4) fully landed — non-droppable; the recovery extraction's core landed (§3.5), its tail re-placeable by the stop rule.** A stop-rule re-placement satisfies the plan-management rule; it satisfies this criterion only for the tail. §5's and §6's re-placements named |
| 2. Both counting sets closed with no falsified prediction; the record from per-round evidence | §4 — the fill hypothesis holds; L1 holds; the record cites per-round artifacts |
| 3. CI green on main including `integration`, on Python 3.12, **against the locked deps the images install** | `integration` is already required (1.7.4 §3.1); #637 is the deliverable that makes the last clause true for the composition roots |
| 4. Zero drift between the measured deploy and the tag; the package captured on the first try with the `Closes` column correct | §7 step 14; the preview read before `--write` (the 1.7.4 lesson) |
| 5. SIP promotion sweep | SIP-0104 stays `accepted` (#1122 does not ship); SIP-0102's open steps 3–7 named as staying `accepted`; SIP-0084's #353 amendment moves with #353 to 1.8; nothing else moves |

And the three gates 1.7.4 kept apart, so "landed" never stands in for "proven":

| gate | criterion |
|---|---|
| **implementation** | every §3.2, §3.3, §3.4 row merged and §3.5's core; §3.6's rows merged or dropped by a plan revision that names the destination (§5); both design artifacts merged before the first closure PR; both host preconditions recorded before deploy A |
| **experimental** | **L1 holds**; the fill hypothesis holds; **every one of the five diagnostics reached its seam on the pinned deploy** and the untouched-file invariant read true on the absent-suite diagnostic — no amendment; a "not reached" after the two-run budget is a closure finding that stops the line; the rewind invariant is CI-only by declaration and is not counted among the five |
| **evidence** | every field §4 names is populated on every counted record in the three-state vocabulary, with its unaskable state declared; the record reconstructs every counted/void/reset boundary from per-round evidence; deploy-to-tag drift named item by item, expected zero |

### 3.10 Merge discipline

One PR per row; `--head` on every PR; every job of main's run read after every merge; the
seam table in every PR that binds, removes or re-weights a check (#1406, #668, #820); the
mirror rule on every removal (#286's workaround, #580's fixtures); the composition-roots guard
in the same PR as the first root it constrains; the characterization tests in the same PR as
the first call site #929 migrates; **no merge to main while a set is open**; the compose init
edit (#1180) on the owner's recorded OK. The plan's own PR carries the 1.7.0 plan §7
amendment pointing here.

---

## 4. The verification set — a regression check on the loop, with one hypothesis in front

Two counting sets on one frozen deploy, **6 + 3** — the fourth consecutive set at that size,
for comparability across 1.7.2, 1.7.3 and 1.7.4 on one PRD and two stacks.

**Bar.** **L1** (#1268), as amended before the 1.7.4 set opened: blocking on a counted roll
whose contentless emission is *not recovered*; the occurrence count tracked and never quoted
as zero. It stays the bar because it is the condition every other reading is measured
through, and because this line changes the declaration that produced its only breach. **H1 is
retired as a bar**: it holds by construction since #1430 and the 1.7.4 record said so; its
content — every required file the roll's own rows declared — stays as a texture field in the
three-state vocabulary (on a clean roll the framework row is filtered at `validation.py:252`,
so the field reads `unaskable(filtered at the typed-check seam)` and the driver reads the run
report's executed/passed counts beside it).

**Live hypothesis — one, from the prelude:**

| claim | method | falsified by | what a clean set proves |
|---|---|---|---|
| **the fill declaration** (#1434): zero contentless fill-mode first attempts across the counted set | every Next.js roll; emission-shape lines and the #1436 stamp | one contentless fill-mode first attempt | **that `NONE` was semantically misdeclared, that `LOW` is the minimum honest declaration, and that the measured set found no contentless recurrence under the pinned provider, model and deploy on this workload.** Not that `LOW` is generally sufficient; a provider or model change re-opens the reading |

**The hypothesis and L1 intentionally have different thresholds.** The hypothesis measures
whether the declaration prevents recurrence: one contentless fill-mode first attempt falsifies
it. L1 measures whether recurrence, from any producer, remains recoverable: only an
*unrecovered* contentless emission breaches it. One contentless fill attempt can therefore
falsify the hypothesis while the loop demonstrates honest recovery and L1 stays green — and
that outcome is useful evidence, not a contradiction.

**Seam invariants — proven on the pinned deploy this time.** The **five** diagnostic configs
are re-registered under a `1.7.5/` prefix and run on the pinned deploy with a two-run budget
each: absent-suite (the retest seam, L2), own-frame-then-prose-repair (L7, L4, L5),
path-prefix (L8b; L8a read as the count on every roll), contentless-builder (the retry with
its fact, R1), and absent-suite-then-false-claim (the analyzer's refuted claim reaching the
decision, A1). **The recovery extraction is what these exercise.** A seam not reached after
two runs is a closure finding and stops the set; it is not declared and carried, as 1.7.4's
two-run rule allowed for seams the pack had not touched.

**The untouched-file rule (#1406) is a seam invariant, not a live hypothesis** — "no fault,
no prediction" applied to it. Its condition needs a correction round, an environment skip and
a criterion on an untouched file, and nine ordinary rolls may produce none; the 1.7.4 set
produced one such roll in nine. So it is exercised deterministically: **the absent-suite
diagnostic runs on the React stack (`validated-fullstack`), forces a qa repair, and that
repair's patch verification runs at the runtime-api where npm is absent** — the exact shape
that demoted three view-compile criteria on `cyc_dd3068d22f2c`. The readout on that diagnostic
is the invariant's proof: the executed-and-passed view criteria survive the skip. The stored
1.7.4 case is replayed as a CI fixture beside it. Live occurrences on counted rolls are
texture, read from #1407's readout in the three-state vocabulary.

**CI invariants, read live as texture:** the rewind invariant (W1 — no honest rewind fault
exists, unchanged from 1.7.4), the locus invariant (D1) and the derived-rows invariant (F1).

**Texture — observed, never blocking, every field with a producer and its unaskable state
declared as a schema property (#1445) before roll 1:** the framing run's verdict (#1428);
packaging findings per roll by class (unchanged rate expected; the #598 decision reads it);
emissions versus banked artifacts (#1436, now exact); fill-mode qa completion tokens under
`LOW` (Q1 re-read); interface-coherence findings (#820) and mock-surface findings (#668) per
roll; the boot-audit image name (#1197); fence counts and placeholder strips per roll (L8a);
generation records per LLM call on the shakeout pair (#1206, a LangFuse read); the required
files the rows declared (H1's content); correction rounds; verdict rate against 1.7.4's.

**Shakeout loop** (`docs/plans/verification-sets/README.md`): deploy A gets **one checkpoint
pair** (a red is the prelude tranche's); deploy B enters the loop — exit on a pair with no
new seam finding, **budget three pairs**; the record reports rounds taken and rounds
attributable to the closures. **The loop is retained because an extraction of this width has
behaviour the goldens do not fully represent; zero attributable findings is acceptable only
if every registered diagnostic reaches its seam on the pinned deploy.** A clean extraction is
not suspicious by definition, and a finding is not evidence of adequacy — the reachability
count is.

**Early stop, one direction.** A falsified hypothesis or an unreached seam stops the set; a
good result never stops it early; a stop in one arm does not stop the other.

**Drift the record must declare:** intended zero — the tag is the measured deploy plus the
pre-registration and the record.

---

## 5. Capacity — what was dropped, what drops next, and what cannot

**Dropped proactively at rev 2 and rev 3**, to the 1.8 plan's hardening rider by name (§6):
#567 (rev 2, the emission-path refactor gave its capacity to the correction runner), #579 and
#353 (rev 3, the two list items that could move runtime behaviour beside the closures, and
neither central to a closure contract). The line now carries: nine prelude PRs plus the
database role; three start-up PRs; one invocation PR; the extraction PRs by the map; four
list PRs; two design artifacts; the harvest; two host preconditions; five verify-then-closes.
Against the 1.7.0 plan §3.1 ceilings: **one live hypothesis** (against 6–8 roll-verified —
the prelude is readouts, not predictions) and **eleven CI-verified issues** (#286, #301, #637,
#929, #1206, #1152, #1443, #198, #580, #1182, #176 — inside 10–15).

**If capacity forces another drop**, it comes from §3.6 in reverse order — #176 first, then
#580 — to the same destination, recorded as a revision of this plan in the open. The
extraction's tail drops by its own stop rule (§3.5).

**Non-droppable:** the prelude (§3.2), start-up truth (§3.3), invocation truth (§3.4), the
extraction's core (§3.5), the host preconditions and the verify-then-closes (§3.1). If
capacity cannot carry these, the line does not close 1.7, and the plan says so rather than
re-placing a closure.

---

## 6. Re-placements by name — nothing silently carried

Forty-seven open issues after the three this review filed. Twenty-eight are in this line
(§3.1–§3.7). The nineteen that are not:

**#598's first half — the 1.8 lane, by recommendation (§8, decision 1).** The 1.7.4 plan §6a
placed the promotion of `container_packaging` to blocking at the head of this line. Three
sets of evidence since say the shape is wrong: the check fails on five of nine, four of nine
and eight of nine counted rolls across 1.7.4, 1.7.3 and 1.7.2 — a rate at which the packaging
is a deliverable the squad does not reliably author, not a defect a blocking check corrects —
and SIP-0102 §4.2 ("environment definition is the contract; Dockerfiles are an adapter
rendering") and SIP-0105 both say the packaging should be rendered from the stack's
declaration, not emitted by the builder. A blocking check spends correction budget repairing a
file the framework should own. The right-shaped fix is stack-rendered packaging with
`container_packaging` as a guard on the rendering — a role-contract change (SIP-0071's
builder authors the Dockerfile today), so feature-shaped, so 1.8, beside #598's second half
(the in-cycle image build). **If the owner holds the 1.7.4 placement**, the fallback shape is
stated in §8 so it is not designed at the PR.

**#567, #579, #353 — the 1.8 rider, by name.** The fenced parser's CommonMark recognition
engine (its subject is the emission path every roll runs through; its bar is the stored
replay corpus unchanged); the frontmatter parser (five sites — `prompts/renderer.py:53`,
`adapters/prompts/filesystem_asset_adapter.py:86, :113`, `adapters/prompts/filesystem.py:209`,
`wrapup_tasks.py:145` — four inline, one helper; on every prompt render); the manifest hash
stamped at build (a SIP-0084 post-acceptance amendment first, then the build; on the agent's
boot path). Each on its fifth plan (§3.8); each re-placed by decision, with the reason, so
the 1.8 plan names them or revises this placement in the open.

**The 1.8 lane — Scoped Code Revision, a feature, always 1.8's** (the owner's ruling,
2026-09-09; PR #1325; subsumes #1213; #1176 beside it). Nothing of it is built here, and
nothing of it is reviewed here. Its design review — a named reviewer, a written outcome from a
fixed vocabulary (accepted; accepted with required revision; rejected and reframed), a
completed design decision rather than acceptance of PR #1325 — **is the 1.8 plan's opening
step**. It is named in this document only because the 1.7.4 plan's "opens beside this line"
produced zero reviews across a whole line, and the 1.8 plan must name a reviewer rather than
repeat the phrasing. Nothing in 1.7.5 depends on its outcome. What this line hands it: the
extraction of `_try_accept_patch` and the correction protocol, which are the seams a scoped
revision lands through, and **#1444 — the qa and dev handlers' `handle()` split by output
shape (645 and 354 lines carrying fill and authoring under one function) — as the first
extraction the feature requires**; it precedes the feature's first PR, it is 1.8's and is not
a feature, and the 1.8 plan carries it as an explicit precondition rather than pulling it
here. #1122 stays with SIP-0104.

**Still at design review, unchanged:** #414 (severity-aware correction reserve), #557
(post-retest governance review), #316 (request-profile taxonomy, moves with Campaign); and in
the 1.8 lane #80, #950, #949, #194, #1039, #1031.

**Spark host and Atlas — after the counted set closes (§7 step 12):** #1408 (the Flash-Next
plan-authoring replay — needs the box to itself, 94.87 GiB against a 121 GiB box) and #1412
(the content-loop diagnosis session). Both execute substantial model workloads on the
measured host; neither touches the deploy, and that is not enough for a physical-machine
experiment — residency, caches, memory pressure, temperature and operator changes during a
diagnosis all move host state without moving git. The box is idle after the set too. **Nothing
goes to the vendor without the owner's explicit go-ahead** (#1412's own rule).

**SIPs that stay `accepted`, named so the sweep does not read silence as shipped:** SIP-0101
(replay harness; the minimum slice landed in 1.5), SIP-0102 (steps 3–7 — feature-shaped),
SIP-0104 (#1122), SIP-0105 (the blueprint rewrite after #1131), SIP-0088/0090/0091/0092/0093
(the runtime-modes cluster, 1.6-era targets, untouched by 1.7 and re-read at the 1.8 plan).

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.7.0 plan §7 amendment (the 1.7.5 row placed here;
   #376's label corrected). Merges on the owner's review.
2. **Verify-then-close** the five §3.1 issues, evidence cited on each; the #352 test located or
   its gap filed.
3. **The two design artifacts** (§3.1), reviewed by the owner as two independent decisions —
   the design gate. **#1149's harvest** for the extraction map's paths. In parallel, the
   prelude PRs are built on branches.
4. **The host preconditions** (§3.1): the owner installs the backup timer; #1178 merges, is
   applied to the box, and `doctor local-spark` is green. Both recorded. **Deploy A cannot
   start without both.**
5. **The prelude** (§3.2), one PR each — #1445 and #1436 first, #1434 last — and **#1180**,
   classified.
6. **Deploy A; one checkpoint pair** — a red belongs to this tranche and is identified per PR
   by its signature; every driver field re-checked on the pair's records in the three-state
   vocabulary (#1445 changes every field's shape; #1436 moves the L1 grouping key; #1197
   moves the contract hash); the fill hypothesis's first reading.
7. **The three closures**, one PR each in order — start-up truth (#286, #301, #637);
   invocation truth (#929 with #1206); the recovery extraction by the map (#1152, #1443) —
   and **the hardening list** (§3.6: #198, #580, #1182, #176) riding in CI beside them, none
   in the cycle path.
8. **Deploy B; the shakeout loop** to the exit rule, budget three pairs — **a red belongs to
   the closures**, because nothing else that can move runtime behaviour is on this deploy.
9. **The five diagnostics on the pinned deploy**, two-run budget each, recorded with the entry
    point each used; the untouched-file invariant read on the absent-suite diagnostic. A seam
    not reached stops the line here, before the set opens.
10. **Pre-register** (`1-7-5-<arm>.yaml`, pins from the last shakeout; every field's producer
    and unaskable state as schema properties, checked against a real record).
11. **Counted set 6 + 3** — no merges to main while a set is open; the counted/void/reset
    reading at each boundary.
12. **Close the set; the live reads** — #1177 on the box, #300's reading carried or exercised
    — named in the record as read live. **Then, and only then, the idle-box work**: #1408's
    plan-authoring replay and #1412's diagnosis session, on the same harness and gate as
    #1184's measurement.
13. **The preliminary measurement conclusion**: §3.9's five close criteria and three gates,
    read against the frozen deploy before anything else moves.
14. **Final record; cut 1.7.5 by the seven steps** — the release-package preview read and its
    verdicts checked against the records before `--write`; the SIP sweep as §3.9 states it;
    zero drift named. **The 1.7 line closes.** Then the 1.8 plan, whose opening step is the
    Scoped Code Revision design review, with #1444 as its first extraction and the re-placed
    items §5 and §6 name.

The key property of this order: the two things that can move a verdict — the prelude and the
closures — are on different deploys with a checkpoint pair between them; nothing that can
move runtime behaviour rides beside the closures; the host does not move between the
checkpoint and the counted set; and the diagnostics that prove the extraction's seams run on
the deploy the numbers come from.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

**Ruled by the owner, 2026-09-09, at rev 3's review: decisions 1 and 2 approved** — #598's
promotion is not taken and the packaging becomes a rendering in the 1.8 lane; the fill-mode
declaration moves to `LOW`. The plan merges on that ruling and the verify-then-close (§7 step
2) opens the line.

1. **#598's promotion to blocking is not taken in this line; the packaging becomes a
   rendering in the 1.8 lane** (§6). **Fallback if the owner holds the 1.7.4 §6a placement:**
   it lands as step 0 of §3.2 with the finding routed to the builder as a *repair* (a required
   check with a correction path, not a straight rejection), a registered hypothesis ("a
   packaging finding on the accepted emission is repaired within the correction budget"), and
   a declared non-closure rejection cause; the record then says Functional App Yield's meaning
   changed on this line, since it would include packaging for the first time.
2. **The fill-mode declaration moves to `LOW`, not back to the task default and not to a
   third wire.** `NONE` is defined for transcription and a fill is not one; `LOW` is
   `think:true` on this provider and stays honest on one with an effort dial. Omitting the
   `think` key — the third wire #1268 measured — is a provider default, which the policy's
   own rule ("a level, never a provider's switch") forbids declaring. **A clean set validates
   the pinned configuration; it does not prove `LOW` generally sufficient** (§4).
3. **#1406 lands as the untouched-file rule** (its option 2), credit-restoring only, in the
   prelude; **it is a seam invariant, proven on the absent-suite diagnostic and by the stored
   1.7.4 case as a fixture**, with live occurrences as texture — "no fault, no prediction"
   applied to it. Option 1 (route the re-evaluation where tooling exists) is the wider change
   and touches the verifier's environment axis mid-line.
4. **#820 and #668's second half land reporting-only**, with their replay sets as
   validation; promotion is a separate deliberate call on the counts the set produces.
5. **The three closures are separate sections with separate proofs, and the recovery
   extraction has its own design artifact** — the composition-root standard and the recovery
   extraction map are two independent decisions that may share one review PR.
6. **#567, #579 and #353 are re-placed to the 1.8 rider now**, proactively: #567 at rev 2 so
   the correction runner takes its capacity; #579 and #353 at rev 3 because they can move
   runtime behaviour beside the closures and neither is central to a closure contract.
7. **#376 closes as verified**, and the 1.7.0 plan §2.7 mislabel is corrected in this PR's
   amendment rather than left as two documents disagreeing.
8. **#906 lands in the prelude** or is closed by name; not carried a fourth time.
9. **#637 is the lock-and-import closure only**; the console's dependency pin belongs to
   #198's row.
10. **The set is 6 + 3, L1 the bar, one live hypothesis, five diagnostics on the pinned
    deploy with no amendment**, the rewind invariant CI-only and not counted among them, and
    every field in the three-state vocabulary (#1445, filed with this revision).
11. **The Scoped Code Revision review is the 1.8 plan's opening step, not this line's** (§6);
    its outcome vocabulary is fixed there — accepted, accepted with required revision,
    rejected and reframed — and the gate is a completed decision, not acceptance of the PR.
    Rev 3 carried it as a step of this line's sequencing; rev 4 removes it on the owner's
    ruling that nothing in 1.7.5 depends on it.
12. **#1408 and #1412 run after the counted set closes**, not in the gap between deploys: the
    measured host does not carry unrelated heavy work between the checkpoint and the set.
13. **The composition-root standard states its rule as an architecture invariant** and its
    guard proves it by AST today; the standard is not amended when the factory layout moves.
14. **The line carries eleven CI-verified issues and one live hypothesis**, inside the 1.7.0
    plan §3.1 ceilings, with §5's next drops and destination fixed so a drop is a revision and
    never a carry.
15. **The correction runner joins the extraction map** (#1443): one extraction class with
    #1152, one proof, extracted by protocol step, #1149's harvest first; the recovery-path
    portion is the close criterion's core and `_execute_sequential` is the re-placeable tail.
16. **The qa and dev handlers' `handle()` split is 1.8's first extraction, not a feature and
    not this line's** (#1444).
17. **The backup timer and OOM containment are required host preconditions of deploy A**, not
    advisory notes: the plan's own reason for naming the timer was that the first deploy
    should not run on a box with no scheduled backup, and a gate is what that sentence means.
18. **Start-up truth and invocation truth are non-droppable; the extraction's core is
    non-droppable; a stop-rule re-placement satisfies the close criterion only for the tail.**

---

## 9. Findings from the review that produced this plan

Named here so they are not the next §6a. None blocks the plan; each has a home above.

- Three rider issues are open with merged PRs (#330, #372, #352) and #157 is open though
  declared closed — §3.1. The 1.7.4 line's own memory and its plan §6 both read them as closed.
- The 1.7.0 plan §2.7 labels #376 as SIP-0102 steps 3–7; it is SIP-0096 Phase 2 evidence —
  corrected in this PR's amendment.
- #579's premise ("five byte-identical copies") no longer matches the tree — §6 states the
  count found.
- The executor grew from 4,349 to 4,933 lines since #1152 was filed; `_try_accept_patch` is
  now its largest method — §2, §3.5.
- The Scoped Code Revision design review never opened — the 1.8 plan's opening step (§6).
- The ROADMAP's Stats header still reads "As of 2026-09-07 (v1.7.3)" beside a 1.7.4 framework
  version: the cut's step 4 (the timeline entry) was done and the Stats header was not.
  Cosmetic; fixed with the next ROADMAP edit this line makes, not in this PR.
- The nightly backup timer is still not installed — §3.1, now a gate.
- **The god-file measurement (2026-09-09, main `191e8e49`).** The criterion is **one growing
  unit that owns multiple independent reasons to change** — never a line count. By it, four
  files fail: the executor (#1152), the correction runner (#1443 — `run_correction_protocol`
  536 lines, the file up 47% since v1.6.0), and the qa and dev handlers (#1444 — `handle()`
  645 and 354 lines). Large files that are *not* god files, so no action: `acceptance_checks.py`
  (2,245 lines, 64 units, largest 75 — a registry with one reason to change per unit) and
  `scaffold.py` (down from 2,312 to 1,806 after the 1.7.1 stack extraction). Two watch items
  with no dominant unit yet: `patch_verification.py` (up 63% since v1.6.0,
  `verify_patched_artifacts` 207) and `task_plan.py` (`generate_task_plan` 237, table-driven).
- **Rev 2 carried a contradiction its own gate could not satisfy**: §4 counted "six
  diagnostics" while naming the rewind invariant CI-only, and the experimental gate required
  all six to reach a seam. There are five diagnostic configs
  (`docs/plans/verification-sets/1-7-4-diagnostic-*.yaml`). Found by the owner's review;
  fixed everywhere the count appears.

---

## 10. Revision history

- **Rev 4 (2026-09-09, after the merge of rev 3)** — on the owner's ruling that a 1.8
  feature's design review is the 1.8 plan's step, not this line's: the Scoped Code Revision
  review removed from §7 (rev 3's step 2; the later steps renumbered and every cross-reference
  moved), §6 restated so the review is the 1.8 plan's opening step and nothing in 1.7.5
  depends on it, §8 decision 11 and the §1 and §9 rows aligned. What this line hands the 1.8
  plan is unchanged: the recovery extraction's seams and #1444 as the feature's first
  extraction. No change to the content, the set, the gates or the attribution structure.
- **Rev 3 (2026-09-09, the same morning)** — on the owner's written review of rev 2. The
  structure now matches the thesis: **three closure contracts** (start-up truth §3.3,
  invocation truth §3.4, recovery structural integrity §3.5) with separate proofs, the
  observability port promoted out of the list and made non-droppable, the recovery extraction
  separated from Composition Root with its own design artifact and a core/tail split for the
  close criterion. **The deploy-B attribution claim is made true by construction**: #579 and
  #353 re-placed to the 1.8 rider proactively, #1180 classified on deploy A, #1178 moved to
  the host preconditions, leaving a four-item list in neither deploy's cycle path. **The
  six-diagnostic contradiction fixed** — five on the pinned deploy, the rewind invariant
  CI-only, one count everywhere. **#1406 demoted from live hypothesis to seam invariant** and
  exercised on the absent-suite diagnostic (React), with the stored 1.7.4 case as a fixture;
  the fill hypothesis is the line's one live hypothesis, its conclusion worded to the pinned
  configuration and its threshold distinguished from L1's. **#1445 filed** (the three-state
  evidence vocabulary) and placed first in the prelude. #929/#1206 gets an extraction-only
  rule and a characterization proof independent of the LangFuse count. The backup timer and
  OOM containment become required host preconditions of deploy A; #1408/#1412 move after the
  counted set. #637 narrowed to the lock-and-import closure, the console pin left with #198.
  The invariant wording of the composition-root standard, the import-versus-start principle,
  the shakeout wording, the design-review outcome vocabulary, and the god-file criterion (also
  written into #1443 and #1444) per the review. Unchanged: the decision to close 1.7 here,
  6 + 3, the prelude-before-structure checkpoint, the #598 reversal, Scoped Code Revision as
  design-only until 1.8, and the three-gate cut.
- **Rev 2 (2026-09-09, the same morning)** — on the owner's two rulings and the god-file
  measurement (§9): Scoped Code Revision is always 1.8's, as a feature — restated in §6 with
  nothing of it built here; **#1443** (the correction runner's extraction) filed and placed in
  the extraction map beside #1152 as one class with one proof; **#1444** (the qa/dev
  `handle()` split) filed and placed as 1.8's first extraction; **#567 re-placed to the 1.8
  rider** so the correction runner takes its capacity.
- **Rev 1 (2026-09-09)** — written the morning the 1.7.4 line closed, on the owner's ask, from
  the 1.7.4 plan, pre-registration and record, the 1.7.3 plan §6/§8, the 1.7.0 plan §2.5/§3.1/
  §6.2 and the tracker (44 open issues, every one placed by name). Structure: a verdict-surface
  stratum of eight behind a checkpoint pair, then Composition Root behind a design note with
  the executor extraction under the diagnostics, then a CI list with its drop order fixed. Two
  predictions; L1 the bar; H1 retired as a bar; the diagnostics on the pinned deploy with no
  amendment. Fourteen decisions by recommendation, the first of which (#598's promotion
  re-placed to the 1.8 lane as stack-rendered packaging) reverses a 1.7.4 §6a placement and is
  stated with its fallback.
