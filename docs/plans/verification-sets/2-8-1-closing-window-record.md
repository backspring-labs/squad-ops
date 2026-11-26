# 2.8.1 closing window record (#3218, #3147; the 2.8.1 plan's items 6 and 7)

The last window before the 2.8.1 cut. It held two uncounted Campaigns on the Roblox product, and the Spark ruled
their gates under the owner's grant of 2026-11-16. Pre-registered by amendment 12j of
`2-8-0-demonstration-preregistration.md` (#3241, merged before the first launch).

## 1. The result

- **#3218's threshold holds** (item 6). 32 entries were counted, against at least 20. No worker request took more than 2 s,
  and none timed out (§3).
- **The QA capture was taken, and the replay's QA case was read on it** (item 7, §4).
- **Both Campaigns were accepted on their first build cycle.** Each proposal was returned once at the increment
  gate, then approved at version 2 (§2).

## 2. The window

- **Named by the owner** in the Spark session at 10:56 ET on 2026-11-20 ("Ok let's open the next window now"). The
  MacBook lane took Studio and the worker on the owner's "Go now" in its own session.
- **The deploy:** framework `a67dace4`, with `dep_06ab48234612` for the window. The provider was switched from `none` to
  `runtime_api` at 16:03:01Z, on the runtime-api and the QA agent both, and verify_loaded read 302 loaded, 0 not.
  It was switched back after the window (`dep_35d8150535c1`, 302 loaded).
- **The worker:** `wks-e6cc469bd50949e3b4a81cc755638a66` on the MacBook, registered at 16:07:01Z from `a67dace4`.
- **The window-opening check (12j):** Studio `0.748.0.7481526`, channel `production`, tools `39:b7cd2a22…`, with the list
  byte-identical to the one requalified at 13:12:44Z. It was read twice: after a fresh launch (16:05:47Z) and after the
  worker's start reset (16:06:34Z). One Studio launch served every play, no reset ran inside the window, and the pin
  was unchanged after it. The front guard ran from 16:06:22Z and made no re-activation.

| Campaign | what | ran (ET) | proposal | build | ending |
|---|---|---|---|---|---|
| A `cmp_78172e5d0861` | capture 5's objective (a shop discount rule), no development profile, so no skill loaded | 11:09–11:23 | v1 returned (`criteria_not_checkable`): one of its four examples contradicted its own arithmetic. v2 corrected it and was approved | `cyc_39531b9c38cd` accepted | §10 row 3 |
| B `cmp_3d0944a1710d` | the lives-label objective (replay case `strategy-hud-text`'s, word for word), under `game_dev_roblox` | 11:24–11:51 | v1 returned (`unclassified`, a coverage gap, below). v2 was approved | `cyc_78f98f6462f2` accepted | §10 row 3 |

**B was the first live Campaign under the revised scenario skill (#3228).** It is reported here, not counted.
- **v1:** one played criterion, the label's text at the start. Every player starts with the same lives, and no action
  in a play changes them. So a label written once, never updated, passed it: the obvious broken build in the skill's
  rule 3, and a sentence of the objective no criterion read (rule 1).
- **The return:** it said so, and named no module or test.
- **v2:** kept the played half and added a headless criterion on the label's rule at three counts, with a
  `Not played:` line saying what no play reaches. That is the shape of rule 6.
- **What this shows:** the skill's route was taken after one return, not before it.
- **Not covered,** as the skill's proposals declare: that the HUD's label uses the rule the headless criterion proves.

**B's plays,** each `completed` and accepted on attempt 1, with the claim-to-completion times from the worker's log:

| operation | play | named assertion | claim → completion |
|---|---|---|---|
| `rop-ff03b806…` | the baseline | failed (`<absent>`), as it must; the precondition passed | 98.3 s |
| `rop-e4eb8bc3…` | the in-run candidate | passed | 98.2 s |
| `rop-18b4217e…` | the Campaign's candidate | passed | 99.8 s |

Every play ran past the 60 s lease, and every renewal succeeded. A had no plays.

## 3. #3218's threshold

**What counted (12j):** rows of `campaign_control_log` with outcome `applied`, and rows of `cycle_gate_decisions`.

| | control rows | gate decisions |
|---|---|---|
| A | 13 | 3 |
| B | 13 | 3 |
| **total** | **26** | **6**, so 32 entries |

**The runtime-api, 16:03:00Z to the window's end:**
- **Worker requests:** 802 log lines on `/api/v1/workers/*`. One `slow_request` (over 1 s): a heartbeat at 1.06 s,
  16:23:26Z. None was over 2 s.
- **The loop watchdog:** nine stalls, with lag 1.00–1.08 s, each ended with `held_s=0.10`. The stack at each names only the
  server's own run loop, not a vault or database frame. That is the shape #3238's fix left behind: the 13–41 s holds
  in the vault's index reads are gone.
- **Slow pool acquires:** none.
- **One request over 2 s, not a worker's:** B's `POST /api/v1/campaigns/…/start` took 2.06 s (16:24:21Z). It is outside the
  threshold, which reads worker requests, and is recorded so the cut record can name it.

**The worker** (the MacBook lane, `worker.log` lines 442–449, 16:07:01Z–16:52:15Z):
- no request timed out or went unanswered, no lease renewal failed, and no result went undelivered;
- zero WARNING or ERROR lines;
- `last_unreachable_at` null throughout.

**What the reading can't show.** The worker logs a request only when it fails. A response over 2 s that still arrived
inside the client's timeout shows only in the runtime-api's `slow_request` lines, which is why both sides are read.

**Reading:** holds. Item 6 is done.

## 4. The Luau QA capture and the replay's QA case

**The capture.** A's build run, `run_94ce5332faaa`, holds one `qa.test` envelope (`fff215c9…`). It was rendered by the
deploy on #3229's Luau fragment, with no skill loaded. The replay's validity check reads `qa-capture` as valid,
with the capture checked byte for byte: 59,618 characters, and 66,352 with its skills. On the last capture,
`roblox-skills-v4-revised-3` read it as not valid, since #3229 had changed the prompt since that capture.

**The replay:** `roblox-skills-v4-capture-6`, cases `roblox-skills@3`, 3 generations, seed 7. A's three envelopes
were used: the proposal (v2), the first development attempt, and the test task. The product checkout was `0beaac09`,
with Lune installed by the product's own install step.

| case | skills arm | what was judged |
|---|---|---|
| **qa-capture** | **3 of 3 met** | every generation's spec loaded and passed under `tests/run.luau`, with the capture's implementation laid over it (5 of 5 tests each), and **discriminates**: it reads `only_setup_failures` without the implementation (SIP-0109 §24ec) |
| dev-capture | 3 of 3 | as before |
| dev-saved-field | 3 of 3 | as before |

- **The strategy cases read as not valid on this capture,** whose proposal envelope is a revision's. They were read
  on the earlier capture by #3199's replays, and nothing in this window changes them.
- **The baseline arm** left its specs to the product's runner in every generation, and is held to nothing.

**Reading:** the replay's QA case meets its expectations, and #3229's render tests pass in CI. Item 7 is done.
#3147 stays open for its per-stack move, unplaced (SIP-0112 H.37).

## 5. What this doesn't cover

- **One window, two Campaigns, three plays.** The threshold held with 32 entries and a worker polling throughout. A
  longer Campaign, with more promotions per gate, is untested on this deploy.
- **B's result is one Campaign.** It shows the revised skill reaching its route after a return. It is not a rate.
- **A's outcome is not evidence;** only its envelopes are used.
