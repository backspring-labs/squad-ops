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
| Implementation run | `run_29b53b6e3d4b` — RUNNING |
| Verdict | — |
| Executed / passed | — |
| criteria_total / verified / unverified | — |
| Probe count (non-gating) | — |
| Scaffold slots (non-gating) | — |
| Correction rounds | — |
| Fills first-attempt / slots | — |
| Any fill asserts on store (non-gating, #980) | — |
| Fill body size / store slots (non-gating) | — |
| Boot audit (separate fact) | — |
| Manual interventions | none so far |
| §5.1 validity | — |
| Score | — |

Contract artifact: `art_746df747bf41` (`verification_contract.yaml`, framing run).

## Rolls 2–6

Pending.

## Mid-window detections (recorded, left unfixed per §6)

None yet.

## Night-shift log (2026-08-18/19 ET)

- 21:10 ET — night shift armed: cycle-level watcher, mechanical scorer, this record. Routine:
  on each roll terminal → pull §4 fields → boot audit → score → triage (issues filed; fixes
  stacked on branches as unmerged PRs) → lease check → launch next roll on the identical §3
  recipe. Gate policy: §7.3(c) pinned text verbatim on any gate that opens; auto-approvals
  recorded as-is. A reset-class detection (new harness-attributable mechanical failure) HALTS
  the night shift — abort-and-re-register is an owner decision (§6), not a night-shift one.
