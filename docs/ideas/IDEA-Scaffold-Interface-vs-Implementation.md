# IDEA: Scaffold the Interface, Generate the Implementation

## Target Release
Vision item — motivating principle for `sips/proposed/SIP-Contract-First-Build-Scaffolding.md`.

### Status
Idea / lesson-learned draft

### Owner
Build / Architecture

### Origin
Distilled from the group_run 1.3.1 regression (cycle `cyc_769db63c9d2b`): a `completed` full-squad cycle shipped a React frontend that fails `vite build` at `✓ 0 modules transformed` — no `index.html` / `src/main.jsx` entry point, and an `App.jsx` that rendered inline `<h1>` stubs while never importing the three real components it had written. See #376 (field evidence) and the honest-red work in SIP-0096.

---

## The lesson

The failure was never *"a 27B can't build a Vite app."* It built the **hard** part — real, working components — and dropped the **rote** part: the entry files and the cross-file wiring. That is not a capability ceiling; it is an **unscaffolded task**. The system was asking the model to do the thing LLMs are *worst* at — rote, cross-file-consistent assembly held in working memory across independent tasks — and then repairing the inevitable slips reactively. **That is backwards.**

Invert it:

- **Scaffold everything that is identical regardless of what the app does** — entry files, config, bootstrap, directory layout — deterministically, from a template. No LLM judgment; it is the same every time.
- **Generate only what depends on what the app does** — the component and endpoint *bodies*, the actual logic. That is where the model adds value and is reliable.
- So the dividing line is **not "boilerplate vs. logic." It is "interface vs. implementation."**

And the elegant part: **the interface is already framing's job.** Framing designs the entities, endpoints, and routes — today as prose trapped in a prompt. Make it emit that as a **typed interface manifest**, and a deterministic expander turns it into a **walking skeleton that already builds and boots**. The dev agent then *fills bodies into a green baseline it cannot rewire* — extending working code, instead of assembling boilerplate and logic simultaneously and hoping it all connects.

**Net:** the model does its strongest thing (localized logic) and is structurally prevented from its weakest (global consistency). Failures shift from *"forgot the entry file / didn't wire the imports"* — now impossible — to *"this component has a bug"* — which is real, and exactly where a repair loop earns its keep. And you judge it **behaviorally** (does it build, boot, pass its endpoint tests?), not structurally (*"does a file with the right shape exist?"*).

## Why this is not the advisory scaffolding we already have

`dev_capabilities.py` already *tells* the agent "Include `frontend/index.html` as the Vite entry HTML" and shows an example tree. The 27B ignored it. Prose guidance in a prompt is not a scaffold. The difference that matters: the skeleton must be **materialized files the agent fills**, with the wiring **scaffold-owned and off-limits** — so re-dreaming it is structurally impossible, not merely discouraged.

## Relationship to the honest-red work

Complementary, not competing. SIP-0096 (Verification Evidence Integrity) makes a broken build **honest** — a failed/unverified run reads as red instead of false-green. This idea makes that failure **rare** — most of the failure class never occurs because the invariants are scaffolded, not generated. One is detection; the other is prevention. You want both.

## What "enough design" means

The scaffold needs the app's **interface contract** and no more: entities (name + fields), endpoints (method + path + shape), routes (path + component + which endpoints it uses). Three short lists — exactly what framing already produces in prose, and small enough that a 27B emits it reliably as structured data. Everything below that line is implementation, and stays the model's job. This fits CRUD-shaped web/CLI apps (what the example projects are); a genuinely novel architecture needs a richer manifest or degrades gracefully toward more LLM freedom.
