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
**Open decision D1 (resolve in the fix PR):** implementation vehicle — `ruff --select
F821` requires ruff in the *agent* images (acceptance checks evaluate in handler
context); `pyflakes` is a lighter dep; an AST-based custom check needs no dep but
re-implements scope analysis. Default lean: pyflakes if the dep is acceptable, else
ruff-in-image; hand-rolled AST only as last resort.
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
- Close #114 (bookkeeping — code audit-confirmed landed with tests; no code change).

## Deploy window (after all four merge)

1. Rebuild all + explicit runtime-api restart + verify-LOADED behaviorally in-container
   (#688/#691 touch runtime-api; #689 touches agent images + possibly a new dep;
   #686 touches agent images: template bumps + new asset).
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

- **#668 + #593** — the hash-moving pair (both change the contract). They travel
  together as a deliberate seed-roll window (contract v10 + re-baseline event), either
  a dedicated 1.4.3 or folded into 1.5. Mixing them here would turn a fast
  correction-chain patch into a re-baselining exercise.
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
| #689 | F821 typed check (D1: vehicle) | agents (check registry, images) | shk-2 trip + shk-1 clean set |
| #686 | authoring-rules render | agents (prompts/templates) | in-container render + negative live proof |
