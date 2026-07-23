---
title: Scaffolded Test Harness and Frozen-File Enforcement
status: proposed
author: jladd
created_at: '2026-07-22T00:00:00Z'
updated_at: '2026-07-22T00:00:00Z'
---
# SIP-XXXX: Scaffolded Test Harness and Frozen-File Enforcement

## Status
Proposed

**Extends:** SIP-0099 (Contract-First Build Scaffolding). SIP-0099 makes the *interface*
scaffold-owned and frozen; this SIP closes two gaps that SIP-0099's current surface leaves
open, both surfaced empirically by the group_run measurement rolls.

**Motivating case:** pf-26 (`cyc_af8800f8943f`, deploy `ee4ac71c`) — the backend `qa.test`
correction loop never converged. Root cause was **not** the framing, targeting (RC2), or
workspace-staleness (RC3) fixes that preceded it — those all worked. It was a **package-root
inconsistency the squad could not settle**: source files live under `backend/` (a package),
but the qa test invented its own root (`from app.main import app` — no `app` package), and the
correction loop rewrote the *frozen* `backend/main.py` four times (`.routes` → `models` →
`app.models` → `app.routes`) without ever matching the layout. pytest collection crashed on an
unresolvable import every attempt; the loop oscillated and exhausted.

**Coordinates with:** SIP-0086 (Build Convergence Loop) — this SIP makes the correction loop
*respect* scaffold-owned files it must never rewrite.

---

## 1. Abstract

SIP-0099 establishes a deterministic walking skeleton whose non-fill files are **frozen**
(hash-pinned) so the dev agent fills bodies into slots it cannot rewire. Two gaps remain:

1. **The test harness is not scaffolded.** The expander emits no `conftest.py` and no test
   file, so every qa suite invents its *own* import root. When that guess doesn't match the
   scaffold's package layout (`app.main` vs `backend/`), pytest collection crashes before any
   assertion runs — and no correction can converge because the failure is structural, not
   logical.

2. **Frozen is only enforced at initial fill, not through the repair loop.** The SIP-0086
   correction path emits artifacts directly; it can (and in pf-26 did) re-emit a *frozen*
   file (`backend/main.py`), overwriting the scaffold's invariant imports with a broken guess.
   A convention the scaffold seeds correctly is worthless if the repair loop can clobber it.

This SIP makes the **test import root a scaffold invariant** (a frozen `conftest.py` that owns
the app import behind a `client` fixture) and enforces **frozen-stays-frozen through the entire
build+repair lifecycle**. The dividing line SIP-0099 drew — interface (deterministic) vs.
implementation (generative) — is extended to cover the test harness and is made to hold under
correction, not just at first fill.

## 2. Motivation

pf-26 is the cleanest evidence yet that the remaining build-convergence wall is **structural
divergence between independent agents**, not model weakness. Neo (source), Eve (tests), and the
repair agent each independently decided the package/import root, and they disagreed. No amount
of per-agent prompting converges independent LLM guesses onto a byte-consistent structural
decision — we watched three correction attempts oscillate and exhaust on it.

The fix is the SIP-0099 principle applied one level deeper: a structural decision that needs no
judgment (the package root) should be **materialized once by the scaffold** and **referenced,
never re-derived**, by every agent — and it must be *impossible* for a downstream fill or repair
to overwrite it. "Assign the decision to one owner and have everyone reference it" is the right
shape; the strongest form of "reference" is "the decision is materialized and frozen, so there
is nothing left to get wrong."

## 3. What already works (so this SIP doesn't rebuild it)

The build test-runner (`capabilities/handlers/test_runner.py`, `_source_dir_pythonpath`, #303 +
#454) **already resolves the scaffold's package convention correctly** and is battle-tested:
a directory that is a package (`backend/__init__.py`) is never put on `PYTHONPATH` directly;
instead the **workspace root** goes on the path, so `from backend.main import app`
(package-qualified) *and* `from .routes import router` (relative, inside `main.py`) both resolve.
#454 was itself a fix for exactly this failure mode (a 35/35-passing fill-contract suite that
broke on `attempted relative import with no known parent package`).

**Implication:** the import-*resolution* layer is done. This SIP does **not** change the runner.
It only ensures the tests *use* the convention the runner already supports (piece A) and that
the source keeps using it under repair (piece B). The runner resolves imports to modules that
exist; it cannot rescue a reference to a package that doesn't (`app`), which is precisely what
pieces A and B prevent.

## 4. Proposal

### Piece A — Scaffold the test harness (import root as a frozen invariant)
The `fullstack_fastapi_react` expander emits a **frozen `conftest.py`** at the workspace root:
it puts the root on `sys.path` (portable even outside the runner) and exposes the app behind a
single `client` fixture:

```python
import os, sys, pytest
from fastapi.testclient import TestClient
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.main import app  # after the anchor
@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

Test suites become fill slots that use `client` and **never author the app import**. The package
root stops being a per-suite guess. (Prototyped — see §5.)

### Piece B — Enforce frozen through fill *and* repair (the teeth)
Scaffold-owned frozen files (per SIP-0099 `frozen_files`, now including `conftest.py`) are
**re-materialized after every fill and every repair**, and a fill/repair that emits a frozen
path is rejected (or its frozen emissions dropped) before `patch_verification`. The correction
loop may rewrite `routes.py` and the views (slots); it may **never** re-emit `main.py`,
`errors.py`, `models.py`, or `conftest.py`. This is the piece pf-26 proves is not optional: the
scaffold seeded a correct `main.py`, and the repair overwrote it.

### Piece C — Bind the qa proposer to the harness
The qa fill-only prompt appendix instructs suites to import the app via the seeded `client`
fixture and never author their own app import; the contract adds `conftest.py` to `frozen_files`
so its hash is pinned. (Prompt content lives in the managed asset, not Python — CLAUDE.md #448.)

## 5. Prototype and proof (pieces A, partial)

Piece A is prototyped on `proto/scaffold-import-convention` (`ab295167`) and proven
deterministically — no cycle, no LLM:

- **Positive:** a qa suite authored against the seeded `client` fixture runs against the
  freshly-materialized skeleton → `1 passed`, no `ModuleNotFoundError`.
- **Counterfactual:** the *exact pf-26 pattern* (`from app.main import app`) against the **same**
  skeleton → crashes collection with `ModuleNotFoundError: app`. The delta between converging and
  exhausting is purely the import convention.
- No regression: 1316 capabilities + verification-contract tests pass.

## 6. Scope and phasing

- **Phase 1 (small, mostly done):** Piece A — `scaffold.py` emits the frozen `conftest.py`;
  add `conftest.py` to the contract `frozen_files`; qa fill-only prompt uses `client`. Acceptance:
  the §5 proof, plus a bind-mode plan where the qa slot fills test bodies against `client`.
- **Phase 2 (the real engineering):** Piece B — re-materialize / reject frozen emissions in the
  build + correction materialization path (`dispatched_flow_executor` + `patch_verification`).
  Acceptance: a replay where a repair *attempts* to re-emit `main.py` and the frozen original
  survives the retest.

## 7. Validation

Primary acceptance is **deterministic replay**, not live cycles (per the replay-verification
discipline): materialize the skeleton, run a `client`-based suite (passes), run a pf-26-pattern
suite (fails), and — for Phase 2 — feed a repair that re-emits a frozen file and assert the
frozen content is what `patch_verification` sees. A live group_run roll is the *integration*
check, not the unit gate.

## 8. Risks and non-goals

- **Non-goal:** changing `test_runner.py` import resolution (#303/#454 already correct).
- **Risk (Piece B):** over-aggressive frozen rejection could drop a *legitimate* slot edit if the
  frozen set is computed wrong; mitigated by deriving the frozen set from the same
  `fill_slot_paths`/`frozen_files` the contract already uses (single source of truth).
- **Risk:** the seeded `client` fixture assumes `TestClient` (fastapi); other stacks carry their
  own harness alongside their expander (same pattern SIP-0099 uses for per-stack slot maps).

## 9. Relationship to SIP-0099

SIP-0099 makes the interface scaffold-owned; this SIP (a) adds the **test harness** to the
scaffold-owned surface and (b) makes scaffold-ownership hold **through the repair loop**, not
only at first fill. It is a strict extension — no SIP-0099 mechanism changes; the frozen set and
slot map are reused verbatim.
