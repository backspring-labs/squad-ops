# 1.4.1 Hardening Patch — Plan

**Established:** 2026-07-31 (post-v1.4.0 cut). **Vehicle:** patch release per the #281
convention (small fixes, either lane, any time). **Principle carried from the cut:**
v1.4.0 shipped exactly the measured tree; this patch is where the window-3 fix ledger
lands, each item receipted by a measurement roll and verified by deterministic replay
against stored artifacts — no new cycles needed to prove any mechanism.

## Scope

**In (five fixes, all hash-stable — no contract/manifest re-seed, no measurement
window required):**

| # | Issue | One-line | Receipt |
|---|-------|----------|---------|
| 1 | #672 | `runtime_activities` reaper (sibling of #373) | 4 stranded `running` rows from July 21–25 cycles; every roll trips `uq_runtime_activities_one_active_per_agent` per agent |
| 2 | #671 | Validator: typed-check module params must exist in the scaffold surface | fay-17's blocking `import_present: app.routes` passed validation against a nonexistent package |
| 3 | #673 | Validator: reject duplicate `expected_artifacts` across tasks | fay-18 task 5 dual-claimed task 4's test file with a do-not-produce instruction |
| 4 | #667 | Thread the #659 testid surface into repair envelopes | fay-14: neo's first fill carried manifest anchors; every repair stripped them |
| 5 | #669 | Thread rejection context into framing re-rolls | window 3 framing first-roll 2-for-6; dev-claims-frozen ×3, every re-roll blind |

**Out (explicitly):**
- **#670** (qa typed-check enforcement) — blocked on the owner fork
  (enforce vs declare-advisory). If "advisory" is chosen it becomes a small validator
  change that could join late; if "enforce," it lands only after #671 (prerequisite)
  and deserves its own deploy + a watchful first roll.
- **#668** (DOM/client-contract enforcement) — its enforcement shape may add check
  vocabulary or testid surface → **moves seed hashes** → belongs to the next
  measurement window's package, not a quiet patch.
- **SIP-0102 migration steps 3–7** — 1.5/1.6 scope per the release record.
- Audit-then-promote SIP queue (0096/0093/0088/0092) — docs-only, rides any time,
  not fix work.

## Design sketches (owning seams)

### 1. #672 — activities reaper *(first: independent, trivial, kills log noise)*
- **Seams:** `adapters/cycles/run_completion.py` (finalize path) + a startup/admission
  reclaim mirroring the FocusLease #373-line fix in `src/squadops/runtime/`.
- Both halves: (a) run-finalize ends all activities owned by the finishing run's cycle
  (aligns with the §4.5 unit-of-work direction, #244); (b) one-time/startup reaper ends
  `running` activities whose owning cycle is terminal — clears the 4 historic rows.
- **Verify:** replay = none needed (DB-state fix). Post-deploy: stranded rows ended;
  one fresh cycle logs zero `UniqueViolationError` / `best-effort start_activity failed`.

### 2. #671 — module-existence validation *(validator sibling pair with #673)*
- **Seam:** the #645 rule set in `src/squadops/cycles/implementation_plan.py`
  (`validate_*` family), reading the scaffold-derived module surface (expander/manifest
  already enumerate fill + frozen files → importable module paths).
- Rules: `import_present.module` unknown → reject with teaching message;
  `harness_boundary.entry_modules` entries unknown → reject (or strip when ≥1 valid
  entry remains — pick ONE behavior and document it; recommend reject, consistent with
  the net philosophy). Preserve #441 dotless-relative semantics.
- **Verify:** stored-plan replay — fay-17 framing-2 trips (`app.routes`), fay-16/18
  trip on `app.main` in entry_modules, fay-19 passes clean.

### 3. #673 — duplicate expected_artifacts net
- **Seam:** same validator family, plan-wide pass (cross-task, so it lives beside the
  ownership rules, not per-task).
- Rule: same path in >1 task's `expected_artifacts` → reject, message names both tasks
  and teaches the artifact-less `criteria_refs` form (the fay-13-f2 legal shape).
- **Verify:** stored-plan replay — fay-18 framing-2 trips (tasks 4/5); fay-15/16/17/19
  pass.

### 4. #667 — repair-envelope testid threading
- **Seams:** `adapters/cycles/correction_runner.py` (`repair_inputs` construction —
  the exact #555 `resolved_config` shape) + `repair_handlers.py` render sites; the
  fill-only appendix v4 `{{testid_surface}}` slot already exists and currently renders
  empty on repairs.
- Thread `testid_surface` (dev chain) and `dom_testid_surface` (qa.test_repair) —
  copy from the failed task's own envelope inputs (same source the executor threaded
  at initial dispatch; no re-derivation needed).
- **Verify:** deterministic replay vs fay-14 stored artifacts — rebuild the
  RunDetailView repair envelope under the fix; rendered repair prompt must contain the
  anchor inventory block; today's provably doesn't.

### 5. #669 — framing re-roll rejection context
- **Seams:** `adapters/cycles/dispatched_flow_executor.py` re-roll path (~L644:
  `_create_next_workload_run`) + the #657 envelope-local `artifact_contents` channel
  into the proposer/merger prompts (`planning_tasks.py` renders it already — #660's
  machinery reused wholesale).
- Thread: the gate rejection reasons (already persisted in `gate_decisions`) + the
  rejected `implementation_plan.yaml`, framed in an appendix asset as "prior attempt
  + why it was rejected — revise, don't repeat" (prose in the asset per the #448 rule).
- **Verify:** replay vs fay-19's framing-1 rejection — the rebuilt re-roll envelope
  carries the rejection text + prior plan; plus a seam test that a NON-re-roll framing
  envelope carries neither.

## Sequencing

One lane, five PRs, one issue per PR (`Closes #N` each), in the order above —
reaper first (independent), the validator pair second/third (same seam, reviewed
together), the two threading fixes last (both are prompt-context plumbing; #667's
pattern informs #669's). No cross-PR dependencies; any can land independently if
review stalls another.

## Test standard notes
- Validator rules: stored-plan replays as fixtures (the real fay YAMLs, not synthetic
  minimal plans) + one negative (clean plan passes) each. No tautological
  count-the-rules tests.
- Threading fixes: envelope-content assertions (the block RENDERS), not
  mock-call-count; one boundary test each (non-repair / non-re-roll path unchanged).

## Deploy + release
- All five merged → single deploy window: rebuild all + restart + verify-LOADED
  behaviorally in-container (reaper: rows ended + clean dispatch log; validators:
  fire on stored fay-17/18 shapes in-container; threading: rendered-prompt checks).
- No re-seed (hashes untouched — assert at deploy: contract v9/manifest v4 ids
  unchanged).
- Patch release ritual: `version_cli.py bump 1.4.1`, ROADMAP timeline entry, README
  "Current" line, tag `v1.4.1`. SIP status: none move.
- First post-deploy cycle (whenever the next real roll runs, no dedicated window):
  watch the two threading fixes' first live firings and the validators' first
  teaching rejections; #672's success is silence.
