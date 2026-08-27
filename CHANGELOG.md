# Changelog

All notable changes to SquadOps are recorded here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); versions follow semver.

## [Unreleased]

Nothing yet.

## [1.6.5] — 2026-08-27

**The qa-emission patch line, measured on two stacks.** The pack (A–E) makes a truncated qa
emission rarer and cheaper on the Next.js verification scaffold; #772 gives the success-status
default one home; #1120 stops a qa-side failure from emptying the dev repair target; and the
verification-set driver is promoted with its parameters as data. Its evidence is the first
**two-stack** pre-registered set.

### The evidence

Two counting sets on frozen deploy `7ebdb00e` —
`docs/plans/1-6-5-verification-set-record.md`, pre-registered before roll 1 (PR #1124, merged
as `fea4b5d6`) and unchanged throughout, executed overnight under delegation. **Twelve counted
rolls, no voids, no resets, every pre-registered prediction held on both sets; the early stop
never fired. Zero code drift between the measured deploy and the tag.**

- **Next.js+TS: 6 of 6 functional (95% CI 61.0–100%), zero correction rounds, zero cap hits
  (0 of 7 qa primaries against 3 of 8 under the old cap; max 9,148 of 12,288), fills first on
  7 of 7 emissions, every criterion credited on every roll.** Q1/Q2/Q4 — items C and D live —
  were not exercised, which is not passed.
- **FastAPI+React: 2 of 6 (95% CI 9.7–70.0%) — the stack's first authored-mode baseline, no bar.**
  Both greens **by repair**, none by re-dispatch. #1120 held 6 of 6. One scaffold defect sits
  under five of the six rolls' round 0 (#1125: `default: null` freezes a non-nullable field);
  two rolls ended after a **refused** repair patch counted as a round (#1129); roll 1's green
  re-dispatch was discarded by a Next.js-shaped check (#1126) after a harness gap (#1127); roll 3's
  contract was unsatisfiable by construction (#1128) and its qa-owned test defect was never
  routed (#1130). Filed with #1131 (the structural cause, 1.7); the fixes are the 1.6.6 plan.

### 1.6.5 line — the qa emission under the completion cap (plan: `docs/plans/1-6-5-plan.md`)

- **A — fills first** (#998 ask 2, ordering half). The qa fill-mode brief (appendix v4) states
  the emission order: every fill block, then any additive file. A cut at the completion cap now
  lands on the additive file — which #1082 detects and the self-eval re-emits — never on a fill.
  Roll 6 of the previous verification set (`docs/plans/1-6-4-verification-set-record.md`) lost all eight fills to an additive file written first.
- **B — the suite runs on what the task stores** (#1109). `qa.test` derived its suite-execution
  set before the self-eval loop, so a self-eval re-emission that fixed a blocking typed check was
  stored but never run; roll 8 failed on a truncated file whose replacement was already in hand,
  and a correction round was spent rediscovering it. The set is now derived from the artifacts at
  the moment of the run.
- **C — the self-eval merges fills** (#947). Under fill mode the self-eval prompt carries a
  fill-mode addendum naming the slots still unfilled (from the merge record), and its fills fold
  into the primary emission per slot — a missing or rejected slot takes the followup fill, an
  already-filled slot keeps its fill and the re-emission is recorded — then pass through the
  same merge gate (#1087 phantom tables, #1094 element kinds). Replayed on roll 6's banked
  self-eval fills: 8/8 merged where the handler had discarded all eight.
- **E — a qa-only completion budget** (#998 ask 2, budget half). `full-38`'s `eve` entry carries
  `config_overrides: {max_completion_tokens: 12288}`; four of ten qa primary emissions in that
  set sat at or within 3% of the 8,192 cap. The registry clamp (the V38 pin) and the dev
  budget are untouched. Changes `resolved_config_hash`; measured by prediction Q5.
- **#772 — the success-status default has one home.** The contract deriver asserted 201 for an
  undeclared collection POST while the stack #1 skeleton omitted `status_code=` and FastAPI
  answered 200 — an unwinnable contract, gate-mitigated since 08-10 and never fixed. The rule
  (`capabilities/success_status.py`: declared wins, else collection POST 201 / child POST 200,
  else HTTP's 200) had seven homes — three deriver sites, the skeleton, the framing mirror, the
  scaffold gate's allowed set, the Next.js route stub; every one now calls the seam, the
  decorator pins the derived status too, and a structural test fails if a copy returns.
  Reference fixtures unchanged (they declare their statuses).
- **#1120 — a qa-side failure no longer empties the dev repair target.** The analyzer half of
  #1015-A let the failed task's *own* artifact (a free-authored frontend suite the analyzer
  honestly implicated) act as a narrowing site: the language-wide surface was withheld, the #884
  veto removed the qa-owned file from the dev-role target, and every round was dispatched with
  nothing to produce and refunded — found on the first stack #1 cycle since 08-09
  (`cyc_3cde35fa5204`). Own artifacts ride the target but never narrow it; the package-scoped
  surface applies as it did before the analyzer half shipped.
- **D — an own-artifact qa repair can reach a fill** (#970, with #969's brief). Under fill mode
  the shells are merge products, never in `expected_artifacts`, so the own-artifact repair aimed
  at the plan's declared file and a failing fill was structurally unreachable. Now: the target is
  the failing slot's shell, read from the scaffold evidence's fill-layer observations; the repair
  authors under the **same** fill-mode brief as `qa.test` (one composition seam,
  `fill_mode_brief`, plus a repair addendum naming the failed slots with the runner's reason);
  it emits fill blocks, and the handler recovers every other slot's fill from the task's current
  shells, folds the repair's fills in, passes the same merge gate (#1087, #1094) and emits the
  merged shell at the shell path, so the patch overlay supersedes the failed one and the retest
  runs it. Round-trip pinned: recovering the fills from a merged shell and re-merging reproduces
  it byte for byte. Measured by prediction Q4.
- **Tooling — the verification-set driver is promoted** (`scripts/dev/verification_set_driver.py`).
  The scratchpad copies that drove sixteen counted rolls carried the stack, the deploy pins and
  the gate constant as code constants and were hand-edited per set; the promoted driver reads
  every fixed parameter from a set-config YAML (`docs/plans/verification-sets/`, the
  pre-registration's §1 as data), derives the stack from the request profile plus overrides,
  dispatches the P0 seeded-tree check per stack (an unregistered stack is refused, not passed),
  and reads the runtime log window with an explicit UTC zone — the `docker logs --since` defect
  the previous set's record logged against the instrument.

## [1.6.4] — 2026-08-26

**The self-consistency patch line.** Every fix in this line is one shape: **the framework derived
the same declared fact twice and the two renderings disagreed.** The frozen model against the
response floor (#1096); the store's table handles against what a correct application writes
(#1087); the boot audit against the suite (#1079); the ledger's identity against per-file criteria
(#1021); a qa fill against the declared element kind (#1094); the repair target against the file
the diagnosis named (#1015). All three of 1.6.3's rejections were the first of these, and the
repair rounds that failed to land them were the last.

### The evidence

A pre-registered eight-roll set on frozen deploy `5a697dfa` —
`docs/plans/1-6-4-verification-set-record.md`, registered before roll 1 (`39f6abc0`) and unchanged
throughout, executed overnight under delegation. **No voids, no resets.** Six gates decided by
`system:no_open_questions`, two by the pre-registered constant; zero manual intervention on every
roll.

- **8 of 8 functional — 100%, 95% CI [63.1%, 100%]**, against 1.6.3's 5 of 8 on the same project,
  squad, request profile, overrides and config hash. The intervals overlap; per the inherited §1.3
  this is **not a significance claim** on the rate.
- **14 of 14 criteria credited on every roll.** Every 1.6.3 roll had read 8/14–13/15 (#1021).
- **Zero framing re-rolls**; eighteen consecutive cycles have framed on the first attempt.
- **Every prediction the pack made about its own mechanisms held on every roll that exercised
  it**: P0 (seeded tree agrees with the floor) 8/8, coverage 8/8, P2 (audit judges the floor) 8/8,
  P4 (empty emission carries a signature) 1/1. **P1, P3 and P5 were not exercised** — the loss
  modes they were built against did not occur — and unexercised is not passed.

**Mechanism versus luck (record §1.1).** The frozen-tree, ledger and probe fixes are mechanism:
their effect was read on the seeded files before the squad ran, on every roll, and could not have
gone the other way. **The correction loop is not.** Two rolls entered it and **neither was repaired
by it**: roll 6 recovered because the executor re-dispatched the whole `qa.test` task and the second
attempt fit under the completion cap; roll 8 because the self-eval had already fixed the file
before the loop ran. Two safety nets held, two for two, at N=2. The cause behind both is
systematic — **three of eight qa primary emissions hit the 8,192-token completion cap** with ~17k-token
prompts — and this line did not touch it. Had either net failed, the set is 6/8.

### Fixed

- **#1096** — the `nextjs_ts` expander typed every entity-typed field as `string`, so the frozen
  `lib/models.ts` contradicted the response floor on every roll that declared `list[Participant]`
  — the exact case behind all three 1.6.3 reds. Declared entity and shape names now pass through.
  Read on the seeded tree at N=1 on every roll: four rolls declared `list[Participant]` and were
  given `Participant[]`.
- **#1087** — the frozen store exported a table handle for every declared entity, including
  embedded shapes and response projections no correct application writes. `root_persisted_entities()`
  derives which entities are stored as rows of their own; `TABLES` and the harness consume it; a
  fill naming a table the store does not export is rejected at the fill gate with the real tables
  named. Stack #1's per-entity dicts are the same shape and remain a follow-up.
- **#1079** (producer half; closes the pair) — success probes derive `json_has` from the shell's own
  response-shape derivation, so **contract probes now verify response bodies** and the boot audit
  judges them with the shared judge. Five probes with `json_has` on every roll.
- **#1021** — the final-state ledger keyed a result on `(check_id, subject)`, so a develop subtask
  that compiled three files recorded three results under one identity and the last superseded the
  rest: credited nowhere, failed nowhere. The identity now includes the criterion. In both
  directions — a *failed* compile can no longer be hidden by the next file's passing one.
- **#1015 part A** — the repair target was the entire application in 18 of 18 rounds of 1.6.3's
  reds. The contract now carries endpoint ownership as data on `nextjs_ts`, an in-suite probe
  failure indicts its owning slot, the language-wide fallback is withheld when a site is known, and
  the analyzer's `implicated_files` are verified against the failed inputs before use (#968 slice).
  **Unexercised live**: neither correction this set was a dev repair.
- **#1094** — a qa fill contradicting the element kind the floor pins is rejected at the fill gate,
  with the declared kind and the fix named; roll 5 of 1.6.3 had discarded a correct repair on
  exactly this. Replayed over all 72 banked fill slots of the 1.6.3 set: only roll 5's two fills
  flag. **Unexercised live.**
- **#998** (detection) — an empty emission says which kind of nothing it was: `cap_exhausted`,
  `empty` or `unextractable`, from the token facts the call already reports, with the remedy named
  per kind. The generic repair path had attached no marker at all for an empty response — the
  source of 1.6.3 roll 5's zero-byte repairs. Exercised on roll 8's repair (1/1) and two in-task
  develop emissions.
- **#1089** — the framework version is single-sourced from `pyproject.toml`; installed metadata is
  read only when no source tree is present. The CLI had reported 1.4.0 on a 1.6.3 tree.
- **1.6.3 record corrected** (§6, PR #1095): its two "false rejections" were not. All three rejected
  applications failed the frozen response floor at every round; #1087 was a second failure in two.
  The 1.6.3 CHANGELOG section, release package and GitHub Release carry the correction.

### Known and named, not fixed

- **The qa completion cap** — three of eight qa primary emissions at 8,192 tokens with 16.7–17k-token
  prompts, recovered by fallback each time. #998's ask 2 (fills first, a budget, or the prompt
  shape) now has its data. This is 1.6.5's headline (`docs/plans/1-6-5-plan.md`).
- **`qa.test` self-eval versus suite ordering** (roll 8) — a self-eval re-emission that fixes a
  blocking typed check is stored as the task's artifact, but the suite has already run against the
  broken file; the loop then pays a correction round to rediscover the fix. Raised in the record
  (§5.1), not yet filed.
- **#947, #969, #970 observed live** in roll 6: the self-eval's re-emitted fills are discarded; an
  own-artifact qa repair cannot reach fills. Recovery came from the executor's re-dispatch.
- **The root-table rule's single-object edge** — shakeout 1 and roll 8 declared a single-object
  response entity and the store gave it a table; nothing asserted on it.
- **Instrumentation** — whether the aimed-retry prompt renders the #998 signature is unobservable
  from stored state (LangFuse's 10,000-character input cap; the executor's retry log does not echo
  the marker).
- **#1099** — sixteen integration tests fail identically on every run of main and nothing runs them
  in CI (#242). 1.7.

### Scope of the evidence

Same scope as 1.6.3: `full-38` (qwen3.8:27b) with `build_profile=nextjs_ts` and
`dev_capability=nextjs_ts` on `group_run`. `full` (qwen3.6) remains the canonical squad.

**Code drift between the tagged tree and the validated deploy: zero.** Main after `5a697dfa` is the
pre-registration, the record and this release commit — documents only.

**Pinned fixtures moved, deliberately and once** (owner-cleared 2026-08-25): `GENERATOR_VERSION`
7 → 8; reference contract v10 (`contract_v10_json_has_1079.yaml`, classified `ambiguity_removal`)
beside v9; the reference scaffold manifest's `expanded_tree_hash`. Stack #1's contract v10 is
byte-identical (ownership is presence-keyed).

**No SIP promotions.** This line's fixes are issue-driven. SIP-0104 stays `accepted`: 1.6.4 extends
its fill gate and moves its generator, but its §9 extraction of proven semantic patterns and stack
#1 parity for #1087 remain open.

## [1.6.3] — 2026-08-25

**The measurement patch line.** 1.6.2 merged roughly twenty fixes and none of them had been
measured. This release ships three fixes and, for the first time, a **rate**.

### The evidence

A pre-registered eight-roll set on a frozen deploy — `docs/plans/1-6-3-repeatability-set-record.md`,
registered before roll 1 and unchanged throughout. **No voids, no resets.** Every gate was decided
by `system:no_open_questions`, so zero manual intervention is literally true rather than
true-by-ruling.

- **5 of 8 functional — 62.5%, 95% CI [30.6%, 86.3%]** (verdict *and* boot audit *and* zero
  intervention). The interval is wide and was pre-registered as such: this establishes a baseline,
  it does not claim an improvement it cannot detect at N=8.
- **8 of 8 delivered applications booted** and answered their declared status codes.
- **Zero framing re-rolls across all eight**, and ten consecutive cycles have now framed on the
  first attempt — against **three** framing runs for the pre-1.6.2 green roll. That is 1.6.2's
  success-status single-sourcing (#1067/#1070A), measured rather than asserted.

**The finding that outranks the rate — corrected 2026-08-25 (record §6):** the cut-time reading
was that two of the three failures were the framework wrongly rejecting a working application
(#1087). The stored per-round test reports say otherwise: all three rejected applications failed
the frozen response floor of the join probe at every round, and the phantom-table assertion was a
second failure in two of them, never the only one. The loss mode is the repair round not acting on
a correct round-0 diagnosis — wrong file emitted, nothing emitted, or a correct repair discarded by
a contract-violating fill (#1094). #1087 stands as a defect; its yield on this set was zero rolls.

### Fixed

- **#971** — a failed task's emission is banked for triage instead of discarded. Before this, the
  one artifact guaranteed absent was the one that *caused* the failure. Triage-only, with three
  independent exclusions so known-bad bytes can never reach a workspace or the deliverable. The
  set banked 44/48/11/48/11 failed emissions on the rolls that needed them, and roll 1's root
  cause was traced by reading artifacts that would not previously have existed.
- **#1082** — an emission that stopped mid-construct is caught at the task that wrote it, rather
  than surfacing later as the consumer's test failure. Validated against all 4,513 scannable
  source artifacts in the banked corpus: 8 flags, every one a genuine truncation, zero false
  positives. Two false positives found *during* that validation drove real fixes (JSX punctuation
  read as a regex opener; parens counted inside JSX text) rather than a tuned threshold.
- **#1079** (parity half) — the boot-audit oracle and the in-cycle probe runner judge a contract
  with the same code. The oracle had re-implemented the expectation block and carried two of the
  three kinds, making the more trusted of two judges the more permissive one.
- **#1076** — the release package captures cycle evidence instead of reporting that it did.

### Known and named, not fixed

- **#1087** — the frozen store exports a table handle for every declared entity, including
  embedded shapes and response projections no correct application writes. Two of this set's three
  rejections. Fixing it moves the generator hash, so it is a deliberate 1.6.4 scaffold change.
- **#1079** (producer half) — `json_has` still has no producer, so **contract probes do not verify
  response bodies**. The boot audit certifies that an app boots and answers with the right status
  codes, not that it answers correctly. Roll 5 is the demonstration: rejected for a real missing
  field, audit passed.
- **#1021** — `criteria_unevidenced` never settled across eight rolls on one frozen deploy (1–5
  `vc-compiles-*` dropped per roll). Marked confounded before the set opened; the set is now the
  largest same-configuration sample the question has.
- **#1089** — the single-sourced framework version reads stale editable-install metadata. Found
  during this cut.

### Scope of the evidence

The set ran `full-38` (qwen3.8:27b) with `build_profile=nextjs_ts` and `dev_capability=nextjs_ts`
on `group_run`. `full` (qwen3.6) remains the canonical squad and the meaning of every historical
record; this set says nothing about it. Nothing in eight rolls was truncated, so #1082 demonstrated
only that it does not reject healthy work — its catching behaviour rests on the corpus sweep.

**Code drift between the tagged tree and the validated deploy: zero.** The freeze held from roll 1
to the tag.

## [1.6.2] — 2026-08-24

The information-flow patch line. Every fix here is one shape: **a fact the system
already holds, not reaching the agent judged against it** — and the release is the
first in the 1.6 line validated by a green roll with an independent boot audit.

**Cut evidence.** `cyc_79eebcb82205` / `run_9c879ff5458e`: verdict `accepted`, zero
failed checks, 5/5 contract probes verified — and the delivered application
independently **installs, builds, boots, answers every contract probe over real HTTP,
and its UI reaches every path it requests**. The verdict and the oracle agree, which is
the standard SIP-0096 exists to hold and the thing 1.6.2 could not previously show.

**Telling an agent what it is judged against:**
- #1029 — the frozen shell spine pins the success body's declared floor: required fields
  present, declared collection element kinds honoured. A floor, not a schema — every
  exclusion is a false-positive source, and the pin was replayed against banked green
  trees before it gated anything.
- #1042 — the declared success status reaches the developer by derivation. It previously
  survived only as a TODO comment inside the fill body the fill replaces.
- #1060 — the repair receives **every** manifest surface the initial author does. Three
  were missing; two of them (error contract, model surface) had renderers that had been
  producing empty output since they were written.
- #1002 — the detector's inspected-file inventory reaches the record, so a clean verdict
  is distinguishable from a detector that never saw the file.
- #1015 (B/C) — the repair is told to change the minimum, and can see "attempt N of M".

**The success status stops being authored three times** (#1067, #1070 part A). The status
existed in seven places, three of them independently authored — manifest, plan prose,
handler code — while `scaffold_contract` already derives it from endpoint shape. Five
incidents in three weeks took four fixes before anyone counted the recurrence.
- #1067 — a declared status contradicting the derived default must carry a `decisions[]`
  entry naming the endpoint **and** stating the status. Silence becomes the safe default:
  the rule decides, and there is nothing to disagree with.
- #1070 part A — the plan stops restating statuses. The authoring rule had *instructed*
  the copy ("an enforced non-200 status must be STATED"), because prose was once the only
  channel to the implementer; #1042 and #1063 replaced it. `cyc_79eebcb82205` was rejected
  twice, on two differently-named endpoints, for two documents disagreeing about an integer
  neither needed to decide.

**Correction-loop integrity:**
- #1053 — an emission containing nothing is not an attempt. A prior roll spent two of
  three rounds on zero-byte files while holding a correct, stable diagnosis; the refund
  is bounded so a producer that never emits still terminates.
- #761 — the `tests_pass` signature stops collapsing where the runner emits no machine
  report, so A4 can tell REPEAT from SHIFTED on pytest.
- #1030 — `framing_max_rerolls` defaults to 2; #522's free re-roll was dead code.
- #880 — `runs retry` after a failed run, broken by construction.

**Evidence integrity:**
- #1021 — a contract criterion with no result row stops being a silent fourth state;
  `criteria_unevidenced` separates "never ran" from "ran and failed". Reporting from
  production on the cut roll.
- #1022 / #1055 — containment findings for additive suites and for insert-as-update in
  route handlers. **Banked, deliberately not enforced**: #1049 is this line's own
  demonstration of what a rejection gate costs when its premise is never checked
  against real traffic.
- #980 follow-up — the dropped additive suite is recorded, not just the weakened fills.

**Gates and scaffold:**
- #1049 — the framing omission check reads both channels. #1042 made its stated premise
  ("the implementer will default to 200") false, and it was costing one to two re-rolls
  per cycle, dead-ending correct framings.
- #1055 — the frozen store gains `update(table, row)`. Its whole write surface was
  `insert`, which is `push`, so persisting a change had no correct form; two independent
  authorings on two models both stored duplicates instead.
- #972 — the regression gate no longer exits 0 when ruff is absent.
- The blueprint falsification gate stops depending on xdist's work distribution — it
  passed at 4 workers and failed at 20 on the same commit, so its verdict tracked the
  machine.

**Not exercised by the cut evidence, stated plainly.** The green roll ran on `98eb805e`.
Three changes merged after it launched and ride this tag without that roll having tested
them: #1064 (the store `update` seam — additive, a new export, no existing behaviour
altered) and **#1067 / #1070 part A, both authoring-facing behaviour changes**. They are
the right fixes and they are green in CI, but the boot-audit evidence above does not cover
them, and the first roll of 1.6.3 is what will.

**Known and named, not fixed:** #1021's underlying mechanism (why those two compile
criteria produce no row), #1054 (a repair routed to qa while the lead named dev task
types — 3.6 only, never fired on a 3.8 roll), #1070 part B (the manifest's own
`success_status` field remains authorable where the rule decides it — blocked on the
reference-manifest question).

## [1.6.1] — 2026-08-22

The correction-loop and framing-information patch line — six fixes, every one earned by the
V38 window's banked evidence, each validated live before the cut.

**Correction-loop integrity:**
- #1017 — a failed retest's `test_report.md` persists (evidence only; workspace files never
  stored, protecting the rejected-candidate exclusion). Four reports banked on validation
  night; every triage instant.
- #1014 — emission-side ownership veto: a foreign-role repair cannot land the failed task's
  own artifacts (the #884 completion; fired live on its first shakedown, killing exactly the
  slot-6 incident class).
- #1011 — the registry completion clamp rides the base chat path; observed binding at
  exactly 8,192 on two live repairs.

**Framing information:**
- #1013 — manifest↔plan consistency + completeness gate at plan validation, with the
  per-stack `skeleton_pins_success_status` fact at the S1 seam and the rule taught in the
  authoring-rules asset (v4). Caught a real contradiction on the first live framing it saw.
- #795 — error-envelope authority settled: nextjs unified on `message` (generator v5),
  root-contradicting `error_contract.shape` declarations rejected at M2, taught in the
  manifest authoring rules (v2).
- #913 — error envelope pinned in the frozen shell spine (generator v6); sandbox-proven
  against banked artifacts: no false rejection on a green app, exactly the pinned shells
  fail on a mutated envelope.

**Cut evidence:** red confirmation shakedown (correction paths exercised organically) +
full green roll on the integrated deploy (`cyc_3095fe4bdb83`: accepted 23/23, boot-audit
PASS, three honest qa-side repairs on the one deliberately deferred class). Filed at the
cut: #1029, #1030, #1031.

## [1.6.0] — 2026-08-21

In-flight **1.6 — the Authorship release**. The rung above 1.4: from *filling* a given
interface design to **authoring the design from the PRD**. Lane M is SIP-0103
(Squad-Authored Manifest, accepted 2026-08-07); Lane S is Generalized Build Capability,
whose Stack Blueprint SIP is deliberately held until a second real stack exists.

Landed so far, gates before author: the queue-front fixes (#762 bind-mode preflight,
#766 Langfuse prompt linkage, #770 SIP promotion), then the M-ladder — M0a contract
derivation pinned to the deployed reference pair (#777), M0b derive-at-seed when a cycle
seeds a manifest but no contract (#779), M3 winnability gate (#781), M2 schema gate and
the `decisions[]` judgment record (#783), M6 authoring failure taxonomy (#785), and **M1
the authoring stage itself (#791)** — a dedicated `development.author_manifest` framing
step that revises against the gates, replacing the ungated proposer-side emission it
relocates, and **#796** — the fix V4 roll 1 exposed: an authored manifest now derives and
pins its contract mid-framing, so the plan authors bind to the design their own squad just
wrote instead of inventing paths, and every contract-gated net engages. M4 (the human
manifest gate, narrowed to question-gated review — #807: the gate stops only when the
design declares an unresolved decision, and the question itself is what the operator is
shown; a design that asks nothing records a distinguishable system approval and proceeds) and **M5 authoring provenance (#803)** —
a system-owned block recording mode, cycle, task, attempt count and the *classified* reason
for each revision, excluded from the manifest's canonical projection so recording how a
design was written can never move the hash its contract binds.
**#811** closes the revision loop: a design question the gate asks can now be *answered* —
`RETURNED_FOR_REVISION` re-executes framing with the notes and the prior manifest as
authoring context, bounded by `manifest_max_attempts`, instead of stopping the sequence for a
manual retry run. It **restores the prefix the note does not invalidate** via SIP-0101's
checkpoint translation — enabled by framing task ids becoming deterministic in the same
change — and re-runs from the technical design, so the design answers the note rather than
describing an interface the revised manifest no longer has.
**#812** makes a gate decision say who made it. `decided_by` was a hardcoded `"system"` with
a TODO beside it, so all 140 human approvals in the project's history carried the word that
means *no human was involved* — in the same namespace the machine paths use. It now composes
`{actor}:{principal}` from the request identity, and an agent can declare itself
(`--as-agent`) since a token cannot tell.
**B1 (#809)** closes the one item whose omission would have been permanent: rejections are
now classified at the moment they happen — plan-validation by producing validator, authoring
by M6 class — so the pre-memory recurrence baseline Cross-Cycle Memory will be measured
against is capturable. Read by nothing in 1.6, deliberately.
**Track S opens with S1**: the five per-stack facts — expander, fill slots, QA namespace,
harness boundary, check-stack vocabulary — collapse from four module-level dicts plus one
inline answer into a single `ScaffoldStack` registration. Pure refactor; the reference
manifest and contract hashes are unmoved. It removes a silent-omission trap: `fill_slot_paths`
guarded on whether a stack was *registered* and then returned FastAPI's slot map to whoever
asked, so a second stack would have inherited `backend/routes.py` with nothing objecting.
Plan: `docs/plans/1-6-0-authorship-plan.md`.

Closed out 2026-08-21 at the cut. Later stages beyond the narrative above: Stage 2g
rewrote the Stack Blueprint Contract against main and it was **accepted 2026-08-17 with
its unbuilt parts named (SIP-0105)**; SIP-0104's deterministic verification scaffolding
carried both measurement windows. **Release gate MET**: the pre-registered V7
authored-mode FAY window closed **amended 4/6 functional** (dual record 3/6 pre-registered
instrument / 4/6 corrected, #1004/#1005, both always reported), zero manual interventions;
the V38 model-comparison window (qwen3.8:27b) re-exercised the full authored path at
**4/6, roughly half the wall-clock**, and its §6 synthesis records the failure-class
shift toward framing-rooted contract violations. **Cut basis:** zero code drift between
the window-validated frozen deploy `f7a5e0a2` and main (docs only); full regression 7,615
passed; Guard 1a/1b green. SIP-0103 promoted to implemented at the cut. Post-window
queue deferred to 1.6.1+: #1011, #1012 (byte-verified reproducer banked), #1013, #1014,
#1015, compile-credit bookkeeping.

## [1.5.0] — 2026-08-07

**Finish the Promises, Extract the Proven** — the odd-minor stabilization release.
Feature-free by rule and verified as such at the cut: no new contract fields, manifest
fields, request-profile capabilities, or squad-facing handler/workflow surfaces, and
**contract v9 / manifest v4 byte-stable line-wide**. 34 PRs, one per issue, across three
gates. Plan: `docs/plans/1-5-0-stabilization-plan.md`.

### Added — verification integrity, finished
- **SIP-0096 implemented**, not merely promoted. Gate waivers as additive schema plus CLI
  `--waive/--waiver-reason`, where a waived check is recorded and disclosed but the
  verdict itself is never rewritten (#682, migration 1030); wrap-up consumes the
  `CycleOutcome` seam and **clamps** over-claiming closeout prose to the evidence it cites
  (#683); inert-cycle detection derived on read — a squad that stops producing evidence is
  detected rather than read as passing (#684). The promotion PR also caught its own
  premise delta: the audit's fourth normative item (a SKIP-only pulse is zero evidence,
  not a pass) had been dropped from the plan and was implemented rather than waved through.
- **qa joins the typed-acceptance seam (#670)** — authored checks *and* framework
  injections now reach both authoring surfaces, closing the gap shk-3 found where
  `undefined_names` stopped at the qa boundary.
- **SIP-0101 Cycle Replay Harness, minimum slice** — maintainer-only replay from a
  recorded execution boundary, rails before mechanism (#735–#737, migration 1020).

### Added — correction evidence and termination
- **#687** captures the application's real traceback from the probe runner's spool delta;
  **#431** makes emission accounting explicit at four producer seams so extraction loss is
  *named* rather than silently truncated. Together: the correction loop's long-standing
  diagnosis blindness.
- **#435** progress-aware correction termination — a moving chain is never cut short, a
  repeating one never burns the budget.
- **#629** a test suite whose assertions contradict the frozen contract is a blocking
  failure; the prose half ships advisory by construction.

### Changed — the structural quarantine
- **#663** the executor's context assembly becomes a declared `ContextAssemblyContract`
  per task type, replacing five tables and three branches — landed in three golden-first
  slices, 19 goldens captured *before* each refactor and byte-identical through.
- **#331** the 1,887-line planning handler splits into a package by authoring stage; a
  pure move, AST-verified 20/20 top-level names, every pre-split test passing unmodified.
- **#730 + #504** every typed check declares its own governance metadata in one registry
  with required, no-default fields — a new check cannot be added without declaring who
  owns its failures and whether it replays — plus the blocking `fill_slot_signature` check
  and a generated menu pinned by drift tests.
- **#481** stranded-cycle detection as a fourth startup sweep, read-only, emitting the
  exact recovery command. Its first live boot surfaced two genuinely stranded cycles that
  had been invisible for weeks.
- **#734** every acceptance verdict names the workspace revision it measured.
- **#506** transport owns the full task lifecycle, fixing retry attempts that never
  re-entered RUNNING; **#724** ~20 config reads swept onto `resolved_config`; **#452** the
  last live-path prompt prose moved into managed assets with byte-equivalence pinned.

### Verified as a line
Two green confirmation shakedowns on integrated deploys — the Gate-2 exit
(`cyc_ea0b82cfbd17`, accepted, 17/17, zero corrections) and the cut shakedown
(`cyc_b07183b3cf5c`, accepted, 36/36 checks, 15/15 contract criteria, zero corrections,
zero machinery defects) — plus a live replay demonstration, a waiver end-to-end probe, and
a replay zero-diff over the stored green corpus.

### Filed forward
#761, #762, #668's suite half, #707, `package_builds` (declared-unbuilt with its trigger
recorded in the registry), SIP-0102 migration steps 3–7, SIP-0092's M3, and the #557
post-retest governance review (SIP drafted) → v1.6+.

## [1.4.4] — 2026-08-05

**No False Verdicts** (verification integrity). Every verdict is earned: greens are
enforced, reds are explained, budgets are honored. Seven premise-verified fixes, one PR
each — **#427** terminal failure reason persisted on the run row and surfaced by
`runs show` (migration 1010); **#426** builder offer and gate net both key off configured
`build_profile` via the new single-source `Cycle.resolved_config()`; **#715** a qa task
whose declared artifacts can never satisfy required `tests_pass` is rejected at authoring,
on both gate seams; **#423** an authored check the evaluator cannot run is an evidence gap
and never `passed: true`; **#424** plan-authoring collapse is a gate rejection, never a
silent static-step fallback; **#511** the time budget gates every dispatch lane including
correction chains; **#571** semantic-memory recall prefilters in-query with a valid cosine
metric.

Verified as a line on an integrated overnight deploy: in-container validator replays
against stored artifacts, a designed-failure probe budget-killed at the first boundary,
and confirmation shakedown **shk-5 green** — verdict accepted, zero corrections, the new
nets silent on a well-formed roll.

## [1.4.3] — 2026-08-04

**Lifecycle Hygiene** — a cycle can neither strand the next one nor fail silently. Seven
hash-stable fixes, five planned plus two found *by the deploy window itself*: **#373+#529**
focus-lease reaper across cancel routes, executor finalize, and startup sweep; **#561**
activity self-heal; **#498** interpreter resolution (bare `python` resolves to
`sys.executable`, strictly after the safelist gate); **#572** queue capability honesty;
**#573** a redaction char-class overrun that swallowed adjacent log fields; **#710**
stranded-mode sweep; **#712** owner-checked lease release.

**Found by the window, not the tests:** #710 — pre-deploy capture showed six agents in
`cycle` mode holding zero leases, so focus arbitration had been silently inert for 64
cycles over two weeks. #712 — a cancelled run's late finalize would have stripped the
*relaunched* run's focus, unreachable before this patch only because #529's leak was an
accidental guard.

Confirmation **shk-4 green**; 9/9 leases released, zero residue, no restart.

## [1.4.2] — 2026-08-04

**Correction Aim + Authoring Prevention** — the correction chain aims true, and known
authoring classes can't be authored. Every fix traces to shk-2's diagnosed loss chain,
where a one-line defect survived two correction attempts: **#688** repair targeting now
leads with the owning fill slot (failed probe → endpoint → contract's endpoint→slot map);
**#691** scaffold-frozen paths excluded from interface-drift detection; **#689**
`undefined_names` (pyflakes F821) framework-injected at emission acceptance on `.py` fill
slots — the call-time NameError class every prior gate missed; **#686** plan-shape rules
rendered into the four authoring prompts.

**Corrected premise, recorded:** #691's filing blamed an unauthorized dev write;
provenance showed the artifacts were scaffold-seeded and hash-identical to the contract's
frozen entries. The real defect was drift detection reporting the scaffold's own probe as
producer drift — a permanent false positive on every bind-mode cycle that corrects. The
issue was rewritten before it was built.

Confirmation **shk-3 green**, zero corrections; #686 confirmed at framing in its strongest
form (a compliant plan on the first roll, where shk-1 needed a rejection plus a re-roll).

## [1.4.1] — 2026-08-03

**Hardening Patch** — the five hash-stable fixes filed as known-open at the 1.4.0 cut, one
PR per issue: **#672** runtime_activities reaper (startup + finalize sweeps through the
abort choke point); **#671** module-existence validation at the gate; **#673** the first
plan-wide cross-task rule, rejecting two tasks that claim the same expected artifact;
**#667** repair-envelope testid threading, with the surface re-derived from the manifest at
repair-input construction; **#669** framing re-rolls revise instead of re-dicing, turning
`framing_max_rerolls` into a revision budget.

Contract v9 / manifest v4 unchanged (hash-stable by construction). #668/#670 deliberately
held for the next window. Plan: `docs/plans/1-4-1-hardening-patch-plan.md`.

Confirmation shakedowns unscored by pre-declaration: **shk-1 green** — framing authored a
real dual claim, #673 auto-rejected it (a live true positive), #669 threaded the rejection
into a surgically revised re-roll, and implementation cleared all 14 criteria with zero
corrections. **shk-2** fired #667's trigger live, then surfaced a *pre-existing*
correction-chain loss mode diagnosed to root cause and filed as #687/#688/#689.

## [1.4.0] — 2026-07-31

**The Verified Canonical App Build** (133 merges since 1.3.1) — first dual-lane-headline
feature release. Lane M's golden-path stack (scaffold + verification contracts +
frozen-file enforcement) plus Lane S's Ephemeral Application Sandbox 1.4 floor.

**Exit evidence, pre-registered:** Functional App Yield window 3 — **6/6 functional
(100%), 5/6 fully green, five consecutive greens**, unfiltered, on frozen deploy
`9522ef4d`, in **seeded-manifest (bind) mode**; the bar was ≥4/6. The cut gate's original
condition ("≥3 consecutive golden-benchmark runs, squad-authored-manifest mode") was
superseded by owner decision 2026-07-28 and executed at the cut.

**What this honestly demonstrates:** given a PRD **and a fully specified interface
manifest**, the squad implements, verifies, and delivers a working app. What remains
unmeasured — by the original gate's own correct reasoning — is squad-authored-manifest
mode; that rung moved to v1.6 as a headline. The claim is *a specified contract, not
PRD-to-app*.

Entries are grouped by arc rather than listed per-PR; the volume
here is dominated by the correction/repair loop, which had to converge before any of the
scaffold work could be measured at all. Bare `#NNN` references in this section are **pull
requests**; the issues they close are named in the PR bodies.

### Added — the golden-path scaffold stack (Lane M)
- **SIP-0099 Contract-First Build Scaffolding** — an interface manifest expands to a
  deterministic walking skeleton, and dev tasks *fill declared slots* instead of
  authoring structure. Phase-0.5 spike (#428 hand-written group_run manifest, #429
  `fullstack_fastapi_react` expander proving the empty skeleton builds and boots) then
  phases 99.1–99.3 (#482 expander canonicalization + skeleton CI gate, #486 manifest in
  framing, #487 executor materialization + fill-only develop).
- **SIP-0098 Verification Contracts** — acceptance criteria now come from a contract the
  cycle is *bound* to, not authored per-plan. Proposed #475, accepted with implementation
  plans #477; phases 98.1–98.4 (#478 contract schema, #483 expander emission +
  emission-time gates, #488 orchestration binding — "bind, don't author", #489 behavioral
  probe runner + coverage accounting); 98.5 migration slices (#491 live probe emission +
  PRD v0.4 split, #493 `contract_gate emit` mode for operator seeding).
- **SIP-0100 Scaffolded Test Harness and Frozen-File Enforcement** — frozen scaffold
  files are restored when a producer rewrites them, and unauthorized slot emissions are
  dropped. Prototype #538, accepted #539 with plan #540; phases 0–4 (#541 characterization,
  #542 harness contract, #544 authorization spine + live frozen-ownership enforcement,
  #547 evidence + QA write-scope, #548 contract-compliance circuit breaker, #549/#550
  deterministic replay, path/atomicity matrix, no-regression).
- **SIP-0101 Cycle Replay Harness** — proposed #594, revised #595, accepted with a
  Phase-1 plan #596. Implementation deliberately held until the 98.5 baseline closes.
- **`function_defined` acceptance check (#533)** — a style-immune "this file defines N
  functions matching a prefix", replacing regex-on-source criteria that failed on
  formatting rather than behavior.

### Added — verification evidence integrity (SIP-0096, Phases 1–3)
- **Phase 1 (#369):** the integrity core — pure aggregation, evidence families, and the
  `blocked_unverified` verdict. Cycle-level `request_profile` provenance (#367).
- **Phase 2:** task-result verification normalized into the ledger with honest-red guards
  (#378); final-state resolution for re-verified checks (#386).
- **Phase 3:** `CycleOutcome` roll-up pure core (#412), per-run `RunVerificationSummary`
  persistence (#416), derive-on-read `CycleOutcome` + cycle-detail surface (#418).
- **Check governance:** canonical framework-check registry rejecting unknown
  `required_checks` ids (#396); required-check tooling parity at preflight + a `doctor`
  verification category (#398); `required_files` enforced at run completion (#390) and
  recorded as a `CheckResult` (#402, corrected builder seam #405); fullstack
  `frontend_build` as evidence (#408).
- **Honest verdicts:** a non-succeeded run never reads `accepted` on zero evidence
  (#409); cycle outcome reconciles per-check evidence across runs (#446); typed
  acceptance reaches the builder seam with wire-shape criteria coercion (#421).

### Fixed — correction and repair convergence
- **Repairs are verified behaviorally, not structurally.** Re-run the failed check on a
  patch (#385); accept behaviorally-verified patches instead of re-rolling repaired tasks
  (#413); re-execute repaired `qa.test` suites before acceptance (#461); reject patches
  whose intra-package imports can't resolve (#592).
- **Repair targeting** — a correct diagnosis is useless if the repair edits the wrong
  file. Retarget onto the drifted source rather than the failing check's tests (#532);
  target the union of drift files and the failing artifact (#534); dependency-scoped
  targeting so no-drift `qa.test` failures reach the source under test (#536); the drift
  branch reaches the fill-slot source (#554); repair artifacts re-homed onto expected
  paths before overlay (#517).
- **Repair context** — the recurring root cause was the system holding an authoritative
  fact and never putting it in front of the agent that needed it. The dev repair gets the
  same fill-only constraint as develop (#555); `resolved_config` threading + frozen
  enforcement on the repair path (#562); deterministic interface-drift diagnosis feeds the
  repair (#527); contract expectations, emission integrity and candidate-free workspaces
  (#564); error-contract block, exit-4 locus, initial-QA expectations (#585); the initial
  dev prompt carries the scaffold contract it was filling (#589); repairs are told the real
  model names instead of guessing them (#604).
- **Workspace correctness:** the correction workspace is re-resolved from live stored
  artifacts each attempt, so the loop can see its own progress (#535).
- **Policy and routing:** `continue` cannot discard executed-failed required checks (#449);
  locus-keyed QA repair routing + emission recovery with aimed retry (#569); cancel reaches
  the dispatch boundary so repairs stop on a cancelled run (#587); four shakedown fixes
  raising roll-success odds (#505).
- **Removed** the unconsumed `qa.validate_repair` step (#558) — its verdict was never read.

### Fixed — the scaffold's own contract
- Success status is declared in the manifest so the skeleton can satisfy its own probe
  (#600), and is included in the content hash (#601).
- The scaffold-owned status code is held inside fill slots (#602); the router takes no
  prefix — stated in the stub and enforced on emission (#608).
- The in-memory store the manifest already declares is emitted rather than left for the
  planner to invent (#606).
- The seeded scaffold reaches `qa.test` and `builder.assemble` (#445).

### Fixed — acceptance checks and emission parsing
- `import_present` matches relative imports (#437) and dotless specs (#442); the backend
  import check imports package members by qualified name (#471); the delivered backend is
  verified to import, not just its tests (#393).
- `regex_match` criteria restricted to document artifacts — the style-lottery guard
  (#468); AST checks skip non-Python files instead of erroring (#607).
- A missing command binary skips instead of erroring (#463); failed suites disclose
  exit-code meaning (#514); the coverage denominator comes from the bound contract rather
  than dispatched checks (#513); behavioral rows are stamped with their contract criterion
  ids (#519); unbound criteria attach to the tail `qa.test` at dispatch (#516).
- Package dirs stay off the test runner's `PYTHONPATH` (#455); the runner refuses
  non-pytest suites precisely, and the QA fragment gained a discovery contract (#518).
- Fenced-parser hardening: nested fences (#432), path-prefix on the first body line (#490),
  path-labelled headers and unterminated-at-EOF fences (#528).
- Probe readiness accepts any HTTP response rather than only 200 on `/health` (#521);
  create-probes expect 201, resolving a contract that contradicted the PRD it verifies
  (#523); typed sample values for probes (#526).

### Fixed — plan authoring and framing
- A system plan-validation rejection re-rolls framing instead of killing the cycle (#525);
  pre-gate plan rejection records a system gate decision instead of dying silently (#476);
  the inter-workload gate stops the sequence on `returned_for_revision` (#467).
- Plan substitution preserves the workload-invariant tail (#440); invariant tasks run in
  canonical order, assemble before `qa.test` (#459); warning/info-severity criteria
  violations are tolerated rather than rejecting the plan (#530).
- Command-safelist lint at the authoring boundary + manifest retry runway (#425);
  style-dependent regex criteria forbidden in guidance (#438); the bind-criteria proposer
  leaves `criteria_refs` empty for contract-owned files (#537); the strategy proposer
  supplies `guidance_id`, unblocking multi-role framing (#485); `qa.test` prompt content
  routed through the fragment system (#450); test-isolation doctrine in the QA fragment
  (#460).
- Bind mode requires a framing-emitted interface manifest (#495) and seeds the canonical
  one (#497).
- Deterministic fill-slot binding at plan authoring landed (#552) and was **reverted**
  (#553) to keep the measurement baseline free of an unvalidated confound.

### Fixed — runtime and ops
- Agent identity is never fabricated (#387); the agent secret is provisioned on deploy and
  fails honestly when absent (#391); runtime-api application logging reaches stdout (#492);
  `init: true` on agent containers reaps subprocess zombies (#543).
- `runs retry` resolves `workload_type` positionally instead of defaulting to `None`
  (#479); forwarding overrides are rebuilt from durable state on mid-sequence entry (#480).
- group_run manifest path param renamed `{id}` → `{run_id}` (#565); anchored hash
  replacement in `regen_fragment_manifest.py` (#453).

### Removed
- Vestigial analysis skills and their dead JSON parsing (#400).
- The dead SIP-0.8.8 skill handler layer, end to end (#403).
- Warmboot operational artifacts, with the era's lessons distilled for the book (#406).

### Docs & SIP lifecycle
- **Proposed:** Contract-First Build Scaffolding (#383), Verification Contracts (#475),
  Cycle Replay Harness (#594), LLM Emission Contracts (#570), fine-grained issue
  enumeration (#384), process lexicon (#599).
- **Accepted:** SIP-0098 + SIP-0099 with both implementation plans (#477), SIP-0100
  (#539, plan #540), SIP-0101 (#596).
- Night triage runbook (#609); RuntimeActivity lifecycle requirements (#546); enum-shadow
  architecture guardrail failing CI on status string-literal comparisons (#382); idea and
  vision drafts tracked under `docs/ideas` (#366); CLI cheatsheet corrections (#499).

## [1.3.1] — 2026-07-08

Hardening patch on the 1.3.0 stabilization line — the post-1.3.0 batch surfaced by
the 2026-07-04 independent health assessment, reassigned to the Macbook lane while
Spark was offline. All fixes; no feature SIPs (patches land on either lane anytime,
independent of the even/odd feature parity — #281). Every runtime-affecting change
was live-validated on the deployed stack before merge.

### Security
- **Agent-status writes moved off the unauthenticated `/health` lane (#326).**
  `POST/PUT /health/agents/status` were writable by any anonymous network client
  (the auth middleware allowlists the whole `/health` prefix). They now live at
  `POST/PUT /api/v1/agents/status` behind the `agents:write` scope; `/health/*`
  keeps only GET probes. The middleware allowlist is now **method-scoped**
  (GET/HEAD), so a future write route under `/health` fails closed instead of
  riding the no-auth lane. Agents authenticate their heartbeats via a new
  `squadops-agent` service identity (client credentials, `agent` realm role ⇒
  `agents:write` only); a half-configured identity raises at startup rather than
  silently sending anonymous heartbeats.

### Fixed
- **Concurrent same-agent cycles no longer bypass FocusLease arbitration (#288).**
  `RuntimeCoordinator.request_transition` short-circuited every same-mode request
  to `idempotent_skip` before arbitration, so a second cycle recruiting an
  already-recruited agent free-rode the first run's lease and lost the agent when
  the first finalized. A same-mode request from a *different* lease owner now
  rejects with `focus_lease_conflict` (admission defers the run); a same-owner
  replay still skips.
- **QA agent image now has Node.js so the frontend build check runs (#306).** The
  `qa.test` frontend build check (#290) and vitest shelled out to `npm`/`npx` in an
  image with no Node — every frontend check silently skipped, so a non-building
  frontend shipped green. Node ships in the qa image only (the sole Node consumer),
  declared via a config-driven per-role `system-packages.txt` (the apt analog of the
  existing per-role `requirements.txt` — no role name hardcoded in the Dockerfile).

### Added
- **Broker-hygiene check in `squadops doctor` (#328).** A new `broker` category
  flags queues on the retired pre-SIP-0094 `cycle_results_*` naming scheme and any
  queue holding messages with no consumer (an undrained backlog). Reads queue stats
  via `rabbitmqctl` inside the container (resolved from the compose service name, no
  credentials); an unqueryable broker warns rather than fails. The orphaned
  `cycle_results_*` queues left by the SIP-0094 migration (one with 48 undrained
  messages) were swept.

### Docs & SIP lifecycle
- Filed the **Externalized Build Sandbox** proposal (`sips/proposed/`) — the
  principled long-term home for build/test execution (a `BuildSandboxPort` so agents
  carry no toolchain), with #306 as its interim. Stays `proposed`.

## [1.3.0] — 2026-07-08

First **stabilization release** on the even/odd minor cadence (#281): odd minors are
feature-free by rule, and the big risky structural refactors quarantined out of the
feature releases are the *product*. Spark was offline for this cycle, so the entire
core scope landed from the Macbook lane. Every structural change below was
live-validated on the deployed stack before merge.

### Changed
- **SIP-0097 Dispatched Flow Executor decomposition (#186, #295).** The 3,358-line /
  53-method executor god-object decomposed to 1,805 lines across six sliced PRs
  (#341, #344, #347–#350), extracting five plain injected collaborators: pure hoists,
  **`RunLedger` + `RunCompletion`** (append-only run evidence + terminal-outcome
  mapping — the executor now carries **zero per-run mutable state**, and
  `RunCompletion.finalize(ledger, …)` is the seam SIP-0096 §6.4 wires into),
  **`CorrectionRunner`**, **`PulseBoundaryRunner`**, and **`TaskDispatcher`** (the
  interim dispatch callables were replaced by the real collaborator per AC#9). Slice
  6 carried the arc's one behavior addition (#295): the plan-review gate validates
  the run's materialized implementation plan against the squad profile *before*
  pausing — completing SIP-0095's materialized-plan half. SIP-0097 accepted (PR #340)
  and **promoted to implemented** within this release.
- **`cycle_tasks.py` split into the `capabilities/handlers/cycle/` package (#152).**
  The 3,276-line handler monolith is now per-handler modules behind a compat shim
  (PR #339), preceded by hoisting its copy-pasted helpers into `_CycleTaskHandler`
  (#332, PR #338). Shim retirement rides the importer migration filed in #339.
- **Agent comms migrated from queue polling to a persistent push consumer (#323,
  PR #354).** The entrypoint's 1s open/close `consume()` poll is gone; agents hold
  one long-lived `subscribe()` consumer (delivery-time pickup, `prefetch_count=1`,
  ack semantics unchanged). Removes the consumer-count flapping, up-to-1s dispatch
  latency, and the `aio_pika` "closing" INFO flood that was 99.7% of retained agent
  logs — which also closed #329 (the interim log-demotion mitigation) as obsolete.
- **Dead sqlalchemy `DbRuntime` backend removed (#234, PR #356).** Audit found zero
  production callers (its factory was only ever constructed by its own tests, and
  the one production breadcrumb referenced a method that never existed).
  `src/squadops/ports/` now contains no vendor types in any contract; the `postgres`
  extra and sqlalchemy test pin are dropped. Every active persistence path is asyncpg.

### Fixed
- **Prompt-pack drift broke `merge_plan` fleet-wide (#327, PR #351).** Agents resolve
  prompts from the LangFuse registry, which was seeded once and never re-synced —
  SIP-0093's templates were missing at runtime though the files shipped in the image.
  Deploys now re-sync prompts to LangFuse (production label) as a pipeline step; the
  manifest loader hard-fails on hash mismatch (was warn-and-continue); the regen tool
  maintains the whole-manifest hash; CI guards manifest integrity. Design-debt
  follow-ups filed: #352 (registry runtime guard), #353 (build-time fingerprint).
- **`runs resume` insta-failed since 1.1.1 (#342, PR #343).** The resume route
  pre-flipped the run to RUNNING and the executor then re-issued an illegal
  RUNNING→RUNNING transition — every resume died in ~2s. Found by SIP-0097 slice-2
  live validation; pause→resume→complete now verified live end-to-end (closed #258).
- **Test suite is color-env-proof (#345, PR #346).** Shells exporting `FORCE_COLOR`
  broke CLI output assertions (rich token-splits digits under forced color); all
  assertions now ANSI-strip first.

### Added
- **CI docs-drift guards (#336, PR #357).** Version markers across
  CLAUDE.md/README/ROADMAP must equal `pyproject.toml` (this release's bump is the
  first it enforces), accepted-SIP `Targets:` lines must respect even/odd parity,
  and planning-doc references must resolve — lifecycle-aware, with the historical
  residue frozen in an explicit allowlist.

### Docs & SIP lifecycle
- **SIP-0096 Verification Evidence Integrity accepted** (PR #337, rev 2) — the 1.4
  headline alongside SIP-0091; execution plan in `docs/plans/1-4-evidence-arc-plan.md`.
- **SIP-0095 promoted to implemented** (PR #324); SIP-0091's stale `Targets: v1.3`
  remapped to v1.4 per the parity rule (#335).
- **Docs hygiene pass (#335, PR #357):** ROADMAP stats/tables reconciled (they were
  frozen at 1.0.6), Forward Cadence section added (1.3 → 1.4 → 1.6 → 2.0 pillar map),
  referenced-but-untracked drafts committed (Edge Deployment Profile, Experiment
  Queue), and a registry entry pointing at a never-committed file removed.
- **Drafts filed** (proposed, not accepted): Agent Comms Delivery Guarantees
  (PR #355 — Campaign 1.6 gate candidate), Campaign SIP revision + two-lane/evidence
  plans (PR #325).

### Deferred / follow-ups
- **#288** (same-mode lease bypass — a named Campaign 1.6 gate) slipped this release;
  pulled forward into the 1.4 window as hardening.
- **#331** (`planning_tasks.py` split) and **#333** (entrypoint config-masking
  fallbacks) → 1.5 stabilization backlog.
- SIP-0097 post-arc open questions (residual-method review / optional seventh
  collaborator; `RunOrchestrator` rename + #168 sweep) are standalone follow-ups.

## [1.2.0] — 2026-07-04

First **feature release** on the even/odd minor cadence (#281): even minors carry
features, gated by headline feature SIPs. 1.2.0 is led by three — the SIP-0089
runtime-arc completion, the SIP-0090 Agent Embodiment Substrate (Phase 1), and the
SIP-0095 Cycle Create Preflight — riding a hardening base (#158, #231). Two lanes
fed it: features from the Macbook lane, hardening + supporting decisions from Spark.

### Added
- **SIP-0090 Agent Embodiment Substrate — Phase 1 (core model).** The internal
  substrate for embodied agents: an `Embodiment` lifecycle state machine
  (`unattached→attaching→attached→desynced→reconnecting→detached`) with an explicit
  transition allow-list and a single-active-embodiment-per-agent invariant (enforced
  both in code and by a Postgres partial unique index); resource budget primitives
  (attention/compute/action consumables + a concurrency capacity gauge, with
  non-silent exhaustion made type-unrepresentable); an `EmbodimentStatePort` with a
  Postgres adapter; and an `EmbodimentCoordinator` that validates transitions and
  emits canonical events. No adapter yet — Discord/browser embodiments are later
  phases (#312, #317).
- **SIP-0095 Cycle Create Preflight.** A create-time fail-fast gate: a cycle is
  rejected (HTTP 422 `PREFLIGHT_REJECTED`) when the squad can't satisfy the requested
  workloads' required roles, or names a model definitively not pulled (exact
  canonical-tag match, no family inference). An unreachable LLM backend
  warns-and-allows rather than blocking on missing evidence; warnings surface on the
  create response and in the CLI. `squadops doctor` gained model-availability parity
  via the same shared decision (#298, #309, #311, #315, #321).
- **SIP-0089 runtime-arc completion.** Cycle recruitment now routes through the
  RuntimeCoordinator with FocusLease arbitration (a lease conflict is a deferral, not
  a failure) (#233), and coordinator transitions commit lease + activity + mode in a
  single `RuntimeTransaction` unit of work with live-validated rollback (#244).
- **Validated-fullstack request-profile** — instrumentation + builder + stack for
  end-to-end framework validation (#279).

### Changed
- **Health signal consolidated to a single source of truth (#231).** `runtime_status`
  is now the canonical health signal across every read surface (API single + list
  routes, CLI, both console plugins); it is always-populated (the heartbeat ensures
  the runtime row and reconciliation backfills legacy agents), and the
  `runtime_status || network_status` fallback is gone. `network_status` is demoted to
  a deprecated back-compat field (column drop tracked separately) (#302).
- **Squad profiles consolidated to `smoke` / `lite` / `full`** (#173).

### Fixed
- **CLI now renders cycle-route error messages (#319).** They were nested under
  FastAPI's `detail` and silently dropped — the operator saw `validation failed —`
  with no reason (e.g. the preflight's actionable "pull model X"). Found via live
  cycle validation (#320).
- **Operational hardening (#158)** — configurable adapter timeouts + a DDL↔model
  drift guard; the `_schema_migrations` applier remains idempotent.
- Local-spark bootstrap models reconciled with the squad profiles (#285); QA-harness
  robustness + portable-frontend build fixes (#303, #296, #280).

### Deferred / follow-ups
- SIP-0095's materialized-plan capability check at the plan-review gate (#295) —
  deferred to land with the #186 executor decomposition; the dispatch-time check
  remains the net.
- SIP-0090 Phase 1 budget persistence + composition-root wiring — no live consumer
  until Phase 2 (Discord).

## [1.1.1] — 2026-06-29

Hardening patch on the 1.1.0 runtime line. The runtime lane (SIP-0089) was
live-validated end-to-end after 1.1.0, surfacing two regressions the unit
suites couldn't catch (#270, #272); both are fixed here alongside the resume
and reliability work from the 1.1.x hardening plan. No new SIPs — the additive
items are backward-compatible and the one rename (#79) is internal.

### Added
- Per-role Prefect task names: tasks render as `{role} [{n}/{total}]: {title}`
  so a role appearing multiple times in a plan is distinguishable in the
  Prefect UI (#94).
- Agent **`mode`** and **`runtime_status`** are now surfaced on the agent-list
  API and the console agent view, alongside the heartbeat fields — health is
  `runtime_status`, posture is `mode` (see
  `docs/agent-runtime-status-model.md`) (#230, #231).

### Fixed
- **Auth:** cycle API routes returned 403 for every authenticated user — #150
  applied `cycles:read`/`cycles:write` scope checks, but the role-centric
  Keycloak realm issues *roles*, not those scopes. Bridge realm roles to their
  implied scopes in `resolve_identity` so role-bearing tokens authorize as
  intended (#270).
- **Duty scheduler:** duty windows never auto-opened under the default
  `missed_window_policy="skip"` — the poll-cadence lag before the first
  observing tick was misread as a missed window. A just-active window is now
  treated as on-time within one poll interval (plus jitter margin) (#272).
- **Resume:** a duty-deferred run is now re-attempted *and* actually
  re-executed on resume — the resume route never re-invoked the executor
  before (#222).
- **Resume:** mid-sequence runs resume at the correct workload index instead of
  re-running from workload 0 (#257).
- **Comms:** `publish()` now retries with bounded backoff across the RabbitMQ
  reconnect window instead of failing the first send after a drop (#245).
- **Capabilities:** strip `<think>` blocks before fenced-code parsing, and log
  the raw output on zero extraction so empty parses are diagnosable (#130).
- **CLI/API:** `runs retry` now actually executes the run (it previously
  no-op'd); corrected stale docstrings (#133, #205).
- **Telemetry:** the `BrokenExporter` test no longer leaks a global OTel
  provider into sibling tests (#239).

### Changed
- Renamed the `governance.establish_contract` capability → **`governance.define_done`**
  and its `run_contract.json` artifact → **`definition_of_done.json`** (the fields
  are a standard Definition of Done, not a "contract"). Internal rename, no
  behaviour change; historical artifacts on disk are left as-is (#79).

### Internal / tooling
- Regression suite runs in parallel via `pytest-xdist -n auto` (#216).
- `update_sip_status.py` now rewrites the body `**Status:**` line on promotion,
  not just the frontmatter (#253).
- Deduplicated three copies of the JSONB-parsing helper into one (#156); routed
  the dispatched-flow factory through `create_workflow_tracker` (#250); corrected
  stale flow-executor references in the control-plane context doc (#168).

## [1.1.0] — 2026-06-28

The v1.1 line ships the **Agent Runtime State** platform (SIP-0089) on top of a
hardened 1.0.x foundation. Per the release decision, "1.0.x hardening
completeness" was read as the foundational CI-trust + reliability arc (complete);
the remaining build-reliability work continues as the **1.1.x hardening plan**
(`docs/plans/1-1-x-hardening-plan.md`).

### Added — Agent Runtime State (SIP-0089, Phases 1–4)
- **Runtime modes** (`ambient` / `cycle` / `duty`) with a single-writer
  RuntimeCoordinator (D16) and an in-process duty scheduler that drives
  `ambient↔duty` transitions on a poll — the live central mode-writer.
- **Assignments & duty windows** (hard/soft strictness, pre/post reserve
  buffers) plus a cycle-recruitment reserve-buffer guard that defers a run
  rather than pull an agent into a hard-duty window.
- **FocusLease** arbitration — `granted`/`rejected`/`preempting`, the hard gate
  for an agent's primary attention. lease ≠ mode; a failed mode write rolls the
  lease back (no stranded leases).
- **RuntimeActivity** — an agent's current cycle task is observable
  (`running` → `completed`/`failed`), instrumented at the executor dispatch
  boundary; surfaced via `squadops agent activity <id>` and
  `GET /health/agents/{id}/activity`.
- Postgres migrations `1100`–`1130` (agent_runtime_state, agent_assignments,
  focus_leases, runtime_activities), each with single-active-row invariants.
- CLI: `squadops agent state`, `squadops agent activity`,
  `squadops assignment list|show|create`.

### Security
- Enforce `cycles:read` / `cycles:write` scopes on all cycle API routes
  (`require_scopes` was wired in SIP-0062 but never applied — any authenticated
  user could perform any cycle operation). No-op when auth is disabled (#150).

### Changed — 1.0.x hardening (CI-trust foundation)
- Dev and CI standardized on **Python 3.12** (production stays 3.11; build a
  3.12 venv to reproduce the gate) (#217).
- Regression gate now enforces `ruff format --check` and runs the adapter unit
  tests (#196, #207).
- Declared previously-transitive deps as optional extras: `sqlalchemy`
  (`postgres`) and `python-jose` (`auth`), and decoupled the core `DbRuntime`
  port so the `postgres` extra is truly optional (#206, #191).

### Fixed
- Cancelling a cycle/run now propagates to Prefect — the orphaned flow run is
  transitioned to CANCELLED instead of running on (#77).
- Stop in-place mutation of the frozen `HandlerResult` in the planning retry
  path (#155).
- RabbitMQ consume-loop channel recovery locked with regression tests (the
  spin-forever path was already fixed by SIP-0094; #146).
- Integration test config no longer drifts from the stack: env vars now override
  `test_config.env`, and creds match the deployed broker (#209).
- `test_pulse_check_e2e` repaired (event-loop seeding + stale-API drift) (#211).

### Known limitations (1.1.0)
- Cycle **recruitment does not yet acquire FocusLeases through the coordinator**
  — the lease gate is enforced at the coordinator, not at recruitment (#233);
  the coordinator's lease+activity+mode writes use best-effort compensation, not
  a single Postgres transaction (#244).
- A cycle **deferred by a hard-duty reserve window cannot be resumed** — the
  deferral is correct, but no checkpoint exists to resume from (#222).
- RuntimeActivity is emitted for **cycle tasks only** (executor-side);
  ambient/duty-handler activities are not yet instrumented.
