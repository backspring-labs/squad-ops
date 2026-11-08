# 2.6.1 cut record — what the deploy ran, and what the cut doesn't cover

**The line:** `docs/plans/2-6-1-plan.md`, adopted 2026-11-07. Item 4 and D1 moved to 2.7 the same evening, and the
owner added item 7 (#2921) while the release PR waited. The plan records all three rulings.

## 1. The deploy the cut was read on

- **`dep_22a327b5006a`,** with every service built from `699230a1` (#2968, the line's last code change),
  2026-11-07 ~22:20 ET.
  - The runtime API and the console were rebuilt first (`dep_c60c90b8afe7`), then the agents, so the deploy is one
    commit throughout.
  - No Campaign was active and no run was running for either build.
  - `verify_loaded.py`: 249 loaded, 0 not.
- **An earlier deploy, `dep_b2d017bd1db9` (`7f2552af`), carried items 1–6** before item 7 was added. Its shakeout,
  `cyc_e6acda62f855`, was accepted with 22 of 22 criteria verified. It isn't the cut's run, because #2968 changed
  how every cycle's artifacts are stored and listed.
- **What the tag adds beyond it:** this release's commit: the version bump, the version markers, the changelog, the ROADMAP timeline, the open-issues
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
| 7. The Signal view doesn't hold the API | requests timed through the API, before and after | before: the API at 100% CPU, a `py-spy` dump on `_collect_artifacts` on the main thread, and one `GET …/cycles` at 5 ms on one try and 9 s on the next. After: five `hello_squad` cycle reads at 6–34 ms while a `group_run` artifact listing ran for 2.3 s; each Project's cycles at 3–8 ms; the API at 0.5% CPU. Both panels' bundles carry the "newest" note |

## 3. The cut's run

- **`cyc_a8c1b78ef675`,** `group_run`, `full-38-tf`, `validated-fullstack`, memory disabled, on the final deploy. It
  is the line's shakeout: the package's plumbing run, not a measure of any item.
- **Runs:** framing `run_f135bc0d9796` (14m40s) and implementation `run_074f728d7c0f` (7m44s), both completed.
  `progress_plan_review` was approved by `system:no_open_questions`.
- **Verdict:** `accepted`, criteria 21 of 21 verified (the cycle's assessment).
- **Rounds:** two, one per deploy, and neither found a seam defect. CLAUDE.md's exit rule is a pair on one deploy
  with no new seam finding, and the final deploy had a single run. Item 7 is the only item on a cycle's path (the
  vault stores and lists every artifact), and the run stored and read its artifacts through it. A pair wasn't
  registered.

## 4. What the cut doesn't cover

- **Item 3's restart path ran only in tests.** The deploy read a match, because Caddy had already been restarted by
  hand after #2958. The restart, the wait and the recheck run live at the next deploy that follows a Caddyfile change.
- **Item 7 has no index.** The walk still reads every metadata file under a Project, about 2.3 s for group_run, now
  off the event loop. An index in its place is later work.
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
