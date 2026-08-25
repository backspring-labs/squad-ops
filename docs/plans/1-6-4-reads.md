# 1.6.4 — the two reads

The 1.6.4 plan (`1-6-4-plan.md` §2.1, rev 3) required two reads before any code: what the
repair target list was in the rounds where the repair emitted the wrong file, and which path
rendered the response surface into the developer's brief. Both are done (2026-08-25). The
second one found the root cause of the set's dominant loss mode, and it is not where the plan
was looking.

Everything below is from the frozen deploy the set ran on (`5c6c64f7`, containers still up),
its banked artifacts under `data/artifacts/group_run/`, and its LangFuse traces. Nothing is
inferred from analyzer prose.

---

## Read 1 — the repair target list

**Question.** Roll 1 round 2 and roll 4 rounds 2–3: the lead's decision named the join
handler; the repair emitted the create route. Did the target list exclude the join route?

**Source.** `docker logs squadops-runtime-api | grep correction_repair_target` — 18 lines,
one pair per correction round across rolls 1, 4 and 5, all still present.

**Answer: no.** Every round, in all three rolls:

```
correction_repair_target: package scoping matched nothing for anchors __tests__/runs-api.test.ts,
__tests__/join-leave.test.ts — falling back to same-language implementation source
app/api/runs/route.ts, app/api/runs/[run_id]/route.ts, app/api/runs/[run_id]/join/route.ts,
app/api/runs/[run_id]/leave/route.ts, app/page.tsx, app/runs/new/page.tsx, app/runs/[run_id]/page.tsx
correction_repair_target: ownership veto (#884) — qa-owned … removed from dev-role repair target
```

The #688 language fallback fired **18 of 18 times**. On `nextjs_ts` the anchors are the qa
suite's files (`__tests__/*.test.ts`), which share no package with `app/`, so package scoping
(`_scoped_implementation_surface`, `adapters/cycles/correction_runner.py:118`) can never
match on this stack. The repair target is the entire application, every round.

**What that means for the plan.** The join route was always *in* the list. It was never
distinguished in it — seven files under "the file list is what you MAY emit", the named file
living only in the decision's prose. #1015 part A is therefore *narrow the list to the
verified implicated file*, not *add the missing file*. Rev 3's guess that the list lacked the
join route is withdrawn.

---

## Read 2 — which path rendered the response surface

**Question.** Three of eight developers returned the wrong `participants` element kind at
round 0, with #1029's response surface wired into the develop brief. Did the rendering reach
the task on the roll's real path?

**Code path (verified on the zero-drift tree).** `development.develop`'s
`ContextAssemblyContract` declares `SURFACE_RESPONSE` (`context_assembly.py:141`); the
executor threads `manifest_surface_fragments(contract, interface_manifest)` at
`dispatched_flow_executor.py:2510`; the handler renders it through
`request.development_develop_response_surface_appendix` into the `nextjs_ts` fill-only
appendix (`develop.py:842`, template line 80). The manifest was loaded for all three impl
runs (runtime-api log: `Loaded interface manifest (stack=nextjs_ts, 3 entities) for run
run_6d6b25fea86e`, and likewise `run_ec714c00e171`, `run_996e340ea0f1`).

**Whether the block reached the prompt is not recoverable from stored state.** LangFuse
holds the generation, but observation text is capped at 10,000 characters
(`src/squadops/telemetry/models.py:134`, `MAX_OBSERVABILITY_TEXT_LENGTH`); roll 4's develop
prompt (`prompt_tokens=9673`) is stored as a 1,845-character head, an ellipsis, and a tail
that ends *inside* the FROZEN FILES block, before the response surface would appear.
`run_checkpoints` stores `prior_outputs` and artifact refs, not envelope inputs. Artifact
metadata's prompt-provenance fields are null on every artifact. **An instrumentation gap,
recorded:** the question "what did the developer actually see" cannot be answered for a
prompt over 10k characters, which is every develop prompt on this stack.

**But the stored head answers the real question.** The FROZEN FILES surface in roll 4's
prompt reads:

> `lib/models.ts` — defines `Participant(name: string)`, …, `Run(…, participants: string[],
> participant_count: number)`

and the response floor rendered from the same manifest reads:

> `POST /api/runs/{run_id}/join` returns HTTP 200 with `Run` — … each `participants` element
> carries `name`

The frozen model, labelled *authoritative — import from these, never rewrite them*, declares
the collection as `string[]`. The floor demands objects. The seeded `lib/models.ts` says the
same in all four rolls checked, including a green:

| roll | manifest | frozen `models.ts` |
|---|---|---|
| 1 | `participants: list[Participant]`, `Participant{name, joined_at}` | `interface Participant {…}` **and** `participants: string[]` |
| 2 (green) | same shape, `joinedAt` | same |
| 4 | `Participant{name}` | same |
| 5 | `Participant{name, normalized}` | same |

**Mechanism.** `_ts_type` (`src/squadops/capabilities/stack_nextjs_ts.py:59`) lower-cases the
token, recurses into `list[…]`, and maps anything absent from `_TS_TYPES` to `string`. Entity
references were never a case. The FastAPI expander's `_py_type` (`scaffold.py:1242`) passes
entity names through, so stack #1 is not affected. `_models_source` writes the file;
`frozen_surface_index_lines` reads the written interfaces back into the prompt; the wrong type
arrives twice with the word *authoritative*.

**How the greens passed.** Roll 2's join route declares its own
`Array<{ name: string; joinedAt: string }>` and never imports `Run`. The stubs do not import
the models either, so `next build` never forces the frozen type — it is a teaching signal,
and the developers who trusted it were the ones rejected.

**Filed as #1096.** It moves the generator hash, so it ships with the #1087 / #1079-producer
pair.

---

## What the reads change in the plan

1. **#1096 is the headline.** Deterministic, one function deep, on every `nextjs_ts` roll
   since the stack landed, and checkable at N=1 with no model in the loop: diff the seeded
   `models.ts` against the manifest before the roll starts.
2. **#1015-A is a narrowing**, not an inclusion, and its precondition stands: the analyzer
   has to emit a structured, verified file list before the runner can narrow to it.
3. **The repair-loop items (#1015-A, #998, #1094) stay.** They were real losses; they were
   also all spent repairing a contradiction the scaffold authored.
4. **Record the 10k-character cap** as the reason "what did the developer see" is
   unanswerable from stored state, so the next reader does not spend an hour learning it.

## Method, for the next reads

- Repair target lists: the runtime-api container log, `correction_repair_target`, survives
  as long as the deploy does. Read it before theorising about targeting.
- Prompts: LangFuse `GET /api/public/observations?fromStartTime=…&toStartTime=…`, then
  `GET /api/public/observations/{id}` for `input`. Expect the 10k cap.
- Seeded files: artifacts whose `metadata.producing_task_type` is `scaffold.expand` are the
  frozen tree exactly as the developer received it.
