# Fix + Dev Plan — Deterministic Fill-Slot Binding at Plan Authoring

**Status:** proposed (SIP-0100 follow-up — the real "3.5"). Fix, not a new SIP.
**Owner surface:** plan authoring (`task_plan.py`, `implementation_plan.py`, proposer prompt assets) +
a read-only projection of `write_authorization.py`.
**Revision:** v2 — incorporates design review (invariant precision, canonical paths/globs, trusted
deliverables, coverage + duplicate-ownership, classified bounded re-roll, role matrix, prompt structure).

## The finding (evidence-backed)

A `full` (27b) `validated-fullstack` roll (`cyc_8a61a853f979`, 2026-07-23) produced a plan whose dev
tasks targeted **frozen** files (`backend/main.py`, `backend/models.py`) and **undeclared** paths
(`.tsx` under `frontend/src/components/`, `backend/store.py`) — **zero** fill-slot targets. It never
named `backend/routes.py` or `frontend/src/views/*.jsx`.

**Root cause (grep, not theory):**
- Dev-task targets come straight from the proposer: `task_plan.py:567` → `inputs["expected_artifacts"]
  = plan_task.expected_artifacts`, read from the LLM's task dict (`proposed_role_tasks.py:357`).
- `scaffold.fill_slot_paths(manifest)` — the authoritative writable-slot list — is consumed **only**
  on the enforcement side (`bound_scaffold_record.py`, `write_authorization.py`), **never** in the
  plan/proposer flow.
- So **nothing deterministically binds dev-task targets to the fill slots.** The proposer guesses; it
  hits `routes.py`/`views` only by LLM adherence, which varies by model and roll. The authoring-side
  bind never existed; earlier plans landed on the slots by luck (pf-26's brief itself said
  `app/routers/`, `src/pages/`).

SIP-0100 made **writes** contract-bound but left **requests** for those writes probabilistic. This
plan closes that.

## The invariant (bind mode)

> Every **workspace-mutating** expected artifact declared by a development task MUST resolve, under
> canonical workspace-path semantics, to an authorized writable path in the bound scaffold ownership
> record. No workspace source target may be inferred, invented, or accepted solely from proposer
> output. QA tasks are held to the same rule against the QA-authorized surface.

`expected_artifacts` is not all workspace mutations. Validation MUST first classify each declared
artifact into exactly one of:

1. **workspace mutation target** — a source/test file the task writes into the build workspace (the
   only class the invariant authorizes);
2. **evidence / report artifact** — run outputs (test reports, decision docs) that never land in the
   workspace source tree;
3. **declared external deliverable** — a non-workspace output (see the trusted-source rule below);
4. **directory / glob / symbolic descriptor** — resolved per the bounded-scope rule below.

Over-strictness (rejecting a legitimate report) and escape hatches (a mutation smuggled in as a
"deliverable" or a glob) both live in this classification — it is load-bearing.

## Authorization matrix (state before implementing)

| Role | Workspace source | Test slots | Evidence/report namespace | Declared deliverable | Frozen files |
|------|------------------|-----------|---------------------------|----------------------|--------------|
| **dev fill** | authorized fill slots only | only if a slot is declared dev-owned | no, unless declared | yes, only from a trusted framing declaration | **never** |
| **qa** | never (unless an explicit correction grant exists — the SIP-0100 §3.1/§3.2 grant/delegation) | QA-authorized slots only | yes | yes, only from a trusted framing declaration | **never** |
| **builder** | packaging/manifest slots per the build profile | no | yes | packaging deliverables per profile | **never** |

QA is explicitly **not** compressed to "qa→namespace": SIP-0100 was motivated by QA rewriting a frozen
implementation file, so QA touching product source requires an explicit correction grant, nothing less.

## Canonical paths + bounded scope (before any comparison)

Target-slot validation MUST canonicalize every workspace artifact using the **same path-resolution
semantics as runtime write authorization** (`normalize_ws_path`, D7) — `./`, `//`, `..`, repeated
separators, repo- vs workspace-relative, platform separators, workspace-filesystem case sensitivity,
and symlink resolution if the build workspace can contain symlinks. Textually different paths that
resolve to the same workspace location MUST receive the same authorization result — a plan can neither
be wrongly rejected nor bypass the gate via alternate notation.

`fill_slot_paths` returns **concrete files** (`backend/routes.py`, `frontend/src/views/RunCreationForm.jsx`).
So the default rule is: **reject directory/glob targets; require concrete slot targets.** A bounded
namespace target passes ONLY if the ownership record authorizes the same bounded namespace AND the
validator can prove the proposed scope is a subset of the grant (never "the glob textually resembles an
allowed one"). `frontend/src/**` never passes because one authorized view lives below it.

## Trusted deliverables (close the bypass)

A proposer-authored artifact does **not** become authorized merely because the proposer labels it a
deliverable. Deliverable authorization MUST originate from a **trusted pre-proposer framing artifact**
established before plan generation — the request contract, the scaffold manifest, the verification
contract, or an operator-approved output declaration. Otherwise the proposer could declare
`backend/main.py` a "deliverable" and restore the exact nondeterminism this fix removes.

## Dev plan (revised phase shape)

### Phase A — Publish authoritative planning surfaces
At bind time, derive a read-only **planning authorization projection** from the bound scaffold
ownership record + trusted deliverable declarations, and inject it into proposer inputs alongside
`contract_criteria_index` (`task_plan.py:389`; rendered at `planning_tasks.py:849-853`). Expose it as
**separated, named surfaces**, not one blob:

- `READ_ONLY_CONTEXT_PATHS` (frozen files — read for context, never a mutation target)
- `DEV_WRITABLE_SLOTS`
- `QA_WRITABLE_SLOTS`
- `DECLARED_NON_WORKSPACE_DELIVERABLES`
- `REQUIRED_SLOT_COVERAGE` (the slots the plan MUST assign)

Asset prose (#448) states: every workspace-mutating dev task names ≥1 entry from its writable surface;
do not translate extensions/frameworks/dirs/naming; do not swap a concrete slot for a similar file;
frozen files are read-only context; a non-mutating task fabricates no source artifact; all required
slots are assigned. Data in code, instruction in the asset.
**Files:** `task_plan.py`, `planning_tasks.py`, a bind appendix asset. **Acceptance:** the rendered
proposer prompt names the exact slots under the right headings; injection + asset-render tests.

### Phase B — Validate authorization + coverage (the core)
Before a bind-mode plan is accepted, at `task_plan.py:688` (beside `validate_criteria_refs`):
1. classify each declared artifact (workspace-mutation / evidence / deliverable / glob);
2. **canonicalize** every workspace-mutation target;
3. **authorize** it via the same canonical decision path as runtime enforcement (a lossless read-only
   projection of `WorkspaceOwnership` — see the boundary note);
4. reject unauthorized, ambiguous, or over-broad targets;
5. **coverage**: every required fill slot is assigned exactly once (missing → reject; two tasks on one
   slot → reject — the same invariant as duplicate-ownership, from both sides);
6. permit non-workspace deliverables ONLY from a trusted pre-proposer declaration.
Reject the **whole plan atomically** if any workspace target is unauthorized — never silently strip a
target (that would change plan semantics and hide proposer behavior). Route rejection through the
bounded framing re-roll machinery (#522).
**Files:** `implementation_plan.py` (new validation), `task_plan.py:688`, read-only projection off
`write_authorization.py`. **Acceptance:** the deterministic matrix below.

### Phase C — Deterministic slot allocation (if indicated — not merely a stretch)
C is the **logical completion** of contract-first planning, deferred to avoid expanding the immediate
repair — not because deterministic allocation is unnecessary. A+B still let the proposer decide task
count, slot grouping, ownership, and whether a slot is assigned. If evidence after A+B shows recurring
target re-rolls, missing-slot plans, duplicate ownership, or unstable grouping, promote C.
**Middle step (C-lite):** deterministically create the slot assignments, let the proposer **group**
authorized slots into tasks and describe implementation intent, then validate full coverage +
uniqueness — removes path invention without forcing one-task-per-file granularity on large scaffolds.

## Rejection classification (first-class)

A target-slot rejection is a **deterministic plan-contract violation** — not proposer-quality, not
implementation failure. Stable codes (family: `FailureClassification.CONTRACT_COMPLIANCE`, reusing 0.5):
`PLAN_TARGET_UNAUTHORIZED`, `PLAN_TARGET_MISSING_REQUIRED_SLOT`, `PLAN_TARGET_DUPLICATE_OWNERSHIP`,
`PLAN_TARGET_AMBIGUOUS_SCOPE`. Each rejection record carries: task id, role, raw target, canonical
target, authorization result, matched/nearest authorized slot(s), and the source ownership-record /
contract hash. This lets the re-roll prompt name the exact defect + alternatives, keeps metrics honest,
and lets a circuit-breaker spot a proposer that structurally can't comply.

## Bounded re-roll behavior

Repeated target-binding rejection is bounded by the framing retry policy. The corrective prompt
includes the **rejected canonical targets and their exact authorized alternatives** (not a replay of
the original slot list). Exhaustion terminates with a **distinct plan-binding failure** and does **not**
proceed into implementation. Acceptance: first rejection yields actionable correction context; repeated
identical violations are detected; exhaustion stops before any build task executes; the final report
reads *authoring-bind failure*, not build-convergence failure.

## Acceptance

**Deterministic (unit, group_run manifest, mirroring `test_write_authorization.py`)** — atomic
whole-plan reject on any unauthorized workspace target (no silent strip):
authorized exact file · frozen file · undeclared file · authorized namespace child · over-broad dir ·
over-broad glob · normalized-equivalent path · traversal path · duplicate slot assignment · missing
required slot · optional slot omitted · proposer-declared-but-untrusted "deliverable" · trusted declared
deliverable · non-workspace evidence output · dev target assigned to QA · QA target assigned to dev ·
correction task with/without an explicit correction grant · mixed task (legal + illegal targets) · task
with no workspace-mutating artifacts.

**Live (a bounded bind-mode validation set, not one roll)** — across profiles including the one that
failed (`cyc_8a61a853f979`) and one that previously succeeded by chance: every accepted plan has **zero**
unauthorized workspace targets, **complete** required-slot coverage, and **no** duplicate ownership; any
violating plan is rejected before implementation. Record separately:
- unauthorized-target **escape** rate (MUST be 0) · missing-required-slot escape rate (MUST be 0)
- first-pass target-valid rate · avg target-related re-roll count · retry-exhaustion rate
- accepted-plan slot coverage · downstream empty-slot failures.
This separates correctness (the escape rates) from efficiency (the yield/re-roll rates).

## Architectural boundary

Plan validation MUST reuse the canonical write-authorization **decision path or a lossless read-only
projection** of it — it MUST NOT independently reimplement fill-slot, frozen-file, role, or deliverable
rules (that would drift from runtime). But the plan domain model MUST NOT construct or depend on runtime
grant objects: the caller derives a read-only authorization projection from `WorkspaceOwnership` and
passes it in — `validate_plan_write_targets(plan, projection)`, not
`ImplementationPlan.validate_target_slots(ownership)`. **One authority, not necessarily one object type.**

## What this supersedes

Supersedes the brief-generation fix as the **primary correctness remedy**: the brief was never the
authoritative root cause, and fixing it alone cannot establish correctness (it can't be the
authorization mechanism). Brief quality may still improve first-pass proposer adherence and reduce
re-rolls — a worthwhile *quality* lever, kept, just not the *bind*.

## Risks

- **Over-strict rejection** blocking a legitimate deliverable/report — mitigated by the classification
  step + trusted-deliverable rule; start permissive on evidence/reports, tighten on measured escapes.
- **Re-roll cost** if A's first-pass yield is low — measure the first-pass rate after A before leaning
  on B's gate; low yield is the signal to promote C-lite.
