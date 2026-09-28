# Post-1.8.2 Roadmap Reconciliation — the campaign's two loops

**Established:** 2026-09-28, during 1.8.2 deploy A′'s diagnostics, on the owner's direction. This
note records that direction, why it was given, and what it changes in 2.0's shape. `docs/ROADMAP.md`'s
v2.0 row cites it. The Campaign SIP's revision, which turns it into design, follows the 1.8.2 set's
close.

## The direction

What the owner wants from 2.0: **a campaign that runs for about ten hours, in which the squad improves the
group_run app across successive cycles** — new features, fixes and refactors — while **frontier models
improve the SquadOps framework** from how those campaigns perform.

The two loops, and who owns each:

| Loop | What evolves | Who evolves it | What it is |
|---|---|---|---|
| **Inner** | the app's scope | the squad — `strat` proposes the next increment, the squad builds it | a SquadOps feature: Campaign |
| **Outer** | the SquadOps framework | frontier models — today the owner with Claude Code sessions; Nostromo's cloud roles as the crew commissions | a process: campaign evidence → triage → fix PR → redeploy → the next campaign |

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

Nostromo's own operating model — `crew-operating-model.md` in the private `nostromo` repository —
holds that archetype for its frontier roles (§44.1, "cross-layer tracing", "recovery-path
semantics"). The Nostromo section numbers below refer to that document.

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
| A **durable, frontier-readable evidence package** and a morning digest | #1710 |
| A **prior-cycle brief** for a repair or retry cycle | #1692 |

**Two of these exist because of the outer loop, and deserve the most care:**
- **The calibration cycle (#1709).** If the squad evolves the app, every campaign faces a different
  app. Campaign-to-campaign performance then mixes the framework change, model variance and harder
  scope, and cannot say whether a framework fix helped. The same group_run PRD, built from scratch on
  each campaign's deploy, is the comparable signal. It is warm-boot's "how good is the squad config?"
  yardstick.
- **The evidence package (#1710).** The outer loop's throughput is how fast a frontier reader gets
  from a campaign to a finding. On 1.8.2 that was hand-reading container logs that die on the next
  rebuild.

## The outer loop — a process, written close to the first campaign

#1711 carries the runbook.

**Its one rule worth stating now is two speeds of verification:**
- a **fast lane** between campaigns — the unit suite, the calibration cycle, a small fixed regression
  pack; the next campaign is the soak;
- **full pre-registered sets** kept for release cuts and headline claims. That discipline caught
  #1699 before it shipped.

**Nostromo's part.** Its cloud roles can triage **during** a campaign, since their models do not load
the Spark. They land fixes only **between** campaigns, when the deploy may move.
- Nostromo's §36 forbids crew local inference beside SquadOps execution on the Spark. So Mother, on a
  local model, cannot orchestrate during a campaign unless she moves to a cloud model.
- The crew authors, at most, a campaign's **objective and backlog**, never the per-cycle scope inside
  a running campaign. Its constitution: the crew "is never a squad".
- The crew is pre-commissioning: its §43 gate is unmet, and its one squad-ops PR is the WP-1 probe,
  #1512. Its "safe first" archetypes (§44.1) fit 1.9's bounded debt, so 1.9 is a natural place to
  commission it.

## What changes on the roadmap

- **v2.0** — Campaign stays the headline. Its inner loop gains #1705–#1710 and #1692, and loses the
  squad's framework self-improvement.
- **v1.9** — unchanged in identity: #1507's completion boundary is 2.0's entry condition. By the 1.8.2
  plan's §3.10, #1697 is its first item unless a 1.8.3 opens, because a campaign's evidence needs
  clean per-round attribution.
- **Nothing moves between releases by this note.**

## What this note does not decide

- The Campaign SIP's design — its revision, after the 1.8.2 set, and its design review.
- Whether `strat`'s proposals need approval before a cycle builds them, or run automatically within
  the allowed scope (#1706, #1708).
- The runbook's details (#1711).
- Nostromo's commissioning order, which is the crew's operating model to settle.
