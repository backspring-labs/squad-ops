---
title: Scaffolded Test Harness and Frozen-File Enforcement
status: proposed
author: jladd
created_at: '2026-07-22T00:00:00Z'
updated_at: '2026-07-23T00:00:00Z'
---
# SIP-XXXX: Scaffolded Test Harness and Frozen-File Enforcement

## Status
Proposed

**Extends:** SIP-0099 (Contract-First Build Scaffolding). SIP-0099 makes the *interface*
scaffold-owned and frozen at generation time; this SIP promotes that ownership to a **lifecycle
invariant** and extends it to the **test boundary** — closing two gaps SIP-0099's current surface
leaves open, both surfaced empirically by the group_run measurement rolls.

**Coordinates with:** SIP-0086 (Build Convergence Loop) — this SIP gives the correction loop a
deterministic *contract-compliance* signal, distinct from an implementation-defect signal, so it
never spends convergence budget rediscovering a malformed (frozen-violating) correction.

**Motivating case:** pf-26 (`cyc_af8800f8943f`, deploy `ee4ac71c`). The backend `qa.test`
correction loop never converged — not because of the framing, targeting (RC2), or workspace-staleness
(RC3) fixes that preceded it, which all worked. Two distinct ownership violations combined:

1. **The test boundary was un-owned.** Source lives under `backend/` (a package), but the qa suite
   independently inferred its own application entry (`from app.main import app` — no `app` package),
   so pytest collection crashed before any assertion ran.
2. **Scaffold ownership did not survive repair.** The correction loop rewrote the *frozen*
   `backend/main.py` four times (`.routes` → `models` → `app.models` → `app.routes`) — and it was a
   **QA** correction rewriting production **source** it had no ownership of. The scaffold seeded a
   correct `main.py`; the repair destroyed it.

The system never identified the frozen overwrite as the actual breach; it re-entered ordinary
convergence and oscillated to exhaustion.

---

## 1. Architectural statement

**Scaffold ownership is a lifecycle property, not a generation-time hint.** Once a build attempt
binds to a scaffold instance, that instance defines both:

- the **deterministic artifacts** whose bytes remain invariant for the life of the attempt; and
- the **generative slots** that named producers may modify, each within its declared scope.

Every artifact-producing stage — initial fill, QA fill, correction/repair, retry/continuation,
artifact merge, patch materialization, verification preparation, and any producer introduced later —
must **enforce that ownership boundary before materialization and verify it afterward**. Prompt
instructions may improve compliance, but only contract-governed **path authorization** and
**integrity verification** establish the guarantee.

This is the abstraction pf-26 demands: the architecture delegated a deterministic structural decision
to multiple generative actors, and it did not preserve scaffold ownership during repair. Both are
lifecycle-ownership defects, not a "bad import."

## 2. The frozen-file invariant

> **Frozen-file invariant.** From scaffold materialization until completion or abandonment of the
> bound build attempt, the bytes at every frozen path MUST equal the scaffold-materialized bytes
> identified by the bound scaffold instance — regardless of which producer or lifecycle stage emits a
> conflicting artifact.

This gives acceptance a precise property to prove. "Frozen" today describes an *initial-fill*
constraint; this SIP makes it a *bind-time-to-completion* constraint.

**Hash identity and timing.** The authoritative frozen bytes and hashes are captured from the
**fully materialized scaffold instance at bind time** — after any expansion-time substitution
(e.g. `project_id`), not from the raw expander template and not from the verification contract alone.
The hash is bound to the specific build attempt. Restoration, where used, restores from *that bound
instance*, never by re-running the current (possibly newer) expander. This keeps deterministic replay
sound: a later scaffold revision can never mutate an in-progress or replayed attempt.

## 3. Enforcement model: authorize → materialize → verify

Enforcement is **primarily authorization**, with integrity verification and restoration as defense in
depth — not the reverse. The normative sequence at every producing stage is:

1. **Pre-materialization authorization.** Reject any emitted path outside the producer's authorized
   write set *before* writing. A frozen path is never in any generative producer's write set.
2. **Materialize permitted artifacts** (the producer's authorized slots only).
3. **Post-materialization integrity verification.** Confirm every frozen path's bytes still equal the
   bind-time scaffold bytes.
4. **Restoration** (defense in depth): if integrity is unexpectedly violated, restore from the bound
   scaffold instance and record it as an enforcement fault — never silently.

The rejected alternative — *materialize everything, then overwrite frozen files with originals* — is
explicitly **not** the mechanism: it permits forbidden content to exist transiently, and it can
normalize an enforcement bug instead of surfacing it.

**Write authority is the general capability; frozen files are the minimal scope here.** This SIP does
**not** introduce a general filesystem authorization model, but frozen enforcement MUST be implemented
through a **contract-owned path-authorization seam** — never a stack-specific or filename-specific
blacklist. The seam expresses:

- `frozen_files` are always outside generative write authority;
- a **fill** producer may write only its declared fill slots;
- a **repair** producer may write only the repair-authorized subset of fill slots;
- a **QA-owned** producer (fill or correction) may write only QA-owned slots **unless the bound
  correction request explicitly delegates an implementation slot** (see §4.4);
- future contract-owned artifact classes (databases, queues, auth boundaries, integration harnesses)
  reuse the same seam without expanding this SIP's acceptance burden.

## 4. Proposal

### 4.1 Piece A — Scaffold owns the test *boundary* (not merely an import line)

> **Test-boundary invariant.** Test suites consume a scaffold-provided application test boundary and
> MUST NOT import or construct the application entry point independently.

- **Cross-stack requirement:** the expander owns the test application boundary.
- **Current-stack realization (`fullstack_fastapi_react`):** a frozen root `conftest.py` exposing a
  `client` fixture backed by FastAPI `TestClient`, bound to the canonical `backend` package root.

Framing the boundary semantically (not as "a root `conftest.py` with a fixture named `client`") leaves
room for the harness to grow to own environment setup, dependency overrides, test-DB lifecycle,
startup/shutdown, auth fixtures, seeded state, and async transport — without re-litigating the
architecture. Piece A is **prototyped and proven** for the first stack (see §6).

**Test-file ownership model.** The scaffold owns the test *boundary* (the frozen harness); the test
*files* are QA fill slots, governed by the same slot model SIP-0099 uses and the §3 authorization seam:

- QA test-slot paths are **declared in the bound plan and deterministic** — the producer fills bodies
  into fixed paths, it does not free-choose file locations.
- A QA producer (fill or correction) may write **only** its declared test-slot paths. A file at an
  undeclared path is an **unauthorized write** (§3), not a silent addition — so "can QA add test files"
  is answered by the plan's declared slot set, not by producer discretion.
- The scaffold is **not required to seed a skeletal test file**; the per-stack invariant is the
  *boundary* (the frozen harness), not a stub. A stack MAY seed a skeletal fixture-based smoke test as
  realization, but that is optional and, if seeded, is itself frozen.
- **Repair authority follows §4.4:** a QA correction may modify only QA-owned test slots and has no
  authority over implementation slots (`routes.py`, views) unless the bound correction request
  explicitly delegates one. This is what pf-26 violated — a QA correction wrote production source.

### 4.2 Piece B — Frozen enforcement across fill *and* repair (the lifecycle teeth)

Implement §3 (authorize → materialize → verify) at every artifact-producing stage, deriving the
authorized-write set and frozen set from the **same** `fill_slot_paths` / `frozen_files` the contract
already owns (single source of truth — no second definition of "frozen"). pf-26 proves this is not
optional: the scaffold seeded a correct `main.py` and the repair overwrote it.

### 4.3 Piece C — Bind the QA proposer to the boundary, and verify it mechanically

Prompt guidance and mechanical enforcement are **separate**, and the SIP relies on the latter for the
guarantee:

- **Prompt (guidance):** the QA fill-only appendix directs suites to consume the scaffold `client`
  fixture and never author an app import. Prompt content lives in the managed asset, not Python
  (CLAUDE.md #448).
- **Mechanical (guarantee):** deterministic validation establishes whether the generated suite
  actually uses the scaffold-owned boundary. At minimum, a bound QA plan/artifact that authors its own
  application import in a QA test slot (e.g. `from app.main import app` **or** `from backend.main
  import app` — technically resolvable, still a boundary violation) is **rejected** by a
  stack-owned harness check. A narrow stack-owned check suffices; no universal AST policy is required
  in this SIP. The central claim — the package root "stops being a per-suite guess" — is only as
  strong as this mechanical check; prompting alone cannot establish it.

### 4.4 QA-correction write authority (the second pf-26 defect)

pf-26 was not only a frozen overwrite; a **QA** correction producer had write authority over production
**source** outside its ownership. Independent of frozen-ness:

> A QA-owned correction may modify only QA-owned fill slots unless the bound correction request
> explicitly delegates an implementation slot.

This prevents a future recurrence even for non-frozen implementation files, and it is expressed through
the same §3 path-authorization seam.

### 4.5 Failure and correction semantics (SIP-0086 coordination)

On any frozen-path or unauthorized-path emission, the orchestrator MUST:

1. not materialize the forbidden artifact;
2. record a structured **scaffold-integrity violation** (§5);
3. return a **targeted correction** to the same producer naming its permitted slot paths;
4. **not** consume an ordinary implementation-verification attempt — track it separately as a
   contract-compliance attempt;
5. stop after a bounded number of repeated contract violations.

"Respect frozen files" must mean the loop receives *actionable, deterministic feedback and preserves
convergence budget for real implementation defects* — not that it merely fails differently.

### 4.6 Response atomicity (resolving "reject or drop")

A producer response containing **any** frozen-path or unauthorized-path mutation is a **contract
violation**; the forbidden artifacts are never materialized and the frozen originals remain intact.
The remaining question — whether permitted sibling artifacts from the same response are retained — is
resolved by one **defined atomicity rule**, applied identically on every path:

- **Default: response-atomic.** If any emission is forbidden, reject the entire producer response and
  request a constrained correction. This is the safe default (silent partial application of a
  multi-file repair is a diagnosis and evidence hazard).
- **Artifact-atomic** (retain the permitted slot artifacts, reject only the forbidden ones) is
  permitted **only** where artifact-level validation is already atomic and unambiguous.

The SIP fixes *response-atomic* as the default so different paths cannot enforce "frozen" differently.

## 5. Evidence semantics for attempted violations

An attempted frozen/unauthorized write is a **malformed correction response**, not a failed
implementation hypothesis, and must be classified distinctly (e.g. `scaffold_integrity_violation` /
`frozen_path_violation`) — never as a generic test or patch failure. Structured evidence records, at
minimum:

- producer / lifecycle stage;
- attempted path (and its normalized form);
- bound scaffold / contract identity;
- expected frozen hash and observed/attempted hash;
- enforcement disposition (rejected; response-atomic vs artifact-atomic);
- whether permitted sibling artifacts were retained or rejected;
- whether a targeted correction was re-requested.

This preserves the causal signal for future Campaign analysis and Functional App Yield measurement,
and keeps the pf-26 breach identifiable as a breach.

## 6. Prototype and proof (Piece A, partial)

Piece A is prototyped (merged via PR #538) and proven deterministically — no cycle, no LLM:

- **Positive:** a `client`-based qa suite runs against the freshly-materialized skeleton → `1 passed`,
  no `ModuleNotFoundError`.
- **Counterfactual:** the pf-26 pattern (`from app.main import app`) against the **same** skeleton →
  `ModuleNotFoundError: app` at collection. *In this isolated reproduction, the only changed variable
  is the import convention* (this does not by itself establish what the full live cycle would have
  done — see the expanded validation matrix in §9).
- No regression: 1316 capabilities + verification-contract tests pass.

## 7. What already works (so this SIP doesn't rebuild it)

The build test-runner (`_source_dir_pythonpath`, #303 + #454) already resolves the scaffold's package
convention: a package dir (`backend/__init__.py`) puts the **workspace root** on `PYTHONPATH`, so
`from backend.main import app` and relative `from .routes` both resolve (#454 fixed exactly this,
citing a real 35/35 regression). **No additional runner change is required for the failure class pf-26
demonstrated.** This SIP does not modify the runner; it ensures tests *use* the convention (Piece A/C)
and source *keeps* using it under repair (Piece B).

**Path-setup ownership (one normative model).** The scaffolded harness inserts the workspace root on
`sys.path` *and* the runner sets `PYTHONPATH`. This SIP chooses the **self-contained harness** model:
the harness MUST remain executable both under the production runner and through direct deterministic
replay, so it establishes the workspace-root convention locally and treats the runner's `PYTHONPATH`
as compatible redundancy. A future maintainer must not remove the harness-side setup as "duplication."

## 8. Scope, phasing, and convergence

- **Phase 1 (preparatory, Piece A + the mechanical harness check of Piece C):** the expander emits the
  frozen harness; `conftest.py` joins the contract `frozen_files`; a bound QA suite that bypasses the
  boundary is rejected. **Phase 1 may merge as preparatory work, but bind mode MUST NOT claim frozen
  *lifecycle* enforcement until Phase 2 is active.** Any live-cycle success after Phase 1 is evidence
  for the harness only — not acceptance of this SIP.
- **Phase 2 (the foundational change, Piece B + §4.4/§4.5):** authorization + integrity across all
  producing paths. The SIP is **not converged** until Phase 2 ships — pf-26 already proved a correct
  scaffold can be destroyed later, so shipping only Piece A improves the initial state while leaving
  the lifecycle guarantee false.

## 9. Acceptance criteria

**Scaffolded harness**
- The `fullstack_fastapi_react` expander materializes a frozen test harness bound to the canonical
  `backend` package root.
- The scaffold-owned QA fixture is discoverable from **every declared QA test slot under the production
  test-runner's invocation shape** (not merely a direct dev-shell `pytest` call).
- A skeletal app + a fixture-based smoke test reaches assertion execution without collection/import
  failure.
- A QA artifact that independently imports the app entry point — via `app.main` **or** `backend.main` —
  is rejected by deterministic harness validation (or another explicitly named contract check).
- The frozen harness hash is included in the bound scaffold integrity set.

**Frozen lifecycle**
- Every artifact-producing build/repair path authorizes output paths against the same bound scaffold
  ownership data *before* materialization.
- No frozen-path artifact reaches materialization or `patch_verification`.
- Frozen bytes equal the bind-time bytes after initial fill, QA fill, repair, retry, and verification
  preparation.
- A mixed valid+frozen producer response follows the §4.6 atomicity rule and emits §5 evidence.
- Path normalization prevents alternate spellings (`./backend/main.py`, traversal) from bypassing
  enforcement.
- Restoration, where used, restores from the bound scaffold instance, not a newly expanded scaffold.
- A frozen-path violation produces a distinct evidence classification and a targeted correction, and
  does not consume an ordinary convergence attempt.
- Existing non-bind / non-scaffolded flows retain prior behavior unless explicitly migrated (§10).

**Integration**
- A replay of the pf-26 correction pattern **cannot** mutate `backend/main.py`.
- The corrected QA suite reaches test execution through the scaffolded fixture.
- At least one live bind-mode group_run completes with no package-root divergence and no frozen-path
  mutation.
- No regression in the capability, verification-contract, and build-convergence suites.

### Validation matrix (deterministic replay first)

Primary acceptance is deterministic replay, not live cycles. Cases:
1. QA artifact authoring `from app.main import app` → rejected.
2. QA artifact authoring `from backend.main import app` (resolvable, still boundary-violating) →
   rejected.
3. Repair emitting **only** a frozen file → response rejected, frozen intact, `scaffold_integrity`
   evidence.
4. Repair emitting one frozen file + one valid slot file → §4.6 atomicity rule applied deterministically.
5. Repair emitting a path in neither the frozen set nor the authorized slot set → rejected.
6. Repair that changes then restores a frozen file to identical bytes → still a violation (authorization
   is on the *attempt*, not the net byte diff).
7. Alternate spelling / normalization (`./backend/main.py`) resolving to a frozen path → rejected.
8. Nested/traversal path resolving to a frozen path → rejected.
9. Deterministic replay after the underlying expander asset changed → restoration uses the bound
   instance, output unchanged.

## 10. Backward compatibility and applicability

Enforcement applies **only when a build attempt is bound to scaffold-ownership metadata**. Legacy
scaffolds without `frozen_files`, non-bind-mode plans, stacks without a scaffold-owned harness, repairs
generated before contract binding, and resumed cycles whose stored contract predates this SIP **retain
existing behavior until migrated, but may not claim scaffold-integrity guarantees.** This prevents the
change from introducing a global filesystem policy into unrelated execution paths.

## 11. Risks and non-goals

- **Non-goal:** changing `test_runner.py` import resolution (#303/#454 already correct); introducing a
  general filesystem authorization model.
- **Risk (Piece B):** over-aggressive rejection dropping a legitimate slot edit — mitigated by the
  single-source-of-truth frozen/slot set (§4.2) and response-atomic default (§4.6).
- **Risk:** the seeded harness assumes FastAPI `TestClient`; other stacks carry their own boundary
  realization alongside their expander (same per-stack pattern SIP-0099 uses for slot maps).

## 12. Relationship to SIP-0099

SIP-0099 makes the interface scaffold-owned at generation time. This SIP (a) adds the **test boundary**
to that owned surface and (b) promotes scaffold ownership from a generation-time hint to a **lifecycle
invariant enforced through every mutation path**. It is a strict extension: the frozen set and slot map
are reused verbatim, and it establishes a reusable path-authorization seam for future scaffold-owned
infrastructure.
