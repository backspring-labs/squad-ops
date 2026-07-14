# IDEA: Getting to a Functional App — Current Obstacles and Resolution Roadmap

**Date:** 2026-07-14
**Status:** Idea / discussion draft (written for a second opinion)
**Evidence base:** five live cycles run 2026-07-14 on the Spark deploy
(`cyc_bc325a67417d`, `cyc_dafd6b5fe58c`, `cyc_7d2f505e5e8f` — group_run/lite;
`cyc_23c6d9a7363a` — play_game/lite; `cyc_b9be8be77b31` — group_run/full,
in flight at time of writing), plus the #374/#376 post-mortem.

## North star and current state

The goal is a cycle that ends with a **functional app** — one that assembles,
boots, and does what the PRD says — not a cycle that ends `completed`. The
#376 lesson stands: those are different claims, and until recently the system
could only make the first one. No cycle to date has produced an app that ran
without manual intervention.

Today's sessions produced an unusually clean failure taxonomy. The headline:
**almost nothing failed because an LLM wrote bad application code.** Even 7b
devs produced acceptable components; 27b devs produced correct Vite/Router
structure first try. What failed was everything around the code. That should
drive where we invest.

## Obstacles, ranked by what actually blocks "app runs"

### O1 — The verification environment cannot verify (blocking, not close)

The deployed stack structurally cannot answer "does the frontend build?":

- **Node.js is absent from agent evaluation sandboxes** (#306). Live evidence:
  roll 4's dev task emitted a *correct* frontend and still failed its
  `node --check` acceptance with `command_spawn_failed` — the binary does not
  exist. The 27b corrector correctly classified this as environmental
  (`failure_classification: execution`, `correction_path: continue`), which is
  the right behavior, but the check simply never runs on this box.
- **Skip-as-pass** (#423): typed checks on unsupported syntax/extensions are
  `skipped` but counted `passed: true`. In `cyc_bc325a67417d`, 7 of 14
  evaluations were free passes, including every `.tsx` import contract.
- **The command safelist is static-analysis only** (py_compile/mypy/node
  --check/ruff/tsc/eslint/pyflakes). Nothing that *runs* the app or its tests
  is executable as an acceptance command — by design (RC-10a security posture),
  but it caps what "verified" can mean. The `command_check_safelist` CRP key
  that was meant as the operator extension point is declared but consumed
  nowhere (dead key, found during #425).
- **Failed runs are black boxes** (#427): terminal exceptions are persisted
  nowhere and runtime-api application logging never reaches stdout. Two of
  today's five cycles required reproducing executor code paths by hand to
  recover a failure reason the executor had already cleanly diagnosed.

Consequence: even a perfect plan with perfect code cannot read green honestly.
SIP-0096's `blocked_unverified` verdict (working — verified live twice today)
correctly reports this, but reporting the gap is not closing it.

### O2 — Apps fail to assemble, not to compile (the #376 class)

The historical failure that motivated this whole arc: components are fine,
but the *app* doesn't build — missing entrypoints, files that disagree about
imports and paths, absent index.html. One-shot generation has no mechanism
that guarantees cross-file agreement, and the correction loop repairs code
defects, not assembly gaps. This is the class the deterministic scaffold
targets (see `IDEA-Scaffold-Interface-vs-Implementation.md`: scaffold the
interface deterministically, LLM fills implementation only).

### O3 — Contract authoring was the biggest failure source; now largely mitigated

Three of today's five cycles died or degraded on plan-authoring defects:
unrunnable acceptance commands (`npm test`, `pytest`, `make`), invalid check
params, malformed YAML → silent static fallback (#424). Mitigations landed
today in #421 + #425 and verified live:

- Typed criteria survive distributed dispatch and are evaluated at every task
  seam, including `builder.assemble` (#419/#420; 10+ `typed_check_evaluation`
  artifacts per cycle where there were zero before).
- The safelist is single-sourced; the proposer vocabulary teaches the allowed
  command forms; the authoring lint rejects violations with corrective
  feedback. Post-fix evidence: 7b merger went from 0/3 valid plans to a
  clean converged plan; 27b merger authored 6/6 safelisted commands and picked
  the right form per stack (`py_compile` for Python, `node --check` for JSX).

Remaining tail: semantic check quality (a syntactically valid check that
means nothing), and the structural fix — **schema-constrained decoding** for
control artifacts (Ollama supports JSON-schema-constrained generation), which
would make the malformed-manifest class impossible rather than retried.

### O4 — Config coherence traps

The system's per-stack knowledge is scattered and self-inconsistent:

- Planner offers `builder.assemble` when the *squad* has a builder;
  `generate_task_plan` requires `build_profile` in *resolved config*; profiles
  exist that satisfy one but not the other → plans that pass the gate and are
  deterministically dead at implementation start (#426, found live today:
  8ms run failure).
- Plan-merge exhaustion silently downgrades a `typed_acceptance: true` cycle
  to untyped static steps (#424) — the profile's instrumentation promise is
  voided with no surface.

### O5 — Outcome honesty (mostly landed, tail remains)

SIP-0096's derive-on-read `CycleOutcome` + required-check throttle are working:
both failed cycles today reported `blocked_unverified` with explicit
`required_unmet`, not false green. Tail: #423 feeds wrong data into it, and
failing typed-check evaluations persist no artifact (#114 comment), so the C1
evaluator-error metric undercounts exactly the events it exists to measure.

## Roadmap

Ordering principle: **speed is explicitly not the concern yet** — each phase
is ranked by how directly it closes the gap between "cycle says done" and
"app runs."

### Phase 1 — Make verification real (gates everything)

1. Tooling parity in agent images: Node.js (+ npm for builds) in the
   evaluation sandbox (#306). The safelist already authorizes `node --check`
   and `tsc --noEmit`; the image must honor what the vocabulary advertises.
2. Fix #423 polarity: explicitly-targeted-but-unsupported checks surface as
   `unverified`/eval-gap, never `passed`.
3. Fix #427: persist terminal failure reason on the run; fix runtime-api app
   logging. (Cheap, and every later phase's debugging depends on it.)
4. Wire `command_check_safelist` into the now-single-sourced safelist seam,
   or delete the dead key.

### Phase 2 — Deterministic scaffold, delivered as "build profile = skill pack"

Reframe `build_profile` from a string into the unit that owns everything
stack-specific:

- the scaffold expander (manifest → deterministic project skeleton; pure
  function per the scaffold idea doc),
- `required_files` for the stack,
- safelist extensions the stack needs,
- the tooling manifest the agent image must satisfy (checkable by preflight —
  the #306 class becomes a validated contract instead of a discovered gap),
- the stack-specific prompt fragment (the vocabulary pattern, generalized).

This also dissolves #426 structurally: the planner offers builder tasks when
a real build profile is configured, not when a squad happens to carry a
builder. Scope discipline per the amortization thesis: **one expander**
(fastapi+react, the canonical stack) until it proves out.

### Phase 3 — Builder tool-in-the-loop pilot (bounded)

Give the builder role only an interactive verify loop at assembly time: run
the build, read errors, patch, re-run — inside the task, instead of routing
every failure through the outer correction loop (minutes per round). MCP is
plumbing candidate, not the decision; the decision is one-shot-plus-validation
vs. agentic-with-tools for the one role whose job ("it assembles") is
intrinsically interactive. Bounded blast radius: one agent, one task type,
sandbox-scoped tools, safelist-governed. Success criterion: builder-seam
failures resolved in-task at a higher rate than the #413 outer loop achieves.
Known risk: local-model multi-turn tool-use reliability — which is exactly
what the pilot measures before any wider commitment.

### Phase 4 — Schema-constrained decoding for control artifacts

Plan, brief, proposals emitted as schema-valid JSON (converted to YAML where
the artifact contract wants YAML). Eliminates the #424-trigger class and the
SIP-0093 YAML-escaping class structurally. Subordinate to Phases 1–3 because
framing already converges on `full` with the #425 vocabulary+lint.

### Explicitly deferred

- **Mixed-tier squads** (27b judgment roles / 7b generation roles): a
  throughput optimization with real promise — today's tier delta concentrated
  entirely in judgment tasks, not generation — but it optimizes the wrong
  variable while functional apps are not yet routine. Revisit with a
  three-way experiment (lite/full/mixed, same PRD) once a `full` cycle
  reliably produces a working app.
- Broader MCP/tool access for dev agents: pending Phase 3 evidence.

## Model policy meanwhile

- Every real build attempt: uniform `full` (27b) — treat as settled, not a
  variable.
- Repair/enforcement-machinery validation: `lite` deliberately (small-model
  flakiness is organic fault injection).
- Deploy-alive smoke: `hello_squad`/`smoke`; PR smokes should exercise the
  changed surface (e.g. `play_game`/`lite`/`validation` for plan-authoring
  changes).

## Questions for the second opinion

1. Is Phase 1 before Phase 2 right, or should the scaffold land first on the
   argument that it shrinks what verification must prove?
2. Is "build profile = skill pack" the right home for the scaffold, or does
   bundling too much into one unit slow every stack addition?
3. Phase 3 security posture: is a sandbox-scoped, safelist-governed tool loop
   for one role an acceptable expansion of the execution surface, given
   RC-10a's original intent?
4. Is there appetite to treat the canonical-stack scaffold as *the* 1.4
   feature SIP, folding #306/#423/#426 hardening around it — or should the
   verification work ship first as pure hardening with the scaffold as the
   1.6 headline?
