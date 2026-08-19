# V7 FAY Window — Record

**Pre-registration:** `1-6-0-v7-fay-window-preregistration.md` (frozen; §6 prohibits changing it
mid-window, so the per-roll record accumulates here). **Deploy:** `4fa74525`, images per §3.
**N=6, bar ≥4/6 functional.** A roll scores functional iff verdict `accepted` AND
`audit_delivered_app.py` passes (incl. UI data-path) AND zero manual intervention (§7.3).
Validity per §5.1: void / reset / counted. Mechanical result and boot audit are recorded as
distinct facts, never collapsed (SIP-0104 §13a).

This file lives on a branch for the duration of the window (no merges to main, §6). Times UTC
in tables; the closing claim will restate in ET.

---

## Roll 1 — cyc_8b569ce34074

| Field | Value |
|---|---|
| Launched | 2026-08-18 23:48 UTC |
| Framing run | `run_c86f7911fe8c` — completed, 64 min, 11 artifacts |
| Gate | `progress_plan_review` → approved, `system:no_open_questions` (§7.3 rule 2 — zero manual touches) |
| Implementation run | `run_29b53b6e3d4b` — **failed** 02:37 UTC (1h45m), "Rewinding to checkpoint after development.develop failure" |
| Verdict | `blocked_unverified` |
| Executed / passed | 12 / 11 |
| criteria_total / verified | 14 / 2; failed: `acceptance:frontend_compiles`; required unmet: frontend_build, required_files, tests_pass |
| Probe count (non-gating) | 5 (contract `6357b2cbf288`) |
| Correction rounds | 1 completed repair (accepted), then develop re-dispatch failed 3 emissions → 1800s task timeout |
| Fills / assertion strength | n/a — `qa.test` never dispatched |
| Boot audit (separate fact, run as triage) | **PASS** — the stored tree (acceptance-aware assembly) installs, builds, boots, answers all 5 probes, UI data-path clean |
| Manual interventions | none (gate auto-approved) |
| §5.1 validity | **VOID** — never reached `qa.test`; neither counts nor resets; re-launched |
| Score | not scored (void) |

Contract artifact: `art_746df747bf41`. **The void roll's delivered application works** — the cycle
possessed an accepted, working repair at 01:38 UTC and failed anyway (#994). Failure chain,
verified against neo logs (the banked analysis is wrong — #995): real defect in `app/page.tsx`
(server-component prerender fetch, #996) → correct accepted repair (`force-dynamic`) → rewind
re-dispatched develop for the same subtask → three re-authored variants each failed
`frontend_compiles` → task timeout at 1800s → run failed.

## Launch 2 — cyc_18931c371a55

| Field | Value |
|---|---|
| Launched | 2026-08-19 03:0x UTC, notes record roll-1 void |
| Framing run | `run_e2d85438f3fe` — in flight |
| Config hash | matches §3 pin |

## Rolls thereafter

Pending. Counted-roll tally: 0 of 6 (roll 1 void).

## Mid-window detections (recorded, left unfixed per §6)

| # | Detection | Source |
|---|---|---|
| #994 | Rewind after a successful repair re-dispatches develop, discarding the repaired state — cycle rejected a working deliverable | roll 1 (void) |
| #995 | Task timeout mid self-eval banked as "zero response chars", erasing 2 substantive rounds; analysis names a disproven mechanism | roll 1 (void) |
| #996 | Authoring surfaces teach the api() client seam but not the server-component prerender constraint | roll 1 (void) |

## Night-shift log (2026-08-18/19 ET)

- 21:10 ET — night shift armed: cycle-level watcher, mechanical scorer, this record. Routine:
  on each roll terminal → pull §4 fields → boot audit → score → triage (issues filed; fixes
  stacked on branches as unmerged PRs) → lease check → launch next roll on the identical §3
  recipe. Gate policy: §7.3(c) pinned text verbatim on any gate that opens; auto-approvals
  recorded as-is. A reset-class detection (new harness-attributable mechanical failure) HALTS
  the night shift — abort-and-re-register is an owner decision (§6), not a night-shift one.
