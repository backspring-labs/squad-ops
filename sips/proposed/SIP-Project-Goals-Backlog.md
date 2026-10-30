---
sip_uid: '17933742279101532'
title: Project Goals and Backlog
status: proposed
author: Jason Ladd
created_at: '2026-10-30T00:00:00Z'
---

# SIP: Project Goals and Backlog

**Status:** Proposed (2026-10-30), for design review
**Authors:** Jason Ladd (the owner's direction, 2026-10-30); drafted by the Spark lane's supervisor
**Created:** 2026-10-30
**Targets:** proposed as 2.6.0's headline by the 2.6 plan's draft (`docs/plans/2-6-0-plan.md`, PR #2832). Not
placed until the owner adopts that plan and accepts this SIP.
**Builds on:** SIP-0112 (Project Lifecycle Management: the Project Record), SIP-0109 (Campaign Orchestration: the
objective and its requirements source), SIP-0113 (Outcome Evaluation: the held-out suite), SIP-0069 (the console's
Continuum plugins)

> **Intake check (2026-10-30, against `sips/PORTFOLIO.md`).** No conflict found. Overlaps, each with its boundary:
> - **SIP-0112's Project Record and Development Configuration** (cluster 14). SIP-0112 owns the Project's identity,
>   lifecycle, and how it is built and run. This SIP owns what the Project is meant to achieve, as a record beside
>   them, keyed by the Project's id. It adds nothing to the Project Record itself.
> - **SIP-0109's objective** (cluster 1). SIP-0109 owns the decision table, the objective's envelope and every limit.
>   This SIP is a source the objective can name, beside `objective.requirements` (§24bv point 5, the 2.5 plan's D10).
>   The rails and rows it touches change by a numbered SIP-0109 amendment in the PR that builds them (its Delivery ledger).
> - **SIP-0110's project instructions** (Q31: no second instruction store). An instruction says how the squad
>   works on a Project. A goal says what the Project should come to do. Neither is stored in the other.
> - **SIP-0113's held-out suite** (clusters 3 and 5). The suite stays the independent judge and stays unread by the
>   squad. A goal set never holds a scenario's steps or values (§7).
> - **The word *outcome*** (cluster 2). SIP-0113 uses *outcome* for its independent scenarios. So the owner's
>   "expected outcomes" are named **expected results** here, and the word *outcome* is not used for them.
> - **The ROADMAP's 2.6 row, "the squad-authored backlog".** This SIP is the owner-ordered half. The squad records
>   what it finds as candidates (§5.4); the strategy role ordering its own features is not in it.
> - **The Game Development Platform draft** (PR #2405, its Q37 on that branch). Its `GAME_DESIGN.md` requirement in
>   every game repository would become a goal set here, held as SquadOps metadata, as Q37's recommendation already
>   reads.
> - **The Design Decision Register** (proposed, cluster 13). It records design decisions inside a cycle. This SIP
>   records goals and their order across a Campaign. They don't share a record.
> - **The Continuum Runtime Console** (proposed, partly absorbed). The goals panel here is a SIP-0069 plugin. The
>   duty view that SIP keeps is unrelated.

---

## 1. Summary

A Project gets a **goal set**: a versioned record of what it should come to do, held in SquadOps's database beside
its Project Record. A goal set holds:
- **the goal:** one statement;
- **expected results:** what the owner will accept as the goal met, each one observable;
- **constraints** and **out of scope;**
- **the backlog:** ordered items, each sized for one increment and naming the expected results it serves;
- **candidates:** what the squad or the crew found along the way, which nobody has ordered yet.

A Campaign names a goal set. Each proposal takes the next pending backlog item and names it. Each item's status is
**derived** from the Campaign's control log, never typed in. The owner edits the goal set in the console or through
the CLI, and each edit is a new revision.

**The rule that keeps the tools apart:** a goal is discussed wherever people talk (Buzz), and decided in SquadOps.
A conversation is never the record.

## 2. Motivation

**The owner, 2026-10-30:** "I'm trying to envision the right persistence tool for these goals and expected
outcomes. Would it be best in continuum persisted in db records of the project definition. Then the buzz tool is the
collab and convo on achieving those goals. I want to consider MECE in how to manage these requirements and use the
best tool for the job and get away from a claude terminal to build apps and games." (Spelling corrected.)

**What 2.5 showed** (`docs/plans/2-6-0-plan.md` §1):
- **A Campaign's goals are one flat document.** `objective.requirements` is a stored artifact or a
  `repo:file:…@current` reference. Nothing records which part of it is done, so each proposal re-derives "what's
  next" from the whole text. 2.5's `z_continuum` squad proposed the same non-discriminating criterion three times.
- **The measurement has one machine reading,** `target_accepted_increments` (SIP-0109 §24ah). The objective's
  `measurement` line is free text with no reader.
- **The goals are edited in a terminal.** Every 2.5 requirements file was written into this repository and ingested
  by the CLI.
- **The crew already decides in Buzz.** Nostromo's Campaigns record their definitions as `buzz-approved:<name>`
  with a hash (`examples/03_group_run/campaigns/provenance.yaml`, 2026-10-24 and 2026-10-25). The approval
  happened, but the approved definition lives only in the conversation, and SquadOps holds its digest. That is the
  pattern this SIP replaces for goals.

## 3. Where each concern lives

| concern | system of record | who writes it | who reads it |
|---|---|---|---|
| **intent:** the goal, expected results, constraints, the backlog's order | **the goal set** (this SIP), in SquadOps's database | the owner; the crew where §6 allows | the squad, the crew, the console |
| **progress:** each item's status and why | **derived** from the Campaign's control log | nobody, by hand | everyone |
| **proof:** test results, evaluations, held-out verdicts | the vault and the evaluation records (SIP-0113) | the system | the crew and the owner; the squad never reads held-out content |
| **deliberation:** questions, options, discussion | Buzz | anyone | anyone |
| **decisions:** rulings, approvals, goal-set revisions | SquadOps's database, written by an action | whoever §6 authorizes | everyone |
| **code:** the product and its review requests | the product's Git repository | the squad, through the Campaign | the owner |

**One authority each.** A goal kept both in a repository file and in a record would drift. So the record is the
authority, and a repository file, if wanted, is a generated, read-only export (§8.4), never an input.

## 4. The goal set

A goal set belongs to one Project. A Project has at most one active goal set. Its fields, by revision:

| field | what it holds |
|---|---|
| `goal` | one statement of what the Project should come to do |
| `expected_results[]` | `id`, `statement`, and `surface`: where it can be observed (an HTTP endpoint, a page, a command, a package interface, or `none` with a reason) |
| `constraints[]`, `out_of_scope[]` | plain statements, shown to every proposal |
| `backlog[]` | `id`, `title`, `description`, `serves` (expected-result ids), its position in the order, and an optional size note |
| `candidates[]` | `id`, `title`, `description`, `found_by` (a cycle, a proposal or a person), `found_at`, and the evidence it cites |

**Revisions.** A revision is immutable. Any edit, a reorder included, writes the next revision with its author and
reason, as a Development Configuration revision does (SIP-0112). Ids are stable across revisions, so an item keeps
its history when it moves.

**Status is derived, never stored on the item.** Read from the control log of every Campaign that named the goal set:

| status | when |
|---|---|
| `pending` | no live proposal names it |
| `proposed` | a proposal names it, not yet ruled |
| `in_increment` | an approved proposal names it, and its increment is running or being repaired |
| `accepted` | an increment naming it was accepted (with the Campaign, increment and tree) |
| `abandoned` | its last proposal or increment was abandoned (with the row and reason); it returns to `pending` on a new proposal |
| `removed` | a later revision dropped it |

This follows 2.5's rule for increments: no writable table, a view derived from the control log (#2578 part 4).

## 5. A Campaign on a goal set

### 5.1 Naming it

`objective.goals: { goal_set: <id>, revision: <N> | current }`. A Campaign names `goals` or `requirements`, never
both, and creation refuses one that names neither on a repository-backed Project (SIP-0109 §24bv point 5's rule,
extended). **Require, don't default:** no fallback from one to the other.

### 5.2 What the proposer sees

Each proposal is shown the goal, the expected results, the constraints and out of scope, and the backlog with each
item's derived status and the reason for any abandonment. That sits beside §24bu's proposals never approved, which
stays as it is.

### 5.3 What a proposal must do

- **Name one backlog item,** pending or abandoned. Its criteria serve that item's expected results.
- **One item per increment.** An item too large for one increment is returned for a split. The split is a new
  revision, made by whoever §6 allows.
- A proposal that names no item, or one that is `accepted` or `removed`, is returned with that reason before a cycle
  is spent (a new rail, by SIP-0109 amendment).

### 5.4 What the squad and the crew find

A cycle, a proposal or a crew member may add a **candidate**: a follow-up, a defect, a gap. A candidate is never
added to the order on its own. The crew or the owner, as §6 allows, promotes it into the backlog at a position, or
drops it with a reason. Either is a new revision.

### 5.5 A revision while a Campaign runs

`revision: current` reads the latest revision at each launch and records which one it read, as an instruction
binding reads `@current` (SIP-0110). A revision that removes the item an increment is building doesn't stop that
increment. Its acceptance is recorded against the item as it stood, and the next proposal reads the new revision.
`revision: <N>` pins one revision for the Campaign's life.

### 5.6 When the goal is met

SIP-0109's row 3 reads `objective_met`. With a goal set, the Campaign may declare `stop_when: backlog_done`: every
item, in the revision the launch read, is `accepted` or `removed`. `target_accepted_increments` stays available and
is read as today. **Whether the expected results actually hold** is SIP-0113's reading, not this SIP's: an accepted
item is the squad's tests passing, and the held-out suite is the independent judge.

## 6. Who may do what

| action | the owner | the crew (the supervisor identity) | the squad (the strategy role) | the system |
|---|---|---|---|---|
| write the goal, expected results, constraints, out of scope | yes | no | no | no |
| reorder the backlog, add or split an item | yes | **only if the owner delegates it** (Q41) | no | no |
| add a candidate | yes | yes | yes, from a cycle or proposal | yes, from a finding it records |
| promote or drop a candidate | yes | **only if delegated** (Q41) | no | no |
| write an item's status | no | no | no | derived only |

Each action records its author, its reason and, where it came from a conversation, the conversation's link
(`source_ref`).

## 7. The held-out boundary

- **Expected results are public to the squad.** They say what the owner wants, in the owner's words.
- **The held-out suite is not.** A scenario may name the expected-result id it reads. That mapping lives in the
  suite's store, never in the goal set, and the squad can't read it.
- **No scenario step, value or goal text is copied into a goal set.** The leak sweep (`heldout_sweep.py`) gains the
  goal-set store as a root.

## 8. Surfaces

### 8.1 API

Under `/api/v1/projects/{project_id}/goal-set` (the authenticated lane, `docs/architecture/api-route-lanes.md`):
read a revision, write the next revision, list revisions, add a candidate, and read the derived backlog view. A
create answers 201, and every body is the standard envelope.

### 8.2 CLI

`squadops goals show|edit|history|candidates|promote|drop <project>`. `edit` takes a file and writes the next
revision, so a terminal is never required, and still works.

### 8.3 The console

A goals panel, a Continuum plugin (SIP-0069): the goal and expected results, the backlog with each item's derived
status and its increments, the candidates waiting, and the revision history. Editing writes a revision through the
API, as every console action does.

### 8.4 A repository export (optional)

A generated, read-only rendering of a revision, written to the product's repository only when the owner asks, and
marked as generated. Nothing reads it back.

### 8.5 Buzz

Buzz carries the conversation. A decision taken there reaches SquadOps as an **action**: an API call by an identity
§6 authorizes, with the thread's link as its `source_ref`. A notice goes to Buzz when a Campaign stops, a candidate
is waiting, or an item is accepted, each with its console link. **The bridge's mechanics** (the `buzz-acp` shim
discussed in `docs/ideas/IDEA-Reselling-Squad-Back-Office.md`, and how Nostromo's `buzz-approved` flow calls the API)
**are not designed here** (Q43).

## Delivery ledger (current as of 2026-10-30)

| part | status | where |
|---|---|---|
| slice 1: the goal-set record, its revisions, the API and the CLI | **unplaced**, deliberately: proposed for 2.6.0 by the plan's draft, PR #2832 | — |
| slice 2: a Campaign on a goal set: `objective.goals`, the proposer's view, the one-item rail, derived status, `stop_when: backlog_done` (with a SIP-0109 amendment) | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 3: candidates, their promotion and drop | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 4: the console's goals panel | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 5: Buzz notices and decisions as actions with a `source_ref` | **unplaced**, deliberately: proposed for 2.6.0 as deferrable, after Q43 | — |
| slice 6: the repository export | **unplaced**, deliberately: not proposed for 2.6 | — |

**What closes this SIP:** slices 1–4 shipped and read live on a Campaign whose backlog reached three accepted items;
slices 5 and 6 shipped or dropped by a numbered amendment.

## 9. Open questions for the owner

| # | question | recommendation |
|---|---|---|
| Q41 | **the crew's authority over the order:** may the supervisor identity reorder the backlog, split an item, or promote a candidate without the owner? | **promote and split, yes, within a Campaign the owner started, each recorded with its reason; reorder, no.** The order is where the owner steers |
| Q42 | **`requirements` beside `goals`:** keep both sources for a Campaign? | **keep both.** The sample applications' Campaigns read PRDs, and their yardstick is built on them. A product Campaign names one or the other |
| Q43 | **Buzz:** which decisions may be taken in Buzz, by which identity, and through what bridge? | **notices first** (slice 5's half that writes nothing), then decisions once the overnight identity (the 2.6 plan's D7) exists, so a Buzz action carries an identity SquadOps already knows |
| Q44 | **one goal set per Project, or several** (one per Campaign theme)? | **one active,** with revisions. Two goal sets on one Project would compete for the same tree |
