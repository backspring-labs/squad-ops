---
sip_uid: '17883224960412001'
status: proposed
title: Slot-Scoped Emission
author: SquadOps Architecture
created_at: '2026-09-06T00:00:00Z'
---
# SIP: Slot-Scoped Emission

## Status
Draft (proposed)

## Summary

An agent that changes one region of a file today re-emits the whole file. The unit of
change is a slot; the unit of emission is a file. This SIP proposes closing that gap: the
agent emits the slot body, and the framework composes the file.

## 1. The problem, in one roll

1.7.2 counted roll 1 (`cyc_eafdc918e8b0`, deploy `d95af712`) dispatched a single repair for
a single defect — an import-ordering mistake in `docker/serve.py`. That one repair produced
eleven framework restorations and one silent loss:

```
SIP-0100 fill_slot_integrity: task=repair-run_877ecfc0-00-builder.assemble_repair
  path=backend/routes.py
  restored POST /runs: status_code=201 declared by the scaffold, emitted as absent
  restored POST /runs/{run_id}/join: status_code=200 declared by the scaffold, emitted as absent
  restored POST /runs/{run_id}/leave: status_code=200 declared by the scaffold, emitted as absent
  observed GET /runs: response_model=list[RunSummary] declared by the scaffold, emitted as absent
  observed GET /runs: scaffold-owned handler name 'get_runs' emitted as 'list_runs'
  observed GET /runs/{run_id}: response_model=Run declared by the scaffold, emitted as absent
  observed GET /runs/{run_id}: scaffold-owned handler name 'get_runs_run_id' emitted as 'get_run'
  observed POST /runs: response_model=Run declared by the scaffold, emitted as absent
  observed POST /runs: scaffold-owned handler name 'post_runs' emitted as 'create_run'
  observed POST /runs/{run_id}/join: response_model=Run … emitted as absent
  observed POST /runs/{run_id}/leave: response_model=Run … emitted as absent
```

The agent was asked to fix an import. It rewrote `routes.py` from memory and dropped every
declared status code, every response model, and every scaffold-owned handler name. The
framework restored them, so nothing broke — this time.

The same repair also wrote `docker/serve.py`, a path it was not authorized to touch:

```
scaffold_integrity: violation_code 'unauthorized_slot_emission'
  attempted_path 'docker/serve.py'  disposition 'dropped'
  correction_requested False  siblings_retained 7  expected_sha256 None
```

That file carried the **only fix for the defect the repair existed to address**. It was
dropped, nothing asked for another attempt, and — because the patch had been verified 3 ms
earlier against a set that still contained it — the failing check was superseded and
vanished from the run report while the defect stayed in the delivered file (#1323).

## 2. Why this is structural, not an agent-quality problem

The fill-only constraint exists and is applied two ways, both soft:

- **Instructional.** `repair_handlers._render_fill_only_section()` renders "fill only within
  the markers" into the prompt. It asks.
- **Post-hoc.** `fill_slot_integrity` restores what the agent dropped; `scaffold_integrity`
  drops what it should not have written. It repairs the damage afterwards.

Neither makes the wrong emission impossible. The agent is handed a whole file and asked to
return a whole file, so everything it is *not* changing has to survive a round trip through
a language model's attention. The restoration log above is what that costs on one file, on
one repair, on a roll that was otherwise unremarkable.

This is the shape recorded in `[[feedback-find-the-consumer-first]]` and ruled on for #1312:
each instance gets fixed correctly — restore the signature, drop the file, add a guard —
and nobody asks why the unit of emission is a file when the unit of change is a slot.

## 3. Prior evidence, beyond this roll

`sips/proposed/SIP-LLM-Emission-Contracts.md` (proposed 2026-07-25, rev 2) carries a
reactive-patch ledger whose consequence column is the same three words, three times:

| defect | issue | consequence |
|---|---|---|
| Nested-fence truncation | #430 | **whole files lost** |
| Path-prefix on first body line | #470 | **whole files lost** |
| Bare filename on first line | #502 | **whole files lost** |

Those are parser fixes for a transport that carries whole files. A slot body is smaller,
has no filename line, and does not span fences — the class shrinks rather than being parsed
more cleverly.

Related, from this line:
- **#1323** — a dropped emission verified as a passing patch.
- **#1259 / #1264** — repairs judged against trees that do or do not carry the file.
- **#1289** — variables computed and dropped before the consumer, the same "reproduce it all
  from memory" failure one layer up.

## 4. Proposal

**Emission granularity follows the authorization boundary.** Where the scaffold declares fill
slots for a file, a repair or fill task emits `{path, slot_id, body}` rather than
`{name, content}`. The framework composes the file from the frozen scaffold plus the emitted
slot bodies.

Consequences that fall out rather than needing separate mechanisms:

1. **Declared surface cannot be dropped**, because the agent never emits it. The eleven
   restorations above become structurally impossible instead of repaired after the fact.
2. **An unauthorized path cannot be emitted**, because `slot_id` either resolves or it does
   not. `unauthorized_slot_emission` becomes a parse-time refusal with a reason, not a
   silent drop at storage.
3. **The verified set is the stored set.** #1323's mechanism — verification 3 ms before a
   drop it could not see — has nowhere to live, because there is no whole-file overlay whose
   membership can differ between the two stages.
4. **Emission size falls to the size of the change**, which is where the three "whole files
   lost" parser classes come from.

### Out of scope

- Files with no declared slots (a stack's own new modules) keep whole-file emission. This
  SIP does not propose diffs or patch formats against arbitrary files.
- The prompt-side fill-only section stays; it becomes advisory reinforcement of a structural
  rule rather than the rule itself.

## 5. Open questions

- **Slot granularity per stack.** Stack #1 declares slots per handler body; `nextjs_ts`
  declares them per route module. Whether one grammar covers both, or the blueprint contract
  (SIP-0105, accepted) owns the answer, needs settling before design review.
- **Multi-slot edits.** A repair spanning three slots emits three bodies; whether that is one
  task result or three, and how partial acceptance behaves, is undecided.
- **Migration.** Both stacks scaffold slots today, so the mechanism exists; what is missing
  is the emission contract and the composer. Whether this lands as one change or per-stack is
  a design-review question.
- **Interaction with SIP-LLM-Emission-Contracts.** That SIP types the *response*; this one
  narrows the *payload*. They are complementary and should be sequenced deliberately.

## 6. Why a feature SIP

This changes what an agent emits, so it gates an even minor (1.8) under the parity
convention — not 1.7.3. Filing it now so the evidence is attached while it is fresh; the
1.7.2 record is the strongest case for it that exists.
