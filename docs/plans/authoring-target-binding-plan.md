# Fix + Dev Plan — Deterministic Fill-Slot Binding at Plan Authoring

**Status:** proposed (SIP-0100 follow-up — the real "3.5"). Fix, not a new SIP.
**Owner surface:** plan authoring (`task_plan.py`, `implementation_plan.py`, proposer prompt assets) + reuse of `write_authorization.py`.

## The finding (evidence-backed)

A `full` (27b) `validated-fullstack` roll (`cyc_8a61a853f979`, 2026-07-23) produced a plan whose dev
tasks targeted **frozen** files (`backend/main.py`, `backend/models.py`) and **undeclared** paths
(`.tsx` under `frontend/src/components/`, `backend/store.py`) — **zero** fill-slot targets. It never
named `backend/routes.py` or `frontend/src/views/*.jsx`. This is the same shape that blocks every
bind-mode roll: the scaffold restores/drops the mis-targeted emissions and the fill slots stay empty,
so the app can't converge.

**Root cause (grep, not theory):**
- Dev-task targets come straight from the proposer: `task_plan.py:567` → `inputs["expected_artifacts"]
  = plan_task.expected_artifacts`, and `proposed_role_tasks.py:357` reads them from the LLM's task dict.
- `scaffold.fill_slot_paths(manifest)` — the authoritative writable-slot list — is consumed **only**
  on the enforcement side (`bound_scaffold_record.py`, `write_authorization.py`). It is **never**
  consumed in the plan/proposer flow.
- So **nothing deterministically binds dev-task targets to the fill slots.** The proposer reads the
  contract (which references `routes.py`) and *chooses* to target it — or not.

**Why earlier rolls looked fine:** they didn't have a working "bind chain" — they had a proposer that
*happened* to choose `routes.py`/`views`. The plan-authoring **briefs were always noisy** (pf-26's
brief said `app/routers/`, `src/pages/`); the *plans* landed on the fill slots by LLM adherence, which
varies by model and by roll. This corrects two earlier mis-reads: it is **not** `lite`-only model
capacity, and it is **not** a code regression — it is the **absence of a deterministic authoring-side
bind**, present since bind mode shipped and masked by lucky draws.

## The principle

Enforcement **derives** its truth from `fill_slot_paths` (deterministic); authoring **guesses** (LLM).
Apply the enforcement's authority to authoring: the proposer targets the fill slots because the code
*tells* it those are the only writable paths, and the plan is **rejected** if it doesn't — reusing the
**same `write_authorization` surfaces** the runtime enforcement uses (`WorkspaceOwnership`,
`WriteGrant.for_dev_fill`/`for_qa`). "Scaffold the interface deterministically; the LLM fills the
implementation" — applied to the plan's *targets*, not just its bodies.

## Dev plan

| # | Phase | What | Files | Acceptance |
|---|-------|------|-------|-----------|
| A | **Inform** | At bind time, derive the per-role writable surfaces from the contract skeleton / `fill_slot_paths(manifest)` and inject them into the proposer inputs alongside `contract_criteria_index`; the proposer is told (asset prose, #448) "write ONLY these paths; frozen files are read-only." Data in code, instruction in the asset. | `task_plan.py:389` (inject `writable_slots`), `planning_tasks.py:849-853` (render), a bind appendix asset | rendered proposer prompt names the exact fill slots; unit test on the injection + a render test on the asset. |
| B | **Validate-reject (the core)** | Add `ImplementationPlan.validate_target_slots(ownership)` that, in bind mode, rejects any dev task whose `expected_artifacts` fall outside `WriteGrant.for_dev_fill` and any qa task outside `for_qa` (∪ declared deliverables) — **reusing `write_authorization`**, the identical authority the runtime uses. Invoke it in `task_plan.py:688` beside `validate_criteria_refs`; a violating plan is rejected → framing re-roll (#522 machinery). | `implementation_plan.py` (new method), `task_plan.py:688`, reuse `write_authorization.py` | a plan targeting `main.py`/`.tsx`/`store.py` is rejected with per-task reasons; a plan targeting `routes.py`+`views/*.jsx` passes; deterministic tests over both. |
| C | **(stretch) Scaffold the plan** | Derive the dev-task *skeleton* from the fill slots directly — one fill task per slot (`routes.py`, each `views/<View>.jsx`) — so the LLM only fills bodies, never picks targets. Removes target variance entirely. Bigger change; do only if A+B leave residual drift. | `task_plan.py` / a plan-scaffolder | a bind-mode plan's dev tasks are exactly the fill slots, regardless of proposer output. |

## Why A+B first

A informs; B *guarantees*. B alone (a hard gate reusing the enforcement's own authority) makes targeting
reliable without any task→slot semantic mapping — a mis-targeted plan simply can't pass framing. A
raises the first-try hit rate so B doesn't burn re-rolls. C is the fuller "scaffold the plan" form but
is only worth it if A+B don't converge; measure first.

## Verification

- **Deterministic:** unit tests on `validate_target_slots` (dev→fill-slot pass, frozen/undeclared
  reject; qa→namespace) reusing the group_run manifest, mirroring `test_write_authorization.py`.
- **Live:** re-run the `full` `validated-fullstack` roll; the plan must clear framing with all dev
  targets ∈ fill slots (the check I run by hand at the gate becomes an automatic reject). This is the
  gate that was manually held on `cyc_8a61a853f979`.

## Relationship to SIP-0100

SIP-0100 secured the **write side** (frozen restored, cross-lane dropped, evidence, circuit-breaker).
This secures the **authoring side** with the same authority, closing the loop the enforcement can't
close alone: enforcement stops bad writes; this stops the plan from *asking* for them. Supersedes the
brief-gen fix floated during the investigation (the brief was always noisy and didn't matter — the
*targets* are what need binding).

## Risks

- **Over-strict rejection** could block a legitimate deliverable a dev task emits (e.g. a doc). Mitigate
  by scoping B to *workspace source* targets and allowing declared deliverables — same
  workspace-vs-deliverable line the enforcement already walks; start permissive, tighten on evidence.
- **Re-roll cost** if A's hit rate is low: measure the first-try rate after A before relying on B's gate.
