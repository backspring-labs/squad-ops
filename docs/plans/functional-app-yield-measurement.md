# Functional App Yield — the 1.4 exit measurement

**Status: DRAFT — pre-registration pending owner sign-off.** Once the window
opens, changes to anything in §2–§6 require a recorded amendment *before* the
affected roll launches; silent mid-window changes void the measurement.

## 1. Purpose and lineage

One pre-registered number gates the 1.4 cut: **given a PRD and frozen seeds,
how often does the system deliver a working application end-to-end?**

This replaces the retired 5/5 consecutive-greens design (closed 2026-07-28 at
3/5 banked). That design certified the *machinery* — layered patch acceptance,
retest-decides, framing re-roll, scaffold restore, plan validation, locus
routing, each validated live — and punished every change with a reset, which
was right for certification and wrong for improvement tracking. The question
now is different: *did the fix package (#628/#629/#627/#593) and the
provisioning work raise the yield?* — and that question wants a fixed budget
of rolls where **every roll is a data point and nothing resets**.

**Pre-1.4 reference: 3 greens / 5 implementation-reaching rolls (60%
unfiltered) on deploy 35f1fc51**, under the *old* green definition
(checks + suite + probes; nothing ever built or booted the deliverable).
The numbers below use a stricter definition, so the 60% is historical
context, not an A/B comparand.

## 2. The two numbers

Per roll, two binary outcomes:

- **In-cycle green** — verdict `accepted` AND all 8 contract criteria hold
  passing evidence (the campaign bar, now including `vc-routes-imports` and
  `vc-probe-runs-rejects-blank`). Verified against stored evidence, never the
  roll-up counter (the #597 lesson).
- **Functional** — the *delivered* application, assembled from the final
  accepted fill files over the canonical skeleton, passes a scripted
  **sandbox audit** in the SIP-0102 canonical environment:
  install → frontend build → boot → the contract v7 probe set (create → 201,
  blank-input → 422 envelope). Pin-verified, cap-dropped, workspace-owner
  identity — the same floor the shakedown proved on this host.

**Functional App Yield (FAY) = functional rolls / total rolls.** A roll can be
green-but-not-functional (that gap is the #374/#376 class the sandbox exists
to close — every such case is a finding) and, in principle,
functional-but-not-green (over-strict criteria — also a finding).

The audit is **post-hoc, not in-cycle** — **SIGNED OFF (Jason, 2026-07-28)**:
the fix-package changes are what this window validates, and folding a freshly
integrated sandbox into the execution path would pollute that signal with
first-exposure integration teething. SIP-0102 phases 102.3–102.4 (in-cycle
clean-room verification) are Mac-lane work still in flight, and this
measurement deliberately does not couple to their timeline. A post-integration
re-run of this same pre-registered design is the natural 1.5-era baseline and
isolates the integration's own effect. The sandbox acts
as the independent auditor of each deliverable — its actual purpose — and
when 102.4 lands, in-cycle enforcement supersedes the audit for future
measurements.

## 3. Budget and decision rule

- **N = 6 rolls**, pre-registered. At ~2.5–3 h per roll this is roughly two
  days of elapsed rolling.
- **Pre-declared extension**: if FAY lands in the ambiguous zone (4/6), the
  window extends by exactly 2 rolls (total 8) under identical conditions.
  Declared now so the extension is part of the design, not a post-hoc rescue.
- **1.4 cut bar (proposed, owner confirms):** FAY ≥ 4/6 (or ≥ 6/8 after an
  extension) **and** zero machinery-class defects discovered during the
  window. Every loss must be root-caused to an artifact/provisioning class
  and filed. A machinery defect (framework bug, not app/plan defect) pauses
  the window for an owner decision — fixing it mid-window voids the run.

## 4. Frozen conditions

| Element | Value |
|---|---|
| Deploy | main as of window open (currently `6a8a4883`-era images) — frozen for the window; any deploy ends the window |
| Contract | v7 `art_af9ddc104b03` (content_hash `e8dca2cf…`, 8 criteria) |
| Manifest | v3 `art_c208ed0da314` |
| PRD | `art_bfa4435f4ddd` (group_run canonical) |
| Squad / model | `full` / 27b |
| Budget | 3 h, 5 correction attempts, `framing_max_rerolls=2` |
| Gate policy | **Standard bar only — NO plan-shape filtering.** The campaign's frontend-qa-task rejection policy is retired: #627 makes those tasks winnable, and their outcomes are now measurement signal, not noise |
| Audit environment | `squadops-sandbox-env:fastapi-react-1.4-dev`, environment contract `637514e5…` |

## 5. Per-roll protocol

1. **Launch** (auto after the previous roll's record is written — non-green
   does *not* stop the train; that is the design).
2. **Gate review** (delegated): the standard bar — frozen-check rerun 0, real
   refs, no source-regex, applicability count, no deadlock shape. Approve or
   reject on plan validity only, never on plan *shape*. System-validator
   rejections and re-rolls are recorded, not intervened in.
3. **Implementation to terminal.**
4. **Green verification** against stored evidence: verdict, 8 criteria, zero
   silent skips (#423 discipline).
5. **Sandbox audit** of the delivered app (scripted; see §7): assemble final
   accepted fill files over the skeleton → install → build → boot → probes.
   Record pass/fail with failure detail.
6. **Record** the roll row (§6) in the measurement log; update the master
   state; launch the next roll.

**Infra-void rolls** (excluded and re-run, pre-declared narrowly): the cycle
died from host/infra failure *before an implementation run produced any task
result* — box crash, LLM backend down, queue outage — evidenced in logs.
Anything the pipeline itself did, including framing exhaustion, **counts as a
roll**.

## 6. Recorded per roll

Verdict; per-criterion evidence (8); corrections used and their classes;
framing re-rolls and rejection classes; plan shape (task counts, frontend
qa.test present — measurement (a) continuation); sandbox audit result and
failure detail; wall-clock. Aggregates at close: in-cycle green rate, FAY,
loss-mode census (each loss → existing issue # or new filing), and the
qualitative comparison to the 60% reference with the definition caveat stated.

## 7. Prerequisite work items (before the window opens)

1. **`scripts/dev/audit_delivered_app.py`** — the scripted sandbox audit:
   vault-pull a run's final accepted fill artifacts → seed skeleton + overlay
   via the SIP-0102 workspace store → run install/build/boot/probes via the
   container backend → one-line PASS/FAIL + detail. Reuses the floor-smoke
   pattern; Spark-side; small.
   *Shakedown of the auditor itself*: positive control = a pf-50/51/52 green
   deliverable; negative control = a deliberately broken fill (drop the
   router header — the pf-54 artifact is stored and perfect for this).
2. **Launcher NOTES rewrite** — the campaign-era notes block is stale; the
   window's notes state this doc as the protocol.
3. **Owner sign-offs**: N and the cut bar (§3), the audit-not-in-cycle
   decision (§2), and the standing window authorization (first
   `cycles create` included).

## 8. Relation to the 1.4 release

1.4 ships with Scaffold (M) + Sandbox (S) headlines and the fix package as
hardening. This measurement is the release's evidence section: the FAY number,
the loss-mode census, and the machinery-defect count (which must be zero).
The measurement does not require 102.3–102.6; it requires only what is already
deployed plus the §7 audit script.
