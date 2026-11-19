# 2.9 plan — stabilization: a supervised Roblox Campaign attributes failures on evidence, and plays unattended and faster

**Status: DRAFT START (2026-11-18). Not adopted.** It places nothing: SIP ledgers and issue labels move when the owner adopts it.
- **Where it came from:** the owner's outside review of the 2.8.1 plan. The owner asked: "Can you update the 2.8.1 plan and draft the start of 2.9 and 2.10 plan accordingly".
- **The review's sequencing:**
  1. 2.8.1's fixes;
  2. stabilization before any extended supervised Campaign;
  3. 2.9 for throughput and stability, without changing what a squad can be asked to build;
  4. 2.10 for the missing game-development capabilities;
  5. a certification Campaign.

This draft takes steps 2 and 3. #3174, which the review placed in step 2, is in 2.8.1.

**What 2.9 is.** An odd minor: stabilization, feature-free by rule (CLAUDE.md, #281).
- **Nothing changes** in what a squad can be asked to build.
- **What changes:**
  - how a failure is attributed;
  - how the worker runs with nobody at the Mac;
  - how long a play takes.

**The claim, drafted:**

> **A supervised Roblox Campaign runs on a dedicated worker with nobody at the Mac. It attributes a failure to the
> candidate only on evidence, and it plays faster. What a squad can be asked to build is unchanged:**
> - a candidate's own setup failure is repaired in the run, on evidence, and an ambiguous one keeps today's routing;
> - the worker runs under a written dedicated-worker policy. Losing the front, a locked screen, a restart and recovery
>   are each tested, and none reads as a defect in the game;
> - a product's `qa.test` names files a runner collects, and its prompt is bounded;
> - one Studio session serves many plays, with qualification, isolation, reset and provenance held. Plays per hour
>   are measured before and after.

---

## 1. The items (drafted)

### 1. A candidate's own setup failure is repaired in the run (#3200) — the Spark lane

- **What happened:** rehearsal 3's B-2 candidate set a property a ScreenGui doesn't have, and its client threw at start.
  - All six candidate plays read `setup_failed`, and each play's console named the error and its line.
  - The baseline had met the same setup minutes earlier.
  - Since `setup_failed` is not executed, the run made no correction. The Campaign's repair was then paused by the elapsed-time guard. That cost about 12 minutes of plays on one named fault.
- **The rule:** a numbered SIP-0117 amendment, next to R5.28. A setup failure is attributed to the candidate only when all three hold:
  - the baseline's identical setup was met on the same place and worker, in the same cycle;
  - the candidate's console names an error in a file the candidate changed, within its footprint (decision D2);
  - the worker reported no environment refusal (R5.28).

  When they hold, the run gets one in-run repair, with the console's error in its evidence. Otherwise today's routing holds: not executed, never credited or failed (SIP-0096).
- **Tests:** a wiring test at the run's correction seam, with three cases:
  - **a candidate fault:** attributed, and one repair carries the error;
  - **an infrastructure failure:** the baseline also failed, or the worker refused, so today's routing;
  - **an ambiguous one:** no console error, or one in a file the candidate didn't change, so today's routing.
- **What it changes for row 8:** after this ships, 2.8.1's repair diagnostic shape is repaired in the run. §10 row 8 is then reached only when the in-run repair can't fix it, and the cut re-reads that (§3).
- **Done when:** a diagnostic on the played path shows the in-run repair carrying the console's error and the same frozen scenarios passing. It uses 2.8.1's fault, with in-run correction on.

### 2. A dedicated worker, and Studio's front (#3193) — the Spark lane

- **Today:** SIP-0117 R5.18 refuses a scenario that acts through Studio's input when another app is in front.
  - R5.28 retries the refusal and never repairs it, so it's never evidence against the game.
  - In attended windows the MacBook lane's guard procedure keeps Studio in front.
  - The owner kept the refusal through 2.8. The activation question comes after #3043, which is now closed.
- **The policy, written:** a runbook beside the worker's setup, and a numbered SIP-0117 amendment to R5.18.
  - The worker's Mac is given over to the run for a window.
  - In an attended window, Studio is kept in front.
  - A person using the Mac is never overridden.
- **The activation is the owner's decision** (D1).
- **Tests:** a Studio that loses the front mid-window, a locked screen, a Studio restart, and a worker restart with recovery. Each ends as a recorded activation, or as a not-executed `tool_unready` that's retried and never repaired. None ends as a failed criterion.
- **Done when:** a window with nobody at the Mac runs a Campaign's plays. Each loss of the front is either recovered and recorded, or refused and retried.

### 3. A product's `qa.test` is bounded (#3182) — the MacBook lane

- **The gap:** on z_tower-ascension, a `qa.test` whose expected file is under `src/` is shown 137 files, 1.7 million characters. One whose file matches no directory is shown the whole tree, 2.9 million characters. Nothing at the plan gate refuses either.
- **Both of the issue's rules** (D3):
  - **at the plan gate:** on a product, a `qa.test` whose expected files no runner of the product collects is refused by name (SIP-0112 H.4 point 3);
  - **at the prompt:** a task whose expected files match no directory is shown the files its text names and its suite imports, under a stated cap. It's never shown the whole tree.
- **Done when:** a plan whose `qa.test` names a source file or a note is refused at the plan gate. A replay of the 2.8 counted run's `qa.test` envelope shows the prompt under the cap, with the files the suite needs.

### 4. The QA prompt names only the product's runner (#3147) — the MacBook lane, if 2.8.1's condition failed

The split from 2.8.1 item 7, with a replay of the existing stacks' QA cases, since their bytes would change.

### 5. One Studio session for many plays, measured — the lane that owns the Studio runner

- **Today:** each play syncs the candidate's scripts, holds the place's state, plays and resets (R5.17, R5.18). In rehearsal 3 that was about two minutes a play (#3200).
- **The change:** Studio stays open between plays. Each play still:
  - starts from the pinned place, with its state read before the play;
  - re-reads the qualification identity (2.8.1 item 3);
  - leaves nothing for the next play.

  `ran_with` names the session and the play's index in it.
- **Tests:**
  - **isolation:** a play that sets an attribute, then a play that reads it absent;
  - **identity:** a session whose Studio changes identity between plays is refused at the next play;
  - **reset:** a place that drifts mid-session is restored before the next play, or the play is refused.
- **Measured:** on the same scenario set and the same Studio, before and after:
  - seconds per play and plays per hour;
  - Studio plays per accepted increment, read on the cut's runs.
- **Done when:** the tests pass and the measurement is on the record. A speed-up is reported as measured, never assumed.

### 6. The dependency move (#3101) — placed by the owner, 2026-11-15

FastAPI 0.163 with Starlette 1.10, aio-pika 10.2 and ruff 0.17. It changes two live paths, the `app.routes` readers and the publisher's return handling, which is a stabilization release's work (the 2.8 plan §7).

### 7. #3218 — only if the owner moves it from 2.8.1

---

## 2. Decisions for the owner (drafted)

- **D1, #3193's activation:** should the runner bring Studio to the front itself?
  - **The Spark recommends yes, under three conditions:**
    - only on a worker its settings declare dedicated;
    - only when the Mac's input has been idle for a stated time, read from the system's idle counter, so a person at the keyboard is never overridden;
    - with the activation recorded in `ran_with`.

    Otherwise the play is refused, as today. A locked screen stays a refusal.
- **D2, #3200's evidence:** the error must be in a file the candidate changed. Must it also be within the footprint? **The Spark recommends yes:** it's the narrower rule, and every case read so far meets it.
- **D3, #3182:** both rules, or one? **The Spark recommends both.** The plan gate refuses what no runner would collect, and the cap bounds what's left.

## 3. The cut's evidence (drafted)

- **#3200:** the in-run repair diagnostic on the played path (item 1).
- **Row 8, re-read:** 2.8.1's row-8 diagnostic re-run with in-run correction off, to show #3200 didn't move it.
- **#3193:** a window with nobody at the Mac (item 2).
- **Throughput:** the before-and-after measurement (item 5).
- **The existing stacks:** a shakeout pair on the final deploy, with its exit rule stated before the first launch.
- **The cut record** says what the evidence doesn't cover.

## 4. Not in 2.9

- **The game-development capabilities** are 2.10's (`2-10-0-plan.md`). So are #3205 and the certification Campaign.
- **Nothing here is a feature.** An item that turns out to need one moves to 2.10, and the plan says so.
