# 2.4's brownfield demonstration: pre-registration (SIP-0112 §7, the 2.4 plan §2.2, G6)

*Draft, the MacBook lane, 2026-10-19; amended 2026-10-21 (below), still before the demonstration's first cycle.
The shakeout cycles on the Mac below aren't the demonstration.*

## The product

- **`backspring-labs/z_continuum`**: a private copy of `backspring-labs/continuum`, its `main` and its tags, at
  `43369054` (v1.0.2). The owner's choice, 2026-10-21 (amendment 1). Every write the demonstration makes lands in the
  copy, and continuum itself is never written.
- What it is: a plugin-driven control-plane UI shell, in Python (FastAPI) with Svelte plugin UIs.
- Registered on the Spark as `prj-z-continuum` (`review_request`, owner `jasonLadd`, contribution delegated).
- Unfamiliar to the squad: no SquadOps file in it, and none of it in any prompt asset or vault before registration.
  Its one instruction source is continuum's `CLAUDE.md`.

## What is read at each stage, and what counts

| stage | what is run | what counts as done | what refutes it |
|---|---|---|---|
| 1. registration | `projects import`, `validate` | a stable Project ID; the record outside the repository; no commit to the product for onboarding | a SquadOps file needed in the product, or the ID changing |
| 2. baseline | `configure`, `baseline --capture` | the delegation and instruction sources recorded; the product's own checks at the pinned, unmodified commit, inherited failures and UNVERIFIED named | a check credited that didn't run, or the source patched to pass |
| 3. first feature | a source-backed cycle; `projects contribute --token-from-gh` | the product's checks accept the candidate with no introduced regression and at least one PASS; the captured commit is the verified tree; a pull request is opened on the product; the contribution is recorded pending | a change delivered that the checks didn't accept, or a commit that isn't the verified tree |
| 4. outside change | a commit to `main` made outside SquadOps, pushed from the owner's account by the MacBook lane as the owner's stand-in (amendment 2) | `projects sync` names the drift by category, and reads the first contribution as integrated if it was merged, pending if not | an instruction or command-input change filed as source; a merged contribution left pending |
| 5. reconcile | `validate`, `configure`, `baseline --capture` at the new commit | a Cycle is refused until the configuration and baseline are at the new commit, and accepted after | a Cycle developing against evidence from the older commit |
| 6. second feature | a second source-backed cycle; `contribute` | as stage 3, on the reconciled baseline | as stage 3 |

**Distinguishable throughout (§7):** each run's verification record, the contribution states and the sync findings are read back from the API at the end and listed in the record.

## The features

- **First:** `continuum --version` prints `continuum <version>` and exits 0 (the PRD as filed for the shakeout cycles).
- **Second:** `continuum inspect --json` reports the version, as a top-level `"version"` key, first, equal to
  `continuum.__version__`, with every other key unchanged (`prd-inspect-version.md`, `implementation_plan_2.yaml`).
  Set on 2026-10-21, after the outside change and before its cycle. It changes the file the first contribution
  changed, so it builds on that change rather than beside it.

## Where it runs

- **The demonstration:** the Spark, the `full` squad, outside the window (the 2.4 plan §2.2). The Spark session runs
  each stage on its own deploy, from the inputs below.
- **Shakeouts:** the Mac's `lite-14b` cycles test the machinery only (`cyc_62ec4593f50a`, `cyc_b78a41df2847`, `cyc_546536a39b2d`, `cyc_50354cfc8dbb`), and are never read as the demonstration.

## The inputs

Fixed here before the first cycle, in `docs/plans/2-4-0-brownfield/`:
- `prd-version-flag.md`: the first feature.
- `development-configuration.yaml`: the product's own install, build and checks (`tests`, `lint`), as its README and
  `CLAUDE.md` describe them. On the Mac's shakeouts, the baseline at `43369054` was `tests` PASS and `lint` FAIL, both
  inherited.
- `implementation_plan.yaml`: the plan the first cycle runs (develop, then QA). It is the operator's, not the squad's,
  and the readout says so: what is shown is a squad delivering a planned change through the product's own process,
  not a squad framing one.

## Not covered

- E.4.5's handoff and archival (not in 2.4, the owner's ruling).
- IR-3's instruction binding, which waits on SIP-0110's #2179.

## Amendments

1. **The product is a private copy of continuum** (2026-10-21). The owner: "I don't want to be pushing actual change
   to Continuum until we have the framework solid", then "yes, use z_continuum". The copy's history and layout are
   continuum's, so it is as unfamiliar to the squad. Only where the pull requests and the outside commit land changes.
2. **The outside commit is pushed by the MacBook lane, from the owner's account** (2026-10-21). The owner: "yes, you
   push it from my account". What stage 4 tests is a change made outside SquadOps's process, never through a cycle,
   and that holds whoever types it. It is a small, real change: a line in `CLAUDE.md`, the instruction source, and one
   source edit, so the instruction drift and the source drift are each named.
3. **The squad is `full-38-tf`, not `full`** (2026-10-21, the Spark lane). `full` names `qwen3.6:27b`, which the Spark
   doesn't serve. `full-38-tf` is the same six-agent roster on the model the Spark serves.

## Stages so far

| stage | what ran | what it showed |
|---|---|---|
| 1–2 | the Spark (`dep_ceda294644b3`, after the owner approved the project registry's cutover to Postgres): `prj-z-continuum` registered, READY at `43369054`, configured, baseline captured | as recorded on #2410 |
| 3 | `cyc_709e3a912150` / `run_7bca712bd35b`; verification `art_0d17c83b411c` | accepted under `no-introduced-regression/v1`: `tests` PASS (60 passed, 3 skipped), `lint` FAIL inherited (59 findings before and after). Captured commit `2f6b3baa` on `43369054`, holding only `src/continuum/cli.py` and `tests/test_cli_version.py`. Pull request z_continuum#1, recorded pending. The change also dropped `cli.py`'s final newline, which no check reads |
| 4 | the pull request merged by the MacBook lane as the owner's stand-in, with a merge commit (`17a819f3`), so the captured commit stays in `main`'s history; then the outside commit `ba8fa68b`: a `CLAUDE.md` convention for CLI option tests, and `__all__` in `src/continuum/__init__.py` | read by stage 4's `sync`, next |
