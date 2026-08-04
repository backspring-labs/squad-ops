# 1.4.3 Patch Plan — The Loop Can't Strand or Hide

**Established:** 2026-08-04 · successor to `docs/plans/1-4-2-correction-aim-patch-plan.md`
(same discipline: one PR per issue with `Closes`, hash-stable throughout, targeted
verification per fix, ONE deploy window, bump only after live confirmation).
**Opens:** after the v1.4.2 tag lands. Sequencing, not dates.

## Character

One coherent claim: **a cycle can neither strand the next one nor fail silently.** Where
1.4.2 aimed the correction chain, this line clears the two ways the machinery stops being
usable without saying so — a run that leaks state the next cycle blocks on, and a check
that reports an environment gap as an outcome.

Every item was verified against the code during the 2026-08-04 backlog triage, not read
off an issue title. Two changed classification on inspection: #605 was already fixed
(**closed 2026-08-04**, evidence on the issue), and #498's fix belongs somewhere other
than where the issue first proposed.

**Amended 2026-08-04** after the full-backlog sweep that followed: **#561 joins as fix 2**
(the sweep narrowed it to a residue that lands in the same module as #373, so it costs one
PR and closes a third stranding issue in a window already about stranding), and a second
rider declares a dependency 1.4.2 left load-bearing but undeclared. Five fixes, two
riders, six issues closed.

**Hash-stable by construction:** no fix touches the verification contract or interface
manifest. This is a live constraint here, not a formality — see #498, where one of the
two candidate fix sites *would* have moved the contract hash. Deploy window asserts
contract v9 `art_4f368ea08799` / manifest v4 `art_8becd104e9fc` unchanged.

## The five fixes (order = build order)

### 1. #373 + #529 — stranded focus leases never self-heal
The highest-value item on the board and the one whose shape is already proven. #529 is
the live symptom (cancelling a run leaks its in-flight focus leases; the next cycle
deadlocks acquiring them), #373 is the underlying gap (nothing ever reclaims a lease
whose owner died). The current mitigation is a **manual** pre-launch check —
`select count(*) from focus_leases where released_at is null` must be 0 — which is
exactly the kind of human-in-the-loop hygiene a framework should not require.

The fix pattern shipped in 1.4.1: `src/squadops/runtime/activity_reaper.py` says so in
its own first line — *"Stranded RuntimeActivity hygiene (#672 — the FocusLease #373
class, applied to activities)"*. We built the analogue and never built the original.
Mirror it: a `list_active_leases` port read on `FocusLeasePort`
(`src/squadops/ports/runtime/focus_lease.py` — it has request/renew/release/revoke/get
and no listing operation today), a domain reaper beside `activity_reaper`, a
release-on-finalize sweep in `RunCompletion`, and a startup reap in runtime-api init,
each keyed on the same cycle-terminal predicate #672 uses.

**Verification:** unit tests on the reaper plus the wiring-seam test #672's PR
established (the guard against a silently-uninjected port — the same silent-no-op class
this line exists to close). Then the behavioral proof, which is the manual check
automated: start a cycle, cancel it, assert `focus_leases WHERE released_at IS NULL` = 0
**without a restart**, and that a fresh cycle acquires leases immediately after.

### 2. #561 — stale activity rows with no owning cycle still never heal
The residue #672 deliberately left behind, and the sweep narrowed this issue to exactly
it. `activity_reaper.py`'s docstring is explicit:

> Activities without a ``cycle_id`` (duty/ambient sources) have no owning cycle to
> consult and are left alone.

So the permanent-breakage claim in #561 still holds for any activity row created in a
**duty or ambient** posture (SIP-0089). Cycle-owned rows heal; those do not, and one
stranded row blocks all of that agent's future activity tracking.

Sequenced immediately after #373 on purpose: same module, same startup/finalize seams,
same reviewer context, and the cancel probe below exercises both. The one design question
it raises is the terminal predicate — there is no cycle to ask, so it needs a different
one. Lease expiry and a heartbeat-age bound are the candidates; resolve in the fix PR and
record the choice there, the way #689's D0/D1 rulings were recorded.

**Verification:** a duty/ambient activity row with no `cycle_id`, stranded active, is
ended by the startup reap — and a cycle-owned row's behavior is unchanged, so #672's
guarantee is not widened by accident.

### 3. #498 — `python` resolves by PATH, so a structural check can report `missing_tooling`
`scaffold_contract.py` emits `vc-*-compiles` as `argv: ["python", "-m", "py_compile", …]`,
and `acceptance_checks._restricted_env()` inherits `PATH`. Ubuntu ships only
`/usr/bin/python3`, so on a box without a `python` alias the spawn raises
`FileNotFoundError` and the check degrades to `skipped (missing_tooling)`.

Reproduced twice during 1.4.2 development: `.venv/bin/pytest tests/unit/cycles/
test_verification_contract_runner.py` fails two tests; the same file with
`PATH="$PWD/.venv/bin:$PATH"` passes. CI passes only because `setup-python` happens to
put a shim on `PATH`.

**Decision (recorded here, pre-build): fix in the EVALUATOR, not the emission.** The
issue offers both. Emitting `python3` changes `scaffold_contract`'s output and therefore
moves the contract hash — inadmissible on a patch line, and it would leave every
already-seeded contract (including v9, which this window must not re-seed) still
carrying the bare `python`. Resolving `python` → `sys.executable` at spawn time inside
the check evaluator fixes the pinned contracts too, and is hash-stable by construction.

**Verification:** the two named tests pass with `.venv/bin` **off** `PATH` — the exact
flip the issue documents — plus a test that pins the resolution so a later refactor
can't reintroduce the bare name.

### 4. #572 — the queue advertises a delay capability it cannot honor
`adapters/comms/rabbitmq.py:175` sets a per-message `expiration` (TTL) with no
dead-letter exchange declared, so an expired message is discarded rather than routed
onward. Line 537 nonetheless reports `"delay": True` with the comment *"Supported via
TTL+DLX"*.

**Nothing is being dropped today.** `delay_seconds` has exactly one caller —
`adapters/capabilities/aci_executor.py:162` — and it passes `0`. The defect is the
capability *declaration*: a consumer that trusts `capabilities()["delay"]` and schedules
a real delay would lose the message silently. Either declare the DLX so the claim
becomes true, or report `"delay": False` until it is. Prefer the honest declaration —
the framework has no delayed-delivery consumer to serve, and a capability flag is a
contract with future callers.

**Verification:** the declaration matches the implementation. If DLX is declared, a
message outliving its TTL arrives on the dead-letter queue; if the flag is dropped, a
test asserts `capabilities()["delay"] is False` and that `publish(..., delay_seconds=N)`
with a non-zero N raises rather than silently under-delivering.

### 5. #573 — literal `|` inside the redaction email character class
`adapters/telemetry/langfuse/redaction.py:49` compiles
`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`. `[A-Z|a-z]` is "uppercase, a
literal pipe, or lowercase".

**This does not leak.** `A-Z` and `a-z` are both still covered, so emails still redact;
the class merely also matches `|` in a TLD position. Included because it is a
one-character fix in a security-adjacent surface where a reader who mistakes intent for
behavior may build on the wrong assumption.

**Verification:** a test asserting the pattern matches a normal address and does **not**
treat a pipe as a TLD character, so the fix is pinned by behavior rather than by
inspecting the regex source.

## Riders (no dedicated PRs)

- **Pin the #605 property with a test.** The issue itself is **closed** (2026-08-04):
  every AST-parsing check already calls `_unparseable_source_skip`, and the four that do
  not — `regex_match`, `count_at_least`, `command_exit_zero`, `frontend_compiles` — never
  parse Python. What remains is that the property is true by construction and asserted
  nowhere. Land a registry-wide test ("every Python-parsing check skips a non-Python
  target") so it cannot regress unnoticed; rides #498's PR, same file.
- **Declare `pyflakes` in `tests/requirements.txt`.** 1.4.2 added it to
  `requirements/base.txt` and the three locks, so every container has it — but the test
  harness gets it only **transitively, through `flake8>=6.0.0`** (`tests/requirements.txt:92`).
  CI and contributors are fine today for that reason alone. They stop being fine the day
  anyone retires flake8 — which is a live prospect, since ruff's own config comment in
  `pyproject.toml` records that its `F` rules *are* pyflakes. #689's `undefined_names`
  would then return `error: missing_analyzer` across the suite with nothing pointing at
  why. One line; declares a load-bearing dependency as load-bearing.

## Deploy window (after all five merge)

1. Rebuild all + explicit runtime-api restart + verify-LOADED behaviorally in-container.
   Surfaces: #373 and #561 touch runtime-api (port, reaper, composition root); #498 and #605
   touch the check evaluator, which runs in **both** the agent images and runtime-api
   (`patch_verification` evaluates criteria too); #572/#573 touch adapters present in
   both. So: rebuild everything, probe both sides.
2. Assert contract v9 / manifest v4 unchanged (no re-seed).
3. **The cancel probe** — a deliberate cancel, not a green roll: launch a cycle, cancel
   it mid-implementation, assert zero unreleased leases and zero stranded activities
   with no restart, then launch again and confirm immediate lease acquisition. This is
   #373/#529's live proof and it cannot be obtained from a passing cycle. #561's residue
   rides the same probe from the other side: assert a `cycle_id`-less active row is also
   ended, which the pre-#561 reaper leaves untouched by design.
4. **One unfiltered confirmation shakedown** (standard seeded launcher, full, bind mode,
   unscored) — proves #498's evaluator change did not disturb structural criteria on a
   real roll, and that nothing regressed.
5. Then `version_cli.py bump 1.4.3` + marker sync (pyproject / CLAUDE.md / README ×3 /
   ROADMAP timeline + stats — the guard catches misses) + tag.

## Deliberately out

- **The 1.4.4 slate** — #423 (skipped typed checks counted as passed), #424 (plan-merge
  fallback strips typed acceptance), #426 (planner/plan-generator mismatched sources of
  truth), #427 (failed runs are black boxes), #571 (memory recall starvation, and a
  prerequisite for the Cross-Cycle Memory SIP — PR #699). These are the *false-green*
  family: bugs that report success that isn't. They are a coherent line of their own and
  splitting them across two windows would blur both.
- **#668** — hash-moving; needs the seed-roll window (contract v10 + re-baseline) and is
  held on the owner's #670 enforce-vs-advisory ruling.
- **#687** — traceback into `failure_evidence`; cross-component (sandbox capture +
  evidence assembly + analyzer inputs) → 1.5. It is the fourth of shk-2's four
  compounding causes; the other three closed in 1.4.2.
- **#663 / #331 / #567 / #559 / #576 / #577** — structural refactors → 1.5.
- **#598 / #582 / #637** — packaging, Spark lane.

## Ledger

| Issue | Fix | Surface | Verification |
|---|---|---|---|
| #373 + #529 | focus-lease reaper (mirrors #672) | runtime-api (port, reaper, composition) | cancel probe: 0 unreleased leases, no restart |
| #561 | reap stale activities with no owning cycle | runtime-api (activity reaper) | cycle_id-less row ends; cycle-owned behavior unchanged |
| #498 | resolve `python` → `sys.executable` at spawn | check evaluator (agents + runtime-api) | the two named tests pass with `.venv/bin` off PATH |
| #572 | declare the DLX or drop the `delay` claim | comms adapter | declaration matches implementation |
| #573 | literal `\|` in the email character class | telemetry redaction | behavioral pattern test |
| #605 | (rider) CLOSED 2026-08-04; pin the property | check registry | registry-wide skip test |
| — | (rider) declare `pyflakes` in the test harness | `tests/requirements.txt` | suite passes without flake8 installed |
