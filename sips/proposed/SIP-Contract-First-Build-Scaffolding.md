---
title: Contract-First Build Scaffolding
status: proposed
author: jladd
created_at: '2026-07-10T00:00:00Z'
---
# SIP: Contract-First Build Scaffolding

## Status
Proposed

**Targets:** feature minor (even) — candidate build-reliability headline. Not release-blocking; sequenced after SIP-0096's honest-red layer lands (this SIP relies on behavioral acceptance to prove the scaffold works).
**Builds on:** the build lineage — SIP-0068 (Enhanced Agent Build Capabilities), SIP-0071 (Builder Role), SIP-0086 (Build Convergence Loop); and the framing/plan artifact `implementation_plan.yaml` (`src/squadops/cycles/implementation_plan.py`, authored in `_plan_authoring_service.py`).
**Motivating case:** #376 — the group_run 1.3.1 regression (`cyc_769db63c9d2b`) shipped a `completed` cycle over a React frontend that fails `vite build` (no entry point; `App.jsx` rendered inline stubs and never imported its own components). The root cause is not model weakness; it is an unscaffolded task. Distilled principle: `docs/ideas/IDEA-Scaffold-Interface-vs-Implementation.md`.
**Coordinates with:** SIP-0096 (Verification Evidence Integrity — makes failure *honest*; this SIP makes it *rare* — complementary), and SIP-Externalized-Build-Sandbox (*where* builds run; this SIP is about *what* gets scaffolded vs. generated — orthogonal).

---

## 1. Abstract

Today the build path asks the LLM to generate an entire runnable application — invariant framework boilerplate, cross-file wiring, **and** application logic — from prose, across independent `development.develop` tasks, then repairs the inevitable slips reactively through the SIP-0086 convergence loop. This inverts the division of labor: it hands the model the work it is *worst* at (rote, cross-file-consistent assembly) and leaves the work it is *best* at (localized logic) tangled up with it.

This SIP proposes **contract-first scaffolding**: framing emits a typed **interface manifest** (entities, endpoints, routes); a deterministic **expander** materializes a **walking skeleton** from it — a wired application that already builds and boots; the dev agent then **fills bodies into fixed, scaffold-owned slots** it cannot rewire. The dividing line between deterministic and generative work stops being *"boilerplate vs. logic"* and becomes *"interface vs. implementation"* — which is also the natural seam between framing (design) and development (build).

## 2. Motivation

*(The lesson this SIP encodes — see `docs/ideas/IDEA-Scaffold-Interface-vs-Implementation.md` for the standalone statement.)*

The failure that motivates this SIP was never *"a 27B can't build a Vite app."* In `cyc_769db63c9d2b` the model built the **hard** part — real, working components — and dropped the **rote** part: the entry files (`index.html`, `src/main.jsx`) and the cross-file wiring (`App.jsx` rendered inline `<h1>` stubs instead of importing the components it had written). That is not a capability ceiling; it is an **unscaffolded task**. The system asks the model to do the thing LLMs are worst at — rote, cross-file-consistent assembly held in working memory across independent tasks — and then repairs the slips reactively. That is backwards.

Invert it:

- **Scaffold everything that is identical regardless of what the app does** — entry files, config, bootstrap, directory layout — deterministically, from a template. No LLM judgment; it is the same every time.
- **Generate only what depends on what the app does** — the component and endpoint *bodies*, the actual logic. That is where the model adds value and is reliable.
- The dividing line is **not "boilerplate vs. logic." It is "interface vs. implementation."**

Two structural gaps in the current system make the failure class reachable:

- **The entry point is left to LLM discretion.** `frontend/index.html` and `src/main.jsx` exist only as prompt suggestions in `dev_capabilities.py` (`file_structure_guidance`), and the `fullstack_fastapi_react` builder profile's hard `required_files` is only `("Dockerfile", "qa_handoff.md")` (`build_profiles.py`). Advisory scaffolding is not a scaffold — the 27B ignored it.
- **Authorship-time acceptance is per-file syntax, not a whole-app build.** The develop step authors `node --check <file>` / `tsc --noEmit` / `eslint` checks (`_plan_authoring_service.py:169`). `node --check` passes on a syntactically valid `App.jsx` that has no entry point and imports nothing. Only a real `vite build` catches that — and today that lives two tasks downstream in QA.

The elegant resolution: **the interface is already framing's job.** Framing designs entities, endpoints, and routes — today as prose in the `implementation_plan.yaml` manifest. Emit it as *structured* data and a deterministic expander turns it into a skeleton the model only has to fill.

## 3. Proposal

A three-tier division of labor:

| Tier | Produced by | Content |
|---|---|---|
| **1. Stack scaffold** | deterministic template (per build profile) | Invariant framework files — `index.html`, `src/main.jsx`, `vite.config.js`, pinned `package.json`, FastAPI bootstrap, directory layout. Identical for every app of the class. |
| **2. App skeleton** | deterministic **expander**, from the interface manifest | Wired but empty — `App.jsx` routes + imports, named component stubs (correct default exports), FastAPI route stubs (correct paths/signatures), Pydantic models. **Must pass the build + boot before the dev agent touches it.** |
| **3. Bodies** | the **LLM** (`development.develop`) | Component and endpoint *implementations*, filled into fixed slots. |

Load-bearing properties:

1. **The interface manifest is the single source of truth.** Framing emits entities / endpoints / routes as typed, schema-validated data. It is reviewed at the `plan-review` / `progress_plan_review` gate — a far sharper human checkpoint (*"are these the right 5 endpoints and 3 routes?"*) than approving prose, and it happens before a line of code is written.
2. **The skeleton is materialized, not suggested.** Expanded files are written into the build workspace as real artifacts (via the existing seed/pre-resolve rails), so the dev agent extends a green baseline rather than assembling from a prompt.
3. **Wiring is scaffold-owned / fill-only.** The agent fills bodies; it does not rewrite `App.jsx`'s import graph. Adding a component means registering it in the manifest and re-expanding — which structurally prevents the inline-stub regression.
4. **Acceptance is behavioral.** The gate for the frontend workstream is a real `vite build` + boot, keyed off the manifest's endpoints for the tests — not per-file `node --check`.

## 4. Design

- **The expander is pure domain logic.** New module `src/squadops/capabilities/scaffold.py`, ideally hung off `BuildProfile` — `BuildProfile.expand(manifest) -> list[{path, content}]` — sibling to `build_profiles.py`/`dev_capabilities.py`, with per-profile templates packaged alongside. Pure `dict → list`, no I/O, unit-testable by exact-content assertion (feed a manifest, assert the emitted files parse and build). **No port / NoOp / factory** — it is pure logic like `build_profiles.py`, not a vendor integration.
- **The manifest schema is the keystone.** Extend `src/squadops/cycles/implementation_plan.py` with the interface contract (entities / endpoints / routes); have `_plan_authoring_service.py` emit and validate it. Get this schema right and both the expander and the behavioral acceptance checks key off it.
- **Invocation is one generic call from the executor's setup — never template logic in the god-file.** The executor already materializes the run root and seeds artifacts at the top of `_execute_sequential` (`dispatched_flow_executor.py`: `_materialize_run_root`, `_seed_prior_artifacts`, the D3 pre-resolution). Add a few lines there — *if build run + manifest present → `expand`, store as artifacts, seed* — delegating the template logic to `capabilities/scaffold.py` (consistent with the #290 "no domain coupling in the god-file" rule).
- **Hand-off reuses existing rails.** Expanded files ride the same pipeline build artifacts already use: artifact vault → `_seed_prior_artifacts` / D3 pre-resolve → `develop._materialize_artifacts` into the task workspace. No new adapter.

Data flow:

```
framing → implementation_plan.yaml  (manifest + interface contract, gate-reviewed)
   └─[impl run setup]→ BuildProfile.expand(manifest)   [pure, capabilities/scaffold.py]
        → file artifacts → vault → _seed_prior_artifacts / D3 pre-resolve
            → develop._materialize_artifacts → dev agent fills bodies into fixed slots
                → behavioral acceptance (build + boot + endpoint tests)
```

## 5. Scope

- **In:** the interface-manifest schema extension; the per-profile deterministic expander + templates (starting with `fullstack_fastapi_react`); materialization at the executor setup seam; fill-only scoping of `development.develop`; behavioral (build + boot) acceptance for the scaffolded workstream.
- **Applies first to:** `fullstack_fastapi_react`; then `python_cli_builder` and `static_web_builder` as follow-on template sets.

## 6. Non-Goals

- **No new verification-integrity mechanics** — that is SIP-0096's lane; this SIP consumes behavioral acceptance, it does not define the aggregation/verdict model.
- **No opinionated application design.** The scaffold is the *invariant substrate* (entry, config, wiring mechanism), not opinions about *this* app (state management, styling, structure). The test for "scaffold-able": *is it identical regardless of what the app does?*
- **No universal manifest.** This targets CRUD-shaped web/CLI apps expressible as entities/endpoints/routes (the example projects). Novel architectures need a richer manifest or degrade toward more LLM freedom — out of scope for v1.
- **Not a code generator replacing the squad.** The model still writes all application logic; the scaffold removes only the rote substrate.

## 7. Relationship to adjacent SIPs

- **SIP-0096 (Verification Evidence Integrity):** complementary. SIP-0096 makes a broken build *honest* (rejected / blocked_unverified instead of false-green); this SIP makes it *rare* (the failure class is scaffolded away). Detection vs. prevention — both wanted. This SIP also depends on SIP-0096's behavioral acceptance being enforced, which is why it sequences after it.
- **SIP-Externalized-Build-Sandbox:** orthogonal. That SIP governs *where* build/test execution runs (isolation, toolchain provisioning); this one governs *what* the LLM must produce vs. what is scaffolded. They compose cleanly.
- **SIP-0086 (Build Convergence Loop):** the repair loop shrinks from *"rebuild the app"* to *"fix a body-level bug"* — operating on a far smaller, more meaningful surface once the scaffold guarantees the app builds and boots.

## 8. Open Questions

1. **Manifest schema shape** — the minimal typed contract for entities/endpoints/routes, and how much the LLM authors vs. infers. (Keystone; resolve first.)
2. **New-component registration** — the exact mechanism by which the dev agent legitimately adds a component (manifest amend + re-expand) without a full re-run.
3. **Template ownership & maintenance** — per-profile template sets are an amortized per-system investment; which profiles justify it and how templates are versioned/pinned.
4. **Validation** — the cheapest proof is empirical: hand-write the group_run manifest, build the `fullstack_fastapi_react` expander, confirm the empty skeleton builds + boots, and re-run the cycle with dev scoped to fill-only — does the 27B produce a working app once freed of the plumbing?
