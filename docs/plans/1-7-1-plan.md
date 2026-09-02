# 1.7.1 — plan

**Revision 1, 2026-09-01.** Written the day v1.7.0 was tagged, from four records and nothing
else: the 1.7.0 plan's Stack Seams pack (`docs/plans/1-7-0-plan.md` §2.2, §3.1), the 1.7.0 cut
record's disclosures and unplaced findings (`docs/plans/1-7-0-cut-record.md` §2, §4), the 1.6.6
verification-set record's two rejections (`docs/plans/1-6-6-verification-set-record.md` §3),
and the stored per-round artifacts of every roll an item below came from — all of which are in
the local vault (`data/artifacts/group_run/`). Nothing here reverses a 1.7.0 item. **This plan
is about one thing: what is stack-specific lives behind the stack seam**, and the two places
the 1.6.x and 1.7.0 rolls showed it does not — the correction loop's last red class (a
free-authored assertion, stack #1) and the checks stack #2 does not get (stack #2).

**The rulings that shape it** (1.7.0 plan §3, cut record §4, owner 2026-08-27 and 08-31):
harvest the rationale before any extraction (#1149 → #1131), and write the seam fixes into the
seam, not into the file it is leaving; #1122 (fill slots for stack #1) is an `enhancement` and
stays in the 1.8 lane as #1131's consumer; #929 and #1206 are designed together, not here;
#1229 — unplaced by the cut record — joins #939, because both are "stack #2 is checked less
than stack #1"; and the deploy this line's preflight runs on is the 1.7.0 one — Ollama,
`full-38`, `qwen3.8:27b`, no provider switch taken.

---

## 1. What the records say the pack has to answer

Three classes, each from the rolls that produced it. Every cycle named is in the local vault
and is the replay input for its item.

| class | roll | cycle | what happened | item |
|---|---|---|---|---|
| **free-authored assertion (stack #1)** | 1.6.6 React roll 3 | `cyc_38d1e1689766` | `LeaveResult.removed` declared `boolean`; all four qa emissions asserted `body["removed"] == "Carol"`; the round-0 dev repair set `removed=True` (correct per contract), verification 9/9, retest failed on the assertion; rejected, audit FAIL | #1153 |
| | 1.6.5 React roll 3 | `cyc_184b3a1d194e` | `client.delete(url, json=…)` TypeError at collection, identical in all three reports; both analyses and both decisions named the qa file; every repair went to `backend/routes.py` | #1130 |
| | 1.6.6 React roll 6 | `cyc_0c4664c2ae9a` | after a landed repair the frontend suite failed on `expected "spy" to be called with […]` then `expected undefined to be defined`; rejected with the boot audit PASSING all five probes | #1123 |
| | fay-14 | `cyc_42eed09efbec` | zero `data-testid` queries in every version of the RTL suite while the dev half complied at first fill | #668 |
| | V7 attempt-2 C3 / C4 | `cyc_6495d9870587` / `cyc_2913ae7abd67` | an additive suite fetched a live server that never exists under vitest; three qa repairs, no convergence; every delivered app of the arc passed an independent boot audit | #1022 |
| **stack #2 is checked less** | 1.7.0 roll 4 | `cyc_58d92ca2b407` | `ReferenceError: created is not defined` at `__tests__/runs.test.ts:30` in the retest report (`art_75146a8a1cfc`) — a `.ts` suite reached vitest with an undeclared name no check had seen | #939 |
| | 1.7.0 line | `cyc_05abfc7c1f00` | three rounds on `app/api/runs/route.ts`, two identical `unverifiable` verdicts, run at 1/14; #1221 now stops the loop and names the reason; the verdict is still unobtainable | #1229 |
| **"generic" is stack #1** | 1.6.5 React roll 1 | `cyc_b9296c255dfc` | `detect_self_mocking_tests` defined "invokes the application" as an `app/api/` import inside the shared `handlers/stub_detection.py` and discarded a green React suite; fixed in place by #1126, so the predicate is now the stack's — the module is still shared and nothing stops the next one | #1149, #1131 |

**The first class is one mechanism.** A suite the framework did not shape asserts something the
contract never said; a correct application, or a correct repair, is rejected by it; and nothing
routes the defect to the file that owns it. The 1.6.6 pack's six items held on every roll they
were exercised on, and both of that set's rejections were this class — its record placed the
class here. Three of the five items are deterministic and testable at emission (#1153, #668,
#1022); two are routing and scoping in the correction loop (#1130, #1123). None is a scaffold
for stack #1 — that is #1122, and §2.4 says why it is not here.

**The second class is one seam.** Typed checks run at emission in the producing role's
agent container, which has node but no TypeScript analyser, so `undefined_names` — pyflakes,
in-process (`src/squadops/cycles/acceptance_checks.py:477`) — reads `.py` only; a repair is
verified in runtime-api instead, which has no node at all. #939 and #1229 are the same
sentence — *a check that needs a toolchain runs where the toolchain is* — and §2.2 settles it
once rather than twice.

**The third class is structural,** and it is why the other two are written the way they are:
every fix goes into a seam that already exists (`ScaffoldStack`,
`src/squadops/capabilities/scaffold.py:1988`), and the guard makes the next shared-file bleed
a CI failure instead of a roll.

---

## 2. The pack

The roll-verified items are the seven that change what a cycle does: #1153, #1130, #1123,
#668, #1022, #939, #1229. #1149 is documentation and #1131 is a pure move proven by digests,
so the roll-verified count sits inside §3.1's 6–8 calibration, and each of the seven carries
one prediction in §4.

### 2.1 The precondition and the move — #1149, then #1131

**#1149 — harvest first.** The "why" of stack #1 lives in comments in the block being moved, and
a comment survives an extraction only if the refactorer reads it. The Design Decision Register
SIP (`sips/proposed/SIP-Design-Decision-Register.md`) is still `proposed`; this line does not
wait for it. The home is a `## Post-acceptance amendments` section on **SIP-0105** (Stack
Blueprint Contract, `sips/accepted/`) — the SIP whose seam the extraction serves, which has no
such section today; SIP-0104 §13 is the shape. One entry per load-bearing comment in the
block: the rule, the evidence (issue and cycle), who ruled it. The extraction PR cites the
entries, and `.github/PULL_REQUEST_TEMPLATE.md` gains one line for extraction PRs — *rationale
harvested, entries cited*. Not a code change.

**#1131 — the pure move.** Facts on main, 2026-09-01: `scaffold.py` is 2,312 lines; the inline
stack-#1 expander is **lines 1335–1985** (`_py_type` at :1340 through
`_fill_slots_fullstack_fastapi_react` at :1982, about 650 lines) and ends at a top-level
boundary — `ScaffoldStack` itself starts at :1988. Stack #1 is registered by the inline `_STACKS`
entry at :2101–2133, with its `AppInvocation` literal at :2119–2130 and `error_seam=ERROR_SEAM_FASTAPI`
at :2116 — stack-#1 payload in the shared module. Stack #2 registers at :2138–2161 from plain
symbols `stack_nextjs_ts.py` exports (`STACK_NAME` :44, `APP_INVOCATION` :52,
`expand_nextjs_ts` :596, `fill_slots_nextjs_ts` :634), imported at :40–46. The #822 comment at
:37–39 says a second inline expander "would push this file past 2000 lines"; the file passed
that with one.

Two corrections to the issue's text, from the tree rather than from memory. `envelope_example`
is a method of `ErrorSeam` (`scaffold.py:741`), stack-neutral, and stays. And **`GENERATOR_VERSION`
is not the pin for stack #1**: it gates only the SIP-0104 verification-scaffold emitter
(`verification_scaffold_emission.py:59`, value 8), which stack #1 does not opt into
(`scaffold.py:2157–2158`). The pin is the reference contract's `frozen:` digests —
`tests/fixtures/reference_contract/contract_v11_harness_cleanup_1127.yaml` holds the sha256 of
every non-fill file the expander emits, asserted against `expand(manifest)` by
`tests/unit/capabilities/test_scaffold_contract.py:94–106` and reproduced byte-for-byte by
`tests/unit/capabilities/test_contract_derivation_reference.py:128`. **Those digests unchanged is
the whole regression proof of the move.** A moved template that changes one byte fails the
reference test, and the change is then a scaffold change, not a move.

**The structural guard lands with the move.** The shape exists:
`tests/unit/capabilities/test_success_status_seam.py:87–102` (one owning module, `rglob` the
tree, skip comment lines, report `path:line`, assert the list is empty), with the reviewed
allowlist of `tests/unit/architecture/test_no_enum_shadow_comparisons.py:35` onward, each entry
carrying its reason. The rule: no module under `capabilities/handlers/` or `cycles/` carries a
stack-shaped literal in live code — `app/api/`, `.test.tsx`, `page.tsx`, `App.jsx`, `routes.py`,
`conftest`, `main.py`, `vitest`, `pytest` — unless its basename starts with `stack_` or the line
is allowlisted with a reason. It would have failed on `1b9b93a9`. What it fires on today,
measured on main: `handlers/stub_detection.py:112–121` (`_JS_TEST_SUFFIXES`, a JS-only
vocabulary no stack declares), `handlers/test_runner.py:591` and `:838` (`conftest.py`,
`_RUNNABLE_TEST_SUFFIXES`), `handlers/cycle/validation.py:40`, and the `example=` literals in
`cycles/acceptance_check_spec.py` at :557, :596, :617, :633, :758, :816, :890. The suffix
vocabularies move behind the seam — the accessors at `scaffold.py:1291–1317`
(`qa_test_namespace`, `is_qa_test_path_for_stack`, `harness_entry_modules`) are where they
belong; the check-spec examples are documentation and are allowlisted as that.
`detect_self_mocking_tests` (`stub_detection.py:142–174`) takes an `AppInvocation` since #1126,
returns `[]` when the stack declares none, and needs nothing.

**As landed (2026-09-01).** The move and the guard shipped together; the guard carries a
reviewed allowlist, each entry with its reason, and a second test fails when an entry no
longer fires. Two helpers in the block were not stack payload and the move said so rather
than carrying them: `_base_type_name` is manifest vocabulary the shared lint calls, and now
lives as `base_type_name` in `capabilities/type_tokens.py`, a leaf both the model and the
stack modules import; `_snake` is stack #1's store-naming rule, which the fill brief in
`scaffold.py` still renders, so the brief imports it from the stack module for now. The
suffix vocabularies (`_JS_TEST_SUFFIXES`, `_RUNNABLE_TEST_SUFFIXES`, the qa handler's suffix
check) and that fill-brief line move behind the seam in a follow-up PR of this line, which
deletes their allowlist entries — split from the move so the byte-identical proof stays a
proof of a move and nothing else.

### 2.2 The seam decision — a check runs where its toolchain exists (#939, #1229)

**What the tree says, 2026-09-01.** Typed acceptance checks run at emission **in the producing
role's agent container**: `_evaluate_typed_acceptance`
(`src/squadops/capabilities/handlers/cycle/base.py:458`) materialises the workspace into a temp
dir (:508–525) and evaluates every criterion in-process (`acceptance_evaluation.py:126`); its
callers are `develop.py:662`, `builder.py:520` and `qa_test.py:187`. The dev and qa images
install node and npm as data (`agents/instances/{dev,qa}/system-packages.txt:9–10`, applied
generically by `agents/Dockerfile:78–86`); **neither installs `typescript` or `eslint`**, which
is the measured claim behind the declaration at `acceptance_check_spec.py:496–505`. So
`frontend_compiles` (`acceptance_checks.py:1552`; `npm run build` at :1617, which for a Next.js
scaffold is `next build` and runs tsc) executes at emission and is the type check for app
files, while `undefined_names` (`UndefinedNamesCheck`, `acceptance_checks.py:425`; pyflakes at
:477–486) is the per-file check and reads `.py` only.

Patch verification runs somewhere else: **in runtime-api**, in-process in the executor
(`verify_patched_artifacts`, `src/squadops/cycles/patch_verification.py:445`; its docstring at
:474 says "runtime-api has no node"; the image is `python:3.12-slim` plus curl and gcc,
`src/squadops/api/runtime/Dockerfile:23–32`). There `frontend_compiles` returns
`skipped(missing_tooling)` (`acceptance_checks.py:1602`), no blocking check executes, and the
gate — correctly — refuses to accept a patch on no evidence (:571–578, `unverifiable /
no_executed_blocking_checks`), which #1221's `correction_is_deadlocked`
(`adapters/cycles/dispatched_flow_executor.py:122`) turns into a named break. Repair handlers
never run typed acceptance on their own output: `repair_handlers.py` has no
`_evaluate_typed_acceptance` caller.

**Roll 4 is both issues in one round.** The suite that reached vitest with `created`
undeclared was written by `repair-run_1a5833f6-00-qa.test_repair` at 14:18:25Z and executed
by the retest at 14:18:52Z (vault metadata, `cyc_58d92ca2b407`). Between them stood only
runtime-api's verification — where `frontend_compiles` cannot run and `undefined_names` does
not read `.ts`. The emission-time seam would have had node; nothing at the emission-time seam
had an analyser. Closing either gap alone leaves the other, which is why they are one
decision.

**The rule this line lands: typed checks execute in the producing role's agent container — at
emission and at repair — and each image provisions, as data, the toolchain the stack's check
specs require.** The vocabulary exists: a check spec already declares `required_tooling`
(`src/squadops/cycles/check_registry.py:34–46`, `TOOL_NODE`), the contract attaches
`requires: node` per criterion (`scaffold_contract.py:42`, :280, :300, :306), and #1216's
`DECLARED_COVERAGE_GAPS` (`acceptance_check_spec.py:495`) is guarded two-sided by
`test_every_coverage_gap_is_declared` and `test_no_declared_gap_outlives_the_gap`
(`tests/unit/cycles/test_check_governance.py:44`, :60). What changes:

- **#939 — the analyser, and the check.** `typescript` pinned into the dev and qa images
  through the same data-driven path as node (a per-role npm-globals list beside
  `system-packages.txt`, never a line in the Dockerfile), and `UndefinedNamesCheck` gains the
  four extensions: `tsc --noEmit` over the materialised workspace, reporting the
  unresolved-name diagnostics only (TS2304 "Cannot find name", TS2552) — the full type check
  stays `frontend_compiles`'s. `checkJs` is expected to give `.js`/`.jsx` the same analyser, so
  the React stack's frontend suites get it too — measured in the PR, not assumed here. The four `DECLARED_COVERAGE_GAPS` rows come out,
  which the two-sided guard forces. Named per file, so the failure lands on the task that
  wrote it — the attribution half the 2026-08-17 comments on #939 asked for, and the detection
  half those comments could not settle without a build against an undeclared name; roll 4
  settled it.
- **#1229 — verification where the checks run.** The repair handlers evaluate the stack's
  typed criteria on their own patched tree before returning — the same
  `_evaluate_typed_acceptance` the primaries use, in the same container — and return the
  executed outcomes with the patch. `verify_patched_artifacts` consumes those outcomes as its
  positive evidence, still re-executing locally what it can (the Python checks) as a
  cross-check, and its "no executed blocking check" exit fires only when the agent could not
  execute either. `correction_is_deadlocked` stays as the backstop it is.
- **The declaration names the environment.** A gap is keyed by check, extension *and* the
  environment that could not run it; the guard asserts, for every spec with `required_tooling`,
  that each environment evaluating typed checks provisions the tool or declares the gap. That
  is #1229's third bullet and #1216's mechanism extended by one axis.

**The options, for the ruling.** (A) Put node and the analyser into the runtime-api image and
keep verification where it is — expedient; a second toolchain in the control-plane image,
emission and verification still in different environments, and every future stack's
toolchain lands in runtime-api too. (B) The rule above — verification runs where emission
checks run; runtime-api consumes evidence and cross-checks what it can. (C) The SIP-0102
docker sandbox (`src/squadops/sandbox/environment.py:139`; Node 20 in
`infra/sandbox/fastapi-react.Dockerfile:22–23`) — dormant behind `provider: noop`
(`src/squadops/config/schema.py:260`, `adapters/sandbox/factory.py:64–69`); turning it on is a
deployment-wide switch that wants its own line. **Recommendation: B**, with A rejected on the
composition-root ground and C left to the line that measures the sandbox. Cost stated: a
repair round gains one in-container evaluation, the correction budget was sized against the
in-process cost, and §4's texture reads wall clock per round so the cost is a number in the
record.

**Ruled 2026-09-01: B** (owner). #939 and #1229 open on that rule; A and C are closed as
options for this line.

**Replays.** #939: the stored `repair-…-00-qa.test_repair` suite of `cyc_58d92ca2b407` through
the new check is rejected naming `created` at `__tests__/runs.test.ts:30`; the 1.7.0 gating
roll's suites (`cyc_2a88dabad94b`, green) pass; a `.jsx` suite from a 1.6.6 green roll passes.
#1229: `cyc_05abfc7c1f00`'s stored repair patches through the agent-side evaluation produce
executed outcomes for every `.ts` criterion, and `verify_patched_artifacts` returns `passed`
or `failed`, never `unverifiable / no_executed_blocking_checks`. The same replay on the React
stack with a `frontend/src/*.jsx` repair — unverifiable in runtime-api today for the same
reason, with no roll yet to show it.

**#939 as landed (2026-09-01).** The analyser is `tsc` (typescript 5.5.3, the version the
Next.js skeleton pins for the app), provisioned into the dev and qa images through a new
per-role `npm-global-packages.txt` read by the same generic Dockerfile step pattern as
`system-packages.txt`; CI installs the same file's globals so the replays execute there.
`UndefinedNamesCheck` runs tsc once per materialised tree and filters `TS2304`/`TS2552` to
the file; a TypeScript project is checked under its own `tsconfig.json`, a tree without one
as an explicit list with `--allowJs --checkJs`, which was measured to report the class in
plain JSX. Where tsc is absent the check skips as `missing_tooling` — the #462 rule `npm`
already follows — so runtime-api's repair verification is unchanged until #1229. The roll-4
shell and the gating roll's shell are committed as `tests/fixtures/roll_replays/` and the
replay is a test. The four declared gaps are gone; the menu is regenerated.

### 2.3 The free-authored-assertion class, at the seam — #1153, #1130, #668 → #1123, #1022

Each item names its mechanism, its replay (the stored artifact from §1 through the new code,
before any roll), and the control that bounds over-rejection.

**#1153 — the kind gate.** On the React stack a `body["<field>"] == <literal>` assertion
(pytest) or a `toBe`/`toEqual` on a response field (vitest) is bound to the response entity's
declared field kinds from the manifest — the same data #1094 uses for fills
(`src/squadops/capabilities/response_shape.py:104`,
`verification_scaffold_emission.py:86–96`) — and an assertion whose literal cannot be of the
declared kind (a string against `boolean` or `integer`, an object against `string`) is rejected
at emission naming the field and the kind, so the re-emission brief carries it. Written as a
stack predicate the seam owns, not a shared regex. Replay: roll 3's four stored suites are
rejected with `removed: boolean` named; a suite asserting `body["removed"] is True` passes;
the suites of the four accepted 1.6.6 React rolls pass (the over-rejection control). On the evidence this flips roll 3
outright.

**#1130 — route a qa-owned defect to `qa.test_repair`.** The repair unit exists and is never
chosen: `qa.test` has an own-artifact entry (`src/squadops/cycles/task_plan.py:254`,
`QA_TEST_REPAIR_STEPS`), `own_artifact_role` (:258) resolves it, and
`_locus_and_repair_target` (`adapters/cycles/correction_runner.py:614`) reads a free-authored
backend suite's failure as "app fails suite" and runs the dev chain. The signal is a machine
fact, not an opinion: the runner's structured failure row names the file
(`handlers/test_runner.py:61`, `test_failures`), the file is qa-owned by the stack's own
predicate (`scaffold.py:1300`, `is_qa_test_path_for_stack`), and the error is raised at
collection in the suite's own frame before any application code is exercised. That routes to
`own_artifact` with the suite as the target. Replay: 1.6.5 roll 3's stored report and
`failure_analysis.md` through the router → target `backend/tests/test_runs.py`, chain
`qa.test_repair`, never `backend/routes.py`.

**#668 — the DOM anchor contract's enforcement layer**, which #1123's signal needs. The anchor
inventory is already threaded to the qa author (`handlers/cycle/qa_test.py:536`,
`_dom_anchor_section`) and to the repair (`handlers/impl/repair_handlers.py:539`); fay-14
showed prompts alone under-deliver on the suite side. The issue's fork is the owner's (§6);
the recommendation is options 1 + 2 together, the shape that made the api-behaviour contract
stick for statuses (#629/#632): a typed check `dom_anchor_queries` — a suite covering a
contract view queries that view's root anchor — and the anchor block rendered as an
authoritative contract above the prose. Replay: fay-14's `art_428bb2c5468c` (zero anchor
queries) is flagged; a suite querying `run-detail`/`participant-list` per the inventory passes.
Scope stated on the issue and kept: anchors arbitrate *where* the suite looks, not the
data-fetch contract.

**#1123 — scope the qa repair, route on a machine signal.** Two deterministic pieces. (1) The
`qa.test_repair` brief names the failing cases from the runner's structured rows
(`test_failures`, `failing_test_identities` at `test_runner.py:746`) with the runner's messages
and forbids touching the passing ones — today the repair re-authors the whole file with no
list. (2) A failing assertion that references a `data-testid` absent from the frozen anchor
inventory is a qa-side defect no application can satisfy; read from the suite's source, not
the verdict (the same test-gaming footing as `contract_assertions`), it routes to the
own-artifact repair. Coverage, stated as the issue states it: (2) does not catch the
empty-state case — whether `runs-list` renders when empty is a view-behaviour fact the
manifest does not carry, and that is #1122's rung. Replay: roll 6's stored frontend suite and
report → the two failing cases isolated in the brief; the 1.6.5 shakeout `cyc_3cde35fa5204`'s
five DOM failures → the absent-anchor ones routed to qa, the rest untouched.

**#1022 — additive-suite containment.** The scaffold gate
(`src/squadops/capabilities/verification_scaffold_gate.py`) validates the fill surface with
named findings; additive suites — the files a qa author writes beyond it — have none, and they
are where every V7 counted red died. Extend the named findings to additive emissions on both
stacks through the seam: (1) no live-server fetch inside an in-process harness (the #877 class
as a gate, not guidance — #879's guidance is on the record as insufficient alone); (2) an
additive test imports the application, by the stack's `AppInvocation.invokes` — the seam's own
definition — since a suite that touches nothing can only self-mock; (3) the authenticity
detectors fire at emission with their evidence banked rather than late on the retest path.
Status assertions keep their existing gate (#629). Over-rejection is the tolerable direction:
a rejected additive file costs one authoring retry with a named finding; an accepted bad one
cost C3 its whole correction budget. Replay: C3 and C4's stored additive suites are rejected
with a named finding; the V7 slot-2/3 greens and the four accepted 1.6.6 React rolls' suites
pass.

### 2.4 What is deliberately not built

- **#1122 — SIP-0104 shells and fill slots for stack #1.** An `enhancement`, which an odd minor
  cannot carry; the 1.8-lane consumer of #1131's seam, with the Stack Blueprint rewrite. #1123's
  coverage note names exactly what it would catch that this pack does not.
- **#929 with #1206** — the LLM call-sequence extraction and the generation-coverage gap.
  Both must choose a value for `prompt_layer_set_id`; settling it twice moves the LangFuse
  grouping twice. Designed together, on a line whose pack reads telemetry.
- **#1204, #1205** — nothing refreshes `ci-constraints.txt`; no dependency vulnerability
  scanning. Hardening, not seams; no prediction here reads them. They join 1.7.3's infra
  rider, named there rather than carried silently.
- **A scaffold for stack #1**, in any form. #1153, #668 and #1022 constrain a free-authored suite
  at emission; they do not shape it. Shaping it is #1122.
- **Loop Honesty** (#788, #994, #995, #999, #1110, #968) — 1.7.2. The 1.7.0 plan's §3 first
  interleaved the two packs and its §3.1 then split them by line; this line holds the split, so
  a red is attributable to one pack.
- **Atlas** — unchanged from the cut record §5. Not adopted; #1158 open; nothing here runs on it.

### 2.5 Instrumentation, because the set will need it

The driver (`scripts/dev/verification_set_driver.py`, `loop_texture` at :808) gains one
readout per roll-verified item, so each prediction in §4 is read from the record and not from
a log by hand:

- `kind_gate_rejections` — per qa emission: field, declared kind, literal (#1153).
- `qa_owned_routed` — each `correction_repair_locus: own_artifact` whose target is a qa-owned
  path, with the collection-error signal that produced it (#1130).
- `dom_anchor_findings` and `absent_anchor_routed` (#668, #1123); `repair_brief_case_count` —
  the failing-case list the qa repair brief carried (#1123).
- `additive_rejections` — per emission, the named finding (#1022).
- `checks_by_environment` — every typed check executed, with the environment that ran it —
  and `unverifiable_toolchain_absent`, which must read 0 once #1229 lands (#939, #1229).
- The structural guard is CI; it has no roll readout.

---

## 3. The rider — CI-verified, beside the pack

- **#1087 (stack-#1 half) + #1112.** `root_persisted_entities` (`scaffold.py:653`) drives the
  Next.js store's `TABLES` since 1.6.4; the React store still exports a table for every entity.
  The same rule drives `_store_source` after the move. #1112 is its known edge — a single-object
  response projection gets a table — and the rider either lands the signal (an entity that is
  never an element of another entity's field and is returned by exactly one read endpoint) or
  records the edge as accepted texture; the 1.6.6 record's rolls 1, 3 and 4 stored
  `participant`/`run_summary` beside `run` and nothing asserted on them. **This is a deliberate
  scaffold change: the reference contract's frozen digests move.** It therefore lands *after*
  #1131 and its no-change proof, and the fixture is regenerated on the owner's go, never as a
  side effect.
- **Packaging fidelity** — #582 (`[project.dependencies]` mirrored from the real imports, the
  `sqlalchemy` audit, a fresh-venv install smoke in CI), #637 (a CI job that installs each
  service's lock and imports its composition root — the cheap remedy the issue names), #1144
  (`audit_sip_registry.py` wired to CI, its 19 data-quality findings fixed, the 24 unnumbered
  proposals indexed or the README's scope made true), #1151 (a tag-push check that
  `site/content/releases/v<tag>/` exists with a non-empty cycle list, and a `SIP sweep:` line in
  the cut PR body read by the closure script).
- **#598 — the emitted container is verified by no criterion.** Its three defects (a lockless
  `npm ci`, `dist-packages` on an official python image, Debian nginx's default site shadowing
  `/api/*`) reproduce from pf-38's stored artifacts, and that replay is the test. The criterion
  itself — build and start the emitted image — changes what a cycle does, so it lands
  **reporting-only this line** and whether it becomes blocking is a separate call (§6), the way
  every new detection has entered a measurement window.

**How we know:** the suite green, the guard green, `pip install` from a clean venv boots the
runtime API, the lock-import job green for every image, the tag-push guard exercised on the
1.7.1 tag itself.

---

## 4. The verification set — test the mechanism, not the rate

Two counting sets on one frozen deploy, the 1.7.0 plan's §4 sizing: **FastAPI+React N = 6**,
where every item of §2.3 came from, and **Next.js+TS N = 2**, which this time is *not* only a
regression arm — #939 and #1229 change what a Next.js roll does. Same driver, two new set configs
beside the 1.6.6 ones in `docs/plans/verification-sets/`, one shakeout per stack on the deploy before roll 1, pre-registered in a
document of its own before the first counted launch, with these predictions read only from
the evidence named:

| # | prediction | falsified by | read from |
|---|---|---|---|
| **R1** | (#1153) no qa emission carrying an assertion whose literal contradicts a declared field kind reaches test execution | one such assertion in a stored, executed suite | `kind_gate_rejections`; stored suites |
| **R2** | (#1130) a collection-time error in a qa-owned file is routed to `qa.test_repair` with that file as the target | one such failure whose repair targets an app file | `qa_owned_routed`; `correction_repair_locus` lines |
| **R3** | (#668) every stored RTL suite covering a contract view queries that view's root anchor | one covering suite with zero anchor queries executed | `dom_anchor_findings`; stored suites |
| **R4** | (#1123) every `qa.test_repair` brief names the failing cases, and a failing assertion on an anchor absent from the inventory is routed to qa | one whole-file repair brief with no case list; one absent-anchor failure sent to the dev chain | `repair_brief_case_count`, `absent_anchor_routed` |
| **R5** | (#1022) no additive suite that fetches a live server or imports nothing of the application reaches test execution | one such suite executed | `additive_rejections`; stored suites |
| **R6** | (#939) no `.ts`/`.tsx` emission with an unresolved name reaches test execution | one `ReferenceError: … is not defined` in a stored report | per-round `test_report.md`; `checks_by_environment` |
| **R7** | (#1229) no repair on either stack returns `unverifiable / no_executed_blocking_checks` because its criteria's toolchain was absent where verification ran | one such verdict | `unverifiable_toolchain_absent`; `checks_by_environment` |
| **S0–S3, Q0, Q3, Q5, P0** | carried from 1.6.6 unchanged — unexercised is not passed | as there | as there |

**Exercise, stated before the rolls.** R6 and R7 fire only when a Next.js emission carries an
unresolved name or a Next.js dev task enters the loop; both 1.6.6 Next.js rolls and the 1.7.0
gating pair took zero rounds. The replay in §2.2 is the proof; a counted roll is the
confirmation *where exercised*. To exercise both on the deploy before roll 1, one
fault-injected diagnostic per item — a fill with a deliberately undeclared name; a dev
emission forced into a repair — non-counting by declaration before launch, reported as a
diagnostic and never as a roll. The same applies to R2 and R4 on the React arm: the 1.6.6 set
exercised their class in two rolls of six.

**Texture, no prediction attached:** the verdict rate against 1.6.6's 4 of 6 and 2 of 2
(intervals, no bar — N=6 cannot show a rate change and the 1.6.6 pre-registration §1.3 said
so); correction rounds; greens by repair versus by re-dispatch, counted separately; refused
versus applied patches; qa primary completion tokens against 1.6.6's `3233–6594` — with the
Reasoning pack now landed, reported as measured; `checks_by_environment` per roll.

**Early stop, one direction, as before.** A falsified R1–R7 stops the set: the fix did not work
and the remaining rolls teach nothing about it. A good result is never grounds to stop early.

---

## 5. Sequencing

1. **This plan**, on its own PR.
2. **#1149** — SIP-0105 gains its amendments section with the harvested entries; the PR template
   gains the extraction line. Docs only.
3. **#1131** — the move and the guard, one PR; the reference contract's digests unchanged is
   the proof. The fixes below are written into the module this creates.
4. **§2.2's decision note** to the owner; then **#939 and #1229** as two PRs on the ruling —
   the agent images and the check spec on one lane, the repair handlers and the verification
   gate on the other.
5. **#1153, #1130, #668, then #1123, then #1022** — each on its own branch off main with its
   replay as its test, in that order; #668 before #1123 because #1123's signal reads the
   inventory #668 enforces.
6. **The rider** in parallel on the other lane; **#1087/#1112 after #1131 merges** (a deliberate
   digest change after the move's no-change proof; fixture regenerated on the owner's go).
7. Rebuild agents and runtime-api, verify the loaded modules in-container, one shakeout per
   stack plus the fault-injected diagnostics of §4, pre-register, roll. **No merges to main while
   the set is open.**
8. Record from the per-round evidence; cut 1.7.1 by the seven steps in `CLAUDE.md`. Then 1.7.2
   opens (Loop Honesty, first half) — or, if a prediction falsifies, a 1.7.1.1 with that item
   and nothing else, under §3.1's rule.

Lanes, per the 1.7.0 plan §3: the seam fixes and the loop (scaffold, handlers, executor) on
one; the agent image, test runner, sandbox, CI and packaging on the other. The one item both
wait on is #1131.

---

## 6. What this plan does not decide

- ~~The §2.2 seam ruling.~~ Ruled B by the owner on 2026-09-01, the day this plan was
  written; recorded in §2.2.
- **#668's option.** The issue's fork (typed check / prompt contract / analyze-time diff /
  demote DOM suites); recommendation 1 + 2, stated in §2.3.
- **Whether #598's criterion becomes blocking in-cycle.** Reporting-only this line; promotion
  is a separate, deliberate call on what the rolls report.
- **#1112's signal**, decided in the rider PR or recorded as texture.
- **Whether 1.7.1 is followed by 1.7.2 or by a 1.7.1.1** — §3.1's rule decides it from the
  set's record.
- **The `lite` fault-injection arm** the 1.6.5 plan left to the owner — still the owner's.

---

## 7. Revision history

- **Rev 1 (2026-09-01)** — written the day v1.7.0 was tagged, from the 1.7.0 plan §2.2/§3.1,
  the cut record §2/§4, the 1.6.6 record §3 and the stored artifacts of the rolls named in §1.
  Two corrections to the pack's own issue text, from the tree: `GENERATOR_VERSION` is not the pin
  for stack #1 (the reference contract's frozen digests are), and `envelope_example` is
  stack-neutral and stays. Same day, before merge: the owner ruled B on §2.2's seam decision.
- **Rev 1, as-landed note (2026-09-01)** — §2.1 records how the move and the guard actually
  shipped: the leaf for `base_type_name`, the `_snake` import, and the suffix-vocabulary
  follow-up split out of the move.
