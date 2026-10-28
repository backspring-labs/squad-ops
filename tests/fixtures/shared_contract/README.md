# The shared fixture (SIP-0112 §8.2.3, #2407)

One small product, Tally, plus each 2.4 lane's recorded outputs, so that each lane can test its side of
the shared contracts before the other lane's code ships (the 2.4 plan, §2.3). The MacBook lane wrote
it, and the Spark lane added its recorded evaluation reference in the same PR (D12).

**Changing anything here is a shared-contract change (G4).** That covers the product, the recorded
outputs and the way the repository is built. The PR names the contract, carries the other lane's
review and only adds: it never repurposes or removes a field.

## The product

`product/` is Tally as of its second commit: a ledger of named counters, served over HTTP, in Python
with no dependencies. It has its own layout, with no SquadOps scaffold. It has:
- native commands: a build that writes `dist/` (kept out of Git by the product's `.gitignore`), one
  check command per file in `checks/`, and `python3 -m tally serve --host 0.0.0.0 --port 18407`;
- **one check that fails before any change:** `checks/check_parse.py`'s
  `test_strips_spaces_around_the_name` (IR-9's inherited failure);
- **one check that needs an environment the fixture doesn't provide:** `checks/check_notify.py` needs
  `TALLY_SMTP_HOST`, so the inherited baseline records it `UNVERIFIED`;
- **one binary asset,** `assets/mark.png` (X-2), which isn't valid UTF-8;
- **one instruction source,** `CONTRIBUTING.md`, which also states the owner's policy for the
  inherited failure;
- **one route that needs an evaluation secret:** `GET /admin` reads `TALLY_ADMIN_TOKEN`, which the
  start declaration lists under `evaluation_environment` (Q40).

`repository.py` makes the product into a Git repository. Pass `build_repository()` a path that doesn't
exist yet. It commits both commits with fixed identities and dates, file modes 0644, and no Git
configuration from the machine, so the hashes are the same on every machine:

| | first commit | second commit |
|---|---|---|
| Git commit | `15c7a12b8ed45f63ae47e90e3e854f6b3a2775f1` | `962858eb0e321ed084463637c9faf661c179a41e` |
| `FileTree.identity` (SIP-0109) | `1c985890772dbda5b07d438658a78f6ab70fafd06e6914c111368dd7e503157a` | `41e6cc797da0ddc58a4456e8ff1e6fce0c9ebedc9d0638bff5f69c630cff67ce` |
| sandbox revision ID | `4132b9d7897eb17f4894fc092263c4225bbbfda2278ebf6af797624539be74f0` | `23f7057c386d19b44136ac1c6ec385bf5d8a13247a00a7769392fbc5cb1808a3` |

- The first commit is the product as its maintainer wrote it.
- The second adds `GET /report`. It is the verified change that Cycle `cyc_2407a0000001`, an increment
  of Campaign `cmp_2407a0000001`, made from the first commit and captured back to Git.
- The second commit is the Project's current development baseline. Every *stale* form points at the
  first commit instead.
- The sandbox revision IDs are `compute_revision_id` over each file's bytes, as X-2 (#2420)
  extended it. Its wiring test seeds the first commit through the sandbox's HTTP client, patches on
  the second, and gets exactly these two values
  (`tests/unit/sandbox/test_http_surface.py::test_the_shared_fixture_seeds_and_captures_to_its_recorded_revisions`).

## The recorded outputs

Each output comes in four forms. Each bad form differs from `valid.yaml` in exactly the one way its
header says, and `test_shared_fixture.py` holds them to that.

| output | lane | contract | missing field | unknown major | stale commit |
|---|---|---|---|---|---|
| `project_source_context` | MacBook | 1 | `development_baseline_commit` | `project-source-context/v2` | every commit names the first |
| `development_configuration` | MacBook | 7 (`technical.commands.start`) | `configuration.revision` | `.../v2` | validated at the first commit |
| `workspace_commit_mapping` | MacBook | 3 and 4 | the captured entry's `commit` | `workspace-commit-mapping/v2` | the captured entry names the first commit |
| `inherited_baseline` | MacBook | none (FR-20, IR-9) | `commit` | `inherited-baseline/v2` | captured at the first commit |
| `derived_profile` | MacBook | 8 (H.6, added for 2.5) | `development_configuration_revision` | `derived-profile/v2` | derived at the first commit |
| `outcome_evaluation_ref` | Spark | 5 | `campaign_id` | `outcome-evaluation-ref/v2` | `evaluated_tree_identity` names the first commit's tree |

Only the start declaration is a shared contract in the Development Configuration. The rest of that
record, and the whole inherited baseline, is the MacBook lane's own, recorded for E.4.2 and IR-9.

**The derived profile (contract 8)** is what H.4 reads from Tally at its second commit, its first
configuration revision and its baseline: Python with no package manager, five unittest checks under
`checks/`, a one-file command through `{name}`, and two disclosed gaps (`notify`'s environment, and no
reader that names unittest's tests one by one). `squadops.projects.derived_profile.parse_profile` is
the one reader both lanes call, and H.6 names what each gap stops.

**The commands are recorded resolved.** SIP-0112 §B.5 stores them behind `technical.commands_ref`. A
reader receives them resolved, so that is what the recording shows.

**The start declaration (contract 7):**
- **URLs** (`readiness.target`, `entry_points[].url`) are as the product sees them: loopback, on the
  port its start argv declares. A runner that publishes the port elsewhere maps the scheme, host and
  port, and keeps the path.
- **`kind: http` readiness** means a 2xx from the target.
- **The product binds `0.0.0.0`**, and answers 404 on a path it doesn't serve.

## The contract tests

The fixture's own checks are in `tests/unit/shared_contract/test_shared_fixture.py`. Each contract's
test enters at its production seam, so it lands with the PR that builds the seam, against this
fixture (agreed by both lanes on #2407):

| contract | its test (SIP-0112 §8.2.1) | the seam | lands with |
|---|---|---|---|
| 1 | `prepare_cycle()` with the fixture's Project: `READY`, not `READY`, a stale pinned commit | `prepare_cycle()` and the Campaign launcher | E.4.1 (#2408) and E.4.3 (#2410) |
| 2 | the standalone and Campaign preparation tests | cycle and Campaign preparation | already on `main`, and run on every change to the seam |
| 3 | seed the fixture at a pinned commit; capture a change back to a commit; the mapping resolves both ways | `WorkspaceStore.seed()` | E.4.2 (#2409), after X-1 (#2419) and X-2 (#2420) |
| 5 | write the recorded reference into Project history; read it back; refuse an unknown major version | the Project history write | the reference's side with #2415; the history side with the slice that first writes Project history (#2410 or #2411) |
| 7 | start the fixture from its declaration; a missing declaration; a readiness timeout | the evaluation runner's start | #2414, with X-3 (#2421) |
| 8 | read the recorded profile back; refuse an unknown major version, a missing field and a stale commit | `parse_profile` first (`test_derived_profile_contract.py`); then the baseline capture that derives it, and SIP-0109 §24bv's Campaign start and increment acceptance | the reader with H.6 (#2619); each seam with the 2.5 PR that builds it |

Contracts 4 and 6 keep SIP-0109's and SIP-0110's tests, with IR-5 and IR-3.

## Using it

```python
from tests.fixtures.shared_contract.repository import build_repository, recorded, tracked_files

repo = build_repository(tmp_path / "tally")  # repo.first_commit, repo.second_commit
files = tracked_files(repo.path, repo.second_commit)  # {path: bytes}, the binary asset included
context = recorded("project_source_context", "stale_commit")
```
