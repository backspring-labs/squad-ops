# 2.6.1 cut record — what the deploy ran, and what the cut doesn't cover

**The line:** `docs/plans/2-6-1-plan.md`, adopted 2026-11-07, with item 4 and D1 moved to 2.7 the same evening (the
plan's own record of both rulings).

## 1. The deploy the cut was read on

- **`dep_b2d017bd1db9`,** built from `7f2552af` (#2965, the line's last code change) with
  `rebuild_and_deploy.sh all`, 2026-11-07 ~21:00 ET. No Campaign was active and no run was running when it was
  built. `verify_loaded.py`: 249 loaded, 0 not.
- **What the tag adds beyond it:**
  - #2966, which records the owner's two moves to 2.7 in the plan and ROADMAP;
  - this release's commit: the version bump, the version markers, the changelog, the ROADMAP timeline, the open-issues
    snapshot and this record.

  All of it is prose, plus `pyproject.toml`'s version. The difference is additive: no code that ran differs from the
  tagged tree. The deploy reports version 2.6.0 until the post-tag rebuild, which changes only that.

## 2. Each item, read live on that deploy

| Item | Read | Result |
|---|---|---|
| 1. Console plugins cached by version | `/api/registry` and each bundle's headers through Caddy | 11 of 11 bundle URLs carry `?v=`. The current `v` answers `public, max-age=31536000, immutable`; no `v`, and the registry, answer `no-cache`; `If-None-Match` answers 304 with an empty body. Continuum 1.0.3 in the console |
| 2. Engine back after a reboot | `docker inspect squadops-tensorfold` | `restart=unless-stopped`, running. A throwaway `unless-stopped` container stayed down after `docker kill` (0 restarts) and restarted after exiting on its own |
| 3. A deploy runs the Caddyfile it pulled | the deploy's own step | it ran and read a match (`6e3326fa586f` on both sides), so it restarted nothing |
| 5. Criterion test briefs | the agents' `task_type.qa.test.md` | version 0.9.28 in the dev and qa agents |
| 6. Home's Create Cycle | the served Home and Cycles bundles | both carry `squadops:open-create-cycle`, and Home no longer calls `window.squadops.executeCommand` |

## 3. The cut's run

- **`cyc_e6acda62f855`,** `group_run`, `full-38-tf`, `validated-fullstack`, memory disabled. It is the line's
  shakeout: the package's plumbing run, not a measure of any item.
- **Runs:** framing `run_c03dd06196c7` (15m32s) and implementation `run_d12635bdaf4b` (5m49s), both completed.
  `progress_plan_review` was approved by `system:no_open_questions`.
- **Verdict:** `accepted`, criteria 22 of 22 verified (the cycle's assessment).
- **Rounds:** one. The exit rule in CLAUDE.md is a pair on one deploy with no new seam finding, and this run found
  none. No item of 2.6.1 changes the cycle's path, so a single run was registered rather than a pair.

## 4. What the cut doesn't cover

- **Item 3's restart path ran only in tests.** The deploy read a match, because Caddy had already been restarted by
  hand after #2958. The restart, the wait and the recheck run live at the next deploy that follows a Caddyfile change.
- **Item 6 is unread in a browser.** The bundles carry the hand-off, but a click on Home's Create Cycle landing on
  Cycles with the form open needs a logged-in browser, which the owner is asked to do.
- **Item 2's reboot is unread on this box.** The policy is set and Docker's handling of a kill was tested, but no
  reboot followed.
- **Item 5 is prompt guidance.** It makes a vacuous criterion test less likely; it doesn't stop one. D1, which would
  refuse one, is 2.7's.
- **No Campaign ran on 2.6.1.**

## 5. A correction to 2.6.0's cut record

`docs/plans/verification-sets/2-6-0-cut-record.md` names `dep_bd2a684d602a` as the deploy no Campaign had run on at
the tag. That deploy was built from `edc34c39`, before the version bump. The deploy that ran after the tag was
`dep_623daddbf654`, rebuilt at `9dba0df3` so the runtime would report 2.6.0. It differed by the version and the
release's documents only, and no Campaign ran on it either. 2.6.0's record is unchanged, since it is a record of
the cut as made.
