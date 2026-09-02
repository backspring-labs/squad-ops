# 1.7.1 — Verification Sets: Pre-registration

**In force from roll 1, by the commit hash of this document on its branch, and unchanged
thereafter.** Written 2026-09-02 (early morning ET), after the rebuild on the stacked 1.7.1
pack and after both shakeouts, before the first counted launch. Merging it is the owner's act
and does not change what it pre-registers; the branch commit is the record.

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
| Deploy — commit | **`a00870d6`** — the head of `fix/1229-repair-forwards-the-dispatched-workspace`, the stacked tip of the pack: #1243 (#1130) → #1244 (#598) → #1245 (#1022) → #1246 (#668) → #1247 (#1123) → #1250 (the shakeout's fix), on main `e8193bb9` (which already carries #939, #1229 and #1153). The first tip, `d95f8e21`, was superseded by the Next.js shakeout's finding (§2). **Not main.** See §2 and §7. |
| Deploy — 7 image ids | runtime-api `027f44a81ccf` · max `0717c85c4992` · neo `235ffc803e53` · nat `3fd32c6bca60` · bob `af9a719b425c` · eve `45fd005a625b` · data `431a5499cd36` — built 2026-09-02 08:08 ET from `a00870d6`; asserted at every counting launch by the driver; every container verified to carry the hand-off fix and the instrument lines (`docker exec … inspect.getsource`), `tsc` in neo and eve only. (The superseded set from `d95f8e21`: runtime-api `ccd81952be2e` · max `f6e8b8dfbe69` · neo `da9da7ab0bae` · nat `58089c21e847` · bob `9816af4df1b0` · eve `e4368e889bb0` · data `1f1358c9488b`.) |
| Loaded, not built | verified in-container before the shakeouts (`docker exec … python -c`): every container imports the pack's seams (`qa_owned_suite_defects`, `absent_anchor_cases`, `INJECTION_SCOPE_SUITE` → `additive_containment`, `row_is_blocking_failure`, `anchor_findings`, `containment_findings`, `parse_pytest_failure_rows`, `parse_vitest_failure_text`, `client_surface_instructions`, the three new evaluators); `tsc` on PATH in neo and eve, absent in runtime-api and bob (as `DECLARED_TOOLING_GAPS` declares) |
| Gate policy | 1.6.3 §6 constant, verbatim in each set config's `gate_notes`; `--as-agent`; the decider is recorded per roll |
| Audit instrument | `scripts/dev/audit_delivered_app.py` at the deploy commit |
| Driver | `verification_set_driver.py roll --set docs/plans/verification-sets/1-7-1-fastapi-react.yaml --roll N`, then `…/1-7-1-nextjs.yaml` — one roll per invocation |
| Order | FastAPI+React rolls 1–6 first (the measurement), then Next.js+TS rolls 1–2 |

---

## 2. Preconditions

- **The deploy is the stacked pack tip, not main — pre-declared.** The owner asked (2026-09-01,
  before bed) for the pack to be stacked as PRs and the validations run overnight; the only
  tree that carries the whole pack is the last PR's head. The six PRs are unchanged from the
  moment the images were built; **merging those exact commits does not void a roll** (the
  merge commits add no tree change), and any other merge, a rebuild, or a force-push to any of
  the five branches does. The owner may instead void the set and re-run from main — that is
  the owner's call, recorded here as the alternative.
- **Launches run from the pre-registration branch** (`docs/1-7-1-preregistration`), which is
  where the set configs and the driver readouts exist; the owner's 2026-08-27 ruling was
  "every launch runs from `main`". Stated as a deviation the owner rules on, not hidden: the
  launch checkout affects only the driver and its configs (not the deploy), and the driver
  pins that branch's HEAD at roll 1 so nothing moves under the set.
- **Both shakeouts on THIS deploy, read before roll 1:**
  - **FastAPI+React `cyc_04e7d5896054`** (10:08→10:53Z, 44 min): accepted, audit PASS,
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
  - **Next.js+TS `cyc_3ac86805439f`** (10:54→11:56Z, 61 min; its driver process was stopped
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
    repair's build check skipped for want of a frontend tree. Fixed in #1250 (stacked on
    #1247), with the agent rows' statuses and reasons now logged. **This shakeout's deploy is
    superseded**; both shakeouts re-run on the rebuilt deploy below, whose identity replaces
    the pins in §1. R4's readout on this run: `repair_brief_case_counts [0]` — the qa repair
    of round 2 followed an emission failure (no fenced block), so the failed row carried no
    cases; the record must distinguish that from a brief that dropped cases it had.
  - **Re-run on the rebuilt deploy (`a00870d6`):** TBD — filled from the records.
- **Diagnostics for the predictions no roll is likely to exercise (plan §4), non-counting
  by declaration — run 2026-09-02 06:20 ET, in the deployed containers, on the stored
  artifacts that cost each item.** These are in-container replays of the deployed code path,
  not fault-injected cycles: the deploy has no fault-injection hook and none was added to a
  frozen deploy. Stated as what they are.
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
- **No merges to main while either set is open** except the five stacked PRs unchanged (§7).

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

Inherited verbatim (1.6.3 §7) with one pre-declared exception: no merges to main **other than
the five stacked pack PRs, unchanged**; no rebuilds; no config edits; no manual intervention on
any roll; a rebuild voids every roll after it; a force-push to any of the five branches voids
the set.
