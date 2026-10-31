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

## Intake check

Checked 2026-10-30 against `sips/PORTFOLIO.md`. **Conflicts:** none found. **Overlaps,** each with its boundary (cluster 16; Q41–Q44 in the portfolio's queue):
- **SIP-0112's Project Record and Development Configuration** (cluster 14). SIP-0112 owns the Project's identity,
  lifecycle, and how it is built and run. This SIP owns what the Project is meant to achieve, as a record beside
  them, keyed by the Project's id. It adds nothing to the Project Record itself.
- **SIP-0109's objective** (cluster 1). SIP-0109 owns the decision table, the objective's envelope and every limit.
  This SIP is a source the objective can name, beside `objective.requirements` (§24bv point 5, the 2.5 plan's D10).
  The rails and rows it touches change by a numbered SIP-0109 amendment in the PR that builds them (its Delivery ledger).
- **SIP-0110's project instructions** (Q31: no second instruction store). An instruction says how the squad
  works on a Project. A goal says what the Project should come to do. Neither is stored in the other.
- **SIP-0113's held-out suite** (clusters 3 and 5). The suite stays the independent judge and stays unread by the
  squad. A goal set never holds a scenario's steps or values (§7).
- **The word *outcome*** (cluster 2). SIP-0113 uses *outcome* for its independent scenarios. So the owner's
  "expected outcomes" are named **expected results** here, and the word *outcome* is not used for them.
- **The ROADMAP's 2.6 row, "the squad-authored backlog".** This SIP is the owner-ordered half. The squad records
  what it finds as candidates (§5.4); the strategy role ordering its own features is not in it.
- **The Game Development Platform draft** (PR #2405, its Q37 on that branch). Its `GAME_DESIGN.md` requirement in
  every game repository would become a goal set here, held as SquadOps metadata, as Q37's recommendation already
  reads.
- **The Nostromo crew's campaign harness** (external, `backspring-labs/nostromo`, its campaign execution harness document;
  SIP-0109's outer loop, cluster 6). The crew already runs Campaigns from Buzz: the owner approves a definition there,
  signed; a broker holds SquadOps's scoped service principals (`campaign-supervisor`, `campaign-triage`, never
  `admin`); one crew role rules the gates and another reviews that ruling; a watcher posts the factual record.
  **Boundary:** the crew is an API client of this SIP, like the console. SquadOps holds the goal set, the derived
  status and the crew's recorded assessments (§5.7); Buzz holds the owner's conversation with the crew and its signed
  statements; the crew's own harness (which commands its broker allows, what a gate's review packet carries) is
  Nostromo's to change, in its repository. This SIP names no Nostromo internals: "the crew" is any external
  supervisor holding those principals.
- **Not an embodiment** (SIP-0090, cluster 8). No SquadOps agent appears in Buzz; the squad never talks to the crew
  there. *This draft's same-day revision read slice 5 as an embodiment surface and deferred it to 3.x. That was wrong:
  the owner's Buzz conversation is with the crew, which is an API client (the owner, 2026-10-30, §2).*
- **The crew's own backlog of framework work** (Nostromo's work items, which its README places in squad-ops issues).
  That is the framework's backlog. A goal set is a product's. A shortfall the crew traces to the framework becomes a
  squad-ops issue, linked from the assessment (§5.7), never a goal-set item.
- **The Design Decision Register** (proposed, cluster 13). It records design decisions inside a cycle. This SIP
  records goals and their order across a Campaign. They don't share a record.
- **The Continuum Runtime Console** (proposed, partly absorbed). The goals panel here is a SIP-0069 plugin. The
  duty view that SIP keeps is unrelated.

## Delivery ledger (current as of 2026-10-30)

| part | status | where |
|---|---|---|
| slice 1: the goal-set record, its revisions, the API and the CLI | **unplaced**, deliberately: proposed for 2.6.0 by the plan's draft, PR #2832 | — |
| slice 2: a Campaign on a goal set: `objective.goals`, the proposer's view, the one-item rail, derived status, `stop_when: backlog_done` (with a SIP-0109 amendment) | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 3: candidates, their promotion and drop | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 4: the console's goals panel | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 5: the crew's surface: the goal set and its derived backlog readable by the supervisor and triage principals, the backlog item and its expected results in each gate's evidence, and the assessment record (§5.7) | **unplaced**, deliberately: proposed for 2.6.0 | — |
| slice 6: the repository export | **unplaced**, deliberately: not proposed for 2.6 | — |

**What closes this SIP:** slices 1–5 shipped and read live on a Campaign whose backlog reached three accepted items,
with at least one assessment recorded by the crew; slice 6 shipped or dropped by a numbered amendment.


---

## 1. Summary

A Project gets a **goal set**: a versioned record of what it should come to do, held in SquadOps's database beside
its Project Record. A goal set holds:
- **the goal:** one statement;
- **expected results:** what the owner will accept as the goal met, each one observable;
- **constraints** and **out of scope;**
- **the backlog:** ordered items, each sized for one increment and naming the expected results it serves;
- **candidates:** what the squad or the crew found along the way, which nobody has ordered yet;
- **assessments:** the crew's judgement of each expected result, and whose work a shortfall is.

A Campaign names a goal set. Each proposal takes the next pending backlog item and names it. Each item's status is
**derived** from the Campaign's control log, never typed in. The owner edits the goal set in the console or through
the CLI, and each edit is a new revision.

**The crew assesses.** An external supervisor (today the Nostromo crew) drives the Campaign, judges whether the
expected results are being met, and says why when they aren't: the squad's next increment, a framework defect, a
framework gap, or a goal that needs the owner. Its assessment is a record on the goal set (§5.7).

**The rule that keeps the tools apart:** the owner and the crew talk in Buzz; what they decide is written to SquadOps
through the API. A conversation is never the record.

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
- **The crew already runs Campaigns from Buzz,** and its assessment has nowhere to live in SquadOps.
  - Nostromo's broker launches owner-approved definitions, one crew role rules each gate, and a second reviews that
    ruling. The watcher posts the factual closing record, and the ruling role adds a signed closing interpretation
    (Nostromo's campaign execution harness document). SquadOps records the definitions only by digest, as
    `buzz-approved:<name>` (`examples/03_group_run/campaigns/provenance.yaml`, 2026-10-24 and 2026-10-25).
  - **The crew already tells the app's work from the framework's.** On 2026-10-26 (`cmp_29048a00fdb3460c0675529a`)
    the calibration plan was for the project's general PRD, not the approved increment, and the framing still read
    `GO`. The ruling role returned `needs_owner`, and the finding reached squad-ops as a comment on #2619.
  - That judgement lives only in Buzz and a comment. Nothing in SquadOps records which expected result it was about,
    or what it concluded.
- **The owner's model** (2026-10-30): "By buzz convo, what I meant was interacting with the Nostromo crew driving the
  campaign execution and outcome assessment. They can determine if outcomes are being met or if squad ops framework
  bugs or functional gaps need to be covered to advance the app building work. Not an embodiment of squad ops agents
  in buzz." (Spelling corrected.)

## 3. Where each concern lives

| concern | system of record | who writes it | who reads it |
|---|---|---|---|
| **intent:** the goal, expected results, constraints, the backlog's order | **the goal set** (this SIP), in SquadOps's database | the owner; the crew where §6 allows | the squad, the crew, the console |
| **progress:** each item's status and why | **derived** from the Campaign's control log | nobody, by hand | everyone |
| **proof:** test results, evaluations, held-out verdicts | the vault and the evaluation records (SIP-0113) | the system | the crew and the owner; the squad never reads held-out content |
| **assessment:** is each expected result being met, and if not, whose work is the shortfall | **assessment records on the goal set** (§5.7) | the crew | the owner, the crew, the console |
| **framework work:** a defect or gap the crew traces to SquadOps | squad-ops issues (GitHub) | the crew | the crew, the owner |
| **deliberation:** questions, options, the owner's direction | Buzz, between the owner and the crew | the owner, the crew | the owner, the crew |
| **decisions:** rulings, approvals, goal-set revisions | SquadOps's database, written through the API | whoever §6 authorizes | everyone |
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

**Status is derived per Campaign, never stored on the item** (revised on the outside review, 2026-10-30). Each
Campaign has its own campaign branch, so an item accepted in Campaign A says nothing about Campaign B's tree. An
item's status in a Campaign is read from that Campaign's control log alone. The goal-set view shows each Campaign's
column.

**Carried forward, only when verified.** When a Campaign starts on a tree that holds earlier accepted work (an earlier
campaign branch merged upstream and reconciled into the Project's baseline), an item accepted elsewhere reads
`accepted (carried)` only if the criterion bundle frozen at its acceptance passes on this Campaign's calibration tree,
run with the calibration record. Otherwise it is `pending` here.

The statuses, per Campaign:

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

- **Name the next eligible item:** the first item in the backlog's order whose status in this Campaign is `pending`.
  An `abandoned` item is skipped until the owner, or the crew if delegated, re-queues it by a revision, so one stuck
  item can't hold the Campaign. Its criteria serve that item's expected results.
- **One item per increment.** An item too large for one increment is returned for a split. The split is a new
  revision, made by whoever §6 allows.
- A proposal that names no item, or any item but the next eligible one, is returned with that reason before a cycle
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

### 5.5a Splits and revisions while a Campaign runs (the outside review, 2026-10-30)

- **A proposal is bound to the revision it was created under,** recorded with it. **At its ruling,** if a later
  revision exists and the named item is no longer the next eligible one, or its expected results changed, the
  proposal is returned as `goals_revised`. That is a return with its reason, not a rejection, and it doesn't count
  toward `max_rejected_proposals_in_row`. An approved proposal keeps its revision.
- **An increment is bound to the revision its approved proposal carries.** The control log records that revision with the
  proposal. A later revision never changes what a running increment is building or how it is judged.
- **Splitting an item** writes a revision where the item is `removed` with `split_into: [ids]`, and the new items
  take its position, inherit its `serves` and start `pending`. **An item that is `proposed` or `in_increment` can't
  be split;** the split waits until that increment ends.
- **An item accepted under an earlier revision stays accepted.** The view shows the revision it was accepted under.
  If a later revision drops it, it reads `accepted (removed in rN)`. If a later revision changes the expected results
  it serves, it reads `accepted (results changed in rN)`, and only a new item or an assessment (§5.7) reopens that
  question.
- **A reorder** changes only which pending item the next proposal takes.
- **An abandoned item whose revision dropped it** reads `removed`, with its last abandonment kept in its history.
- **`stop_when: backlog_done`** is decided at each continuation decision, never mid-increment. The decision reads the
  goal set's current revision in the same transaction as the decision, records which revision it read, and stops
  only if every item in that revision is `accepted` or `accepted (carried)` in this Campaign, or `removed`. So work
  the owner added during an increment is seen at the next decision.

### 5.6 When the goal is met

SIP-0109's row 3 reads `objective_met`. With a goal set, the Campaign may declare `stop_when: backlog_done`: every
item, in the revision the launch read, is `accepted` or `removed`. `target_accepted_increments` stays available and
is read as today. **Whether the expected results actually hold** is SIP-0113's reading, not this SIP's: an accepted
item is the squad's tests passing, and the held-out suite is the independent judge.

### 5.7 The crew's assessment

An **assessment** is the crew's judgement of one expected result at a point in a Campaign:
- `reading`: `met`, `not_met` or `unclear`;
- for a shortfall, `cause`: `app_work` (the squad's next increment can reach it), `framework_defect` or
  `framework_gap` (SquadOps itself stands in the way, with the squad-ops issue it filed), or `needs_owner` (the goal,
  an expected result or the order needs the owner);
- `evidence`: the cycles, evaluations and gate rulings it read, by id. Held-out results are cited by evaluation id and
  counts, never by a step or value (§7);
- its author, the goal-set revision it read, and its `source_ref` (the signed statement or thread it came from).

**Stale and conflicting assessments** (the outside review, 2026-10-30):
- **Assessments have their own order.** Each gets an append sequence on the goal set, and may name the assessment it
  `supersedes`. Its Campaign and control-log position are kept as evidence only, since log positions are per
  Campaign and can't be compared across Campaigns.
- **The latest assessment** of an expected result, in a Campaign, is the highest append sequence not superseded.
- **An assessment reads `stale`** when, after it, an increment serving that expected result was accepted, or a
  revision changed that expected result. The console shows it as stale, never as current.
- **Two current assessments that disagree** (neither supersedes the other, both after the last acceptance serving
  that result) both read `conflicting`, with their authors. Nothing resolves them automatically. A new assessment
  naming both in `supersedes` ends the conflict.
- **An assessment of an expected result a later revision removed** is kept in history and drops out of the
  current view.

An assessment is append-only and **decides nothing.** It doesn't change an item's status, a Campaign's decision table
or a gate. The crew acts on it through the controls it already holds (pause, a ruling, a candidate, an issue), and
the owner reads the latest per expected result in the console beside the backlog.

## 6. Who may do what

| action | the owner | the crew (the `campaign-supervisor` principals) | the squad (the strategy role) | the system |
|---|---|---|---|---|
| write the goal, expected results, constraints, out of scope | yes | no | no | no |
| reorder the backlog, add or split an item | yes | **only if the owner delegates it** (Q41) | no | no |
| add a candidate | yes | yes | yes, from a cycle or proposal | yes, from a finding it records |
| promote or drop a candidate | yes | **only if delegated** (Q41) | no | no |
| record an assessment (§5.7) | yes | yes | no | no |
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
status and its increments, the latest assessment of each expected result (§5.7) with its cause and the issue it
links, the candidates waiting, and the revision history. Editing writes a revision through the
API, as every console action does.

### 8.4 A repository export (optional)

A generated, read-only rendering of a revision, written to the product's repository only when the owner asks, and
marked as generated. Nothing reads it back.

### 8.5 The crew (slice 5)

SquadOps builds nothing for Buzz. The crew is an API client, and slice 5 is what it needs from SquadOps:
- **read:** the goal set and the derived backlog, for the supervisor and triage principals;
- **gate evidence:** each plan and increment gate's evidence names the backlog item and carries its expected
  results, so a reviewer outside SquadOps judges the increment against the goal, not only against its own criteria.
  The 2026-10-26 finding above is the case it serves;
- **write:** candidates and assessments (§5.7), each with a `source_ref`.

What the crew does with them, in Buzz and in its harness, is the crew's.

## 9. Open questions for the owner

| # | question | recommendation |
|---|---|---|
| Q41 | **the crew's authority over the order** (to be ruled before slice 1 is built, the 2.6 plan's D15): may the supervisor identity reorder the backlog, split an item, or promote a candidate without the owner? | **promote and split, yes, within a Campaign the owner started, each recorded with its reason; reorder, no.** **A promoted candidate is appended at the end of the backlog;** putting it anywhere else is a reorder, the owner's. A split's items take the split item's place, which changes no other item's priority. The order is where the owner steers |
| Q42 | **`requirements` beside `goals`:** keep both sources for a Campaign? | **keep both.** The sample applications' Campaigns read PRDs, and their yardstick is built on them. A product Campaign names one or the other |
| Q43 | **where the crew's assessment lives:** a SquadOps record (§5.7), or only the crew's signed closing interpretation in Buzz, as today? | **a SquadOps record,** with the signed statement as its `source_ref`. The owner then reads the goal, the backlog and whether each expected result is met in one place, and a framework finding is linked to the result it blocked |
| Q44 | **one goal set per Project, or several** (one per Campaign theme)? | **one active,** with revisions. Two goal sets on one Project would compete for the same tree |
