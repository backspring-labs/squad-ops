# 1.4.2 Patch Plan — Correction Aim + Authoring Prevention

**Established:** 2026-08-03 · successor to `docs/plans/1-4-1-hardening-patch-plan.md`
(same discipline: one PR per issue with `Closes`, hash-stable throughout, stored-artifact
replay verification, ONE deploy window, bump only after live confirmation).
**Opens:** after the v1.4.1 tag lands (PR #690 merge). Sequencing, not dates.

## Character

One coherent claim: **the correction chain aims true, and known authoring classes can't
be authored.** Every fix traces to the shk-2 confirmation shakedown (cyc_88162ecfd895,
2026-08-03), where a one-line defect (unimported symbol → call-time NameError → 500)
survived two correction attempts because the analyzer guessed causes, the repairs aimed
at drift-named files, an unauthorized frozen write supplied the distracting drift
evidence, and no static gate could see the class.

**Hash-stable by construction:** no fix touches the verification contract or interface
manifest. Deploy window asserts contract v9 `art_4f368ea08799` / manifest v4
`art_8becd104e9fc` unchanged — same check as 1.4.1.

## The four fixes (order = build order)

### 1. #688 — repair targeting must include the defect-owning fill slot
Behavioral probe failures routed to the dev chain derive their repair target set
deterministically: failed probe → endpoint → interface manifest → owning fill slot.
Drift-named files ride as secondary targets, never displacing the defect site. Extends
#650; surface = `correction_runner` target resolution (the #667 neighborhood).
**Replay verification:** rerun target resolution against shk-2's stored failure evidence
(`art_342f03880b9d` / `art_8407713bb314`) + plan (`art_4b9606338510`) → the target set
must contain `backend/routes.py`. Both shipped repairs (`art_deaec27453ae` etc.) are the
regression fixtures for what the old logic produced.

### 2. #691 — write authorization at emission acceptance (SIP-0100 gap)
Unclaimed files in a dev emission are rejected or stripped-with-disclosure at
acceptance/assembly — never silently assembled; frozen/scaffold-owned files doubly so.
Post-hoc drift detection demotes to defense-in-depth. Preserves the legal case: claimed
multi-file emissions are fine. Precedent: #649 (builder write authorization).
**Replay verification:** shk-2's stored dev-task-0 emission (authorized
`backend/routes.py` + unclaimed frozen `backend/main.py` `art_1b357644220a` /
`backend/models.py` `art_4b4a4cb88095`) → routes.py accepted, both frozen files
rejected with disclosure in the validation result.

### 3. #689 — undefined-name (F821) typed check on `.py` fill slots
Error-severity, auto-applied to `.py` fill-slot emissions, catching used-but-unimported
symbols statically at acceptance — the class every current gate missed.
**Decision D0 — the seam, RULED (2026-08-03, pre-build):** the check is
**framework-injected at emission acceptance**, NOT a contract-authored criterion. The
tempting home is `scaffold_contract.py::_routes_criteria`, where #628's `module_imports`
already hangs off `backend/routes.py` — but that function *generates the verification
contract*, so a new row there moves the contract hash, violating this patch's
hash-stability constraint. Worse, it would be untestable in the confirmation window:
bind mode **loads** the pinned contract from `contract_ref`
(`dispatched_flow_executor.py` `_is_bind_mode` / contract loading) instead of
regenerating it, so a contract-authored check would stay invisible until a re-seed —
which this plan defers to the #668 window. Injection at acceptance keeps the check live
under the pinned v9 contract.

**Decision D1 — the vehicle, RULED (2026-08-03, pre-build): `pyflakes`, imported
in-process, added to `requirements/agent.txt`/`.lock`.** Grounds: acceptance checks
evaluate in the **agent container** (the `frontend_compiles` docstring is explicit —
npm runs against "the agent container's warm cache"), and neither `ruff` nor `pyflakes`
is in `agent.lock` today, so either choice adds a dep. pyflakes is pure-Python with zero
transitive deps and is the reference F821 implementation that ruff's F-rules reimplement;
ruff would add a ~25MB binary wheel to seven agent images to shell out for one rule.
Hand-rolled AST is rejected: F821 scope analysis (comprehension scopes, class bodies,
star imports, conditional definition, `__all__`, builtins) is exactly the wheel pyflakes
already is.
**Corollary — this check must NOT follow the skip-on-missing-tooling precedent.** #462's
skip-never-fail rule, and the SIP-0096 `check_tooling.py` declaration seam
(`check_registry.TOOL_NODE`), exist for tooling with **per-role variance** provisioned
via `agents/instances/<role>/system-packages.txt` — Node lives in the qa image only.
A base-lock pip dep is present in every agent image *by construction*, so it is not
provisioned tooling in the §6.3 sense and gets no `TOOL_` identifier. Therefore an
ImportError on pyflakes is a **build defect, not an environment gap**, and must surface
as `error`, never `skipped` — otherwise #689 ships as a silent no-op, precisely the
"looks-enforced-but-isn't" class SIP-0096 exists to kill.
**Forward-compatibility note (SIP-0102):** checks run in-agent-container today only
because 0102 migration step 3 (routing `test_runner.py` / `CommandExitZeroCheck` /
`probe_runner.py` through typed sandbox ops) is a v1.6 S-lane rider. Write the check as a
registry entry whose execution is a single call site, so step 3 can reroute it without a
rewrite.
**Replay verification:** shk-2's stored `backend/routes.py` v2 (`art_87442fcf46db`)
trips exactly once on `RunEvent`; shk-1's accepted fill files (green cycle
cyc_b03d203df3f2) all pass clean — zero false positives on a known-good set.

### 4. #686 — authoring-rules render (retargeted 1.5 → 1.4.2 by this plan)
The validator family's plan-shape rules rendered as a static managed-asset section in
the four plan-authoring prompts (#448 discipline: prose in fragments, data-only inputs).
Covers at minimum #673's one-file-one-owner + verification-only form, #658's
frozen-claim ban, #671's module-existence rule. Pulled forward because prevention
compounds with every cycle run before 1.5, and it is the same fix class as the 1.4.1
five. (The #629/#627 siblings stay on the 1.5 slate — this pulls one item, not the
family.)
**Verification:** template/asset render check in-container (the 1.4.1 harness pattern);
its live proof is negative — shk-1's dual-claim class should not recur in the deploy
window's confirmation cycle, and if framing authors it anyway, the #669 re-roll receipt
shows whether the rules section was present in the authoring prompt.

## Riders (no dedicated PRs; fold where natural)

- Delete the dead `command_check_safelist` CRP key (declared `schema.py:48`, never read
  — 2026-08-03 audit; separately ruled superseded by typed tools). Rides #689's PR
  (same file neighborhood).
- ~~Close #114~~ — **discharged 2026-08-03** before this patch opened; no longer a rider.

## Deploy window (after all four merge)

1. Rebuild all + explicit runtime-api restart + verify-LOADED behaviorally in-container
   (#688/#691 touch runtime-api; #689 touches agent images and adds the `pyflakes`
   dep per D1 — the LOADED probe must import it *and* trip the check, not just find the
   module; #686 touches agent images: template bumps + new asset).
2. Assert contract v9 / manifest v4 unchanged (no re-seed).
3. **One unfiltered confirmation shakedown** (standard seeded launcher, full, bind
   mode, unscored). What it proves: no false positives from #689/#691 on a clean roll;
   #686's rules section renders in authoring prompts. What it cannot prove: #688 fires
   only if a correction round occurs — its bump evidence is the stored-artifact replay
   above, per the 1.4.1 rule (never credit a green cycle for an unfired fix).
4. Then `version_cli.py bump 1.4.2` + marker sync (pyproject / CLAUDE.md / README ×3 /
   ROADMAP timeline + stats — the guard catches misses) + tag. Anomaly in the
   confirmation roll → bump waits, with the shk-2 precedent: an *explained* anomaly
   attributable outside the patch's scope is the owner's call, not an automatic hold.

## Deliberately out

- **#668** — the hash-moving item (it changes the contract). It carries the seed-roll
  window on its own (contract v10 + re-baseline event), either a dedicated 1.4.3 or
  folded into 1.5, and is still held on the owner's enforce-vs-advisory call. Mixing it
  here would turn a fast correction-chain patch into a re-baselining exercise.
  **Correction (2026-08-03):** an earlier draft of this list paired #668 with #593.
  #593 was closed 2026-07-28 by PR #634 (blank-input rejection made scaffold-owned and
  probe-pinned), five days before this plan was written — the seed-roll window is #668
  alone.
- **#687** (traceback → failure_evidence) — cross-component (sandbox capture + evidence
  assembly + analyzer inputs) → 1.5.
- **#682/#683/#684/#423** (SIP-0096 completion) — 1.5, pre-scorecard critical path.
- **#670** — held on the owner's enforce-vs-advisory ruling.
- **#626/#627** — 1.5 hardening slate.

## Ledger

| Issue | Fix | Surface | Verification |
|---|---|---|---|
| #688 | probe→slot repair targeting | runtime-api (correction_runner) | shk-2 evidence replay |
| #691 | emission write authorization | runtime-api/agents (acceptance path) | shk-2 emission replay |
| #689 | F821 check (D0 acceptance-injected, D1 pyflakes — both ruled) | agents (check registry, images, `agent.lock`) | shk-2 trip + shk-1 clean set |
| #686 | authoring-rules render | agents (prompts/templates) | in-container render + negative live proof |
