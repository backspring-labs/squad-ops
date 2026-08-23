---
template_id: request.plan_authoring_rules_appendix
version: "4"
required_variables: []
---
## PLAN SHAPE RULES (authoritative — a plan that breaks one is rejected)

These are deterministic system validators, not reviewer preference. A plan violating any
of them is rejected before it runs, the whole framing is re-rolled, and re-rolls are
limited. Every rule below is checkable from what you are writing — none of them depend on
how the build turns out.

**one-file-one-owner** — An artifact path appears in the `expected_artifacts` of exactly
ONE task. Two tasks naming the same file aliases them onto one file's fate: repair
scoping and missing-artifact routing both key on this list, so a failing non-producing
claimant aims its repair at another task's file, and if both produce, ordering silently
decides whose version ships. A task that only *verifies* a file does not list it.

**artifacts-are-files** — Every `expected_artifacts` entry is a file path, never a
directory (`backend/tests/` is invalid; `backend/tests/test_runs.py` is fine). Presence is
checked against emitted file names, so a directory entry can never be satisfied.

**qa-owns-only-tests** — A `qa.test` task's `expected_artifacts` contains only its own
test files. Never a scaffold file, and never a file another task produces: write
authorization refuses those at emission, so the task provably cannot produce its own
declared output.

**no-frozen-claims** — No task of any role declares a scaffold-frozen file as an
`expected_artifact`. Frozen files are scaffold-owned; an emission touching one is
discarded, so the claim can never be satisfied.

**imports-must-exist** — An error-severity `import_present` names a module the scaffold
surface actually provides. Check the package root: if the scaffold's backend lives under
`backend/`, then `app.routes` and `src.backend.main` do not exist and never will, and a
check requiring one is unsatisfiable by any correct implementation.

**regex-only-on-documents** — `regex_match` targets documents (`.md`, `.txt`, `.rst`)
only. A regex against source prescribes another author's stylistic choices — quote style,
identifier spelling — and rejects correct code. Verify source with the structural checks
instead.

**commands-must-run-here** — An error-severity `command_exit_zero` uses one of the
safelisted forms, against a file type that tool accepts. The safelist is the entire
universe of runnable commands — every form on it is provisioned in every role container,
and anything outside it is rejected here rather than left to fail on every correction
attempt. `node --check` pointed at `.ts`/`.tsx`/`.jsx` is rejected for the same reason:
node refuses those extensions before it parses a line, so the check fails on correct code
too. TypeScript has no command form at all; the frontend build type-checks it.

**roles-must-exist** — Every task's `role` is one the squad profile actually staffs. A
task assigned to an absent role can never be dispatched.

**qa-tests-must-be-discoverable** — When the `tests_pass` check is required, every
`qa.test` task that declares expected artifacts includes at least one file **this stack's
test runner discovers**. The suite check judges a qa task's emission by that runner's
conventions, so a task declaring only files it cannot collect fails on any possible
content — the declared shape, not the work, is the failure. Follow the file-naming
conventions your stack's guidance states (`test_*.py` / `*_test.py` under pytest,
`*.test.ts` / `*.spec.ts` and their `.tsx` forms under vitest); a directory named
`__tests__/` is not itself enough. Express verification that produces no such file
through the acceptance criteria of a verification-only task instead.

**builder-floor-coverage** — When the plan carries a builder task, every file the build
profile's `required_files` lists appears in SOME task's `expected_artifacts` (usually the
builder's). The profile list is a floor — a per-task list may add files, never subtract
one. A plan that leaves a required file unowned passes every task and then fails the
deliverable-completeness gate at run completion, where nothing can repair it.

**do-not-restate-success-statuses** — Success statuses are not yours to state. The
contract derives each endpoint's status from the interface manifest and the endpoint's
shape, and the developer's brief carries that derived status directly — so a status in
your prose is a second copy of a fact the implementer already has, and the only thing a
second copy can add is a disagreement.

Write the behaviour, not the code: *"joining a run adds the participant and returns the
updated run"*, never *"returns 200"*.

If you do name a status anyway, it must match what the contract will enforce, or the plan
teaches the developer to build something the contract then rejects. But the right move is
to leave it out — there is nothing to keep in step with if you never wrote it down.

A verification-only task is legitimate and common: declare `expected_artifacts: []` and
express what it checks through its acceptance criteria.
