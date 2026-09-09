# 1.7.5 — plan

**Revision 1, 2026-09-09.** Written the morning the 1.7.4 line closed, from the 1.7.4 plan (rev
4 §6, §6a, §8), the 1.7.4 record (`docs/plans/1-7-4-verification-set-record.md` §2–§9), the
1.7.4 pre-registration §3a and §9, the 1.7.3 plan §6 and §8, the 1.7.0 plan §2.5, §3.1 (as
amended) and §6.2, the ROADMAP's 1.7 identity, and every open issue in the tracker on the
morning of writing — forty-four, each placed by name in §3 or §6.

**1.7.5 closes the 1.7 line: every port is actually a port.** The three prior lines made the
loop honest (1.7.2, 1.7.4) and the boundaries hold (1.7.3). What remains of the identity is
the place where the framework meets the outside world at start-up — the composition roots —
and the one port that is still bypassed at more than half its call sites, the observability
port. This line wires both roots through their factories, makes a bare import of the runtime
side-effect free, continues the executor strangler on the recovery path the last two lines
instrumented, and lands the packaging, test-isolation and extraction items every 1.7 plan has
scheduled and none has staffed. It is a **list line with a small verdict-surface stratum in
front of it**: the 1.7.3 shape, plus the four findings 1.7.4's set handed forward, which
change what a record reads and so land first, behind a checkpoint pair, before the refactor.

Rules carried from 1.7.3 and 1.7.4 without discount, and one added from the 1.7.4 record:

- **a measured stratum and a refactor do not land on one deploy without a checkpoint between
  them** — here the verdict-surface stratum is banked green on deploy A before the composition
  root moves on deploy B, so a red on the shakeout loop is the refactor's by construction;
- **every registered readout maps to a typed evidence field, checked against a real record,
  before the set opens** — and, new from the 1.7.4 record §9, **every field states what it
  reads when the thing it measures is unaskable**, not merely absent; an empty field whose
  producer is structurally silent on a clean roll is not evidence (the H1 readout lesson);
- **no fault, no prediction** — a claim no counted roll is likely to reach is proven by a
  fault or a CI invariant and reported as texture;
- **the diagnostics run on the pinned deploy**, with no amendment: 1.7.4 skipped its step 10
  and said so; this line's refactor is exactly what those diagnostics exercise, so a seam
  not reached on the pinned deploy is a refactor finding, not a reachability that "was not
  in doubt".

---

## 1. What the 1.7.4 line says the release has to be

| what the line showed | evidence | what it says about this release |
|---|---|---|
| Functional App Yield 7 of 9 with zero intervention; every accepted roll credited all its criteria; both rejections named the criterion they lost | 1.7.4 record §1, §6 | the loop's honesty half is done; the line can be about structure rather than behaviour |
| the line's only bar breach came from the fill-mode reasoning declaration: across the five fill-mode qa rolls on the line, three produced a working suite in one emission at ~3,943 tokens and two produced sentences of intent (2 of 24 and 7 of 35 contentless), both recovered through correction rounds | record §3 (Q1), #1434 | **the fill-mode declaration is decided in this line** (§3.2, §8): the saving is a token cost, the failure is the bar |
| a repair's verification demoted nothing on the set but carried five `missing_tooling` skips on one roll; the registered condition says that roll's coverage is never quoted whole | record §5 (#1406) | **the framework half of #1406 lands before this line's set**, credit-restoring, so the next record quotes every roll whole |
| the diagnostics were not re-run on the pinned deploy; the four carried 1.7.3 invariants and the analyzer invariant rest on earlier deploys | record §4, §8 | **this line runs all six on its pinned deploy**; the executor extraction is what they exercise |
| the handoff bar's readout was structurally empty on every roll — the framework's `required_files` row is filtered at `validation.py:252` and the other source reads log lines emitted only on the patch path | record §2, §9 | the unaskable rule in the preamble; §4 applies it to every registered field before roll 1 |
| `container_packaging` reported a failing row on **five of nine** counted rolls (React 1, 3, 4, 5; Next.js 1 — `npm_ci_without_lockfile` on four, `debian_nginx_default_site_unremoved` on one), after four of nine on 1.7.3 and eight of nine on 1.7.2 | the counted records' `typed_checks.container_packaging_rows` | **promoting the check to blocking is the wrong shape** (§8, decision 1): the finding rate says the packaging is a deliverable the squad does not reliably author, and both accepted sandbox SIPs say it is a rendering, not an emission |
| three rider items whose PRs merged are still open — #330 (PR #1396), #372 (PR #1395), #352 (PR #1394) — and #157, which the 1.7.4 plan §6 declared closed-by-accretion, is open | the tracker, 2026-09-09 | verify-then-close at the head of the line with the record's own readings (§3.1); the memory that "all eighteen rider items closed" was wrong |
| the rider-then-pack structure behind a checkpoint pair attributed every red on the line; zero code drift deploy-to-tag | record §1, the cut | the same structure, inverted in risk: the verdict stratum first, the refactor second (§7) |
| the Scoped Code Revision design review, which the 1.7.4 plan §7 step 2 said "opens beside this line", never opened — PR #1325 has zero reviews and zero comments | the PR, 2026-09-09 | it opens with this plan's PR as a named step, not "beside" (§7 step 2) |

---

## 2. Why this line, on the roadmap

- **The 1.7 identity has a start-up half.** "Every port is actually a port" is false at the
  composition roots today: the runtime-api constructs its queue adapter directly at
  `src/squadops/api/runtime/main.py:310` and its A2A client at `:496`, and the agent
  entrypoint constructs its queue adapter at `src/squadops/agents/entrypoint.py:453` — while
  both roots already route the LLM through `create_llm_provider` (#1157, the LLM half of
  #301). `get_queue_adapter` exists (`adapters/comms/factory.py:40`) and already *requires*
  `comms.provider` (`:29–31`); nothing calls it from a root. The config is loaded at module
  import (`main.py:57`), so `import squadops.api.runtime.main` needs a secrets profile to
  succeed (#286). The ROADMAP names both as load-bearing for the Atlas migration and for
  1.8's scorecard; SIP-0106 §1.2f names #301 a *precondition* of any provider adoption.
- **The observability port is bypassed at eight call sites.** By AST count on the tree this
  plan was written against, `analyze_failure.py`, `correction_decision.py` and
  `define_done.py` each make two LLM calls and record no generation; `_plan_authoring.py` and
  `planning/review.py` one each; `develop.py` and `qa_test.py` record their first call and not
  their self-eval second (#1206). #929's extraction of the call sequence is the fix that
  makes a fourteenth dark site impossible rather than guarded against.
- **1.8 grades over the executor's recovery path.** `_try_accept_patch` is now the largest
  method in `adapters/cycles/dispatched_flow_executor.py` — 511 lines at `:3245`, in a file
  of 4,933 (4,349 when #1152 was filed). The last two lines built the fault diagnostics that
  exercise exactly that path; this is the line where an extraction under those diagnostics
  costs least and proves most.
- **The close criteria are the 1.7.0 plan's §6.2, unchanged**, and one of them — CI green
  "against the locked deps the images install" — has a deliverable in this line (#637) that
  no prior line took.

**What it does not do, stated here rather than implied.** It does not change the loop
(1.7.2's and 1.7.4's), the boundaries (1.7.3's) or the reasoning budget (1.7.0's), except
for the four 1.7.4 findings in §3.2 and the fill-mode declaration. It does not adopt Atlas
(SIP-0106 §1.2a stands on its own measurements). It does not build the in-cycle image build,
the stack-rendered packaging, or any 1.8-lane item (§6). It does not promote a SIP on the
strength of its own work except by amendment (§3.7).

---

## 3. The content

### 3.1 Preconditions — before the first code PR

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

**The design gate.** A composition-roots standard under `docs/architecture/` — the same shape
`api-route-lanes.md` set for #218: a document plus one enforcing test. It is reviewed by the
owner **before** the first stratum-B PR (§3.3). It must answer, with a decision for each:

1. which modules are composition roots — the allowlist at
   `tests/unit/architecture/test_forbidden_imports.py:156` already names them (the runtime
   API's wiring, the agent entrypoint, the sandbox, the bootstrap package); the note adopts
   that list as the definition rather than writing a second one;
2. the rule: **a root constructs an adapter only through its adapter package's factory; a
   factory takes config and a required selector; a root never imports a concrete adapter
   class** — #1157's precedent for the LLM, applied to the queue and the A2A client; the
   `comms.provider` selector is already required by the factory and becomes required at both
   roots (the owner's require-don't-default ruling, 2026-08-28);
3. an A2A factory of the same shape — one entry, a required selector — because the seam's
   consistency is the point, not the number of implementations behind it today;
4. #286's shape: an app factory (`create_app(config)`), with the runtime image's command
   moving to uvicorn's `--factory` form (`src/squadops/api/runtime/Dockerfile:64`;
   `docker-compose.yml` untouched — it names the image, not the module), so that a bare
   import of the module performs no config load and no secret resolution; the
   `_import_fastapi_app()` workaround in `tests/unit/cli/test_integration.py` is deleted, not
   kept;
5. the enforcing test, a composition-roots guard beside the existing ones in `tests/unit/architecture/`: every root
   imports with no environment; no root imports a class from `adapters.<vendor>`; every
   adapter a root binds to a port came from an `adapters.*.factory` function — proven by
   AST, the way the forbidden-imports guard already works;
6. **#1152's extraction map**: the methods that move, the modules they move to, the order,
   and the stop rule — recovery path first (`_try_accept_patch` at `:3245`,
   `_handle_task_outcome` at `:2950`), `_execute_sequential` (`:1565`) second; `execute_cycle`
   and `execute_run` are named as *not* in this line's map.

**#1149's harvest, first.** The rationale in the paths the map moves is harvested into
`docs/architecture/defended-bespoke-decisions.md` — an existing home for exactly this kind of
content, so no new register is invented while the Design Decision Register SIP is still
proposed — and each extraction PR cites the entries it moved. The harvest is a precondition of
the first extraction PR, not of the line.

**#906 lands.** The Next.js baseline stylesheet has been "post-window" through three lines.
It touches `stack_nextjs_ts.py` and a request template, so the #1438 drift guard refuses a
counted roll after it merges until a rebuild — which is why it lands in §3.2's stratum, before
deploy A, where the checkpoint pair reads it. If it is not ready by then it is closed or
re-placed by name, not carried a fourth time.

**One owner-only action, outstanding since 2026-08-30 and not an issue:** the nightly database
backup timer (`scripts/dev/ops/install_backup_timer.sh`, needs sudo) is still not installed;
the only dumps are the ones deploys take. It is named here so the line's first deploy does not
run on a box whose registry has no scheduled backup.

### 3.2 The verdict-surface stratum — before the refactor, behind a checkpoint pair

Eight items that change what a record reads, what a roll rejects on, or what an evidence
line says. They are **not** CI-only in the 1.7.0 plan §3.1 sense, so they cannot ride beside
the refactor: a red on the shakeout loop must be attributable to one thing. They land first,
one PR each, and deploy A's checkpoint pair banks them. In merge order:

| step | item | what lands | prediction or readout |
|---|---|---|---|
| 1 | **#1436** | the attempt is stamped where a failed emission's artifacts are banked (the #971 seam), so the record reports emissions and artifacts as separate, both true | instrument — the L1 count's producer; the driver's grouping key moves to it and is re-checked on the pair |
| 2 | **#1197** | the sandbox environment image retagged for what it is (Python 3.12, Node 20, npm 10, serving both stacks); `environment.py:97, :141` and `build_sandbox_env_image.sh:10` agree; the old tag retired | texture: the boot-audit evidence line carries the new name; the contract hash changes on both stacks **here**, where a change is expected, never mid-set |
| 3 | **#906** | the Next.js baseline stylesheet | read on the pair's Next.js half: boot audit and UI reach unchanged |
| 4 | **#1428** | the run-level roll-up owes only the checks its run's task types can subject — `framework_rows_owed()`'s rule (1.7.4 pack row 2) applied at the run level; `frontend_build` stays stack-conditional | texture: no framing run reports `blocked_unverified`; a genuine harness failure on a framing run is visible again |
| 5 | **#820** | `PROOF_INTERFACE_COHERENT` in `cycles/manifest_gates.py` beside the existing proofs (`:35–48`): path-parameter naming consistent across endpoints, declared testids correspond to what endpoints and views promise — string coherence over the manifest's own declarations, no PRD semantics, no LLM. **Reporting-only** | texture: findings per roll by class; promotion to a gate is a later deliberate call on the count |
| 6 | **#668** (second half) | a check that a suite's `apiFetch` mock honours the frozen client surface — behind the stack seam (the client is stack #1's), validated on the 34 stored `../api`-mocking suites as its replay set and on the fay-14 suite it must flag. **Reporting-only** | texture: findings per roll; the replay set's result in the PR's Evidence |
| 7 | **#1406** (framework half) | **the untouched-file rule**: an environment skip (`missing_tooling`) on a criterion whose named file the patch did not touch does not erase that criterion's earlier executed-and-passed row — the patch's file set is already known per repair (#1323/#1350). Credit-restoring only; the seam table (emission / agent-side repair / verifier / gate / retest) in the PR | **prediction — the untouched-file rule:** no counted roll has a criterion demoted by an environment skip on a file its patch did not touch; read from #1407's readout (adverse criteria by name beside the skips that caused them); falsified by one. The record computes every coverage figure under this rule and says so |
| 8 | **#1434** | the fill-mode declaration for `qa.test` and `qa.test_repair` moves from `NONE` to `LOW` in `REASONING_BY_OUTPUT_SHAPE` (`reasoning_policy.py:112`); the mechanism (#1285) stays | **prediction — the fill declaration:** zero contentless fill-mode first attempts across the counted set; read from the emission-shape lines and the #1436 stamp; falsified by one. The fill-mode qa token cost is re-read beside it (Q1 under the new level) |

**Why `LOW` and not a revert.** The port's own vocabulary (`src/squadops/llm/models.py:10`)
defines `NONE` as "the level for a transcription — an output the prompt already contains". A
fill is not a transcription: the model reads a scaffold and writes bodies. `NONE` was a
category error on the policy's own definition, and the line measured its cost: #1268 read
`think:false` at one usable emission in six on the authoring shape; the 1.7.4 line read it at
three clean in five on the fill shape, with the two failures costing two and five correction
rounds. `LOW` is the honest declaration — minimal reasoning for a shaped output — and on
Ollama's boolean wire it maps to `think:true` (`adapters/llm/ollama.py:139, :225`), #1268's
six-in-six. The token saving #924 measured is given up on this provider and kept as a
declaration a provider with an effort dial can honour. **The owner overrules** (§8, decision 2).

**Two predictions, both in this stratum, both readable from fields the 1.7.4 line already
built.** Nothing in §3.3 or §3.4 adds a third; that is the 1.7.3 argument again — a red on
deploy B is the refactor's because the stratum was banked on deploy A.

### 3.3 Composition Root — the design gate, then the code

After the design note is reviewed (§3.1). One PR each, in this order, because #637's import
smoke needs #286's bare import and the extraction needs the rationale harvested.

| step | item | what lands | how CI proves it |
|---|---|---|---|
| 1 | **#286** | the app factory; the module-level `load_config` at `main.py:57` gone; the Dockerfile CMD in `--factory` form; the test-side import workaround deleted | `python -c "import squadops.api.runtime.main"` with no environment succeeds, as a test; the composition-roots guard |
| 2 | **#301** | the queue half at **both** roots (`main.py:310`, `entrypoint.py:453`) through `get_queue_adapter`; the A2A client through a factory of the same shape; `comms.provider` required at both roots; no `adapters.<vendor>` class import left in either root | the composition-roots guard: factories are the only constructors reachable from a root; the #154 allowlist test unchanged |
| 3 | **#637** | a CI job that installs `requirements/api.lock` and `requirements/agent.lock` into fresh venvs and imports both composition roots — the registration-time DOA class #636 found. It also closes the live exposure the 1.7.4 audit named: `console/app/requirements.txt:1` pins `fastapi>=0.104.0,<1.0.0` and `console/Dockerfile:58` installs it with no `-c`, so a fresh console build resolves past the `<0.136` cap `tests/requirements.txt:37` holds for #198 | the job, red on a root that fails to import under the locks; it is the deliverable for the 1.7.0 plan §6.2 criterion 3 |
| 4 | **#1152** | the extraction, in the design note's map: the recovery path first (`_try_accept_patch`, `_handle_task_outcome`), `_execute_sequential` second; **extraction only, no behaviour change rides an extraction PR**; each PR cites the #1149 entries it moved | byte-identical on the context-assembly, correction-context and plan-context goldens (`tests/unit/cycles/test_*_golden.py`) and on the `tests/fixtures/roll_replays` corpus before and after; then the six diagnostics on the pinned deploy (§4) — the seams the moved code owns |

**The stop rule for #1152.** The map is the scope. If the shakeout budget (§4) is spent
before the map is complete, what remains is re-placed by name into the 1.8 plan's rider with
the map attached, and §3.6's count is incremented — never a silent carry, never a partial
extraction left on main without its guard.

### 3.4 The list — CI-verified, riding beside the refactor

One PR per item; each PR's Evidence names the structural test or guard that proves it. Ordered
so the close-criterion items land first and the widest-blast item last (§5's drop order is
this order reversed).

| step | item | what lands | how CI proves it |
|---|---|---|---|
| 1 | **#929 with #1206** | the LLM call sequence (budget → prompt guard → call → content → duration → generation record) extracted onto `_CycleTaskHandler` as one method; the eight dark sites (`analyze_failure.py` ×2, `correction_decision.py` ×2, `define_done.py` ×2, `_plan_authoring.py`, `planning/review.py`) and the two unrecorded self-eval second calls (`develop.py`, `qa_test.py`) record through it; designed together, as the 1.7.1 plan §2.4 required | `test_every_llm_seam_captures_what_it_emitted` **inverts** to "no handler calls the port directly"; a generation-record twin of it counts records against calls per file and fails on a gap. Live: the shakeout pair's LangFuse generation count equals its LLM-call count (1.7.4's pair read 26 of 35) |
| 2 | **#198** | the console router include graph flattened so a router is mounted once; `console/app/requirements.txt` constrained to the lock set; the `<0.136` cap lifted | `tests/unit/console/` green on the current lock's fastapi (`0.135.4`) and on the first release past `0.136`, in the #637 job |
| 3 | **#580** | the session-scoped `event_loop` override (`tests/conftest.py:39`) and the duplicate marker registrations (`:54–60`) retired; pyproject is the one marker registry | the whole regression suite, not the affected subset — the loop-scope change can surface cross-test loop assumptions |
| 4 | **#1182** | an architecture test asserting no file under `tests/` names the deployment database in a connection string — broader than `*.py` (the `.env` and `.md` literals #1099 found outranked the corrected default), matching the database *name* not one URL | the test itself, beside the existing guards in `tests/unit/architecture/` |
| 5 | **#1180** | a `squadops_test` role whose grants make the deployment database unreachable (`REVOKE CONNECT … FROM PUBLIC` is the hole), created by the bootstrap path and the compose Postgres init so a fresh environment has it without a manual step; a `doctor` check that verifies the **negative** — the test role cannot connect to the deployment database; the #1099 guard stays as defence in depth. **The compose init edit needs the owner's explicit OK, recorded on the PR** (CLAUDE.md "Docker") | the doctor check; an integration test that asserts the permission error |
| 6 | **#1178** | OOM containment in the `local-spark` bootstrap profile — `earlyoom` at a conservative threshold as the first choice (it keys on available memory, which is the thrash the box saw; `systemd-oomd` keys on PSI and cannot see a unified-memory GPU allocation), `MemoryMax=` on the serving unit as the bound, and a `doctor local-spark` check | the profile schema; the doctor check; **applied to the box as a live read (§3.5)** |
| 7 | **#353** | the fragment manifest's 32 committed `sha256` values move from source to the build: `manifest.yaml` becomes a pure registry, `build_agent.py` stamps the fingerprint into the artifact, the #351 runtime check verifies the *shipped* copy against its *shipped* fingerprint, and the regen tool and CI hash guard retire. **A SIP-0084 post-acceptance amendment first** — it is a governance change to where a prompt's integrity is asserted | the amendment merged before the code; the agent build; the runtime check's test |
| 8 | **#579** | one `parse_frontmatter()` under `src/squadops/prompts/`. **Premise re-verified for this plan, as the post-1.5 reconciliation asked:** five sites remain — `prompts/renderer.py:53`, `adapters/prompts/filesystem_asset_adapter.py:86, :113`, `adapters/prompts/filesystem.py:209`, and `wrapup_tasks.py:145` behind its own `_parse_frontmatter` at `:134` — four inline, one helper; not "five byte-identical copies". The PR states the count it found | parity tests ported from every site; the #327 hash-integrity paths provably untouched |
| 9 | **#176** | the framework smoke integration test: the pipeline invariants (create → dispatch → framing → gate → handoff → correction → persistence) asserted over a cycle's artifacts and run state, runnable on the `smoke` squad, **explicitly decoupled from terminal `completed`** on content-gated paths | a `pytest` smoke marker against a small-model squad, in the integration lane; a run that fails a content gate still passes the invariants |
| 10 | **#567** | the fenced parser's recognition layer on a CommonMark-spec engine under the existing mapping strategies (`fenced_parser.py`, 533 lines); the security guards unchanged at the mapping layer | **every existing parser test and every replay fixture passes unchanged; the refactor may only add recovered files on the stored corpus, never lose or remap one.** Its subject is the emission path every roll runs through, which is why it is last and the first to drop (§5); if it lands, the driver's per-roll fence counts are its texture |

**Sixteen items in twelve PRs, one above the 1.7.0 plan §3.1 ceiling of 10–15 CI-verified
per line, plus the executor extraction, which is several.** Stated rather than described as
"at" the ceiling. §5 says what drops and where it goes.

### 3.5 The ops rider — live reads, not CI

| item | what | read where |
|---|---|---|
| **#1177** | the Atlas A/B replay scripts routed through `arm.sh` so the rig cannot put both arms in the Spark's unified memory; the host reserve restored. Its scripts live in `~/atlas/scripts`, outside the repo | on the box, after the counted set (§7 step 12); a stated precondition of #1408 |
| **#1178** (applied) | the containment §3.4 lands, applied to the box | `squadops doctor local-spark` on the box; named in the record |
| **#300** (carried reading) | the 1.7.4 record §7 read the advisory-lock key loaded and the acquisition path unexercised (no migration ran) | stays "loaded, not exercised" unless a migration lands in this line; the record says which |

### 3.6 The count this line owes the record

The 1.7.2 plan §3 started this table so a plan scheduling an item for the fifth time says
so. Counted from the plans' own placement sections; the 1.5-era items enter at the 1.5 plan's
capacity roll, where the post-1.5 reconciliation classified them.

| item | release plans that scheduled it | times, incl. this plan |
|---|---|---|
| #301, #286 | 1.5.0 (capacity roll), 1.7.0 (§2.5, the row then called 1.7.4), 1.7.3 §6, 1.7.4 §6, 1.7.5 | **5** each |
| #567, #579 | 1.5.0, 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **5** each |
| #820, #376 | 1.6.0 (deferred by name), 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **5** each — #376 closes as verified, not as built |
| #929 (+#1206) | 1.7.0 (rider), 1.7.1 §2.4, 1.7.3 §6, 1.7.4 §6, 1.7.5 | **5** |
| #353 | 1.7.0, 1.7.2, 1.7.3, 1.7.4 (not landed, pre-registration §9), 1.7.5 | **5** |
| #198, #176, #580 | 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **4** each |
| #1152, #1149 | 1.7.0, 1.7.3, 1.7.4, 1.7.5 | **4** each |
| #637, #598, #668 | 1.7.1, (lost), 1.7.4 §6a, 1.7.5 | **3** each — #598 re-placed by recommendation (§8) |
| #1180, #1182, #1197 | 1.7.3 §6, 1.7.4 §6, 1.7.5 | **3** each |
| #1177, #1178 | 1.7.3 §6 (parked), 1.7.4 §6a, 1.7.5 | **3** each |
| #1406, #1428, #1434, #1436 | 1.7.4 (§6a or the record), 1.7.5 | **2** each |

Five items are on their fifth plan. As the 1.7.4 plan said of its rider, that is governance
evidence and not a technical reason: repeated deferral raises the requirement to dispose of
each item by explicit decision, and it does not override experiment isolation — which is why
the verdict stratum sits in front of the refactor rather than beside it.

### 3.7 The cut criterion — the 1.7.0 plan §6.2, criterion by criterion, plus the three gates

The line closes when the 1.7.0 plan §6.2 holds. Each criterion has a deliverable in this
plan; the record reads them one at a time:

| §6.2 criterion | this line's deliverable |
|---|---|
| 1. Composition Root fully landed; Hardening's remainder re-placed by name | §3.3 complete to the design note's map, or the remainder re-placed with the map attached (§3.3's stop rule); §5's drops named |
| 2. Both counting sets closed with no falsified prediction; the record from per-round evidence | §4 — the two predictions hold; L1 holds; the record cites per-round artifacts |
| 3. CI green on main including `integration`, on Python 3.12, **against the locked deps the images install** | `integration` is already required (1.7.4 §3.1); #637 is the deliverable that makes the last clause true for the composition roots |
| 4. Zero drift between the measured deploy and the tag; the package captured on the first try with the `Closes` column correct | §7 step 14; the preview read before `--write` (the 1.7.4 lesson) |
| 5. SIP promotion sweep | SIP-0104 stays `accepted` (#1122 does not ship); SIP-0084 gains the #353 amendment; SIP-0102's open steps 3–7 named as staying `accepted`; nothing else moves |

And the three gates 1.7.4 kept apart, so "landed" never stands in for "proven":

| gate | criterion |
|---|---|
| **implementation** | every §3.2 and §3.3 row merged; §3.4's rows merged or dropped by a plan revision that names the destination (§5); the design note merged before the first §3.3 PR |
| **experimental** | **L1 holds**; the two predictions hold; **every one of the six diagnostics reached its seam on the pinned deploy** — no amendment; a "not reached" after the two-run budget is a refactor finding that stops the set |
| **evidence** | every field §4 names is populated on every counted record, with its unaskable state declared; the record reconstructs every counted/void/reset boundary from per-round evidence; deploy-to-tag drift named item by item, expected zero |

### 3.8 Merge discipline

One PR per row; `--head` on every PR; every job of main's run read after every merge; the
seam table in every PR that binds, removes or re-weights a check (#1406, #668, #820); the
mirror rule on every removal (#286's workaround, #353's regen tool, #580's fixtures); the
composition-roots guard in the same PR as the first root it constrains; **no merge to main
while a set is open**; the compose init edit (#1180) on the owner's recorded OK. The plan's
own PR carries the 1.7.0 plan §7 amendment pointing here.

---

## 4. The verification set — a regression check on the loop, with two predictions in front

Two counting sets on one frozen deploy, **6 + 3** — the fourth consecutive set at that size,
for comparability across 1.7.2, 1.7.3 and 1.7.4 on one PRD and two stacks.

**Bar.** **L1** (#1268), as amended before the 1.7.4 set opened: blocking on a counted roll
whose contentless emission is *not recovered*; the occurrence count tracked and never quoted
as zero. It stays the bar because it is the condition every other reading is measured
through, and because this line changes the declaration that produced its only breach. **H1 is
retired as a bar**: it holds by construction since #1430 and the 1.7.4 record said so; its
content — every required file the roll's own rows declared — stays as a texture field **with
its unaskable state declared** (the framework row is filtered at `validation.py:252` on a
clean roll, so the driver reads the run report's executed/passed counts, or the field says
"unasked").

**Live hypotheses — two, both from §3.2:**

| claim | method | falsified by |
|---|---|---|
| **the fill declaration** (#1434): zero contentless fill-mode first attempts | every Next.js roll; emission-shape lines and the #1436 stamp | one contentless fill-mode first attempt |
| **the untouched-file rule** (#1406): no criterion demoted by an environment skip on a file its patch did not touch | every roll with a correction round; #1407's readout | one demoted criterion of that shape |

**Seam invariants — proven on the pinned deploy this time.** The six diagnostic configs are
re-registered under a `1.7.5/` prefix and run on the pinned deploy with a two-run budget
each: absent-suite (the retest seam, L2), own-frame-then-prose-repair (L7, L4, L5),
path-prefix (L8b; L8a read as the count on every roll), contentless-builder (the retry with
its fact, R1), absent-suite-then-false-claim (the analyzer's refuted claim reaching the
decision, A1), and the rewind invariant (W1) as CI-only by declaration, unchanged. **The
extraction is what these exercise.** A seam not reached after two runs is a refactor finding
and stops the set; it is not declared and carried, as 1.7.4's two-run rule allowed for seams
the pack had not touched. The locus invariant (D1) and the derived-rows invariant (F1) stay CI
invariants and are read live as texture.

**Texture — observed, never blocking, every field with a producer and an unaskable state
before roll 1:** the framing run's verdict (#1428); packaging findings per roll by class
(unchanged rate expected; the #598 decision reads it); emissions versus banked artifacts
(#1436, now exact); fill-mode qa completion tokens under `LOW` (Q1 re-read); interface-
coherence findings (#820) and mock-surface findings (#668) per roll; the boot-audit image name
(#1197); fence counts and placeholder strips per roll (L8a, and #567's texture if it lands);
generation records per LLM call on the shakeout pair (#1206, a LangFuse read); the required
files the rows declared (H1's content); correction rounds; verdict rate against 1.7.4's.

**Shakeout loop** (`docs/plans/verification-sets/README.md`): deploy A gets **one checkpoint
pair** (a red is the verdict stratum's); deploy B enters the loop — exit on a pair with no
new seam finding, **budget three pairs**; the record reports rounds taken and rounds
attributable to the refactor. This line expects the second number to be non-zero: an
extraction of this width has regressions the goldens do not reach, and the pair is where they
are found.

**Early stop, one direction.** A falsified prediction or an unreached seam stops the set; a
good result never stops it early; a stop in one arm does not stop the other.

**Drift the record must declare:** intended zero — the tag is the measured deploy plus the
pre-registration and the record.

---

## 5. Capacity — what drops, in what order, to where

The line is one CI item over the ceiling and carries a multi-PR extraction. If capacity
forces a drop, it comes from §3.4 **in reverse order** — #567 first, then #176, #579, #353,
#1178 — and the destination is **the 1.8 plan's hardening rider, by name, with §3.6's count
incremented**, recorded as a revision of this plan in the open. #1152's remainder drops by
its own stop rule (§3.3). Nothing in §3.2 or the first three rows of §3.3 drops: they are the
line's subject and its close criteria.

---

## 6. Re-placements by name — nothing silently carried

Forty-four open issues on the morning of writing. Twenty-nine are in this line (§3.1–§3.5).
The fifteen that are not:

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

**The 1.8 lane — Scoped Code Revision** (PR #1325; subsumes #1213; #1176 beside it): the
design review **opens with this plan's PR** (§7 step 2) — a named reviewer step with a
written outcome, because "opens beside this line" produced zero reviews across 1.7.4. Its
evidence list is the 1.7.4 plan §6's, plus this line's extraction of `_try_accept_patch`,
which is the seam a scoped revision would land through. #1122 stays with SIP-0104.

**Still at design review, unchanged:** #414 (severity-aware correction reserve), #557
(post-retest governance review), #316 (request-profile taxonomy, moves with Campaign); and in
the 1.8 lane #80, #950, #949, #194, #1039, #1031.

**Spark host and Atlas, in the idle-box slot (§7 step 6):** #1408 (the Flash-Next
plan-authoring replay — needs the box to itself, 94.87 GiB against a 121 GiB box) and #1412
(the content-loop diagnosis session). Neither touches the deploy; both need no cycle in
flight. **Nothing goes to the vendor without the owner's explicit go-ahead** (#1412's own
rule).

**SIPs that stay `accepted`, named so the sweep does not read silence as shipped:** SIP-0101
(replay harness; the minimum slice landed in 1.5), SIP-0102 (steps 3–7 — feature-shaped),
SIP-0104 (#1122), SIP-0105 (the blueprint rewrite after #1131), SIP-0088/0090/0091/0092/0093
(the runtime-modes cluster, 1.6-era targets, untouched by 1.7 and re-read at the 1.8 plan).

---

## 7. Sequencing

1. **This plan**, on its own PR, with the 1.7.0 plan §7 amendment (the 1.7.5 row placed here;
   #376's label corrected). Merges on the owner's review.
2. **The Scoped Code Revision design review opens** (PR #1325) as a named step: a reviewer, a
   written outcome on the PR, before 1.8's plan is written. It gates nothing here.
3. **Verify-then-close** the five §3.1 issues, evidence cited on each; the #352 test located or
   its gap filed.
4. **The composition-roots design note** (§3.1), reviewed by the owner — the design gate. In
   parallel, **the verdict-surface stratum** (§3.2), one PR each, #1436 first and #1434 last.
   #1149's harvest for the extraction map.
5. **Deploy A; one checkpoint pair** — a red is the stratum's; every driver field re-checked on
   the pair's records (the #1436 stamp moves the L1 grouping key; #1197 moves the contract
   hash), each with its unaskable state stated.
6. **The idle-box slot.** While §3.3 and §3.4 are written and reviewed, the box has no cycle in
   flight: #1408's plan-authoring replay and #1412's diagnosis session run here, on the same
   harness and gate as #1184's measurement. They leave nothing in the deploy.
7. **Composition Root** (§3.3) in order — #286, #301, #637, then the extraction PRs — and **the
   list** (§3.4) in order, riding beside it, #567 last.
8. **Deploy B; the shakeout loop** to the exit rule, budget three pairs; a red is the
   refactor's.
9. **The six diagnostics on the pinned deploy**, two-run budget each, recorded with the entry
   point each used. A seam not reached stops the line here, before the set opens.
10. **Pre-register** (`1-7-5-<arm>.yaml`, pins from the last shakeout; every field's producer
    and unaskable state checked against a real record).
11. **Counted set 6 + 3** — no merges to main while a set is open; the counted/void/reset
    reading at each boundary.
12. **Close the set; the live reads** — #1177 on the box, #1178's doctor check on the box,
    #300's reading carried or exercised — named in the record as read live.
13. **The preliminary measurement conclusion**: §3.7's five close criteria and three gates,
    read against the frozen deploy before anything else moves.
14. **Final record; cut 1.7.5 by the seven steps** — the release-package preview read and its
    verdicts checked against the records before `--write`; the SIP sweep as §3.7 states it;
    zero drift named. **The 1.7 line closes.** Then the 1.8 plan, opening with a reviewed
    Scoped Code Revision design and the re-placed items §5 named, if any.

The key property of this order: the two things that can move a verdict — the stratum and the
refactor — are on different deploys with a checkpoint pair between them, and the diagnostics
that prove the refactor's seams run on the deploy the numbers come from.

---

## 8. Decisions made by recommendation — the owner overrules, not fills in

1. **#598's promotion to blocking is not taken in this line; the packaging becomes a
   rendering in the 1.8 lane** (§6). The evidence is the failure rate on three sets and the
   two accepted SIPs that already say Dockerfiles are renderings. **Fallback if the owner holds
   the 1.7.4 §6a placement:** it lands as step 0 of §3.2 with the finding routed to the
   builder as a *repair* (a required check with a correction path, not a straight rejection),
   a registered prediction ("a packaging finding on the accepted emission is repaired within
   the correction budget"), and a declared non-refactor rejection cause; the record then says
   Functional App Yield's meaning changed on this line, since it would include packaging for
   the first time.
2. **The fill-mode declaration moves to `LOW`, not back to the task default and not to a
   third wire.** `NONE` is defined for transcription and a fill is not one; `LOW` is
   `think:true` on this provider and stays honest on one with an effort dial. Omitting the
   `think` key — the third wire #1268 measured — is a provider default, which the policy's
   own rule ("a level, never a provider's switch") forbids declaring.
3. **#1406 lands as the untouched-file rule** (its option 2), credit-restoring only, before
   the set; the record computes every coverage figure under it and says so. Option 1 (route
   the re-evaluation where tooling exists) is the wider change and touches the verifier's
   environment axis mid-line.
4. **#820 and #668's second half land reporting-only**, with their replay sets as
   validation; promotion is a separate deliberate call on the counts the set produces — the
   rule that kept #598's first half reporting-only in 1.7.1.
5. **#1152 is scoped by a map with a stop rule**, recovery path first, `execute_cycle` and
   `execute_run` out of this line's map by name.
6. **#567 is last in the list and the first to drop**, because its subject is the emission
   path; its acceptance bar is the corpus, unchanged.
7. **#376 closes as verified**, and the 1.7.0 plan §2.7 mislabel is corrected in this PR's
   amendment rather than left as two documents disagreeing.
8. **#906 lands in the verdict stratum** or is closed by name; not carried a fourth time.
9. **#353 is a SIP-0084 amendment before it is code.**
10. **The set is 6 + 3, L1 the bar, two predictions, six diagnostics on the pinned deploy with
    no amendment**, and every field carries its unaskable state.
11. **The Scoped Code Revision review is a named step with a written outcome** (§7 step 2).
12. **#1408 and #1412 run in the idle-box slot** between the checkpoint pair and deploy B,
    not after the counted set — the box is idle then, and nothing they do enters the deploy.
13. **The composition-roots design note answers the six questions in §3.1**, including the
    `--factory` form for #286 and an A2A factory of the same shape as the LLM's, with
    `comms.provider` required at both roots.
14. **The line carries sixteen CI items and says so**, one over the ceiling, with §5's drop
    order and destination fixed now so a drop is a revision and never a carry.

---

## 9. Findings from the review that produced this plan

Named here so they are not the next §6a. None blocks the plan; each has a home above.

- Three rider issues are open with merged PRs (#330, #372, #352) and #157 is open though
  declared closed — §3.1. The 1.7.4 line's own memory and its plan §6 both read them as closed.
- The 1.7.0 plan §2.7 labels #376 as SIP-0102 steps 3–7; it is SIP-0096 Phase 2 evidence —
  corrected in this PR's amendment.
- #579's premise ("five byte-identical copies") no longer matches the tree — §3.4 row 8 states
  the count found.
- The executor grew from 4,349 to 4,933 lines since #1152 was filed; `_try_accept_patch` is
  now its largest method — §2, §3.3.
- The Scoped Code Revision design review never opened — §7 step 2.
- The ROADMAP's Stats header still reads "As of 2026-09-07 (v1.7.3)" beside a 1.7.4 framework
  version: the cut's step 4 (the timeline entry) was done and the Stats header was not.
  Cosmetic; fixed with the next ROADMAP edit this line makes, not in this PR.
- The nightly backup timer is still not installed — §3.1, owner-only.

---

## 10. Revision history

- **Rev 1 (2026-09-09)** — written the morning the 1.7.4 line closed, on the owner's ask, from
  the 1.7.4 plan, pre-registration and record, the 1.7.3 plan §6/§8, the 1.7.0 plan §2.5/§3.1/
  §6.2 and the tracker (44 open issues, every one placed by name). Structure: a verdict-surface
  stratum of eight (the four 1.7.4 findings, the sandbox retag, two reporting-only checks, the
  Next.js stylesheet) behind a checkpoint pair, then Composition Root behind its design gate
  with the executor extraction under the six diagnostics, then a sixteen-item CI list one
  above the ceiling with its drop order fixed. Two predictions (the fill declaration, the
  untouched-file rule); L1 the bar; H1 retired as a bar; the diagnostics on the pinned deploy
  with no amendment. Fourteen decisions by recommendation, the first of which (#598's
  promotion re-placed to the 1.8 lane as stack-rendered packaging) reverses a 1.7.4 §6a
  placement and is stated with its fallback.
