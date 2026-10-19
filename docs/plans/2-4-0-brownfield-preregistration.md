# 2.4's brownfield demonstration: pre-registration (SIP-0112 §7, the 2.4 plan §2.2, G6)

*Draft, the MacBook lane, 2026-10-19. Written before the demonstration's first cycle. The shakeout cycles on the
Mac below aren't the demonstration.*

## The product

- **`backspring-labs/continuum`**: the owner's choice, 2026-10-19.
- What it is: a plugin-driven control-plane UI shell, in Python (FastAPI) with Svelte plugin UIs. Public.
- Registered as `prj-continuum` (`review_request`, owner `jasonLadd`, contribution delegated).
- Unfamiliar to the squad: no SquadOps file in it, and none of it in any prompt asset or vault before registration.

## What is read at each stage, and what counts

| stage | what is run | what counts as done | what refutes it |
|---|---|---|---|
| 1. registration | `projects import`, `validate` | a stable Project ID; the record outside the repository; no commit to the product for onboarding | a SquadOps file needed in the product, or the ID changing |
| 2. baseline | `configure`, `baseline --capture` | the delegation and instruction sources recorded; the product's own checks at the pinned, unmodified commit, inherited failures and UNVERIFIED named | a check credited that didn't run, or the source patched to pass |
| 3. first feature | a source-backed cycle; `projects contribute --token-from-gh` | the product's checks accept the candidate with no introduced regression and at least one PASS; the captured commit is the verified tree; a pull request is opened on the product; the contribution is recorded pending | a change delivered that the checks didn't accept, or a commit that isn't the verified tree |
| 4. outside change | the owner, as an outside developer, commits to `main` | `projects sync` names the drift by category, and reads the first contribution as integrated if it was merged, pending if not | an instruction or command-input change filed as source; a merged contribution left pending |
| 5. reconcile | `validate`, `configure`, `baseline --capture` at the new commit | a Cycle is refused until the configuration and baseline are at the new commit, and accepted after | a Cycle developing against evidence from the older commit |
| 6. second feature | a second source-backed cycle; `contribute` | as stage 3, on the reconciled baseline | as stage 3 |

**Distinguishable throughout (§7):** each run's verification record, the contribution states and the sync findings are read back from the API at the end and listed in the record.

## The features

- **First:** `continuum --version` prints `continuum <version>` and exits 0 (the PRD as filed for the shakeout cycles).
- **Second:** set after the outside change, before its cycle, and appended here first.

## Where it runs

- **The demonstration:** the Spark, the `full` squad, outside the window (the 2.4 plan §2.2).
- **Shakeouts:** the Mac's `lite-14b` cycles test the machinery only (`cyc_62ec4593f50a`, `cyc_b78a41df2847`, `cyc_546536a39b2d`, `cyc_50354cfc8dbb`), and are never read as the demonstration.

## Not covered

- E.4.5's handoff and archival (not in 2.4, the owner's ruling).
- IR-3's instruction binding, which waits on SIP-0110's #2179.
