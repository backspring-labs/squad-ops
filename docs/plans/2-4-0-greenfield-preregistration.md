# 2.4's greenfield proof: pre-registration of its contribution (SIP-0112 E.7, E.4.6, G6)

*The MacBook lane, 2026-10-21. Written before the Spark's first cycle on the product.*

## The product

- **`backspring-labs/z_shelfnote`**, private. The destination the owner approved on 2026-10-20: an empty repository the
  MacBook lane made with gh at the owner's choice, renamed with the `z_` prefix the owner gives test products.
- **Shelfnote:** a shared reading list with notes, on the `fullstack_fastapi_react` blueprint (SIP-0105).

## What has run, on the Mac

| stage | where | what it showed |
|---|---|---|
| create | `projects initialize`, `dep_477ad713ff34` | the blueprint's first commit `31b4aa72` (24 files), pushed to the empty branch, never forced; a repeat was answered with the record |
| reach and configure | `validate`, `configure`, `baseline --capture` | READY at `31b4aa72`; revision 1 names the blueprint, and one naming another stack was refused; `boots` PASS, `backend_tests` FAIL (no tests yet), `frontend_tests` PASS |
| first change | `cyc_28255a07787e`, `lite-14b` | accepted under `no-introduced-regression/v1`, with `backend_tests` resolved. Not contributed: its capture carried SquadOps records into the product's root, which #2591 fixed after it |
| outside change | commit `093ca2a9` (CONTRIBUTING.md) | `sync` named it an instruction change; `validate`, `configure` (revision 2) and a new baseline reconciled it |

## What runs on the Spark, and what counts

The Spark session runs each stage on its own deploy, with the `full` squad, from the inputs in
`docs/plans/2-4-0-greenfield/`.

| stage | what is run | what counts as done | what refutes it |
|---|---|---|---|
| 1. registration | `projects import` of the existing repository as `prj-shelfnote` (`review_request`, owner `jasonLadd`, contribution delegated); `validate --token-from-gh` | READY at `093ca2a9`, with no commit to the product | a SquadOps file needed in the product |
| 2. baseline | `configure -f development-configuration.yaml`; `baseline --capture` | `CONTRIBUTING.md` recorded as an instruction source; each check's result at `093ca2a9`, inherited failures named | a check credited that didn't run |
| 3. change | a source-backed cycle (`implementation`, the plan in `implementation_plan.yaml`, the PRD in `prd.md`) | the product's checks accept the candidate with no introduced regression and at least one PASS; the capture holds only the product's files | a change the checks didn't accept, or a SquadOps record in the captured commit |
| 4. contribution | `projects contribute --token-from-gh` | a pull request on `z_shelfnote` whose head is the verified tree; the contribution recorded pending | a pull request whose tree isn't the verified one |
| 5. integration | the MacBook lane reads the diff and merges the pull request, as the owner's stand-in on a test product; then `projects sync` | `sync` reads the contribution as integrated | a merged contribution left pending |

The plan is the operator's, not the squad's, and the readout says so.

## What it doesn't cover

- **Creation and evolution ran on two deploys:** the first commit on the Mac, the contribution on the Spark. One deploy
  doing both needs another empty repository, which is the owner's choice.
- **IR-7** runs once Outcome Evaluation's phase 1 has shipped.
