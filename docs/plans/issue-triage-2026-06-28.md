# Open-Issue Triage — 2026-06-28 (post-1.1.0)

Deep triage of all **40 open issues**, each verified against the current code (not
just the hardening plan). Snapshot doc — keep, commit, or delete as you like.

Method: 6 parallel investigators read each issue + its comments and checked the
actual code, then I cross-checked the linchpins (DbRuntime backend, version state).
The named `docs/plans/1-1-x-hardening-plan.md` was treated as a hypothesis to
verify — it holds up well, with a handful of corrections noted below.

---

## TL;DR

| Action | Count | Issues |
|--------|------:|--------|
| **Close now** | 5 | #253, #132, #217, #153, #134 |
| **1.1.x patch queue** (bug fixes / quick wins) | 12 | #245, #250, #239, #222, #168, #156, #130, #133, #205, #216, #224, #79 |
| **Reduce scope** (correct a stale claim, then small) | 5 | #154, #158, #94, #198, #114 |
| **Feature / SIP work (1.2.0+)** | 5 | #233, #244, #172, #176, #194 |
| **Tech-debt backlog** (opportunistic, non-gating) | 9 | #152, #186, #234, #173, #157, #80, #218, #219, #242, #231 |
| **Needs your decision** | 6 questions | #237, #234, #173, #218/#219, #225, #114 |

**Headline:** 5 issues are already done/obsolete and can close immediately. The
1.1.x lane has a clean cluster of **~8 small (S-effort) PRs** that are pure wins —
led by one real reliability bug (#245). Most of the rest is correctly-deferred
feature/SIP work or opportunistic tech-debt. The 1.1.x hardening plan's bucketing
was accurate; the main corrections are that several issues are **more done than
the plan credits** (#217, #158, #94, #154, #198).

**My one recommendation for next step:** run a **"1.1.x clean-up sprint"** — close
the 5 dead issues, then land the S-effort patch cluster in priority order starting
with **#245**. Details in the queue below.

---

## A. Close now (5)

| # | Why it can close |
|---|------------------|
| **#253** | Fixed by open PR **#254** (body `**Status:**` rewrite). Closes on merge. |
| **#132** | `runs resume --reason` 422 is **not reproducible** on current code. CLI sends `resume_reason` (`cli/commands/runs.py:266`); DTO accepts exactly that (`api/routes/cycles/dtos.py:303`). `git log -S 'body["reason"]'` is empty — the bare-`reason` key never existed. Symptom was an interim build. *Optional:* add one round-trip test (none exists) before closing. |
| **#217** | 3.12 standardization **landed** (`e9a9144`): `.python-version`=3.12, CI on 3.12. The "ci-constraints uninstallable on 3.11" residue is now moot by design (test env is 3.12-only). Close with a note that 3.11-installable locks were intentionally traded away. *Verify first:* re-check the `test_correction_protocol.py` ~57% hang on a clean 3.12 venv. |
| **#153** | Strict **subset of #234**. Import-coupling already fixed by #232 (TYPE_CHECKING guard). The remaining contract leak is consumed **only by tests** — no domain code reads `.engine`/`.session_factory`. Fold into #234. |
| **#134** | qwen2.5:32b YAML brittleness: the corrective-retry the issue proposes **already exists** (`planning_tasks.py:358` `_retry_without_frontmatter`). This is a **model-selection** question, not a code gap. Close or reframe to "swap Max's full-squad model." |

---

## B. 1.1.x patch queue (priority-ordered)

All verified as real and unstarted (unless noted). Recommended order optimizes
value-per-effort and respects dependencies.

| Order | # | What | Effort | Owner | Notes |
|------:|---|------|:------:|:-----:|-------|
| 1 | **#245** | RabbitMQ `publish()` has no retry during the `connect_robust` reconnect window — task dispatch silently lost on a broker blip. `rabbitmq.py:123-168` is single-attempt; consume path has recovery, publish doesn't. | **S** | spark | **Highest-value bug.** Add bounded retry/backoff + regression test (mirror #146). Doubles as #157 coverage. |
| 2 | **#250** | `factory.py:96-100` inline-builds `PrefectWorkflowTracker`, bypassing the new `create_workflow_tracker` (skips NoOp fallback + logging). | **S** | spark | **Cleanest win — zero behavior change.** Route through the factory with `PrefectConfig(api_url=...)`. |
| 3 | **#239** | OTel `BrokenExporter` test registers a global provider with no teardown → atexit `RuntimeError` traceback on **every** regression run. `otel.py:82` + `test_adapters.py:140`. | **S** | spark | Log-hygiene/CI-trust. **Do before #216** — the global-provider leak is a parallelism hazard. |
| 4 | **#222** | Duty-deferred PAUSED runs can't resume — deferral pauses pre-dispatch with no checkpoint (`dispatched_flow_executor.py:334-353`), but resume hard-requires one (`runs.py:212-214`). | **S** | macbook | Real SIP-0089 bug. **Recommend option 2**: allow checkpoint-less resume for deferral-paused runs (gate on `reason=upcoming_hard_duty_window`) — don't fabricate a checkpoint implying progress. |
| 5 | **#133 + #205** | One PR (shared docstrings). `runs retry` creates an orphan queued run that never executes (`runs.py:37-84`, no enqueue); both CLI help strings are stale/false. | **S** (docstrings) / **M** (wire retry) | spark | Fix docstrings now. Wiring `create_run`→enqueue `execute_run` (copy the cycles-route pattern) is the real fix — small follow-up. |
| 6 | **#168** | DistributedFlowExecutor rename residuals. **Runnable code is clean** (0 hits in src/adapters/scripts). Only a broken doc example `docs/reviews/...:437` (`"distributed"`→`"dispatched"`) + 2 stale filenames. | **S** | — | Doc-sweep only. **Do NOT touch frozen `sips/implemented|accepted/*`** or the SIP-0066 "distributed execution" concept refs. |
| 7 | **#156** | `_parse_jsonb` copy-pasted in 3 adapters (`postgres_cycle_registry.py:439`, `postgres_squad_profile.py:213`, `chat_repository.py:154`). | **S** | spark | Extract one helper. **Subtlety:** `chat_repository` adds a `None→{}` branch — preserve at its call sites; keep the shared helper a pure `str→json.loads`. |
| 8 | **#130** | Neo `development.develop` unparseable output. Parser is already tolerant + persists raw output to `build_warnings.md`. Missing: `<think>`-block strip before fenced parse, and a truncated-raw warning log. | **S** | spark | Reuse `_strip_think_blocks` from `_json_extraction.py`. Bug-defense, not a SIP. |
| 9 | **#216** | `pytest-xdist` is pinned but `-n auto` is **never invoked** (only the dep half is done). | **S→M** | spark | Add `-n auto` to `run_regression_tests.sh:52`; green run = acceptance. **After #239** (isolation hazard). M if collisions surface. |
| 10 | **#224** | Model-availability preflight. Primitive exists (`profiles.py:71-95` `_check_model_availability`) but only runs on profile CRUD as a *warning*; cycle-create has none; doctor checks bootstrap not squad-profile models. | **M** | spark | High value (the #1 time-waster). Lift the existing check to a shared helper + fail-fast at cycle-create. **Decision:** standalone patch, or fold into the #172 preflight SIP (see F). |
| 11 | **#79** | Rename `governance.establish_contract`→`define_done`; `run_contract.json`→`definition_of_done.json`. | **M** | macbook | Pure clarity rename, no behavior change. **Blast radius ~14 files/52 refs** — issue missed the whole `cycles/run_contract.py` module. Register both capability IDs w/ deprecation for one cycle; dual-read the artifact filename. |

---

## C. Reduce scope — correct a stale claim, then it's small (5)

Each of these has a **factually outdated premise**; post an issue comment with the
correction so nobody rebuilds what exists, then the remainder is small.

| # | The issue says… | Reality today | Reduced scope |
|---|-----------------|---------------|---------------|
| **#158** | "No migration tracking table." | **False — `_schema_migrations` already exists** (`api/runtime/migrations.py:27`) with per-file txns. | Remaining: add `pg_advisory_lock` around the migration loop + a model↔DDL drift test + wire the existing `timeout_seconds` ctor params from `SQUADOPS__*` (rabbitmq poll still hardcoded `1.0`). **M, was L.** |
| **#154** | "Move adapter imports out of domain." | Most are **legitimate composition roots** (entrypoint, api/runtime/* self-document as such). Only **one** true leak: `orchestration/orchestrator.py:112` lazy NoOp import. Forbidden-imports test already exists (just doesn't cover `orchestration/`). | Inject the NoOp from the composition root + extend the existing arch test to `orchestration/`. **S, was M.** |
| **#94** | Points at `_build_task_name` in `distributed_flow_executor.py:571`. | Function was **extracted** to `adapters/cycles/task_naming.py::build_task_name` (now agent-prefixed). The divergent-copy problem is solved; only per-role `[n/total]` numbering + framing titles remain. | Add per-role index/total at dispatch-planning + a framing title map. **M.** Refresh the issue's stale pointers first. |
| **#198** | "Adopt FastAPI ≥0.136." | CI-unblock **done** — `fastapi==0.135.4`/`starlette==1.3.1` pinned and running clean. The cyclic router is in the external `continuum` package. | Only the forward adoption remains, and it needs a CI lock-regen (x86_64/py3.12). Low urgency; schedule as a coordinated lock bump, not mid-lane. **L, deferred.** |
| **#114** | typed_check_evaluation.json never emitted. | Root cause **confirmed**: `_validate_output` only takes the typed-check path when `subtask_focus` is present (`cycle_tasks.py:1182`); dev tasks without it fall to `_validate_monolithic` which skips typed checks. | **Decision (see F):** fix routing (M) **or** remove the dead plumbing if SIP-0092 M2's `plan_review.yaml` subsumes it (S). Tie to current SIP-0092/0093 state; not 1.1.x-urgent. |

---

## D. Feature / SIP work — 1.2.0+ minors (5)

Net-new capability or behavioral/contract changes — correctly deferred; ship as
minors behind a SIP or spec.

| # | Item | Effort | Notes |
|---|------|:------:|-------|
| **#233** | SIP-0089 §3.5 — route cycle recruitment through the coordinator to acquire a FocusLease. | **L** | ~~Deferred-by-design~~ **REVERSED — LANDED 2026-07-01** (PR #287 `0e86299`, slices 1–4; `runtime/admission.py` + shared coordinator). Original defer note: lease gate already enforced at coordinator; redundant-for-v1.1 executor path w/ stranded-lease risk. **#244 depended on this.** |
| **#244** | SIP-0089 §4.5/D25 — wrap coordinator lease+activity+mode in one Postgres txn. | **L** | ~~premature infra~~ **LANDED 2026-07-01** (PR #293 `8cf5ab7`, RuntimeTransaction UoW port wired + live rollback test). Landed with #233 as originally sequenced. |
| **#172 (+#224)** | Cycle-create **preflight stage**: capability/role satisfiability (#172) + model availability (#224). | **M** | `validate_against_profile` exists but runs at dispatch, *after* the gate. Both are mostly **placement/wiring**, not new logic. Jason already flagged #172+#224 as siblings → **one combined preflight SIP** is the right boundary. |
| **#176** | Framework smoke integration test — codify the create→…→artifact-persistence invariant chain as machine-checkable assertions; small-model-runnable. | **M-L** | No such test exists (`tests/smoke/` is infra-only). Keep strictly distinct from the QA acceptance pack. Needs a spec for the invariant contract. |
| **#194** | SIP-0093 **B′ revision loop** — proposers hand-back on unresolved cross-role dependency focuses. | **M (alt-D) / L (full B′)** | #189 normalization done; no revision loop (SIP-0093 says so explicitly). **Extract the cheaper "alt-D de-noise" (distinguish vocab-mismatch from real gap) as a standalone small 1.1.x item.** |

---

## E. Tech-debt backlog — opportunistic, never version-gating (9)

| # | Item | Effort | Owner |
|---|------|:------:|:-----:|
| **#152** | Split `cycle_tasks.py` (**3,226 lines**, 9 handlers) into per-handler modules. | L | macbook |
| **#186** | Decompose `DispatchedFlowExecutor` (**3,290 lines / 52 methods** — *grown* since filing). Needs a **boundary SIP**; first slice = #185 task-naming (done-ish). | L | macbook |
| **#234** | DbRuntime port shaped to legacy SQLAlchemy backend. **See decision F.** Absorbs #153. | S–M | spark |
| **#173** | Consolidate squad-profile names (drop `-with-builder`; `full-squad`≡`spark-squad-with-builder` 27b). **Names need a decision (F).** Breaking change + DB migration. | M | spark |
| **#157** | Coverage gaps (api/comms/integration). Convert to an **umbrella tracking issue**; let concrete fixes (e.g. #245's test) check items off. | L (incremental) | spark |
| **#80** | Capture framework version / git SHA / request-profile on the Cycle record. Migration slot is **1140** (issue's "1000–1099" is stale). | M | spark |
| **#218** | Make the API prefix/versioning standard self-enforcing. Doc done (CLAUDE.md); **arch test + SIP checklist + error-envelope unstarted.** | M | spark |
| **#219** | Move `/api/chat`+`/api/agents`→`/api/v1`. **Sequence after #218** (delete the grandfather exemption in the same PR). Don't forget the `dist/plugin.js` rebuild. | M | spark |
| **#242** | Serviceless integration tests rot (nothing runs them in CI). Cheapest: relocate mocked "integration" tests under `tests/unit/`. | M | spark |
| **#231** | Status vs runtime-state terminology + duplicated health field. **Do the doc step now (S)**; defer the `network_status` collapse (strangler). #230 should be built against this model. | doc S / full L | macbook |

*(#230 — surface mode on the agent-list API/dashboard — is a 1.1.x-able M, but sequence it right after #231's doc step so it's built on the canonical model. Listed here as the natural pairing.)*

---

## F. Decisions I need from you (6)

1. **#237 — Drop Python 3.11 / migrate prod to 3.12?** Prod Dockerfiles are all still `python:3.11-slim`; `requires-python` still `>=3.11`. The 3.11/3.12 split is the known accepted temporary state. **When** do we close it — at a clean SIP-0089 phase boundary? (M + deploy-validation risk.)
2. **#234 — Retire the legacy SQLAlchemy DbRuntime, or just de-leak the port?** It's the *sole* DbRuntime backend, but live cycles/SIP-0089 persistence runs on **asyncpg**; `.engine`/`.session_factory` are consumed **only by tests**. Cheap path: drop the leaky accessors from the *port* (#153 resolved for free). Bigger path: confirm what still needs `PostgresRuntime` (health checks?) and retire it. Which appetite?
3. **#173 — Target squad-profile names?** e.g. `selftest`/`lite`/`full`. Pick the set and I'll execute the breaking-change checklist (YAML + bootstrap + DB migration + docs).
4. **#218/#219 — Chat routes: move to `/api/v1` or formally exempt?** And do you want the **enforcement** (arch test that fails CI on a non-standard prefix), or just the doc rule? (Recommend: arch test with the two deviants grandfathered, then #219 deletes the exemption.)
5. **#225 — Rename comms agent id `comms-agent`→`joi`?** Config-only (`docker-compose.yml:550` + `instances.yaml:70`), zero code coupling — but `docker-compose.yml` is on the "don't modify without explicit request" list. Approve the touch?
6. **#114 — Fix the typed-check routing, or remove the dead plumbing?** Depends on whether SIP-0092 M2's `plan_review.yaml` already gives the C2 signal. Your call against the current SIP-0092/0093 roadmap.

---

## Corrections to the 1.1.x hardening plan

The plan is accurate overall; suggest these edits:
- **#217** → move to "done/close" (3.12 standardization landed; not open hardening).
- **#216** → note only `-n auto` invocation remains (dep already pinned).
- **#222** → it's a small **1.1.x bug-patch**, not a peer of the L-effort #233/#244 deferrals.
- **#153** → mark as **subset of #234** (close into it).
- **#158** → note the tracking table already exists (scope is lock + drift-test + timeout wiring).
- **#94 / #154 / #198** → flag as partially-done (function extracted / composition-roots-are-fine / CI-unblock landed).
- Add **#230/#231** to the runtime-lane follow-ups (cheap observability/doc wins).
