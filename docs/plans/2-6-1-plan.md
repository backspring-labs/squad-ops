# 2.6.1 plan — what the operator meets first on 2.6.0, fixed small

**Status: ADOPTED (2026-11-07).** The owner ruled the scope at ~19:30 ET after the 2.6.0 cut: "Please write the 2.6.1
plan and start executing it. You can merge on green CI". That was the reply to six candidates: the console caching fix
(already in flight), #2932, #2933's remainder, #2949's remainder, a deploy gap found the same day (#2960), and #2909. The
owner chose to leave out #2954, #2944, #2935's remainder, #2839, #2931 and #2921 (§4). This plan says how each item
is built and verified, and what it leaves out.

**What 2.6.1 is.** A patch on the 2.6 line (CLAUDE.md, #281: urgent or small fixes, either lane). Each item is a defect
in something an operator running Campaigns on 2.6.0 meets now. None changes a design, and none needs a ruling to
build, except D1 (§3), which is an option the owner can take or leave without blocking the line.

**The claim it makes:**

> **What the console and the box show an operator is what is running:**
> - a rebuilt console plugin reaches the browser on a normal reload;
> - a config change the deploy made is the config that runs;
> - after a reboot the selected model engine comes back, and nothing else does;
> - a suite handed to the product's runner reads as handed off, not as failed;
> - a criterion test that asserts nothing is less likely to be written, and is named when it is;
> - the console's buttons do what they say.

---

## 1. The six items

### 1. Console plugins are cached by version (#2958, #2959; backspring-labs/continuum#4) — done

- **The defect:** a plugin bundle kept one URL across deploys and was served with no `Cache-Control`. After the 2.6.0
  rebuild, Safari kept showing a replaced plugin's text until its cache was emptied.
- **The fix:** #2958 put `Cache-Control: no-cache` on `/plugins/*` in the Caddyfile as a stopgap. Continuum 1.0.3
  (continuum#4, tag `v1.0.3` at `7bbb8e52`) then fixed it at the source:
  - the registry gives each bundle URL `?v=<content hash>`, hashed from the bytes on every read;
  - the current version is cached for good (`immutable`), while a missing or stale `v`, and the registry itself, are
    revalidated;
  - an unchanged file answers 304.

  #2959 pinned the console to 1.0.3 and removed the stopgap.
- **Verified live** on `dep_5c07bbb7dcf2` (2026-11-07): 11 of 11 bundle URLs versioned, the expected header in each
  case, 304 with an empty body on `If-None-Match`, and 249 checks loaded. Continuum's own WebKit test fails on 1.0.2's
  source and passes on 1.0.3.

### 2. The selected model engine comes back after a reboot (#2932, ask 1)

- **The defect:** after the 2026-11-05 power loss every compose service restarted except TensorFold. Its container is
  started by `docker run` in `scripts/dev/ops/engine_switch.py` (`serve_command`, `:302`) with no restart policy, so it
  exited and stayed down, while the agents read healthy.
- **Why a restart policy is safe here:** the two engines must never run together. The switch stops Ollama with
  `compose stop` (`stop_ollama`, `:246`) and removes TensorFold's container (`stop_tensorfold`, `:390-394`). Under
  `unless-stopped`, a container stopped that way stays stopped across a daemon restart, and a removed one doesn't
  exist. So only the selected engine comes back. Ollama's compose service already carries `unless-stopped`.
- **The watchdog's kill holds too:** `memory_watchdog.py:72` stops TensorFold with `docker kill` under memory
  pressure. Tested on a throwaway container (2026-11-07): a killed `unless-stopped` container stayed down, while one
  whose process exited by itself restarted. `always` would restart a killed container at the next daemon start, so
  the policy is `unless-stopped`, not `always`.
- **The fix:** `serve_command` adds `--restart unless-stopped`. The running container is updated in place with
  `docker update --restart unless-stopped`, which doesn't restart it.
- **The test:** `serve_command`'s line carries `unless-stopped` as a `docker run` option, before the image (after
  it, the engine would read it as its own argument).
- **What stays open on #2932:** ask 2, an agent consuming a redelivered task while its engine is unreachable, is
  larger and goes to 2.7. The PR says `Refs #2932 — remaining: ask 2`.

### 3. A config change the deploy made is the config that runs (#2960)

- **The defect:** Caddy mounts `console/Caddyfile` as a single file (`docker-compose.yml`, the `caddy` service). A
  `git pull` replaces the file rather than writing into it, so the container keeps reading the old one. A
  `caddy reload` then reloads the old config and reports success. Found while deploying #2958, 2026-11-07:
  `rebuild_and_deploy.sh` has no Caddy step at all.
- **The fix:** after the console step, `rebuild_and_deploy.sh` compares the Caddyfile the container reads with the
  checkout's. When they differ it restarts Caddy (not a reload, for the reason above), then confirms they match. It
  prints both hashes either way. The deploy record names the step.
- **The test:** the comparison is a function with a unit test over a matching pair, a differing pair, and an
  unreadable container file, which must be reported, not taken as a match. The live check is a deploy where the
  Caddyfile changed.

### 4. A suite handed to the product's runner reads as handed off (#2949's remainder)

- **The defect:** #2953 fixed `test_report.md`'s wording. The hand-off's emission is still banked
  `emission_status=failed` (`dispatched_flow_executor.py:5262-5295`), the marker every unsuccessful emission gets,
  so the run's evidence lists a failure seconds before the product's runner passes the task (#2818, #2877).
- **Before changing it (the mirror rule):** `failed` is read in at least seven places to keep an emission out of the
  delivered tree and the next task's inputs. Among them: `source_delivery.py:130`, `source_checkout.py:197`,
  `delivered_tree.py:66`, `deletions.py:53`, `cycle_assessment.py:368`, and `dispatched_flow_executor.py:1854` and
  `:1953`. A new marker value would pass every one of those checks. So the first step is a table of each reader and
  what it must do with a handed-off emission, in the PR's Evidence.
- **The likely fix:** keep `failed` as the stored marker, since the bytes really are the image's unrun attempt. Then
  name the hand-off where it's read: the run's evidence and the digest say "handed to the product's runner", with
  the runner's verdict beside it, not "failed". If the table shows a reader that needs the distinction, it gets one
  explicitly rather than by a new value slipping past an `==` check.
- **The wiring test** enters at the executor's qa dispatch with a result left to the product's runner and a runner
  that passes. It asserts what the run's evidence says about that first emission.

### 5. A criterion test that asserts nothing (#2933's remainder)

- **The defect:** a criterion test whose only assertions sit in a loop over an empty collection passes on the head
  having checked nothing. §10 row 19 then abandons a real backlog item as already met. #2934 (§24dh) caught the form
  where a qa repair rewrote the test into that pass. The form where qa's first emission is vacuous is still open:
  `cmp_ff52e424aea1` BT-9 looped over `unit.blocked`, which is a number, so 16 tests passed and checked nothing.
- **The fix in scope (prompt work, `docs/PROMPT_AUTHORING_STANDARD.md`):**
  - the qa authoring brief and the qa repair brief show, by example, a criterion test that asserts its collection is
    non-empty before looping over it, and that reads the suite's provided fixture rather than an inlined stand-in;
  - the head check's reading, which reaches the next proposal, names the criterion that passed on the head, so a
    vacuous pass is visible where the item is moved on.

  Each brief change is in `src/squadops/prompts/fragments/`, never inline (#448).
- **The test:** a rendered-prompt test that the example is in both briefs, so it isn't cut from one, plus the
  existing head-check tests.
- **What the prompt can't do:** stop a vacuous test from being written. That is D1.

### 6. Home's "New Cycle" button does what it says (#2909)

- **The defect:** `console/continuum-plugins/squadops.home/ui/src/HomeSummary.svelte:24-26` calls
  `window.squadops.executeCommand`, which the console never defines (`console/app/main.py` defines `apiFetch`). The
  button does nothing.
- **The fix:** go through `console/continuum-plugins/shared/commands.js`, the helper #2903/#2904 added for every
  plugin's command body, as the other plugins do.
- **The test:** a node test that the button's handler posts the command through the shared helper's body, in the
  confined node image (`node --test <file>.test.js`). The live check is a press on the deployed console that reaches
  the command bus.

---

## 2. How the line is built and verified

- **Order:** items 2 and 3 first (operational, small), then 6 and 4, then 5. Item 1 is done.
- **Each item is its own PR,** with `Closes #N` or `Refs #N — remaining: …`, merged on green under the owner's grant
  for this line, with main's CI finished green at its tip.
- **Deploys happen only when no Campaign is running.** The Campaigns API is read before each rebuild, and a running
  Campaign waits for its ending.
- **The cut's evidence:** each item's live check above, on the final deploy, plus one cycle on `group_run` for the
  package. The package names it as `shakeout` and says it is the cut's plumbing run, not a measure of any item. No
  Campaign on battle-trainer is run for the cut: its goals are the game maker's and the operator's, not the cut's.
- **The cut** follows CLAUDE.md's procedure, steps 1–8. Its record says what the deploy ran, and names the 2.6.0 cut
  record's deploy id: that record names `dep_bd2a684d602a`, built before the version bump. The deploy that ran after
  it was `dep_623daddbf654`.

## 3. Decision for the owner

- **D1. A criterion that passes on the head on qa's first emission.** Today row 19 abandons the item, uncounted.
  Option (a): it is refused to qa as a criterion that doesn't fail on the head, spending a repair round, as a
  post-repair pass already is (§24dh), and the item is abandoned only if the round ends the same way. Option (b): leave
  row 19 as it is. **Recommended: (a).** The head check exists because a criterion that holds before the work proves
  nothing about the work. One round costs less than a backlog item moved on with its behaviour missing, which is what
  BT-2 and BT-9 both show. It changes what row 19 does, so it needs a SIP-0109 amendment, and it is built in 2.6.1
  only on the owner's yes. Otherwise it goes to 2.7.

## 4. Not in 2.6.1

- **#2954, #2944:** the operator's assessment and the product's reading reaching the squad's next proposal. New
  features, for 2.7.
- **#2935's remainder:** whether row 19 re-queues an abandoned goal-set item waits for the owner (SIP-0115 §5.3).
- **#2839:** a dev repair that rewrites product code around a missing dependency. A design change, already placed in
  2.7.
- **#2931:** an empty artifact after a power loss strands a re-attached run. Real but rare, and the fix is medium.
- **#2921:** the console's Signal view holds the browser's connections for minutes. Medium, and its own console item.
- **#2932's ask 2:** an agent consuming a redelivered task while its engine is unreachable.
