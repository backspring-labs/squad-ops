# Verification sets — the procedure

The set configs in this directory are a pre-registration's §1 table as data; the driver
(`scripts/dev/verification_set_driver.py`) reads one and runs one cycle per invocation. This
file is the procedure around them — the part that was carried from pre-registration to
pre-registration "verbatim" and that each line re-learned by paying for it. Plans are
superseded at the cut; this is not.

## What a set is

- A **pre-registration** (`docs/plans/<line>-verification-set-preregistration.md`) fixes the
  parameters, the predictions and their readouts, the gate constant and the prohibitions
  *before* roll 1, by the commit hash of the document on its branch. Merging it is the
  owner's act and does not change what it pre-registers.
- A **set config** (`<line>-<stack>.yaml`) carries the fixed parameters the driver asserts:
  project, squad and request profiles, overrides, the expected config-hash and
  squad-snapshot prefixes, the frozen deploy commit and its seven image ids, the gate notes.
- A **roll** is one counted cycle. The driver asserts the frozen image ids, pins the launch
  checkout's HEAD on roll 1 and holds it, and asserts the config hash; a mismatch records and
  stops. Scoring — counted / void / reset — is a reading made at the roll boundary by a
  person; the driver reports, the pre-registration decides.
- A **shakeout** is a non-counting cycle on a fresh deploy. It records the deploy's identity
  instead of asserting it. Its purpose is to find what the pack's tests did not.

## The shakeout loop and its exit rule

One shakeout per stack per deploy. **A deploy on which either shakeout produced a fix is
superseded**: the fix merges, the deploy is rebuilt from main, and both stacks run again.
The 1.7.1 line ran four deploys this way, and each pair found the next seam defect (#1250,
#1252, #1255 with #1256, #1259 with #1261) — every one a bug the pack's own tests had not
reached, three of them latent in the pack's own PRs from the day they merged.

So the loop is the design, and it needs an exit rule stated before the first launch:

- **Exit:** a pair on one deploy with no new seam finding. A finding is a defect in a seam
  the pack touched or a prediction's readout that cannot see its own miss; a defect in the
  application a cycle built is the cycle's, not the deploy's, and does not reset the loop.
- **Budget:** the pre-registration names the number of pairs it expects and the plan's
  sequencing carries them; the cut record reports how many it took. That number is evidence
  about the pack, and a record that hides it is the failure SIP-0103 §5d names.
- **Pins are history.** Every superseded deploy's commit and image ids stay in §1's table,
  parenthesised, with what its shakeouts found in §2. The pinned deploy is the last one.

## What a diagnostic is

A prediction that no roll is likely to exercise (a check that fires only on a defect the
squad rarely produces, a verdict path that needs a specific failure shape) gets a
diagnostic before roll 1. **The diagnostic runs the roll's own path with the fault
injected** — the executor's outcome handler, the correction protocol, the check registry —
and is recorded with the entry point it used. A call into the seam with its input in hand is
a replay of the function: it proves the function and says nothing about whether the cycle
reaches it. It may be recorded, named as exactly that, and it does not stand in for the
prediction. 1.7.1's R7 diagnostic called the verifier with the repair's rows passed in and
passed; the live path had never delivered a row (#1256). The fault-injection hook is #1251.

## Readouts

Every readout counts **non-execution beside failure**: rows skipped, by reason, next to rows
failed. A check that stops running on the files it was meant to guard produces a green roll
with a smaller denominator, and a count of failed rows cannot see it. 1.7.1's R6 gap arrived
as five `skipped / unsupported_stack_or_syntax` rows on the accepted emission (#1261).

The readouts are read from the per-roll record, never by hand from the log; the record is
the driver's `render` of what it collected, and what it collected is listed in the driver.

## Running it

- **Preflight first**, always: `preflight --set <yaml>` (add `--counting` for a roll). It
  refuses a dirty tree, unreleased focus leases, any run in flight, and — counting — an
  image id or HEAD that moved.
- **The launch must outlive the session.** A driver process started as a session's
  background task has been stopped from outside the session three times in one day; the
  cycle keeps running and its gate goes unwatched. Launch detached:
  `setsid nohup .venv/bin/python scripts/dev/verification_set_driver.py shakeout --set … > log 2>&1 < /dev/null & disown`
  and watch the record directory, not the process.
- **A dead driver is re-attached, not relaunched.** The cycle is still running. Import the
  driver as a module and run the tail of `_run_cycle` — `drive`, `collect`, `static_checks`,
  `ledger_checks`, `loop_texture`, `typed_checks_by_check`, `boot_audit`, `render`,
  `_write_record` — with the cycle id, the run id and the launch time.
- **A rebuild over a running cycle leaves its run `running`** in the registry and every later
  preflight refuses. Cancel it through the CLI (`squadops runs cancel <project> <cycle>
  <run>`), never by hand in the database; killing the driver alone does not cancel the run.
- **Records** land in `var/verification_sets/<set>/` under the checkout the driver ran from;
  a docs worktree needs `.venv` and `data` linked (and excluded) for the driver to find the
  CLI and the artifact vault. Counted rolls launch from `main` (owner's ruling, 2026-08-27).

## What the record must say

The per-roll record is facts; the pre-registration says what they mean. The cut record
(`docs/plans/<line>-cut-record.md`) says what the evidence does **not** cover: which
predictions no roll exercised and why, which readouts were vacuous on which stack (a plan
that names no frontend suite exercises no frontend-suite check), and where the tagged tree
differs from the validated deploy.
