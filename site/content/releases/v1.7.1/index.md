---
title: v1.7.1
---

# v1.7.1

**Released 2026-09-03** · [tag `v1.7.1`](https://github.com/backspring-labs/squad-ops/releases/tag/v1.7.1)

**Stack Seams — the first patch line of 1.7.** Plan: `docs/plans/1-7-1-plan.md`. Record:
`docs/plans/1-7-1-verification-set-record.md`.

Validated by a pre-registered two-set verification run on frozen deploy `f85de47a` (HEAD
pinned at `8b58061c`), **zero code drift between the deploy and the tag** — the tag adds only
the pre-registration and the record: **FastAPI+React 3 of 5** (rolls 1, 3 and 4 accepted, roll
2 blocked, roll 5 rejected, the sixth withheld by the early-stop rule when R2 falsified on roll
4) and **Next.js+TS 0 of 2**. The delivered app passed the boot audit on **all seven** rolls.
Rule B evaluated every one of the eleven repairs in the producing role's container; the kind
gate (#1153) refused three contradicting repairs on Next.js roll 2; additive containment
(#1022) rejected a suite that invoked nothing; no undefined name reached execution (#939).

**What the rolls do not validate, said here rather than implied.** R2 (#1130) is falsified on
the JavaScript own-frame shape — the detector is pytest-shaped (#1270). The Next.js arm
validated the gates, not delivery: the qa role's first-attempt emission was a sentence of
intent and nothing else on nine of eleven attempts there and five times on React — **new since
the 1.7.0 tree (first seen 2026-08-31; zero in 1.6.6's eight rolls), not introduced by this
pack, mechanism unread, and the top of 1.7.2 (#1268)**. Every other non-green is a
pre-existing recovery-path seam that a contentless emission reached for the first time: the
retest skipped when the failed result carries no `test_result` (#1269), a re-dispatched task's
passing rows never recorded (#1271), the refund path re-briefed from the empty emission with
prose counted as content (#1273); plus the fence-template placeholder copied literally (#1272).
One process deviation is recorded (record §3.3). Carried, not built: #1251, #1254, #1260,
#1087/#1112. It took six shakeout deploys to reach the counted set; the exit rule (a pair with
no new seam finding) was met on the sixth.

**The 1.7.1 line — Stack Seams** (`docs/plans/1-7-1-plan.md`). Owner's ruling on the
check-environment seam, 2026-09-01: **B** — typed checks execute in the producing role's
agent container, at emission and at repair, and each image provisions its toolchain as data.

### Changed — what the 1.7.1 shakeouts taught, written where it outlives the line
- Four deploys, each shakeout pair finding the next seam defect, three of them latent in
  the pack's own PRs: the tests had handed each seam its input and never entered where the
  cycle enters. `docs/TEST_QUALITY_STANDARD.md` gains anti-pattern 6a (a seam test that hands
  the seam its input) and a wiring-test row in the minimum coverage; the PR template's
  Evidence asks for the entry point exercised, the evaluation-seam table for a new or newly
  bound typed check, and what a removed thing produced and for whom; `CLAUDE.md` gains the
  typed-check binding rule (#1259), the mirror rule on removal (#1253 → #1255), and the
  shakeout loop's exit rule with the diagnostic and readout rules (#1256, #1261). The
  procedure around the driver — the loop, diagnostics, readouts, detached launches,
  re-attaching a dead driver, cancelling an orphaned run — is
  `docs/plans/verification-sets/README.md`, which the driver's docstring now points at.
### Fixed — the repair evaluates the failed task's criteria on the tree the verifier overlays (#1264)
- The React shakeout on `06408dfe` (`cyc_4ec4ad5e2ca1`) refused a correct route fix twice
  and was rejected: the dev repair of a qa failure evaluated the qa suite's criteria in its
  own container on a tree without the suite — the failed emission is not in the accepted
  workspace and the dev never emits it — so six rows were executed failures about a file
  the patch never touched, and #1259's backstop, keyed on the verifier's overlay (which
  carries the failed task's files), kept them. The repair envelope now carries the failed
  task's own emitted files (`failed_task_artifacts`) and the repair materialises them
  beneath the accepted workspace before its patch — the same tree the verifier overlays,
  which is what rule B promised — and the backstop is keyed on the repair's own artifact
  names. Replayed: the suite's criteria pass on the dev's patch once the suite is in the
  tree; with the overlay carrying the suite and the agent's absent-suite rows, the patch
  passes instead of being refused.

### Fixed — a file the patch never carries is not evidence against the patch (#1259)
- The Next.js shakeout on the final 1.7.1 deploy (`cyc_9c379355b5e8`, round 0) refused a
  correct route fix: the dev repair of a qa failure is judged against the qa task's
  suite-bound checks (`assertion_kinds_match`, `dom_anchor_queries`), the failed suite is
  not in the accepted workspace and the dev never emits it, so both environments returned
  `failed(file_not_found)` and the verifier read an executed failure — "an executed failure
  anywhere rejects". Before #1240/#1246 those criteria all skipped on a `.ts`/`.jsx` suite
  and the retest decided; with #1256 delivering the agent's rows, every dev patch of a qa
  failure on either stack took this path. A `file_not_found` on a file the patch does not
  carry is now `skipped / file_not_in_patch` in both environments; one on a file the patch
  names keeps its rejection power. Replayed: the refused patch → `no_executed_blocking_checks`
  (the retest decides); with the suite in the tree → `passed`. The refused fix's absence let
  the re-authored suite drop the case that found the defect — filed as #1260, 1.7.2.

### Fixed — a TS18xxx type diagnostic no longer turns `undefined_names` off for its file (#1261)
- `tsc_syntax_errors_in` read any code starting with `TS1` as syntax, so `TS18048` ("possibly
  undefined") and `TS18046` ("of type unknown") — type checking, the common shape of a real
  test file — made the check return `skipped / unsupported_stack_or_syntax`: five of nine
  accepted test files on the same shakeout were never checked for undefined names, and R6's
  readout counts failed rows, so a green roll cannot see it. Syntax codes are TS1000–TS1999
  and are classified by value.

### Fixed — rule B's rows reach the verifier (#1256)
- `_try_accept_patch` read `repair_typed_checks` off the FAILED task's result — a key the
  repair handler writes on its own outputs — and the correction protocol returned only the
  repair's files, so the rows a repair evaluated in its own container (#1229, shipped in
  #1238) never reached runtime-api's verifier in a live cycle: the 1.7.1 React shakeout
  `cyc_c6db3ffc1f4e` had the dev container report `rows=10 executed=10
  frontend_compiles:failed` on both repairs of the qa task's failure while runtime-api
  logged `agent_rows=0` and fell through to the retest. The protocol result now carries
  each repair step's rows in step order (a dev step and a qa step each evaluate in their
  own environment), the executor hands them to the verifier, and the verifier reads the
  sequence. Every `decided_by_agent` in the line's records before this was 0.

### Fixed — the handoff's required sections are a typed criterion, so a builder repair can be decided (#1255)
- The 1.7.1 React shakeout on the main-built deploy (`cyc_c6db3ffc1f4e`) rejected the
  builder's first handoff for two missing sections, the round-0 repair carried every one
  of them, and runtime-api discarded it — `unverifiable / no_typed_criteria` — then left
  the task failed under #1221. Once #1252 stripped the plan's handoff regexes, a builder
  task carried no typed criterion at all: the section rule lived only inside the builder
  handler's validation, and `container_packaging` is injected at the handler seam, so the
  verifier held nothing to run. `sections_present` is now bound at plan time onto the
  builder task that owns the handoff, with the build profile's sections as params (never
  authored, #1254's direction); the handler's validation and the evaluator read one rule
  (`capabilities.handoff_sections`, the keyword match the builder has always applied), so
  the emission seam, the repair's own evaluation and runtime-api's verifier agree. The
  verifier's `no_typed_criteria` verdict now carries the rows the repair executed — the
  builder had reported one and the log said `agent_rows=0`. Replayed on both stored
  documents: the first fails naming the two sections, the repair passes.

### Fixed — a plan-authored regex over the handoff's headings no longer fails the builder (#1252)
- The 1.7.1 React shakeout `cyc_8118588858a6` spent two of its three correction rounds on
  the word order of two headings: the plan authored `## .*(Backend|Server|API).*(Run|Start|
  Setup|Launch)` and the builder wrote `## How to Run the Backend (API Server)`, the
  convention its own template dictates. The document had every required section from its
  first version. The handoff's sections are the build profile's fact, already checked by
  name in any order; the planner's regex, phrased fresh each cycle, was brittle duplication
  of that check — the same morning's first shakeout passed only because its plan happened
  to phrase `## How to Run`. Dropped at dispatch with a named log line
  (`handoff_regex_stripped`), beside the inapplicable-check strip; the builder template no
  longer promises to apply it and the plan-authoring rules gain **no-regex-on-the-handoff**.
  Replayed: both shakeouts' stored plans — six and five handoff rows dropped, every other
  criterion untouched.

### Fixed — a qa-owned defect in a free-authored suite is routed to the qa role (#1130)
- **pytest's `-q --tb=short` text is its machine report.** The runner parses it into the
  same per-failure rows vitest's JSON reporter gives — file, title, messages, line — plus
  the exception class and the traceback frames, so a pytest failure now carries which
  tests failed (the #878 identities were vitest-only until here; the correction signature
  on a pytest suite is per-test from this release).
- **The suite's own-frame failures are a fact the runner states** (`suite_defects`): a
  `NameError` in the test module, or an argument-binding `TypeError` at a call into the
  harness — raised before any application code runs, so no app defect can produce them.
  A binding error into a callee the application defines, an `ImportError`, a `KeyError`
  on a response body and every assertion stay ambiguous and route as before.
- **The stack stamps ownership, the classifier routes on it, the router targets the
  file.** `failed_tests_pass_row` stamps each defect with `is_qa_test_path_for_stack`;
  a stamped row is an own-artifact signal beside #629/#988/#1153's; the repair target is
  the defective suite alone, not the task's other suites. Replayed: 1.6.5 roll 3's stored
  report routes to `qa.test_repair` targeting `backend/tests/test_runs.py` (three
  `TestClient.delete(json=…)` rows); 1.6.6 roll 6's report (the app raised at
  `backend/routes.py:24`) stays on the dev chain; a stored collection error and a
  rewritten assert are not defects. The log line carries `qa_owned_routed` for the set's
  R2 readout.
### Fixed — the repair is handed the dispatched envelope, so rule B's workspace reaches it (#1229 live gap)
- The 1.7.1 Next.js shakeout (`cyc_3ac86805439f`) reproduced the shape rule B was built
  to end: a dev repair evaluated its own patch in the dev container — four rows, two
  executed, none failed — and runtime-api still returned `unverifiable /
  no_executed_blocking_checks`. Read from the code, not inferred: the executor's own
  verification reads the accepted workspace from the **enriched** envelope, but handed
  the correction runner the **base** one, so `repair_forwarded_inputs` found no
  `acceptance_workspace_files`, the repair's build check skipped for want of a frontend
  tree, and the one local blocking criterion could not execute in either environment.
  The retest hand-off already passed the enriched envelope; the correction hand-off now
  does too. The unit tests of #1238 exercised an envelope that already carried the key;
  a runner-level test now pins the forwarding and an executor-level test pins which
  envelope is handed over.
- **Instrumented, so the next such diagnosis is a log line, not a code-path reading:**
  the agent-side `repair_typed_checks` line names every row with its status and skip
  reason; the executor's `patch_verification` line carries `agent_rows` and
  `agent_executed`.

### Changed — the qa repair is scoped to the failing cases, and routes on an undeclared anchor (#1123)
- **The repair brief names the cases that failed.** The `tests_pass` row carries the
  runner's structured failures as `failing_cases` (file, title, line, first message —
  bounded), and the qa repair renders them as an authoritative REPAIR SCOPE block through
  a new appendix asset: repair exactly these, keep the passing cases byte-for-byte. Before
  this the repair re-authored the whole file with no list (1.6.6 React roll 6: two failing
  cases of four). When vitest's JSON report was not written, its text is parsed for the
  same rows — the shape every stored report carries, so live and replay read one parser.
- **An assertion on an anchor no view declares is the suite's defect.** Read from the
  suite's own bytes (#668's `unknown_anchors`) and only then matched to the runner's
  failing case (`Unable to find an element by: [data-testid="…"]`), so the verdict alone
  never routes; the repair targets the suite that made the assertion. A declared anchor
  the view failed to render stays the dev chain's. Stated: no stored roll asserts an
  undeclared anchor — the 1.6.5 shakeout's four DOM failures all name declared anchors
  and stay the views' — so this signal has a synthetic exercise and a stored control, not
  a stored red.
- Readouts for the set: `correction_repair_brief` logs the case count a qa repair carries;
  `absent_anchor_routed` marks the routing.

### Added — the DOM anchor contract gets its enforcement layer (#668)
- **`dom_anchor_queries`**, a typed check the planner binds onto every bound qa.test
  frontend suite when the manifest declares view anchors, with the inventory as
  self-contained params: a suite that renders must query at least one declared anchor,
  and a suite that imports a contract view must query some anchor of that view — any of
  them, not the root, because seven of the nine accepted-roll suites that import a view
  never query its root container and every one queries some anchor of it (measured over
  the vault before landing). Each failure names the view and its anchors; a failed row is
  the suite's own defect. Banked beside the verdict: the anchors queried that no view
  declares (`unknown_anchors`, the qa-side signal #1123 routes on) and the count of
  text/role/label queries. Replayed: fay-14's suite (`cyc_42eed09efbec`) breaks both rules
  with 55 text queries and zero anchors; the accepted 1.6.6 React roll-6 suite passes.
- **The frozen client's call surface reaches the suite author** — the owner's 2026-07-31
  addition. The React stack derives one line per export of its frozen `frontend/src/api.js`
  (`apiFetch(path, options = {})`, `ApiError(code, message, status)`) from the template
  bytes; the planner threads them as `frozen_client_surface` beside the anchors, the qa
  authoring and repair prompts render them through a new appendix asset, and the repair
  and retest contracts carry the surface. Next.js declares none (its suites call route
  handlers directly).
- Not in this PR, stated: a check that a suite's mock of the client honours that surface.
  fay-14 stubbed `global.fetch` (legitimate beneath the client) and mocked no client
  export, so its stored suite cannot exercise such a check; 34 stored suites do mock
  `../api`, and that replay set is the next step, named on the issue.

### Added — additive-suite containment is a gate (#1022)
- **`additive_containment`**, a typed check the framework injects on every emitted JS/TS
  suite file (the harness's suite suffixes) on both stacks, at emission and on a repair's
  patch: two rules read off the suite's own bytes against the stack's declaration of what
  invokes the application (`AppInvocation`, #1126) — a fetch of a live server inside the
  in-process harness, and a suite that invokes nothing the stack counts as the application.
  Each failure names the rule and what the stack counts, in words, so the re-emission
  brief carries it; a failed row is the suite's own defect and routes to the qa re-author.
  #1052 shipped the same rules reporting-only; promoted on the evidence of the V7 corpus
  (C3, C4 and slot 3's first repair rejected; the slot-2 and slot-3 greens pass) and the
  accepted rolls' suites of the last two lines on both stacks (all pass). Python suites are contained by
  their own gates and the `.py` gap is declared.
- **A third injection scope, `suite`** — the check lands on the suite file only, never the
  source beside it whose extension it also parses, and carries the scaffold stack as a
  self-contained param (the seam's `stack` argument is the check vocabulary, which Next.js
  does not declare). The handler seam is now one table over the three scopes.
- **`AppInvocation.invocation_description`** — what a stack counts as invoking the
  application, in words, for the finding an author is handed back.

### Added — the emitted container's packaging gets its findings, reporting-only (#598)
- **`container_packaging`**, a typed check the framework injects on every emitted
  container recipe (a file named `Dockerfile`; recipe-scoped, since a recipe has no
  suffix for the extension predicate to see): three static findings over the recipe, the
  build context it copies from and the entry script it runs — `npm ci` with no lockfile
  reachable, a `COPY --from` of `dist-packages` off an official `python:*` image, and
  apt's nginx default site left in place under a `conf.d` server block. pf-38's three
  build/run failures behind an accepted verdict, as findings; pf-39 (identical seeds)
  reproduces two of them and the check tells the two recipes apart. It never builds or
  starts an image — `package_builds` is that criterion and stays declared unbuilt.
- **Reporting-only, by severity.** The spec's `blocking_default` is `warning`, and a new
  predicate `row_is_blocking_failure` is the one reading of "this row failed" for the
  verdict ledger, the correction signature and the failure category — an executed
  warning-row failure is banked on the task's evaluation artifact and never rejects a run,
  enters a chain's identity or opens a correction. Whether it becomes blocking, and whether
  the image is built in-cycle, are the owner's separate calls (plan §6).
- Over the vault before landing: 203 stored recipes, 135 with at least one finding —
  `npm ci` without a lockfile on 121, the nginx default site on 31, `dist-packages` on 2
  (pf-38 and one sibling); 68 clean. Reporting-only means those are readouts, not
  rejections.
### Added — cut steps 5 and 7 get their guards (#1151)
- **Step 7, the release package:** `scripts/dev/check_release_packages.py` checks that every
  semver tag has a captured, non-hollow package under `site/content/releases/<tag>/` — from
  `v1.6.2` on, a non-empty cycle list with at least one row actually captured (a verdict and a
  positive run count; a row of nulls is #1076's shape and fails by name). Runs in CI on every
  push and PR rather than on the tag push, because the package lands after the tag by
  procedure: main goes red the moment a tag is pushed without its package and green again when
  the capture lands. Passes on the current release's real package; fails on a synthetic
  hollow one.
- **Step 5, the SIP sweep:** a `release/*` PR must carry a `SIP sweep:` line in its body
  saying what was promoted or that nothing was and why; `check_pr_closure.sh` enforces it with
  the head ref the closure workflow now passes. The live tag-push exercise remains for the
  1.7.1 cut itself.
### Fixed — a bare `pip install squadops` works (#582)
- **`[project.dependencies]` was empty.** The dependency truth lived only in
  `requirements/*.txt`, so a package installed from its own metadata raised
  `ModuleNotFoundError: pydantic` at first import, and dependabot, pip-audit and any
  downstream `pip install` saw no tree at all. Core now mirrors `requirements/base.txt`'s
  floors plus the console script's own imports (`typer`, `rich`); `api` and `agent` extras
  mirror `requirements/api.txt` and `agent.txt` line for line. The `cli` and `pulse`
  extras, satisfied by core and referenced nowhere, are gone. A guard test holds every
  list to the real imports in both directions — each undeclared import and each declared
  package nothing imports fails CI — and to the requirements files they mirror.
- **The package ships its data.** Prompt fragments, request templates, cycle request
  profiles and manifest schemas are read through `importlib.resources`; a wheel carried
  none of them. `package-data` now includes them; the images were unaffected only because
  they install editable.
- **The console script no longer needs the API framework.** `squadops cycles …` imported
  `CycleCreateRequest` through the routes package, whose `__init__` imports every router
  and so FastAPI and python-multipart. The DTO module moved to `api/cycle_schemas.py`,
  beside `api/schemas.py`; a test imports the CLI with `fastapi` blocked.
- **Audit: `sqlalchemy` and `jinja2` were declared in `requirements/api.txt` and imported by
  nothing** (the ORM backend went in 1.3.0, #234; nothing ever rendered a template). Both
  leave `api.txt` and, with their sole-purpose transitives `greenlet` and `markupsafe`, the
  compiled `api.lock` — the entries pip-compile would drop, removed by hand rather than by
  a full `--upgrade` recompile, which is #1204's territory.
- **A `fresh-venv install` CI job** installs the package from a clean venv with no editable
  install, extras or test harness, then imports it, runs `squadops --help` and checks the
  shipped assets from outside the checkout.
- Found on the way, filed as **#1241**: `adapters/capabilities/aci_executor.py` imports
  `agents.tasks.models`, which does not exist, so `import adapters.capabilities` fails; the
  guard carries it as a documented exception keyed to the issue.

### Changed — what is stack-specific lives behind the stack seam (#1131)
- **Stack #1 has its own module.** The inline `fullstack_fastapi_react` expander (651 lines)
  moved from `scaffold.py` to `stack_fastapi_react.py`, registered through `ScaffoldStack`
  exactly as stack #2 is; the reference contract's frozen digests are unchanged, and every
  FastAPI+React manifest fixture expands byte-for-byte identically (3 manifests, 57 files).
  `base_type_name` — manifest vocabulary the block had carried — lives in the leaf
  `type_tokens.py`. The rationale was harvested first into SIP-0105 (#1149, 23 entries).
- **A structural guard**: no string literal in live code under `capabilities/handlers/` or
  `cycles/` names a stack's layout or toolchain unless the module is a `stack_*` module or
  the line is allowlisted with its reason; a second test fails when an entry stops firing.
  Run against `1b9b93a9` it fires on the `app/api/` literal that discarded a green React
  suite in the 1.6.5 set.
- **One suite-suffix vocabulary** (`JS_SUITE_SUFFIXES`, `AppInvocation.suite_suffixes`) read
  by the self-mocking detector, its inventory, the runner's uncollected-suite check and the
  qa handler; the runner's `.ts`-only copy had never named an ignored `*.test.jsx` on the
  React stack. **The fill brief's store paragraph is the stack's** (`store_brief_lines`):
  moving it found `model_surface_instructions` telling the Next.js developer that
  `backend/store.py` defines its stores — Next.js now declares none and loses a wrong
  instruction.

### Added — `undefined_names` reads `.ts`, `.tsx`, `.js` and `.jsx` (#939)
- The per-file unresolved-name check the Python half gets from pyflakes, on the four
  frontend extensions, from `tsc --noEmit` — run once per materialised tree, its
  `TS2304`/`TS2552` diagnostics filtered to the file. A TypeScript project is checked under
  its own `tsconfig.json`; a tree without one (the React `frontend/`) as an explicit file
  list with `--allowJs --checkJs`, which reports the class in plain JSX (measured).
- `typescript@5.5.3` is provisioned into the dev and qa images as data
  (`agents/instances/<role>/npm-global-packages.txt`, the Node analog of
  `system-packages.txt`), and CI installs the same globals from the same file so the roll
  replays execute there. Where no role declared it — runtime-api, until #1229 — the check
  skips as `missing_tooling` and says so.
- The four declared coverage gaps for the check are gone; the typed-check menu regenerated.
  Replay: the Reasoning line's roll-4 shell (`cyc_58d92ca2b407`, `created` undeclared at
  line 30) is rejected naming the name and the line; the gating roll's shell passes.

### Added — the assertion-kind gate for free-authored suites (#1153)
- **`assertion_kinds_match`**, the free-authored counterpart of #1094's fill kind gate:
  injected on bind-mode qa.test tasks per suite file with the manifest's declared field
  kinds as data (names declared with one kind only), it fails an assertion whose literal
  cannot be the declared kind — `body["removed"] == "Carol"` against `removed: boolean` —
  naming the field, the line and the kind, so the re-emission carries them. Python suites
  are read by AST; React suites by their `expect(…).toBe/toEqual` forms; comparisons to
  names, calls, `None` or negated matchers are out of scope by design. A failed row is the
  suite's own defect for locus routing, like #629's.
- 1.6.6 React roll 3 replayed: the stored suite is rejected at line 167 with `removed:
  boolean` named; the accepted rolls 1 and 5's suites pass under their own manifests.

### Changed — a repair is verified where its checks can run (#1229, rule B)
- **The repair evaluates the failed task's typed criteria on its own patched tree before
  returning** — in the agent container, where the stack's toolchain lives, through the same
  `_evaluate_typed_acceptance` the primaries use and against the same workspace (forwarded
  to the repair presence-keyed, as the retest already did). The rows ride the patch as
  `repair_typed_checks`, with the environment that executed them.
- **The executor's verification consumes them.** It still re-runs what it can here as a
  cross-check; for a criterion this environment cannot execute, the repair's executed row is
  the verdict. An executed failure anywhere rejects; an agent pass never overrides a failure
  that executed here; `no_executed_blocking_checks` fires only when neither environment
  executed a blocking criterion, and #1221's deadlock break stays as the backstop. Records
  say where each row ran (`executed_in`), and the verification names how many criteria
  the agent decided.
- Before this, runtime-api — which has no node — was the only judge, so a dev repair on
  the Next.js stack could never earn a verdict (`cyc_05abfc7c1f00`, three rounds of
  `unverifiable` on one route). And the framework-injected checks (`undefined_names`,
  `declared_imports`, `unterminated_source`) never ran on a repair at all there; they do
  in the agent. Replay: the cycle's first stored patch, under the skeleton it landed in,
  with npm absent here — unverifiable and deadlocked without the repair's rows, decided
  by them with.
- **The declaration has an environment axis.** `CheckSpec.required_tooling` names the
  executables an evaluator shells out to (`frontend_compiles` → npm, `undefined_names` →
  tsc); a role whose handlers evaluate typed checks provisions each as data or declares the
  gap in `DECLARED_TOOLING_GAPS` with its reason — the builder image, which emits no
  frontend source, is the first. A two-sided guard reads the provisioning files the images
  are built from and holds both sides; the typed-check menu renders the table.

### Changed — the SIP registry indexes every SIP, and its audit runs in CI (#1144)
- **`sips/registry.yaml` holds a row for every file under `sips/`**, numbered or not: an
  unnumbered proposal is `sip_number: null` keyed by its `sip_uid` — what `sips/README.md`
  always said a proposal carries, and what the registry omitted for 24 live drafts while
  calling itself the authoritative index (7 rows against 31 published). `cleanup_sip_registry.py
  --index-proposals` writes the rows and stamps the uid into the file; acceptance now updates
  that row in place instead of appending a duplicate; proposals sort after numbered SIPs.
- **The audit is a regression-gate test** (`test_sip_registry_audit.py`): zero critical, zero
  data-quality findings, every file indexed. It had been wired to nothing — no workflow, no
  test, no cut step — which is how 19 findings accumulated unreported.
- **The findings are fixed at their source**: nine frontmatter statuses that disagreed with
  the folder (four `proposed/` files claiming `accepted`, five `deprecated/` files claiming
  `implemented`); prose scraped into `created_at` by the legacy migration in nineteen files
  (the audit checked only the registry's copy, so the four #1144 named were fifteen more
  once the file's own field was read); one draft with no frontmatter at all. The timestamp
  rule accepts day precision (`2026-02-23`), which nine correct registry values had been
  reported against.

## Merged pull requests (29)

| PR | Title | Closes |
|---|---|---|
| [#1274](https://github.com/backspring-labs/squad-ops/pull/1274) | chore(release): 1.7.1 — Stack Seams | — |
| [#1267](https://github.com/backspring-labs/squad-ops/pull/1267) | docs(plan): the 1.7.1 verification-set record | — |
| [#1266](https://github.com/backspring-labs/squad-ops/pull/1266) | docs(plans): 1.7.1 verification-set pre-registration — six shakeout deploys, exit rule met on f85de47a | — |
| [#1265](https://github.com/backspring-labs/squad-ops/pull/1265) | fix(cycles): the repair evaluates the failed task's criteria on the tree the verifier overlays (#1264) | [#1264](https://github.com/backspring-labs/squad-ops/issues/1264) |
| [#1263](https://github.com/backspring-labs/squad-ops/pull/1263) | docs: what the 1.7.1 shakeouts taught, written where it outlives the line | — |
| [#1262](https://github.com/backspring-labs/squad-ops/pull/1262) | fix(cycles): an absent file is not evidence against a patch, and TS18xxx is not a syntax error (#1259, #1261) | [#1259](https://github.com/backspring-labs/squad-ops/issues/1259) [#1261](https://github.com/backspring-labs/squad-ops/issues/1261) |
| [#1258](https://github.com/backspring-labs/squad-ops/pull/1258) | fix(cycles): rule B's rows ride the protocol result to the verifier (#1256) | [#1256](https://github.com/backspring-labs/squad-ops/issues/1256) |
| [#1257](https://github.com/backspring-labs/squad-ops/pull/1257) | fix(cycles): the handoff's required sections are a typed criterion, so a builder repair can be decided (#1255) | [#1255](https://github.com/backspring-labs/squad-ops/issues/1255) |
| [#1253](https://github.com/backspring-labs/squad-ops/pull/1253) | fix(plan): a plan-authored regex over the handoff's headings no longer fails the builder (#1252) | [#1252](https://github.com/backspring-labs/squad-ops/issues/1252) |
| [#1250](https://github.com/backspring-labs/squad-ops/pull/1250) | fix(executor): the correction runner is handed the dispatched envelope, so rule B's workspace reaches the repair (#1229 live gap) | — |
| [#1249](https://github.com/backspring-labs/squad-ops/pull/1249) | chore(packaging): [project.dependencies] mirrored from the real imports, the package ships its data, a fresh-venv install job (#582) | [#582](https://github.com/backspring-labs/squad-ops/issues/582) |
| [#1248](https://github.com/backspring-labs/squad-ops/pull/1248) | ci(release): cut steps 5 and 7 get their guards — the SIP sweep line on release PRs, the captured package on every push (#1151) | [#1151](https://github.com/backspring-labs/squad-ops/issues/1151) |
| [#1247](https://github.com/backspring-labs/squad-ops/pull/1247) | feat(correction): the qa repair is scoped to the failing cases, and routes on an undeclared anchor (#1123) | [#1123](https://github.com/backspring-labs/squad-ops/issues/1123) |
| [#1246](https://github.com/backspring-labs/squad-ops/pull/1246) | feat(checks): the DOM anchor contract gets its enforcement layer, and the frozen client's call surface reaches the suite author (#668) | — |
| [#1245](https://github.com/backspring-labs/squad-ops/pull/1245) | feat(checks): additive-suite containment is a gate — named findings at the qa emission seam (#1022) | [#1022](https://github.com/backspring-labs/squad-ops/issues/1022) |
| [#1244](https://github.com/backspring-labs/squad-ops/pull/1244) | feat(checks): the emitted container's packaging gets its findings — reporting-only (#598) | — |
| [#1243](https://github.com/backspring-labs/squad-ops/pull/1243) | fix(correction): a qa-owned own-frame failure routes to the qa repair, targeting the suite (#1130) | [#1130](https://github.com/backspring-labs/squad-ops/issues/1130) |
| [#1242](https://github.com/backspring-labs/squad-ops/pull/1242) | chore(sips): the registry indexes every SIP, and its audit runs in CI (#1144) | [#1144](https://github.com/backspring-labs/squad-ops/issues/1144) |
| [#1240](https://github.com/backspring-labs/squad-ops/pull/1240) | feat(checks): the assertion-kind gate — a free-authored suite's literals against the manifest's declared field kinds (#1153) | [#1153](https://github.com/backspring-labs/squad-ops/issues/1153) |
| [#1239](https://github.com/backspring-labs/squad-ops/pull/1239) | feat(checks): the declaration has an environment axis — required tooling per check, declared gaps per role (rule B) | — |
| [#1238](https://github.com/backspring-labs/squad-ops/pull/1238) | feat(correction): a repair is verified where its checks can run — the agent evaluates its own patch, the executor consumes the rows (#1229) | [#1229](https://github.com/backspring-labs/squad-ops/issues/1229) |
| [#1237](https://github.com/backspring-labs/squad-ops/pull/1237) | fix(site): a SIP renamed by promotion no longer blocks the deploy | [#1236](https://github.com/backspring-labs/squad-ops/issues/1236) |
| [#1235](https://github.com/backspring-labs/squad-ops/pull/1235) | feat(checks): undefined_names reads .ts/.tsx/.js/.jsx through tsc, provisioned per role as data (#939) | [#939](https://github.com/backspring-labs/squad-ops/issues/939) |
| [#1234](https://github.com/backspring-labs/squad-ops/pull/1234) | refactor(seam): the suite-suffix vocabulary and the store paragraph live behind the stack seam (#1131 follow-up) | — |
| [#1233](https://github.com/backspring-labs/squad-ops/pull/1233) | refactor(scaffold): stack #1 gets its own module, and a guard that stack-shaped literals live behind the seam (#1131) | [#1131](https://github.com/backspring-labs/squad-ops/issues/1131) |
| [#1232](https://github.com/backspring-labs/squad-ops/pull/1232) | docs(plan): record the owner's ruling on the 1.7.1 seam decision — B | — |
| [#1231](https://github.com/backspring-labs/squad-ops/pull/1231) | docs(sip): harvest the stack #1 expander's rationale into SIP-0105 (#1149) | — |
| [#1230](https://github.com/backspring-labs/squad-ops/pull/1230) | docs(plan): the 1.7.1 line plan — Stack Seams | — |
| [#1228](https://github.com/backspring-labs/squad-ops/pull/1228) | docs(release): capture the v1.7.0 release package | — |

## Improvement proposals

| Proposal | From | To |
|---|---|---|
| [IDEA-QA-First-Test-Strategy-1h-Cycles-group_run](../../design/sips/IDEA-QA-First-Test-Strategy-1h-Cycles-group_run.md) | new | proposed |
| [SIP-0003-v2-Paperclip-Protocol-Squad-Passive-Income-Flipping](../../design/sips/SIP-0003-v2-Paperclip-Protocol-Squad-Passive-Income-Flipping.md) | new | deprecated |
| [SIP-0006-Warm-Boot-Analysis-Protocol-WBA](../../design/sips/SIP-0006-Warm-Boot-Analysis-Protocol-WBA.md) | new | deprecated |
| [SIP-0006-v2-Warm-Boot-Analysis-Protocol-WBA-Ops-Mode](../../design/sips/SIP-0006-v2-Warm-Boot-Analysis-Protocol-WBA-Ops-Mode.md) | new | deprecated |
| [SIP-0009-Scout](../../design/sips/SIP-0009-Scout.md) | new | deprecated |
| [SIP-0010-Creds-Secrets-Lifecycle-Protocol-Role-First](../../design/sips/SIP-0010-Creds-Secrets-Lifecycle-Protocol-Role-First.md) | new | deprecated |
| [SIP-0012-Pattern-First-Development-Escalation-Protocol](../../design/sips/SIP-0012-Pattern-First-Development-Escalation-Protocol.md) | new | proposed |
| [SIP-0013-Extensibility-Customization-Protocol](../../design/sips/SIP-0013-Extensibility-Customization-Protocol.md) | new | proposed |
| [SIP-0016-HumanAgent-Hybrid-Squad-Operations](../../design/sips/SIP-0016-HumanAgent-Hybrid-Squad-Operations.md) | new | proposed |
| [SIP-0018-Enterprise-Process-CoE-Enablement](../../design/sips/SIP-0018-Enterprise-Process-CoE-Enablement.md) | new | proposed |
| [SIP-0018-v2-Squad-Context-Protocol](../../design/sips/SIP-0018-v2-Squad-Context-Protocol.md) | new | proposed |
| [SIP-0019-SIP-Management-Workflow-Protocol](../../design/sips/SIP-0019-SIP-Management-Workflow-Protocol.md) | new | implemented |
| [SIP-0020-Health-Check-WarmBoot-Enhancement](../../design/sips/SIP-0020-Health-Check-WarmBoot-Enhancement.md) | new | deprecated |
| [SIP-0022-Specialized-Development-Agent-Roles](../../design/sips/SIP-0022-Specialized-Development-Agent-Roles.md) | new | deprecated |
| [SIP-0023-Domain-Expert-Architecture-for-Product-Strategy](../../design/sips/SIP-0023-Domain-Expert-Architecture-for-Product-Strategy.md) | new | proposed |
| [SIP-0026-Testing-Framework-and-Philosophy](../../design/sips/SIP-0026-Testing-Framework-and-Philosophy.md) | new | implemented |
| [SIP-0027-OpenTelemetry-Testing-Results](../../design/sips/SIP-0027-OpenTelemetry-Testing-Results.md) | new | implemented |
| [SIP-0027-v2-Telemetry-Implementation-Execution-Plan-Multi-Cloud](../../design/sips/SIP-0027-v2-Telemetry-Implementation-Execution-Plan-Multi-Cloud.md) | new | deprecated |
| [SIP-0027-v3-WarmBoot-Telemetry-Orchestration-Protocol-Enhanced-Observability-and-Event-Drive](../../design/sips/SIP-0027-v3-WarmBoot-Telemetry-Orchestration-Protocol-Enhanced-Observability-and-Event-Drive.md) | new | deprecated |
| [SIP-0028-Hybrid-Deployment-Model-Industry-Aligned-Architecture-for-Multi-Environment-Depl](../../design/sips/SIP-0028-Hybrid-Deployment-Model-Industry-Aligned-Architecture-for-Multi-Environment-Depl.md) | new | proposed |
| [SIP-0032-Activity-Feed-API](../../design/sips/SIP-0032-Activity-Feed-API.md) | new | deprecated |
| [SIP-0040-Rev-2-Phase-0-Critical-Architectural-Fixes](../../design/sips/SIP-0040-Rev-2-Phase-0-Critical-Architectural-Fixes.md) | new | implemented |
| [SIP-0040-v2-Rev-3-Decorator-Based-CapabilitySkillTool-System](../../design/sips/SIP-0040-v2-Rev-3-Decorator-Based-CapabilitySkillTool-System.md) | new | implemented |
| [SIP-0046-Rev-1-Agent-Specs-and-Configuration-ACPAligned-YAML-Standard](../../design/sips/SIP-0046-Rev-1-Agent-Specs-and-Configuration-ACPAligned-YAML-Standard.md) | new | implemented |
| [SIP-0105-Stack-Blueprint-Contract](../../design/sips/SIP-0105-Stack-Blueprint-Contract.md) | new | accepted |
| [SIP-API-Contract-Hardening](../../design/sips/SIP-API-Contract-Hardening.md) | new | proposed |
| [SIP-Agent-Comms-Delivery-Guarantees](../../design/sips/SIP-Agent-Comms-Delivery-Guarantees.md) | new | proposed |
| [SIP-Agent-Embodiment-Runtime](../../design/sips/SIP-Agent-Embodiment-Runtime.md) | new | proposed |
| [SIP-Campaign-Orchestration](../../design/sips/SIP-Campaign-Orchestration.md) | new | proposed |
| [SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements](../../design/sips/SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md) | new | proposed |
| [SIP-Capability-Backed-Agents](../../design/sips/SIP-Capability-Backed-Agents.md) | new | proposed |
| [SIP-Continuum-Runtime-Console](../../design/sips/SIP-Continuum-Runtime-Console.md) | new | proposed |
| [SIP-Cross-Cycle-Memory](../../design/sips/SIP-Cross-Cycle-Memory.md) | new | proposed |
| [SIP-Cycle-Evaluation-Scorecard](../../design/sips/SIP-Cycle-Evaluation-Scorecard.md) | new | proposed |
| [SIP-Cycle-Request-Profile-Naming-Taxonomy](../../design/sips/SIP-Cycle-Request-Profile-Naming-Taxonomy.md) | new | proposed |
| [SIP-Design-Decision-Register](../../design/sips/SIP-Design-Decision-Register.md) | new | proposed |
| [SIP-Duty-Continuity-and-Handoff-Ledger](../../design/sips/SIP-Duty-Continuity-and-Handoff-Ledger.md) | new | proposed |
| [SIP-Edge-Deployment-Profile](../../design/sips/SIP-Edge-Deployment-Profile.md) | new | proposed |
| [SIP-Experiment-Queue-and-Cycle-Assessment](../../design/sips/SIP-Experiment-Queue-and-Cycle-Assessment.md) | new | proposed |
| [SIP-Fine-Grained-Issue-Enumeration](../../design/sips/SIP-Fine-Grained-Issue-Enumeration.md) | new | proposed |
| [SIP-LLM-Emission-Contracts](../../design/sips/SIP-LLM-Emission-Contracts.md) | new | proposed |
| [SIP-Planning-Sequence-Strategy-First](../../design/sips/SIP-Planning-Sequence-Strategy-First.md) | new | proposed |
| [SIP-Post-Retest-Governance-Acceptance-Review](../../design/sips/SIP-Post-Retest-Governance-Acceptance-Review.md) | new | proposed |
| [SIP-Skill-Layer-For-Capabilities](../../design/sips/SIP-Skill-Layer-For-Capabilities.md) | new | proposed |
| [SIP-Test-First-Verification](../../design/sips/SIP-Test-First-Verification.md) | new | proposed |
| [SIP-Version-Bump-Hardening](../../design/sips/SIP-Version-Bump-Hardening.md) | new | proposed |
| [SIP-intelligent-delegation-protocols](../../design/sips/SIP-intelligent-delegation-protocols.md) | new | proposed |

## Cycle evidence

### `cyc_4d52bbd34a32`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:container_packaging, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_9c085ec2e9e5`

**Verdict:** `blocked_unverified` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:container_packaging, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:function_defined, acceptance:harness_boundary, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, non_stub_files |
| Failed | required_files |
| Required unmet | frontend_build, tests_pass |
| Never executed | frontend_build, tests_pass |

### `cyc_f05692bb3ceb`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_de4b2dea73a0`

**Verdict:** `accepted` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:command_exit_zero, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | — |
| Required unmet | — |
| Never executed | — |

### `cyc_ca02bed7fbb4`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:command_exit_zero, acceptance:declared_imports, acceptance:endpoint_defined, acceptance:fill_slot_signature, acceptance:frontend_compiles, acceptance:import_present, acceptance:module_imports, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, tests_pass, vc-probe-runs, vc-probe-runs-join, vc-probe-runs-join-duplicate, vc-probe-runs-leave, vc-probe-runs-rejects-blank |
| Failed | expected_artifacts, acceptance:function_defined, acceptance:harness_boundary, acceptance:command_exit_zero, acceptance:contract_assertions_match, acceptance:assertion_kinds_match |
| Required unmet | — |
| Never executed | — |

### `cyc_9be98128f0e9`

**Verdict:** `rejected` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:additive_containment, acceptance:assertion_kinds_match, acceptance:declared_imports, acceptance:dom_anchor_queries, acceptance:frontend_compiles, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, frontend_build, no_self_mocking_tests, no_stub_fallback_tests, non_stub_files, required_files, vc-probe-api-runs, vc-probe-api-runs-join, vc-probe-api-runs-join-duplicate, vc-probe-api-runs-leave, vc-probe-api-runs-rejects-blank |
| Failed | tests_pass |
| Required unmet | — |
| Never executed | — |

### `cyc_5b027f3e74fc`

**Verdict:** `blocked_unverified` · **Runs:** 2

| | Checks |
|---|---|
| Verified | acceptance:declared_imports, acceptance:frontend_compiles, acceptance:sections_present, acceptance:undefined_names, acceptance:unterminated_source, acceptance_criteria_prose, expected_artifacts, non_stub_files, required_files |
| Failed | — |
| Required unmet | frontend_build, tests_pass |
| Never executed | frontend_build, tests_pass |
