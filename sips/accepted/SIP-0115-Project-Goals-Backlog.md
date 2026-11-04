---
sip_uid: '17933742279101532'
title: Project Goals and Backlog
status: accepted
author: Jason Ladd
created_at: '2026-10-30T00:00:00Z'
sip_number: 115
updated_at: '2026-11-04T01:15:45.660024Z'
---
# SIP-0115: Project Goals and Backlog

**Status:** Accepted (2026-11-03): the owner's rulings on the 2.6 plan, "Let's go with battle-trainer and then your
recommendations on the other decisions", made this SIP 2.6.0's headline (D1) and ruled Q41–Q44 as recommended (§9).
Proposed 2026-10-30.
**Authors:** Jason Ladd (the owner's direction, 2026-10-30); drafted by the Spark lane's supervisor
**Created:** 2026-10-30
**Targets:** 2.6.0's headline, slices 1–5 (`docs/plans/2-6-0-plan.md`, adopted 2026-11-03, D1). Slice 6 is not in 2.6.
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

## Delivery ledger (current as of 2026-11-04)

| part | status | where |
|---|---|---|
| slice 1: the goal-set record, its revisions, the API and the CLI (as built: §10a) | **shipped** | 2.6.0, PR #2899, closes #2884 |
| slice 2: a Campaign on a goal set: `objective.goals`, the proposer's view, the one-item rail, derived status, `stop_when: backlog_done` (with a SIP-0109 amendment, §24cy; as built: §10b) | **shipped** | 2.6.0, PR #2901, closes #2885 |
| `accepted (carried)`: an item accepted in another Campaign, read as accepted here only when its frozen criteria pass on this Campaign's calibration tree (§4) | **unplaced**, deliberately: not built in slice 2 (§10b) | — |
| slice 3: candidates added, promoted or dropped, and a backlog item split, under Q41's rule for the crew (as built: §10c) | **shipped** | 2.6.0, PR #2908, closes #2886 |
| §6's squad and system candidates: a cycle's or a proposal's findings recorded as candidates by the runtime, with no principal of its own | **unplaced**, deliberately: not built in slice 3 (§10c) | — |
| slice 4: the console's goals panel: a panel of the Projects plugin, its edit a confirm-level command (`squadops.revise_goal_set`). §8.3's latest assessment of each expected result is not shown: no assessment record exists until slice 5 (§5.7), and showing it in the panel is that slice's | **shipped** | 2.6.0, PR #2916, closes #2887 |
| slice 5: the crew's surface: the goal set and its derived backlog readable by the supervisor and triage principals, the backlog item and its expected results in each gate's evidence, and the assessment record (§5.7), shown in the console (as built: §10d) | **shipped** | 2.6.0, PR #2927, closes #2888 |
| slice 6: the repository export | **unplaced**, deliberately: not in 2.6 (the plan's D1, ruled 2026-11-03) | — |

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
| reorder the backlog, add or split an item | yes | **split only, by the owner's grant on the Campaign** (Q41, §10c); never reorder | no | no |
| add a candidate | yes | yes | yes, from a cycle or proposal | yes, from a finding it records |
| promote or drop a candidate | yes | **only by the owner's grant on the Campaign** (Q41, §10c) | no | no |
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

**Ruled 2026-11-03, each as recommended** (the owner, ruling the 2.6 plan: "Let's go with battle-trainer and then your
recommendations on the other decisions"; Q41 is the plan's D15). Slices 1 and 3 build to Q41's rule.

| # | question | recommendation |
|---|---|---|
| Q41 | **the crew's authority over the order** (to be ruled before slice 1 is built, the 2.6 plan's D15): may the supervisor identity reorder the backlog, split an item, or promote a candidate without the owner? | **promote and split, yes, within a Campaign the owner started, each recorded with its reason; reorder, no.** **A promoted candidate is appended at the end of the backlog;** putting it anywhere else is a reorder, the owner's. A split's items take the split item's place, which changes no other item's priority. The order is where the owner steers. *The owner's ruling of 2026-11-04 (§10c): "a Campaign the owner started" is built as the owner's grant, recorded on the Campaign* |
| Q42 | **`requirements` beside `goals`:** keep both sources for a Campaign? | **keep both.** The sample applications' Campaigns read PRDs, and their yardstick is built on them. A product Campaign names one or the other |
| Q43 | **where the crew's assessment lives:** a SquadOps record (§5.7), or only the crew's signed closing interpretation in Buzz, as today? | **a SquadOps record,** with the signed statement as its `source_ref`. The owner then reads the goal, the backlog and whether each expected result is met in one place, and a framework finding is linked to the result it blocked |
| Q44 | **one goal set per Project, or several** (one per Campaign theme)? | **one active,** with revisions. Two goal sets on one Project would compete for the same tree |

## 10. Post-acceptance amendments

### 10a. Slice 1 as built (2026-11-03)

**What changed.** §4, §8.1 and §8.2 name the fields and the surfaces. Slice 1 settles what they leave open and
narrows four of them. Decided by the implementer under the supervisor's slice-1 brief (#2884); the owner reviews it in
the slice's PR.
- **A surface is `{kind, ref}`, or `{kind: none, reason}`.** The kinds are `http_endpoint`, `page`, `command`,
  `package_interface` and `none`. `ref` names what is observed there (`POST /api/sessions`, `/week`). A kind with no
  `ref`, or `none` with no reason, is refused. *Narrowed:* §4 names where a result is observed without saying it
  must be named.
- **A backlog item serves at least one expected result,** and each id it names is one in the same revision.
  *Narrowed:* §1 says each item names the results it serves; an item that serves none is refused.
- **Ids are the author's,** of letters, digits, `.`, `_` and `-`, up to 64 characters, and unique in their list.
  Nothing mints or renumbers them. *Narrowed:* **a backlog item and a candidate never share an id.** So slice 3 can
  keep a candidate's id when it is promoted, and nothing the slice derives by id names two things.
- **Unknown fields are refused,** at every level, naming the field: a misspelt list silently dropped would read as an
  emptied one.
- **The write is `POST /api/v1/projects/{id}/goal-set/revisions`.** It carries `expected_revision` (0 for the
  first), `reason`, an optional `source_ref` and an `idempotency_key`, as a Development Configuration's write does
  (SIP-0112 §D.2). A stale revision is `409 STALE_GOAL_SET_REVISION`; a key reused for another body is
  `409 IDEMPOTENCY_KEY_CONFLICT`; an invalid goal set is `422 GOAL_SET_INVALID` naming its field. `GET …/goal-set` is
  the active revision (`404 GOAL_SET_NOT_FOUND` before the first), and `GET …/goal-set/revisions[/{n}]` the history,
  newest first, or one revision.
- **Who may:** reading needs `cycles:read`, as reading a Project does. Writing needs `admin:write`, as writing a
  Development Configuration does. The crew's principals hold `cycles:read`, so they can already read the goal set; the
  derived backlog view they need is slice 2's and slice 5's. They hold no write scope here (§6; delegated reorders and
  promotions are slice 3's, under Q41).
- **Its own store,** beside the Project registry, not in it: the goal set adds nothing to the Project Record (the
  intake check). Migration `2100_project_goal_sets.sql` (SIP-0115's range, `2100–2199`) holds one row per revision,
  the goal set as JSONB beside its scalar columns. It is chosen by the Project registry's selector, and writes only
  under `postgres`: under `postgres_read_only` (SIP-0112 R3) and `config`, a write is `409 PROJECT_REGISTRY_READ_ONLY`.
- **§7's sweep needs no change:** `heldout_sweep.py` dumps every table of the `squadops` database except the suite's
  own store (`OWN_STORE`, `scripts/dev/heldout_sweep.py:81`; `--exclude-table` at `:294`), so
  `project_goal_set_revisions` is searched already.
- **The CLI's `show` prints YAML that `edit -f` takes back,** with the revision's provenance as comments, every line
  of each commented, and a `# base-revision: N` line. **`edit` writes against the revision its file was shown at,**
  never against whatever is active when it runs, so an export submitted after another editor wrote is refused as
  stale. It is not written over theirs, and a retry with the printed key and the same file replays. A file with no
  `# base-revision` line needs `--expected-revision`. *Added on the outside second review of PR #2899 (its P1–P3).*
  `candidates`, `promote` and `drop` (§8.2) are slice 3's.

**Evidence.** `tests/unit/projects/test_goal_set.py` (each refusal by its field), `tests/unit/api/test_goal_set_routes.py`
(the write entered at the route, behind the runtime's auth, and each role's scope),
`tests/integration/cycles/test_postgres_goal_set_registry_integration.py` (revisions, staleness, replay and racing
writers against Postgres).

### 10b. Slice 2 as built (2026-11-03)

**What changed.** §4, §5.1–§5.6 and §8.1 describe a Campaign on a goal set. Slice 2 builds it. Its SIP-0109 side,
the definition, the rail, `goals_revised` and `backlog_done`, is SIP-0109 §24cy. What it settles of this SIP's own
text, and where it narrows it, is recorded here. Decided by the implementer under the supervisor's brief for #2885;
the owner reviews it in the slice's PR.
- **`goal_set` is the Project's id, required and checked** (§5.1, Q44). A Project has one goal set, so the field
  names nothing the Project doesn't. It is kept so that a definition copied to another Project is refused at
  creation, rather than read against that Project's goals.
- **The derived view is the Campaign's, at `GET /api/v1/campaigns/{id}/backlog`** (§8.1 lists it under the goal set's
  routes). Status is per Campaign (§4), so the view belongs to the Campaign. It is read like the ledger it is derived
  beside, with `campaigns:read`, which every role holding `cycles:read` holds too. `squadops campaigns backlog <id>`
  prints it. The view the goal set's console panel shows, one column per Campaign (§4), is slice 4's.
- **Where a status comes from**, in the Campaign's control log and launch outbox:
  - the item a proposal serves and the revision it was created under come from its submission row, written from the
    change request (`backlog_item`, and the derived `goals_revision`);
  - a version not yet ruled reads `proposed`, and an approved one `in_increment`;
  - a promotion of any cycle that carried the version (its repair or retry included) reads `accepted`;
  - a decision or an owner's word that abandoned its increment reads `abandoned`, with the row and reason. So does a
    terminal decision or an abort that left it unaccepted;
  - a rejection or a return leaves the item `pending`: no live proposal names it. So does a rebase that superseded its
    repair or retry (SIP-0109 §24cd point 2's `upstream_moved`), since the squad's work didn't fail, and an owner's
    word that answered an escalation with a fresh proposal rather than an abandonment.
- **The re-queue (§5.3), settled.** An abandoned item is eligible again when a later revision edits the item itself:
  its title, description, `serves` or size. A reorder alone doesn't re-queue it. Without this, "re-queues it by a
  revision" left open which revisions do. An unrelated edit must not re-queue every abandoned item.
- **An item a revision removed** reads `removed` when it was abandoned or never built, with its last abandonment kept.
  It keeps `proposed` or `in_increment` while a proposal or increment for it is live (§5.5), and reads
  `accepted (removed in rN)` once accepted. An item that was never proposed in this Campaign and is gone from the
  revision read isn't listed.
- **`current` is read at each use** and recorded there:
  - each proposal run, a revision run after a return included: the change request's `goals_revision`;
  - each ruling, for `goals_revised`: the `rule` row's reason;
  - each `backlog_done` decision: the decision row's `goals_revision`;
  - each read of the view.
- **`goals_revised` applies to an approval or a rejection, not to the supervisor's own return,** and never to a
  pinned Campaign. Its return spends neither a rejection nor one of the proposal's revisions (SIP-0109 §24cy item 5).
- **A retried ruling replays what its row committed** (added on the outside second review of PR #2901). The ruling's
  row commits before its gate decision records; a retry with the same key replays the row's decision, or its
  `goals_revised` return with its recorded reason, and never reads the goal set again. A retry asking another decision
  conflicts (SIP-0109 §24cy item 5).
- **Eligibility is read against the transition being prepared** (added on the outside second review of PR #2901). The
  owner's word and a rebase's supersession build their proposal before their row is written, so the next eligible item
  is read as that row will leave it: the owner's `propose` returns the escalated increment's item to `pending`, the
  owner's `abandon_and_propose` reads it `abandoned`, and a rebase reads the repair it supersedes as `upstream_moved`
  leaves it (SIP-0109 §24cy item 7). The proposal run, which shows the proposer the backlog, reads only committed rows.
- **Narrowed: `backlog_done` is read just before the decision's row, not in its transaction.** The goal set has its
  own store (§10a), and the row records the revision it read (SIP-0109 §24cy item 6).
- **Narrowed: `backlog_done` stops at row 3, which needs an accepted increment** (SIP-0109 §10). A backlog emptied
  only by removals is not stopped there. A goal-set Campaign with nothing pending escalates instead of proposing,
  stop rule or not (SIP-0109 §24cy item 7).
- **No requirements document.** A goal-set Campaign's proposal is told to leave `prd_delta` out: the backlog item is
  what its request delivers. A `prd_delta` it writes anyway is not refused.
- **Not built: `accepted (carried)`** (§4: an item accepted in another Campaign, read as accepted here only when the
  criterion bundle frozen at its acceptance passes on this Campaign's calibration tree). It needs that calibration
  run and a cross-Campaign read. Neither exists, and slice 2's brief left it out. The ledger lists it as unplaced. Until
  it is built, such an item reads `pending` here, as §4 says it does when unverified, and `backlog_done` reads only
  this Campaign's acceptances.

**Evidence.** `tests/unit/campaigns/test_backlog.py` (each status from the rows that make it, a later revision read
against what the Campaign did, `backlog_done`, `goals_revised`), `tests/unit/api/test_campaign_backlog_route.py` (the
route, pinned and current), `tests/unit/cli/test_commands_campaigns.py` (`campaigns backlog`), and SIP-0109 §24cy's
evidence for the wiring.

### 10c. Slice 3 as built (2026-11-04)

**What changed.** §5.4, §5.5a, §6, §8.1, §8.2 and Q41 describe candidates, splits and who may act. Slice 3 builds
them as four actions on the goal-set resource, each a revision, and settles what they leave open. Decided by the
implementer under the supervisor's slice-3 brief (#2886); the owner reviews it in the slice's PR.
- **An action is a revision that names itself.** `POST …/goal-set/candidates` adds a candidate,
  `…/candidates/{id}/promote` and `…/candidates/{id}/drop` promote or drop one, `…/backlog/{id}/split` splits an
  item. Each carries `expected_revision` (never 0: an action is on a written goal set), `reason`, an optional
  `source_ref` and an `idempotency_key`, as the whole-document write does (§10a), answers 201 with the revision
  written, and is computed against `expected_revision` itself, not the latest, so a retry under its key replays the
  first write rather than being refused as stale. The revision carries a typed, additive **`change`**:
  `{kind: candidate_added | candidate_promoted | candidate_dropped | item_split, subject, position?, split_into?,
  campaign_id?}` (migration `2101_goal_set_revision_change.sql`, a nullable column), absent on every revision written
  before it and on every whole-document edit. So the history, and the derived view, tell an action from an edit.
- **Who may, by scope** (§6; Q41, ruled 2026-11-03). The owner is `admin:write`, as in §10a. **The crew's seat is
  `campaigns:supervise`:** §6 names the crew as the campaign-supervisor principals, and Q41 frames each delegated act
  as within a Campaign. No new scope: the delegation is per Campaign, which no scope can carry, so it is a row on the
  Campaign (below). Triage reads, and nothing else (#1719): `403`.
  The owner and the crew may add a candidate with no Campaign named. **Not built: §6's squad and system
  candidates.** The agent service account holds `agents:write` alone, and the proposer runs inside the runtime's
  executor with no principal of its own, so nothing a cycle does can call these routes. The runtime recording a
  cycle's or a proposal's findings as candidates is a part of its own, unplaced (the ledger); until it is built, what
  a cycle finds reaches the goal set through the crew or the owner.
- **The crew acts only within a Campaign the owner has granted it** (Q41; the owner's ruling of 2026-11-04). The
  request names `campaign_id`. The Campaign must exist (`404 CAMPAIGN_NOT_FOUND`), be on this Project, name this goal
  set (`objective.goals`), **be live** (its state isn't `completed`, the lifecycle's one terminal state, however it
  ended), and **hold the owner's grant.** Otherwise `403 NOT_DELEGATED`, with the reason; with no grant, the reason
  names the command that records one. The Campaign is recorded on the revision (`change.campaign_id`). The owner needs
  no Campaign and no grant, and a Campaign the owner names is checked for the first three, so the record is true. Adding
  a candidate needs neither.
  - **The grant** is `POST /api/v1/campaigns/{id}/goal-delegation` (`squadops campaigns delegate <id> --reason …
    [--source-ref …]`), with `reason`, `idempotency_key`, and optional `source_ref` and `expected_state`. It writes a
    control-log row, `goal_delegation_granted`: who granted it, why, and `binding: {goal_set, source_ref?}`. It moves no
    state and answers 201 with the control result; a retry with its key replays. A Campaign naming no goal set is
    `404 CAMPAIGN_HAS_NO_GOAL_SET`.
  - **Only the owner writes it:** the route needs `campaigns:control`, which only the admin role holds. The
    `campaign-supervisor` role holds `campaigns:manage`, not `campaigns:control`, so it is refused `403 FORBIDDEN` and
    no row is written.
  - **Only an applied row of the Campaign's own log counts.** Who created the Campaign is not read, and neither is any
    binding on another row or any field of a definition. A refused attempt grants nothing.
  - **It lasts the Campaign's life.** There is no revocation. A completed Campaign refuses a grant
    (`409 CONTROL_OPERATION_REFUSED`, `campaign_completed`, recorded), though a record is otherwise the one kind a
    completed Campaign accepts (`ControlOperation.needs_a_live_campaign`; SIP-0109 §24dd). A committed grant still
    replays after the close.
  - **Evidence.** The owner's review of PR #2908 found that the reading first built, a live Campaign on this Project
    reading this goal set, was broader than Q41: nothing read who started a Campaign, and `campaign-supervisor` holds
    `campaigns:manage`, so the crew could create a Campaign and act within it, authorizing itself. `created_by` can't
    settle it either, because the crew's broker creates the Campaigns the owner approves in Buzz, and SquadOps holds no
    record of that approval. **The owner chose the one-step grant over accepting the broader reading,** so the approval
    becomes a row SquadOps can read. A Campaign the crew should curate needs this step, whoever created it (the
    runbook's §1).
- **The crew appends; the owner places.** A promotion takes `position` (from 1; the end by default). The crew's
  `position` anywhere but the end is `403 NOT_DELEGATED`: a reorder is the owner's (Q41). The whole-document write,
  the only way to reorder, stays `admin:write`; a split changes no other item's place.
- **A promotion keeps the candidate's id** (§10a), its title and description, and takes `serves` from the request
  (a candidate names what it found, not what it serves; at least one result of the same revision). The result is
  validated whole again, as a submitted document is.
- **A retry is answered before anything that can have changed since the write** (the owner's review of PR #2908). A
  delegated act that committed, whose response was lost, and whose Campaign then completed, was refused 403 at the
  check above. Each action now reads its key first (`GoalSetRegistryPort.revision_under_key`, the key and the request's
  hash) and replays. The route's scope check still comes first. A new key on that Campaign is refused as before.
- **A split's guard and its write are one step to the Campaigns it reads** (the owner's review of PR #2908). The guard
  read the Campaign logs and the revision was written after, so a proposal submitted between them named an item the
  split removed. `CampaignRegistryPort.transitions_held` now holds the row lock every transition takes first, on each
  live Campaign of the Project, across the guard and the write. A proposal that arrives then lands after the revision,
  and its ruling returns it as `goals_revised` (§5.5a). A Campaign created during the hold isn't held: its calibration
  comes before any proposal. The goal set and the Campaign stay separate stores: this is a lock, not one transaction.
- **A split's shape** (§5.5a). The document holds the result: the parent gone from `backlog`, the parts in its place
  in order; the revision names it: `change: {kind: item_split, subject: <parent>, split_into: [<parts>]}`. *Narrowed:*
  §5.5a's "the item is `removed` with `split_into`" is the derived view's wording, not a field on a backlog item,
  which isn't in the document once split. The view reads the dropping revision's `change`, so a split parent reads
  `removed` with `split_into` and a removal reads `removed` alone; one the Campaign never proposed isn't listed, as
  §10b reads any removed item it never proposed. Two or more parts, each with an id the goal set doesn't hold (never
  the parent's: a part with its id would read as the parent continuing); `serves` defaults to the parent's; `size` as
  given. **The split waits** (`409 BACKLOG_ITEM_IN_PROGRESS`) while any live Campaign on the Project reads the item
  `proposed` or `in_increment`, read with slice 2's view per Campaign; a completed Campaign doesn't hold it.
- **Refusals name what they refuse:** `404 CANDIDATE_NOT_FOUND`, `404 BACKLOG_ITEM_NOT_FOUND`, `403 NOT_DELEGATED`,
  `409 BACKLOG_ITEM_IN_PROGRESS`, and `422 GOAL_SET_INVALID` naming the field (`serves`, `position`, `into`,
  `into[1].serves`, `candidate`). A candidate submitted with no `found_at` is found at the write, and the key's hash is
  over the request, so a retry replays that time rather than minting another.
- **The CLI** (§8.2): `goals candidates <project>`, `goals promote <project> <candidate> --serves ER-1 [--position N]
  --reason …`, `goals drop …`, `goals split <project> <item> --into <yaml|json> --reason …`, each with `--campaign`
  for the crew. An action's `--expected-revision` defaults to the active revision, read just before: unlike `edit`,
  it has no file to carry the revision it was shown at, and the server computes the result against that revision and
  refuses a write another editor got in front of. A refused write prints the key and the revision for the retry.
- **Not in slice 3:** the squad's automatic candidate extraction (above), the console's goals panel (slice 4), the
  crew's assessments (slice 5).

**Evidence (the owner's ruling).** `tests/unit/api/test_goal_delegation_routes.py`, entered at the routes with the
real authorization adapter: the supervisor creates a Campaign, is refused its promotion and its own grant (403, no row
applied), the owner grants, and the promotion lands naming the Campaign; each role; a replay, also after the close; a
completed Campaign, another Project's, an unknown one, a requirements one. `tests/unit/campaigns/test_goal_delegation.py`:
the row through the registry, and neither a refused grant nor another row's binding standing in.
`tests/integration/cycles/test_postgres_campaign_registry_integration.py`: migration 2102 on Postgres. Mutants, each on
a commit: the route on `campaigns:manage`; the crew's check removed; the owner made to need a grant; the reader taking a
refused row, or another row's binding; a completed Campaign taking a grant; the Project unchecked; a crew act naming no
Campaign let through; a promotion's Campaign check moved before its replay; the CHECK list lacking the value (on a
fresh database, where the migration runs). Each failed a test.

**Evidence (the review's fixes).** `tests/unit/projects/test_goal_set_actions.py`: a retry replays after its Campaign
completed, for each of promote, drop and split, and a new key is refused; a proposal arriving during a split lands after
its revision. `tests/integration/cycles/`: on Postgres, a held Project blocks a transition on another connection and
not its reads, and the key read answers only this request. Mutants, each on a commit: the hold removed from the split;
the memory transition ignoring the hold; the replay removed from each action; `FOR UPDATE` removed; the key read
ignoring the hash. Each failed a test.

**Evidence.** `tests/unit/projects/test_goal_set_actions.py` (each action and refusal by its field; Q41's rule; the
split's wait per Campaign history; replay and staleness), `tests/unit/campaigns/test_backlog.py` (a split parent
`removed` with its parts, the parts `pending` in its place), `tests/unit/api/test_goal_set_routes.py` (the
permission matrix per action; the crew's promotion and the owner's split entered at the route behind the runtime's
auth, asserting what reaches the store; the crew's 403 on the whole-document write),
`tests/unit/api/test_campaign_backlog_route.py` (`split_into` in the view's body), `tests/unit/cli/test_commands_goals.py`
and `tests/integration/cycles/test_postgres_goal_set_registry_integration.py` (`change` round-trips).

### 10d. Slice 5 as built (2026-11-04)

**What changed.** §3, §5.7, §6, §8.3 and §8.5 describe the crew's surface. Slice 5 builds it and settles what they
leave open. Its SIP-0109 side, the ledger's rows, is SIP-0109 §24df. Decided by the implementer under the supervisor's
brief for #2888; the owner reviews it in the slice's PR.
- **The reads needed no scope change.** `campaign-supervisor` and `campaign-triage` both hold `cycles:read` and
  `campaigns:read`, which is what the goal set's routes and `GET /api/v1/campaigns/{id}/backlog` need. The wiring test
  reads each through the real authorization adapter.
- **A gate's evidence is the ledger** (§8.5). What the crew's reviewer reads at a gate is the Campaign's
  `GET /api/v1/campaigns/{id}/ledger`, whose rows its packet carries whole, so the row is extended and no new read is
  added. Each row of a goal-set Campaign names `backlog_item` and `goals_revision`. The row an open gate can be on, its
  item `proposed` (the increment gate) or `in_increment` (the plan gate), also carries `goal_evidence`:
  `{goal, item: {id, title, description, serves, size?}, expected_results: [{id, statement, surface}]}`, in the goal
  set's own document shape.
  - **Read at the revision the proposal is bound to** (§5.5a), never a later one.
  - **Narrowed: not on a decided row.** Such a row keeps its item's id. A reviewer's request is bounded, and on
    2026-11-01 a request over its bound parked a Campaign, so the goal isn't repeated on each increment already judged.
  - **A requirements Campaign's rows are exactly as they were.** The three fields are left out when unset, not sent as
    nulls, and its ledger reads no goal set.
- **An assessment has its own store on the goal set's seam** (§5.7, Q43). `GoalSetRegistryPort` gains
  `record_assessment` and `list_assessments`; migration `2103_goal_set_assessments.sql` holds one row per assessment,
  with `sequence` counted per goal set, and §5.7's rules as CHECKs. It writes no goal-set revision and adds nothing to
  the Project Record. It writes only under `postgres`, as a revision does (`409 PROJECT_REGISTRY_READ_ONLY`). §7's
  sweep needs no change, for §10a's reason.
- **No grant** (§6). Recording one is a report, not curation: Q41's grant is about the order, which an assessment never
  touches. Who may is `admin:write` (the owner) or `campaigns:supervise` (the crew's seat); triage reads, and nothing
  else (`403`). A completed Campaign takes one, since the closing interpretation comes after the close.
- **The write is `POST /api/v1/projects/{id}/goal-set/assessments`,** answering 201 with
  `{assessment, idempotency_key, replayed}`. It carries `idempotency_key`, `campaign_id`, `expected_result`,
  `goals_revision`, `reading`, `cause`, `issue`, `evidence`, `reason`, `source_ref` and `supersedes`.
  - **`cause` is required with `not_met` and refused otherwise.** *Narrowed:* §5.7's "shortfall" is read as `not_met`,
    so an `unclear` takes no cause.
  - **`issue` is the squad-ops issue's number,** required with `framework_defect` or `framework_gap` and refused with
    any other cause. The console builds the link.
  - **`evidence` is `{cycles: [id], rulings: [id], evaluations: [{id, passed, failed}]}`,** with at least one id. Unknown
    keys, and an id with a space in it, are refused, so a step or a value has nowhere to go (§7). *Not checked:* that a
    cited id exists. It is a citation, and an assessment decides nothing.
  - **`reason` is required** (§6: each action records its reason).
  - **`source_ref` is required of the crew** (Q43; §8.5) **and optional for the owner** (§6: "where it came from a
    conversation").
  - **`goals_revision`** is a revision the goal set holds, and `expected_result` one that revision holds.
  - **`supersedes`** names the `sequence` of earlier assessments of the same result in the same Campaign.
  - **Refusals:** `422 GOAL_SET_INVALID` naming the field, as slice 3's do. An unknown Campaign, or another Project's, is
    `404 CAMPAIGN_NOT_FOUND`, a requirements Campaign `404 CAMPAIGN_HAS_NO_GOAL_SET`, and a key reused for another body
    `409 IDEMPOTENCY_KEY_CONFLICT`. A retry replays through the store: unlike slice 3's actions, nothing it checks can
    have changed since the write.
- **The reads are two.** `GET /api/v1/projects/{id}/goal-set/assessments` (`cycles:read`) is the history, in sequence,
  paged, with `campaign_id` and `expected_result` filters. `GET /api/v1/campaigns/{id}/assessments` (`campaigns:read`)
  is how each result stands: `{campaign_id, project_id, revision, results: [{expected_result, standing, assessments}]}`,
  one per expected result of the revision the Campaign reads now, derived and never stored. It is the Campaign's for
  §10b's reason: what makes one stale is this Campaign's acceptances. A result a later revision removed drops out.
- **`standing`** is `current`, `stale`, `conflicting` or `unassessed`. `assessments` holds the latest alone, or, while
  they conflict, each that disagrees, newest first.
  - **Disagree** is read as a different `reading` or `cause`: the cause is whose work it is.
  - **Stale is judged on the latest.** A latest that is stale reads `stale`, whatever older ones say, so a stale
    assessment never reads current and never conflicts with the one that replaced it.
  - **`log_seq`** is the Campaign's last control-log row at the write, compared only within that Campaign (§5.7).
    *Narrowed:* it is when the assessment was written, not when the crew read. An acceptance between the two reads as
    before the assessment.
  - **"Changed"** is the result's statement or surface differing between the revision the assessment read and the one
    the Campaign reads now, so a reorder stales nothing.
- **The console** (§8.3). `squadops.campaigns` replaces its named placeholder with this view, and the goals panel shows
  each expected result's standing, reading, cause and issue for the chosen Campaign. What a standing says lives once, in
  `console/continuum-plugins/shared/assessments.js`.
- **Not built: a CLI for assessments.** §8.2 names none. The crew is an API client, and the owner reads them in the
  console.

**Evidence.** `tests/unit/api/test_crew_surface_routes.py`, entered at the routes with the crew's real roles through the
real authorization adapter: the goal set and backlog read back, the gate's row carries the item and results, a
candidate added and promoted under the grant, an assessment written by the supervisor and read back by triage; each
refusal by its field; the plan gate; the bound revision; a requirements row's exact fields; a retry after the close.
`tests/unit/projects/test_goal_set_assessments.py` (each standing), `tests/unit/campaigns/test_backlog.py`
(`acceptances`), `tests/integration/cycles/test_postgres_goal_set_assessments_integration.py` (the round trip,
sequence per goal set, racing writers, replay, the write gate, each CHECK and foreign key, on Postgres),
`console/continuum-plugins/squadops.campaigns/ui/src/campaigns.test.js` and
`console/continuum-plugins/squadops.projects/ui/src/goals.test.js`. Thirty-eight mutants, each on a commit, each failed
a test. One survived at first, the Campaign's view reading the goal set's whole history, and gained its test.
