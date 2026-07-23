# SIP-0100 — Task 0.1: Workspace Mutation-Path Inventory

**Purpose (SIP-0100 plan Task 0.1):** prove — not assume — every path that can mutate a *bound build
workspace* after scaffold materialization, so Phase 2's authorization seam covers all of them.

## Headline finding

**The plan's "single chokepoint" assumption is FALSE.** There are **two independent
verification-workspace materializers**, and the one pf-26 actually failed in is **not**
`materialize_artifacts`:

1. `cycles/patch_verification.py:136` **`materialize_artifacts(artifacts, workspace_root)`** — used by
   the typed-acceptance-check workspace (`handlers/cycle/base.py:327-329`) and the patch-verify
   workspace (`patch_verification.py:205-207`). Has path-safety, no ownership awareness.
2. `handlers/test_runner.py:67-76` **`_materialize_files(workspace, files)`** — used by
   `run_generated_tests` (`test_runner.py:173` `mkdtemp` + calls at :716/:798) for the **qa.test pytest
   workspace and the frontend build**. It writes `source_files` + `test_files` directly (`os.path.join`
   + `fh.write`). **This is the workspace whose pytest collection crashed in pf-26**, and it materializes
   the accumulated/repaired `source_files` — so a repair-tampered frozen `backend/main.py` reaches pytest
   through here, bypassing `materialize_artifacts` entirely.

**Consequence for Phase 2:** instrumenting only `materialize_artifacts` would leave the pf-26 path
unguarded. The two materializers must be **unified behind one authorization-aware seam** (recommended)
or **both** instrumented with the same `WriteAuthorization`. Recommendation: unify — extract one
`materialize(files, workspace, authorization=None)` that both call, so there is a single place where
authorize→materialize→verify lives (and no third seam can drift).

## Full inventory (every filesystem-write seam in the build/cycle/capability/adapter paths)

| Seam | Location | Writes to a bound workspace? | Through `materialize_artifacts`? | Classification |
|------|----------|------------------------------|----------------------------------|----------------|
| `materialize_artifacts` | `patch_verification.py:136-161` | yes (typed-acc + patch-verify temp workspaces) | **is the chokepoint** | producer-verification — **enforce here** |
| typed-acc workspace | `handlers/cycle/base.py:327-329` | yes | yes ✓ | routes through chokepoint |
| patch-verify workspace | `patch_verification.py:205-207` | yes | yes ✓ | routes through chokepoint |
| **`_materialize_files`** | `handlers/test_runner.py:67-76`, workspace `:173` | **yes (qa.test pytest + frontend build)** | **NO ✗ — BYPASS** | producer-verification — **must be unified/instrumented** |
| PRD / run-root seed | `dispatched_flow_executor.py:2614-2630` | run root (input seed) | n/a | system-owned setup — not a producer artifact |
| artifact vault | `adapters/cycles/filesystem_artifact_vault.py` (37/56/92/97-98/114/155/281-282) | no — persistent store (`data/artifacts/…`) | n/a | persistent store, **not** a build workspace |
| run report | `capabilities/runner.py:399,465` | no — report/evidence output | n/a | evidence output, not a producer workspace |

Search method: `grep -rnE '\.write_text|\.write_bytes|\.mkdir|makedirs|shutil\.(copy|move|copytree)|extractall|open\([wax]|mkdtemp|TemporaryDirectory'` across `src/squadops/{capabilities,cycles}` and `adapters/cycles`, plus caller-tracing of `run_generated_tests` / `materialize_artifacts` / `_materialize_files`. No archive-extraction (`extractall`) or `shutil.copy*` producer paths exist today.

## Vault vs workspace (important boundary)

The **vault** (`filesystem_artifact_vault`) is the persistent artifact store; the **workspace** is the
ephemeral dir where verification runs. Enforcement targets the **workspace** (where a tampered frozen
file would be *executed*). The vault stores whatever a producer emits; SIP-0100 does not gate the vault
(a stored artifact is inert until materialized). This keeps enforcement at the point of *execution
consequence*, not storage — but Phase 2 must therefore cover **every** workspace materializer (both of
them), since either can materialize a vault-stored tampered file.

## Characterization test

`tests/unit/cycles/test_sip0100_mutation_inventory.py` pins this finding:
- demonstrates the **bypass** — `_materialize_files` writes a frozen path (`backend/main.py`) with no
  ownership check today (pins pre-enforcement behavior; Phase 2 flips it to rejected);
- **completeness ledger** — enumerates the two known workspace materializers so a newly-added third
  seam (or a removed routing) fails the test until this inventory + Phase-2 coverage are updated.

## Plan impact

The plan's "candidate chokepoint" note is corrected: `materialize_artifacts` is **one of two**
materializers. Phase 2 Task 2.2 is amended to "unify the two workspace materializers behind one
authorization-aware `materialize(...)`" rather than instrument a single function.
