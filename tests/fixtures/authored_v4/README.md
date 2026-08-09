# V4 roll 1 — the first squad-authored manifest, and the plan that went with it

Captured verbatim from `cyc_9c8c98ea3171` / `run_7115f0f7082d` (group_run, squad `full`,
2026-08-08), the first cycle run in authored mode after #791 landed the authoring stage.

- `interface_manifest.yaml` — artifact `art_c9da5390c7ba`. Authored by dev on attempt 2 of 4
  (attempt 1 failed the `parses` proof). Passes both gates.
- `implementation_plan.yaml` — artifact `art_4ca2c9adfb34`. Authored in the same framing run,
  with the manifest invisible to its authors: **zero of nine expected artifacts land on a
  fill slot**, four claim scaffold-frozen files, five name paths the skeleton does not have.

- `interface_manifest_roll2.yaml` — artifact `art_f3977c787af4`, from `cyc_77cbb5aab7ca`, the
  roll after #796 landed. Same PRD, independently authored: it binds all four fill slots and
  **declares one unresolved decision** (`expansion-gating` — the PRD requires expansion after
  core stability but defines no checkpoint). That open question is the observed case M4's
  question-gate exists for, so this file is the fixture that must stop a gate.

Roll 1's files are kept as a matched pair because the pair is the evidence: a good design and a plan that could
not be built from it, which is what #796 fixes. `test_authored_contract_binding.py` replays
it — deriving the contract from the manifest must make the gate reject this exact plan.

Not a golden. Nothing regenerates these; they are a record of one observed run.
