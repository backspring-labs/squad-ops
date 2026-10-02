# Post-1.8.2 Roadmap Reconciliation — the campaign's two loops

**Established:** 2026-09-28, during 1.8.2 deploy A′'s diagnostics, on the owner's direction. This
note records that direction, why it was given, and what it changes in 2.0's shape. `docs/ROADMAP.md`'s
v2.0 row cites it. The Campaign SIP's revision, which turns it into design, follows the 1.8.2 set's
close.

**Revised:** 2026-09-28, the same day, on the owner's further direction. The squad takes the first pass
at what went wrong in a campaign. Frontier triage reads through the `squadops` CLI, never container
logs, and spends frontier models on judgement, not on reading.

**Revised again, 2026-10-01: the Nostromo crew's part.** The owner's IDEA of that day
(`docs/ideas/nostromo-framework-optimization-crew.md`), and the rulings on it, give the crew two jobs:
**supervising every campaign at its checkpoints**, and **triaging the framework between campaigns**.
They also allow crew local inference between squad cycles. The section below is revised to match.
**`sips/accepted/SIP-0109-Campaign-Orchestration.md` and the adopted 2.0 plan
(`docs/plans/2-0-0-plan.md`) govern on any conflict** with this note.

## The direction

What the owner wants from 2.0: **a campaign that runs for about ten hours, in which the squad improves the
group_run app across successive cycles** — new features, fixes and refactors — while **frontier models
improve the SquadOps framework** from how those campaigns perform.

The two loops, and who owns each:

| Loop | What evolves | Who evolves it | What it is |
|---|---|---|---|
| **Inner** | the app's scope | the squad — `strat` proposes the next increment, the squad builds it | a SquadOps feature: Campaign |
| **Outer** | the SquadOps framework | frontier models — today the owner with Claude Code sessions; Nostromo's cloud roles as the crew commissions | a process: campaign evidence → the squad's first pass → frontier triage → fix PR → redeploy → the next campaign |

**The squad does not recommend framework improvements yet.** The owner trusts it with an app's scope,
not with the framework's, and wants faster framework progress by leaning on frontier models. The
Self-Improvement SIP's framework-improvement targets therefore leave 2.0. Its Test Bay idea survives as
the outer loop's measuring instrument. The goal of the squad improving its own framework stands; it is
not scheduled.

This is the warm-boot era's "dual feedback loop" (`docs/ideas/WarmBoot_vs_SDLC.md`), restated: app
cycles answer *"how good is the app we're building?"*; the outer loop answers *"how good is the squad's
framework?"*

## Why

**The evidence of the 1.8.2 line.** Each framework finding needed cross-layer tracing, from a runtime
log line to a file and line in `adapters/`:
- #1699 — a cancel left the runtime's reply wait open for 30 minutes;
- #1697 — a repeated repair id;
- the three instrument gaps of the deploy A pre-registration's §11b–§11d.

Nostromo's own operating model — `crew-operating-model.md` in the `nostromo` repository
(backspring-labs/nostromo) — holds that archetype for its frontier roles (§44.1, "cross-layer
tracing", "recovery-path semantics"). The Nostromo section numbers below refer to that document.

App work is where the squad already delivers: 7–9 of 9 functional yield on the standing workload, and
scoped edits landing — every qa re-take read so far on deploy A′'s redelivery and own-frame
diagnostics was an accepted edit.

## What 2.0's inner loop needs that the Campaign SIP does not yet have

Each is an issue, placed on 2.0, and each goes into the Campaign SIP's revision:

| Need | Issue |
|---|---|
| A cycle that **starts from the previous accepted app** plus a change request. Every cycle is greenfield today; nothing in `sips/` or `src/` does this. SIP-0107 is the edit mechanism | #1705 |
| **`strat` proposes the next increment** within the objective's allowed scope. The continuation decision stays pure: it chooses whether and what kind, never the content | #1706 |
| **Accumulated acceptance** — a cycle is accepted only if earlier increments still pass | #1707 |
| A **gate policy for unattended cycles** — auto within scope, escalation queues, no unbounded wait. The 1.8.2 plan §8 left this to Campaign | #1708 |
| A **fixed calibration cycle** opening every campaign — see below | #1709 |
| A **durable, frontier-readable evidence package** and a morning digest, opening with **the squad's first pass** at what went wrong | #1710 |
| A **prior-cycle brief** for a repair or retry cycle | #1692 |

**Two of these exist because of the outer loop, and deserve the most care:**
- **The calibration cycle (#1709).** If the squad evolves the app, every campaign faces a different
  app. Campaign-to-campaign performance then mixes the framework change, model variance and harder
  scope, and cannot say whether a framework fix helped. The same group_run PRD, built from scratch on
  each campaign's deploy, is the comparable signal. It is warm-boot's "how good is the squad config?"
  yardstick.
- **The evidence package (#1710).** The outer loop's throughput is how fast a frontier reader gets
  from a campaign to a finding. On 1.8.2 that was hand-reading container logs that die on the next
  rebuild. In a campaign, **the squad takes the first pass**: what went wrong, cycle by cycle, each
  claim citing the run, cycle and artifact ids and the log excerpt it rests on. That pass is a lead,
  not a finding — the models that went off the rails wrote it — so the citations are what make it
  checkable. The package is read through the `squadops` CLI. A log line a finding needs and the CLI
  cannot show is a gap in the package, filed as 1.8.2 filed its instrument gaps, not a reason to read
  the container.

## The outer loop — a process, written close to the first campaign

#1711 carries the runbook.

**Its one rule worth stating now is two speeds of verification:**
- a **fast lane** between campaigns — the unit suite, the calibration cycle, a small fixed regression
  pack; the next campaign is the soak;
- **full pre-registered sets** kept for release cuts and headline claims. That discipline caught
  #1699 before it shipped.

**And one rule on where frontier models are spent: on judgement, not on reading.** The frontier reader
starts from the squad's first pass and decides what the squad cannot: whether the diagnosis is right,
and whether the cause is the app (the next cycle's business), the framework (an issue and a fix PR) or
model variance (the calibration cycle's reading says which). It does not scrape logs; the squad and
the evidence package do the reading.

**Nostromo's part** (revised 2026-10-01; SIP-0109 governs). The crew has two jobs:
- **Supervision, at every checkpoint inside a campaign.** The crew rules on each increment proposal at
  its gate: approve, request revision, or reject, with a reason (SIP-0109 §9.2). It holds escalation and
  abort. **It never authors an increment's content.** The strategy role does, and the crew "is never a
  squad". At most it authors a campaign's objective and backlog.
- **Triage, between campaigns.** This is a bounded session, starting from the squad's first pass, with
  Ripley, Parker and Dallas (§44.1). Framework fixes land between campaigns, with the owner's approval,
  while the deploy may move.

**How it reaches SquadOps:**
- **Through the CLI and the API only. Crew accounts on the Spark have no docker access, by design, and
  gain none.** A log line a finding needs, and the CLI cannot show, is a gap in the evidence package.
- **Two scopes, each enforced by the API, not by a prompt:**
  - a **supervisor role** holding campaign controls (gate rulings, pause, abort, the box lease) and
    reads;
  - a **read-only role** (`cycles:read`) for triage, which can read runs, cycles and artifacts, and
    cannot decide a gate, cancel, retry or resume a run, or create a cycle.

  How the roles and the network path are provisioned is a private security design for the owner (the
  2.0 plan's decision 6).
- **Inference on the Spark: crew local inference is allowed between squad cycles and between
  campaigns, never while the squad runs a cycle** (the owner's ruling, 2026-10-01). This is the crew's
  §36 modes, and SquadOps enforces its half with the box lease and the quiet-box check (SIP-0109 §9.3).
  Cloud roles may work at any time.
- The crew is pre-commissioning: its §43 gate is unmet, and its one squad-ops PR is the WP-1 probe,
  #1512. The 2.0 plan commissions it on 2.0's pre-campaign work (its §3.6).

## What changes on the roadmap

- **v2.0** — Campaign stays the headline. Its inner loop gains #1705–#1710 and #1692, and loses the
  squad's framework self-improvement.
- **v1.9** — unchanged in identity: #1507's completion boundary is 2.0's entry condition. By the 1.8.2
  plan's §3.10, #1697 is its first item unless a 1.8.3 opens, because a campaign's evidence needs
  clean per-round attribution.
- **Nothing moves between releases by this note.**

## What this note does not decide

- The Campaign SIP's design. *(Since decided: SIP-0109, accepted 2026-10-01.)*
- Whether `strat`'s proposals need approval before a cycle builds them, or run automatically within
  the allowed scope (#1706, #1708). *(Since decided: every proposal is ruled on at its gate in 2.0, the
  owner's ruling of 2026-10-01.)*
- The runbook's details (#1711).
- Who in the squad writes the first pass, and in what form — including whether `squadops cycles
  assess` is its seed (#1710).
- How the crew's two roles, the supervisor and the read-only one, are provisioned in Keycloak, and the
  network path to them: a private security design (the 2.0 plan's decision 6).
- Nostromo's commissioning order, which is the crew's operating model to settle.
