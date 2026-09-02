# 1.7.1 — Verification Sets: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Written 2026-09-02, revised the same day as each shakeout's finding became a
merged fix and the deploy was rebuilt from main (§2), before the first counted launch.
Merging it is the owner's act and does not change what it pre-registers; the branch commit is
the record.

This is the 1.7.1 plan's §4 (`docs/plans/1-7-1-plan.md`, rev 1 with as-landed notes) as data:
**six counting rolls on FastAPI+React** (the measurement — every item of §2.3 came from this
stack) and **two on Next.js+TS** (this time not only a regression arm: #939 and #1229 change
what a Next.js roll does). Everything not restated here is inherited **verbatim** from the
1.6.6 pre-registration (`docs/plans/1-6-6-verification-set-preregistration.md`) and, through
it, 1.6.5, 1.6.4 and 1.6.3: §5 (scoring), §5.1 (roll validity — void / reset / counted), §6
and §6.1 (the gate constant and the two approval paths), §7 (prohibited while open).

**The instrument moved with the pack.** The driver (`scripts/dev/verification_set_driver.py`)
gained the readouts §4 of the plan promised, so R1–R7 below are read from the per-roll record
rather than by hand: per-check failed-row counts from the stored typed-check evaluations
(`typed_checks`: kind gate, anchors, additive containment, undefined names, the reporting-only
packaging findings) with `checks_by_environment`; the routing tokens `qa_owned_routed` and
`absent_anchor_routed`; the qa repair brief's `repair_brief_case_counts`; and rule B's
`decided_by_agent` against `unverifiable_toolchain_absent`, all from the runtime-api log
window. Every fixed parameter is read from
`docs/plans/verification-sets/1-7-1-fastapi-react.yaml` and `…/1-7-1-nextjs.yaml`.

---

## 1. Fixed parameters

| Parameter | Value |
|---|---|
| N (rolls) | **6 counted** on FastAPI+React (§3) and **2 counted** on Next.js+TS (§4). 1.6.6 §1.3 on what these sizes can and cannot say holds unchanged: exercise, not a rate. |
| Bar | **none** on either rate; each prediction is pass/fail on its own terms |
| Project / PRD / squad / request profile | `group_run`, `full-38`, `validated-fullstack` — identical to 1.6.6 and 1.7.0 |
| Overrides | FastAPI+React: none. Next.js+TS: `build_profile=nextjs_ts`, `dev_capability=nextjs_ts` |
| `resolved_config_hash` | FastAPI+React `c4d6a2165acf`, Next.js+TS `TBD-from-shakeout` — **unchanged from 1.6.6** on the React arm (the pack changed code, not configuration); asserted on every counting roll; a roll on any other hash is void |
| `squad_profile_snapshot_ref` | `575707c58536cf3b…` — unchanged from 1.6.6 and 1.7.0; a roll on any other snapshot is void |
| Deploy — commit | **`06408dfe`** — **main**, the merge of #1262. Main carries the whole pack merged by the owner on 2026-09-02: #1242 (#1144), #1243 (#1130), #1244 (#598), #1245 (#1022), #1246 (#668), #1247 (#1123), #1248 (#1151), #1249 (#582), #1250 (#1229's hand-off fix), #1253 (#1252's handoff validator), #1257 (#1255) and #1258 (#1256) — found by the third shakeout pair — and #1262 (#1259, #1261) — found by the fourth — on top of #939, #1229 and #1153. Four earlier deploys were shaken out and superseded — the stacked tips `d95f8e21` and `a00870d6`, then main at `816cc8f0` and `dfe466ab` (§2); the owner's ruling was to rebuild from main once the pack merged, which removes the "not main" deviation the first draft of this document pre-declared. **Exit rule for the shakeout loop** (`docs/plans/verification-sets/README.md`): a pair on one deploy with no new seam finding. |
| Deploy — 7 image ids | runtime-api `1b3ba246611d` · max `1c47ec79c29f` · neo `91e38853f741` · nat `dbdc6cd51866` · bob `544d9315c3fa` · eve `ee2ef6644194` · data `ed490b25e257` — built 2026-09-02 17:59Z from `06408dfe`; asserted at every counting launch by the driver. (Superseded sets: from `dfe466ab`, runtime-api `173316830b11` · max `28b20f7479b3` · neo `3c9dd9271553` · nat `d916d357c024` · bob `dab6abb8f0f7` · eve `7631cc721813` · data `58c3b8395693`; from `816cc8f0`, runtime-api `6db6411b4e4b` · max `32b0170b2fd4` · neo `96a955fff072` · nat `636435ff47ad` · bob `fa04483c8ed7` · eve `43e1858c0c18` · data `6caacbbb1680`; from `a00870d6`, runtime-api `027f44a81ccf` · max `0717c85c4992` · neo `235ffc803e53` · nat `3fd32c6bca60` · bob `af9a719b425c` · eve `45fd005a625b` · data `431a5499cd36`; from `d95f8e21`, runtime-api `ccd81952be2e` · max `f6e8b8dfbe69` · neo `da9da7ab0bae` · nat `58089c21e847` · bob `9816af4df1b0` · eve `e4368e889bb0` · data `1f1358c9488b`.) |
| Loaded, not built | verified in all seven containers after the `06408dfe` build (`docker exec -i … python -`, `inspect.getsource` on the loaded objects): the verifier carries `REASON_FILE_NOT_IN_PATCH` and applies it to the agent's rows, `tsc_is_syntax_code` classifies by value (#1262); `sections_present` is in the registry and `task_plan._handoff_section_criteria` binds it, the builder handler reads the shared section rule (#1257); `CorrectionProtocolResult.repair_typed_checks` exists, the executor hands `agent_checks=repair_typed_checks` to the verifier and the verifier reads the sequence (#1258); the executor hands the correction runner the enriched envelope (#1250) and logs `agent_rows=… agent_executed=…`; `validate_handoff_criteria` is wired at the framing gate and the dispatch strip logs `handoff_regex_stripped` (#1253); `squadops.api.cycle_schemas` imports (#582); every container imports the pack's seams (`qa_owned_suite_defects`, `absent_anchor_cases`, `INJECTION_SCOPE_SUITE` → `additive_containment`, `anchor_findings`, `containment_findings`, `parse_pytest_failure_rows`, `parse_vitest_failure_text`, `client_surface_instructions`, `_attach_typed_checks`); `tsc` on PATH in neo and eve, absent in runtime-api and bob (as `DECLARED_TOOLING_GAPS` declares); `/health` reports 1.7.0 |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-7-1-fastapi-react.yaml --roll N`, then `…/1-7-1-nextjs.yaml` — one roll per invocation |
| Order | FastAPI+React rolls 1–6 first (the measurement), then Next.js+TS rolls 1–2 |

---

## 2. Preconditions

- **The deploy is main.** The first draft of this document pre-declared a stacked-tip deploy
  (the owner asked on 2026-09-01, before bed, for the pack to be stacked as PRs and validated
  overnight, and only the last PR's head carried the whole pack). Two stacked tips were built
  and shaken out; each shakeout found a defect, each defect became a PR, and the owner merged
  the whole pack on 2026-09-02 and ruled that the rolls run on a deploy built from main; the
  first main build was shaken out too and found two more seam defects, merged the same day.
  The pins in §1 are the second main build. The three superseded deploys and what each
  shakeout found are kept below because they are the reason this deploy exists.
- **Counted launches run from `main`** (the owner's 2026-08-27 ruling), which requires this
  document and the two set configs to be merged before roll 1 — the driver and its readouts
  are on main already; only the configs and this pre-registration are on the branch. The
  shakeouts below were launched from the pre-registration branch (non-counting by
  declaration; the launch checkout affects only the driver and its configs, not the deploy).
- **Shakeouts, in order, read before roll 1.** Two per deploy; a deploy on which either stack
  produced a fix is superseded, and both re-run on the fix:
  - **On `d95f8e21` — FastAPI+React `cyc_04e7d5896054`** (10:08→10:53Z, 44 min): accepted, audit PASS,
    15/15, 0 corrections, gate `system:no_open_questions`, P0 held. Every typed row passed:
    `checks_by_environment` `{agent:development: 19, agent:builder: 6, agent:qa: 7}`;
    `container_packaging` ran on the builder's `Dockerfile` and passed (a clean recipe on
    this deploy — the reporting-only readout works and reads 0); `assertion_kinds_match`
    bound and passed on `backend/tests/test_runs.py`. **What it did not exercise, and
    why:** the plan's `qa.test` names one artifact, `backend/tests/test_runs.py` — no
    frontend suite — so `dom_anchor_queries` had nothing to bind and `additive_containment`
    nothing to judge: **R3 and R5 are vacuous on this stack unless a roll's plan names a
    frontend suite** (the 1.7.0 gating roll named none either; the 1.6.6 rolls that did
    placed it under `frontend/src/__tests__/`, outside the declared qa namespace
    `frontend/src/tests/`, which the anchor binding filters on — a fact for the record, not
    changed here). R1 bound and held; R2/R4/R7 unexercised (no correction round).
  - **On `d95f8e21` — Next.js+TS `cyc_3ac86805439f`** (10:54→11:56Z, 61 min; its driver process was stopped
    from outside the session at ~11:00Z and a watcher re-attached, approving the gate with
    the §6 constant at 11:24Z): **rejected** after three correction rounds, audit FAIL, 8/15,
    26 failed emissions banked, `container_packaging` reporting `npm_ci_without_lockfile` on
    the builder's recipe (readout, not a verdict). **The shakeout did its job: R7 falsified
    on the deploy built to end it.** The first dev emission failed `frontend_compiles` on a
    real type error; the dev repair evaluated its own patch in the dev container
    (`repair_typed_checks environment=agent:dev rows=4 executed=2 failed=0`) and runtime-api
    still returned `unverifiable / no_executed_blocking_checks decided_by_agent=0`, after
    which #1221's option A left the task failed and the run could not recover. Cause, read
    from the executor: it verifies against the enriched envelope's workspace but handed the
    correction runner the base envelope, so rule B's forwarding found no workspace and the
    repair's build check skipped for want of a frontend tree. Fixed in #1250 (merged), with
    the agent rows' statuses and reasons now logged. **This shakeout's deploy is superseded.**
    R4's readout on this run: `repair_brief_case_counts [0]` — the qa repair
    of round 2 followed an emission failure (no fenced block), so the failed row carried no
    cases; the record must distinguish that from a brief that dropped cases it had.
  - **On `a00870d6` — FastAPI+React `cyc_8118588858a6`** (12:10→13:08Z, 57 min): accepted,
    audit PASS, 17/17, gate `system:no_open_questions`, P0 held, `checks_by_environment`
    `{agent:qa: 16, agent:development: 19, agent:builder: 21}`, `container_packaging` 1
    reporting-only finding — **and three correction rounds, all spent on `regex_match` (6
    failed rows)**: the planner had authored regexes over `qa_handoff.md` that fixed the
    ORDER of the handoff's section headings, and the builder — whose profile requires those
    sections by name in any order — was rejected three times for a heading order no rule
    required. Filed as #1252, fixed in #1253 (a `validate_handoff_criteria` validator at the
    framing gate, a dispatch-time strip of any regex over the handoff, the authoring rule
    `no-regex-on-the-handoff`, and the vocabulary's regex example moved off the handoff), and
    the audit over 40 stored plans behind it is #1254 (planner authors checks the framework
    injects; 1.7.2's rider). R1 bound and held; R2/R4/R7 unexercised — the rounds were
    builder rounds, not dev or qa repairs, so no typed row was decided by an agent. **This
    deploy is superseded** by #1253's merge. Next.js+TS was not re-run on `a00870d6`: the
    owner merged the pack while the React re-run was being read, and the default ruling
    (rebuild from main) made a third deploy the one to shake out.
  - **On `816cc8f0` (main, the merge of #1253) — FastAPI+React `cyc_c6db3ffc1f4e`**
    (13:44→14:58Z, 72 min): accepted, audit PASS, 15/15, P0 held, `checks_by_environment`
    `{agent:development: 19, agent:builder: 1, agent:qa: 22}`, no packaging finding, gate
    approved by the driver's agent user with the §6 constant — **and three correction
    rounds that found two more seam defects, each read from the code, filed and fixed the
    same day:**
    - Round 0: the builder's handoff stopped after `## How to Run`; the handler's
      validation named the two missing sections; the builder's repair carried every one of
      them; runtime-api returned `unverifiable / no_typed_criteria checks=0 agent_rows=0`
      and #1221 left the task failed. A builder task carried **no typed criterion at all**
      once #1252 stripped the plan's handoff regexes — the section rule lived only inside
      the handler, and `container_packaging` is injected at the handler seam. **#1255**,
      fixed in #1257: `sections_present`, bound at plan time onto the builder task that
      owns the handoff with the profile's sections as params, one rule shared with the
      handler's validation; the verifier's `no_typed_criteria` verdict carries the agent's
      rows.
    - Rounds 1–2: dev repairs of the qa task's failure. The dev container reported
      `rows=10 executed=10 frontend_compiles:failed` on both; runtime-api logged
      `agent_rows=0` both times and the retest decided (pf-47's path; the retest failed
      on exactly the suite the patch would have been rejected for). The executor read
      `repair_typed_checks` off the **failed task's** result, and the correction protocol
      returned only the repair's files — **rule B had never delivered a row to the verifier
      in a live cycle; every `decided_by_agent` in this line's records was 0.** **#1256**,
      fixed in #1258: the protocol result carries each repair step's rows, the executor
      hands them to the verifier. **This deploy is superseded** by both merges.
  - **On `816cc8f0` — Next.js+TS `cyc_a72490f76caf`**: launched 15:10Z, stopped by the
    assistant at 15:24Z during framing (four of the framing tasks dispatched, no
    implementation run) when the owner merged #1257 and #1258 and asked for the rebuild;
    no record written, nothing read from it.
  - **On `dfe466ab` (the pinned deploy) — FastAPI+React `cyc_898d88bd9a17`** (15:28→16:14Z,
    45 min; its driver process was stopped from outside the session at ~16:00Z during plan
    review and a detached watcher re-attached, approving nothing — the gate went
    `system:no_open_questions`): accepted, audit PASS, 15/15, 0 corrections, P0 held,
    `checks_by_environment` `{agent:development: 15, agent:qa: 8, agent:builder: 2}`; the
    builder's two rows are `sections_present` (bound by #1257, passed on the first
    emission) and `container_packaging` (passed). `frontend_compiles` 2, `undefined_names`
    4, every typed row passed; 1 failed emission banked, no packaging finding. As on the
    first shakeout: the plan names no frontend suite, so R3/R5 are vacuous here, and with no
    correction round R2/R4/R7 are unexercised — R7 in particular (#1256's fix) has not yet
    been seen deciding a live round.
  - **On `dfe466ab` — Next.js+TS `cyc_9c379355b5e8`** (16:15→17:15Z, 59 min): accepted,
    audit PASS, 17/17, P0 held, gate `system:no_open_questions`, `checks_by_environment`
    `{agent:qa: 114, agent:development: 28, agent:builder: 2}`, `container_packaging` 1
    reporting-only finding (`npm_ci_without_lockfile`, the same recipe defect as the earlier
    Next.js shakeout), `sections_present` bound and passed — **and two correction rounds
    that found three more defects, read from the artifacts and the code:**
    - **#1256 confirmed live** — round 0's dev repair evaluated five rows in its container
      and runtime-api received them: `agent_rows=5 agent_executed=5`, the first live round
      in which rule B's rows reached the verifier. `decided_by_agent` stayed 0 because the
      same rows executed locally too.
    - **#1259** (fixed in PR, this line): the qa task's first suite found a real route
      defect (`capacity` dropped when sent as a number); the dev's correct fix was refused
      because the qa task's suite-bound checks (`assertion_kinds_match`,
      `dom_anchor_queries`) were evaluated on trees without the failed suite — the accepted
      workspace in the dev container, and the patch in runtime-api — and `file_not_found`
      counted as an executed failure in both. Replayed: suite absent → both fail; suite
      present → both pass. Before #1240/#1246 those criteria skipped on a `.ts` suite and
      the retest decided; every dev patch of a qa failure on either stack took this path.
    - **#1260** (filed, recommended 1.7.2): with the fix refused, `qa.test` was re-dispatched
      and re-authored its suite **without** the capacity case; the third emission passed
      25/25 and the cycle shipped the defect green. A re-dispatch carries no memory of the
      cases that failed; needs a design, not a patch.
    - **#1261** (fixed in PR, this line): `undefined_names` skipped
      `unsupported_stack_or_syntax` on five of the nine accepted test files — the ones
      carrying `TS18048`/`TS18046` type diagnostics, which the classifier read as syntax by
      their `TS1` prefix. Rebuilt the evaluated tree from the manifest and fills and ran tsc
      in the qa image to prove it. R6's readout counts failed rows, so a green roll cannot
      see this gap.
    - Texture: round 1's `qa.test_repair` emitted no content (refunded, #1053); R4's brief
      carried the one failing case (`repair_brief_case_counts [1]`); a scaffold fill slot
      filled twice produced the placeholder assertion of the second emission.
    **This deploy is superseded** by #1262 (#1259, #1261).
  - **On `06408dfe` (the pinned deploy) — FastAPI+React:** TBD — filled from the record.
  - **On `06408dfe` (the pinned deploy) — Next.js+TS:** TBD — filled from the record.
- **Diagnostics for the predictions no roll is likely to exercise (plan §4), non-counting
  by declaration — run 2026-09-02 06:20 ET, in the deployed containers, on the stored
  artifacts that cost each item.** These are in-container replays of the deployed code path,
  not fault-injected cycles: the deploy has no fault-injection hook and none was added to a
  frozen deploy. Stated as what they are; the hook is filed as #1251, recommended as 1.7.2's
  precondition.
  - **R6** — `UndefinedNamesCheck` in the **qa container** (`squadops-eve`, tsc on PATH) on
    1.7.0 roll 4's stored shell (`art_0e4eaa25d42d`, the fill that used `created` undeclared):
    `failed — undefined name(s): created (line 30)`; on the accepted roll-6 shell
    (`art_5ad70b6aacb9`): `passed`. The path that reached vitest in 1.7.0 is rejected at
    emission on this deploy.
  - **R7** — `verify_patched_artifacts` in **runtime-api** (no node) on the #1221 repair
    patch (`art_e71d58a6e45c`) with an `undefined_names` criterion: without agent rows,
    `unverifiable / no_executed_blocking_checks` (the 1.7.0 shape); with the repair's own
    executed rows as `_attach_typed_checks` emits them (`environment: agent:development`),
    `passed`, `decided_by_agent: 1`. Rule B decides where 1.7.0 could not.
  - **R2/R4 on the React arm** — no in-container diagnostic: both are routing decisions in
    the correction runner, replayed in the PRs' tests from 1.6.5 roll 3 and 1.6.6 roll 6;
    a counted roll confirms them only where a correction round occurs.
- Leases 0, nothing in flight, HEAD pinned, working tree clean, at every launch (driver
  preflight).
- **No merges to main while either set is open** (§7); the pre-registration PR itself merges
  before roll 1, and the driver pins main's HEAD at that launch.

---

## 3. FastAPI+React (`fullstack_fastapi_react`) — the measurement, six rolls

Every prediction is one item of the pack, read only from the evidence named; each has the
roll that falsified it before the fix.

| # | prediction | falsified by | read from | prior evidence |
|---|---|---|---|---|
| **R1** | (#1153) no qa emission carrying an assertion whose literal contradicts a declared field kind reaches test execution | one such assertion in a stored, executed suite | `typed_checks.kind_gate_rejections` (rejections at emission are the positive trace); stored suites | 1.6.6 roll 3 |
| **R2** | (#1130) a failure the suite raised in its own frame in a qa-owned file is routed to `qa.test_repair` with that file as the target | one such failure whose repair targets an app file | `loop_texture.qa_owned_routed`; `correction_repair_locus` lines | 1.6.5 roll 3 |
| **R3** | (#668) every stored RTL suite that renders queries some declared anchor, and every imported view is located through some anchor of its own | one covering suite executed with none | `typed_checks.dom_anchor_findings` (rejections at emission); stored suites | fay-14 |
| **R4** | (#1123) every `qa.test_repair` brief names the failing cases, and a failing assertion on an anchor absent from the inventory is routed to qa | a qa repair dispatched with a case count of 0 while the failed row carried cases; one absent-anchor failure sent to the dev chain | `loop_texture.repair_brief_case_counts`, `loop_texture.absent_anchor_routed` | 1.6.6 roll 6 (brief); no stored red for the anchor half |
| **R5** | (#1022) no additive suite that fetches a live server or invokes nothing of the application reaches test execution | one such suite executed | `typed_checks.additive_rejections`; stored suites | C3, C4 |
| **R7** | (#1229) no repair on this stack returns `unverifiable / no_executed_blocking_checks` because its criteria's toolchain was absent where verification ran | one such verdict | `loop_texture.unverifiable_toolchain_absent`; `decided_by_agent`; `checks_by_environment` | 1.7.0 roll 4 (Next.js) |
| **S0–S3, Q3, P0** | carried from 1.6.6 unchanged | as there | as there | held |

**Texture, no prediction attached:** the verdict rate against 1.6.6's 4 of 6 (interval, no
bar); correction rounds; greens by repair versus by re-dispatch; refused versus applied
patches; qa primary completion tokens against 1.6.6's `3233–6594`; `checks_by_environment`;
the reporting-only `container_packaging_findings` per roll (#598 — readouts, never a verdict).

**What this arm cannot read:** a repair never attempted (R2, R4, R7 need a correction round);
a manifest with no view anchors (R3); an emission with no additive suite (R5). Unexercised is
not passed; each roll's record says which predictions it exercised.

**Early stop, one direction.** A falsified R1–R7 (or S0–S3/Q3/P0) stops this set. A good
result is never grounds to stop early. A stop in one set does not stop the other.

---

## 4. Next.js+TS (`nextjs_ts`) — two rolls, and what changed on this stack

#939 (tsc on `.ts/.tsx/.js/.jsx` emissions) and #1229 (rule B: a repair evaluates its own
patch in the producing agent's container, and runtime-api consumes the rows) change what a
Next.js roll does; #1022's gate applies to its additive suites; #668/#1123 bind only where a
manifest declares view anchors and a suite renders (Next.js suites call route handlers, so
R3/R4 are vacuous here unless a page test is emitted).

| # | prediction | falsified by | read from |
|---|---|---|---|
| **R6** | (#939) no `.ts`/`.tsx` emission with an unresolved name reaches test execution | one `ReferenceError: … is not defined` in a stored per-round `test_report.md` | `typed_checks.undefined_name_rejections` (the positive trace); per-round reports |
| **R7** | (#1229) no repair returns `unverifiable / no_executed_blocking_checks` because its toolchain was absent where verification ran | one such verdict | `loop_texture.unverifiable_toolchain_absent`; `decided_by_agent` |
| **R5** | (#1022) as §3 | as §3 | as §3 |
| **Q0, Q5, P0, Coverage** | carried from 1.6.6 §4 unchanged | as there | as there |

**Texture:** correction rounds against 1.6.6's 2/0 and 1.7.0's 0/0; `checks_by_environment`.

**Early stop, one direction, per set** — as §3.

---

## 5. Delegation

Executed by the assistant under the owner's delegation of 2026-09-01 for both sets —
FastAPI+React rolls 1–6, then Next.js+TS rolls 1–2: launch, gate approval with the §6
constant, collection, and the per-roll record; **the counted/void/reset reading and the
prediction check are made at each roll boundary before the next launch**; a reset or a
falsified prediction stops that set for the owner.

## 6. Gate constant

Inherited verbatim (1.6.3 §6, §6.1); the text is in each set config's `gate_notes`.

## 7. Prohibited while open

Inherited verbatim (1.6.3 §7): no merges to main; no rebuilds; no config edits; no manual
intervention on any roll; a rebuild voids every roll after it. (The first draft carried an
exception for the five stacked pack PRs; the pack is merged and the exception is gone.)
