# Roadmap — Runtime Maturity → 2.0 (Capability-Backed Agents)

**Status:** Draft / sequencing proposal (feeds `docs/ROADMAP.md` once ratified)
**Date:** 2026-07-01
**Owner:** Backspring Labs / SquadOps
**Related:** SIP-0089 (Runtime State), SIP-0090 (Embodiment), SIP-0091 (Duty Durability), SIP-0095 (Cycle-Create Preflight), SIP-Capability-Backed-Agents (proposed 2.0 umbrella), SIP-0086/0079 (build convergence / correction), even/odd convention (#281)

---

## 1. Thesis

> **1.x matures the execution substrate. 2.0 matures agent expertise.**

Each 1.x layer creates a platform the next relies on; 2.0 then makes agents capability-backed specialists *on top of a substrate that already observes, schedules, verifies, and governs them* (the governing principle: don't grant autonomy the runtime can't yet govern).

- **1.x — execution maturity:** reliable cycles, runtime posture, durable duty, cross-cycle continuance.
- **2.0 — expertise maturity:** capability packs, working sets, scoped memory, skill-mediated tool use, evidence.

## 2. Reconciled release sequence (even/odd)

The conceptual order below is unchanged from the original roadmap; only the **version labels** are reconciled onto the even/odd convention (#281): **even minors carry features (gated by a headline SIP); odd minors are stabilization, feature-free.** Even-minor *slots* are ordered, not calendar-pinned — substance gates each cut.

| Version | Parity | Theme | Headline work | Macbook (build path) | Spark (confirmation gate) |
|---|---|---|---|---|---|
| **1.1.x** | — | Runtime/cycle hardening | *shipped* (SIP-0089) | — | — |
| **1.2** | even · feature | Embodiment + runtime completion | SIP-0090 P1, SIP-0095 Preflight, #231, #233/#244 | Preflight, terminology consolidation, embodiment P1 schema, 0089 completion | E2E duty/embodiment on the 27b squad |
| **1.3** | odd · stabilization | Structural refactors (feature-free) | #186, #152, #234 | #186, #152 | #234 + hardening/regression sweep |
| **1.4** | even · feature | Duty durability | **SIP-0091** *(moved off its stale v1.3 tag — see §6)* | DutyLog + Temporal wiring + recall/window mechanics | long-horizon duty-shift *work quality* over real time |
| **1.6** | even · feature | Campaigns (cross-cycle) | **Campaign** + **Campaign Policy** (mechanic only — see §4) | run-N-cycles-to-objective, per-cycle result eval, squad-from-roster | "does each cycle measurably advance the objective" |
| **2.0** | major | Capability-backed agents | **SIP-Capability-Backed-Agents** (umbrella) | pack/skill/tool substrate, working sets, evidence, config wiring, Design reference pack | Iris/Glyph *deliverable quality* + real-tool full-squad confirmation |

Odd minors (1.5, …) interleave as stabilization between the even feature cuts.

## 3. Lane model — activity, not feature

The Spark/Macbook split is by **development activity**, not by feature:

> **Macbook owns the entire build path** — SIP design, domain models/schemas, capability-pack & plugin design, manifests, binding contracts, registry + DI/config wiring, permission/evidence plumbing, and mechanic-level tests with fakes / `lite` (7b) / `smoke` (3b).
>
> **Spark is a confirmation gate at the end of each lane**, invoked only for what genuinely needs real conditions: (a) 27b builder-squad **output quality**, (b) **long-horizon / real-time** multi-agent behavior, (c) **durability** under a real full-squad run.

Consequences:
- **Tool use does not need Spark.** Its mechanics/governance (skill→tool adapters, `forbidden_skills`/approval gates, evidence ledger, authorized-skill-surface assembly) are deterministic → Macbook with fakes. Agent tool *selection* is fine on `lite` (7b) — lighter models **pressure-test the guardrails**, which is a feature, not a compromise. Only capability-pack **deliverable quality** → Spark.
- **Capability-pack plugin design + config wiring is Macbook** end-to-end; Spark enters only for durability/quality confirmation.
- Feature *substance* is lane-pinned to Macbook (gates even minors); Spark is the primary hardening source and owns odd-minor structural refactors it authors (e.g. #234).
- ~90% of every release is Macbook; **Spark is used only where it is the sole tool that can answer the question.** That is the correct reading of "maximize Spark for full-squad testing."

## 4. Campaign — a goal-directed set of cycles

A **Campaign** is a directed series of cycles toward an **ultimate objective**. Kicking off a campaign fixes the objective; the campaign then runs *N* cycles, evaluating each cycle's **measurable result** against the objective and deciding whether to run another, stop (objective met or unreachable), or adjust — including how the squad is assembled for the next cycle. It inserts the missing level between Project and Cycle:

```
Project → Campaign → Cycle → Run → Task
```

- **Objective** — the target the campaign converges on.
- **Cycle** — one operation that delivers a measurable result toward the objective.
- **Campaign Policy** — the controller that reads each cycle's measurable result and decides continue / stop / adjust / (2.0+) augment. Sibling to the existing `TaskFlowPolicy`.

Campaign fits the existing SquadOps metaphor family (Squad / Duty / Ops) — the militaristic register is already present, so the term is consonant, not new baggage. (Confirm no `campaign` symbol collision in-repo when the SIP is drafted, as we did for "skill".)

**Two layers, two eras** — this is what keeps Campaign from sliding into 2.0:
- **Mechanic (late 1.x, ~1.6):** run N cycles to an objective, evaluate each cycle's measurable result, decide continue/stop, and assemble each cycle's squad *from the existing roster/profiles*. Agent-agnostic; **produces the campaign-level evidence 2.0 consumes.**
- **Intelligence (2.0+):** capability-gap-driven **dynamic squad augmentation** — when a cycle's result exposes a *missing capability*, the campaign composes a new capability pack into the next cycle's squad. Requires capability packs → 2.0.

So the answer to "late 1.x or post-2.0?" is **both**: lock the Campaign mechanic in late 1.x; capability-driven augmentation is inherently 2.0+.

**Naming / positioning (normative for the SIP):** avoids the taken terms — "loop" (SIP-0086 "Build Convergence Loop"), "continue/continuance" (a SIP-0079 correction path), "convergence" (SIP-0086). Campaign is *cross-cycle* and sits **above** the intra-run SIP-0086 and SIP-0079 (correction protocol); **Campaign Policy** is a **sibling to `TaskFlowPolicy`** (SIP-0064, run-level), not a field of it. It reads measurable results from the existing verification/acceptance substrate (SIP-0070) — which is *why* the mechanic is execution maturity (late 1.x), not agent expertise (2.0).

**Boundary vs the existing loops (validated against code 2026-07-01).** Three *distinct* scopes — do not conflate them:
- **SIP-0079 / SIP-0086** refine *within one run* (correction paths, one self-eval pass).
- **SIP-0083** refines *within one cycle* — the `framing → implementation → evaluation → refinement → wrapup` workload sequence, **same plan, same squad**.
- **Campaign** spawns a *fresh cycle* (new plan, possibly different/augmented squad) when in-cycle refinement can't restructure the approach or add a missing capability.

So Campaign's real value is the **objective aggregate + the automated re-cycle decision** — **not** squad-change (per-cycle squads already exist via the immutable `Cycle.squad_profile_snapshot_ref`) and **not** iteration (SIP-0083 already refines intra-cycle). It **reuses cycle recruitment unchanged** — per-run `ambient→cycle` FocusLease via the shared single-writer coordinator (#233, *landed* 2026-07-01), released per run. Only holding an agent *across* cycles would need new lease semantics — avoid it; **re-recruit per cycle** (which is also what lets the squad differ per cycle). Campaign adds **no new RuntimeMode, `owner_type`, Assignment type, or RuntimeActivity kind**, and its decision fires on the **cycle-completion event**, never a background watch (or it drifts into a duty/ambient-like loop).

**Positioning / lineage (carry into the Campaign SIP).** Campaign is SquadOps' **governed expression of the agentic goal-loop — "loop engineering":** engineer the *outer loop / harness* (goal-targeting + incremental, verification-gated builds), not the prompt or the model. It deliberately keeps the loop **bounded, observable, and evidence-gated** rather than unbounded self-directed autonomy — per the §9 governing principle (*don't grant autonomy the runtime can't observe, schedule, verify, and govern*). The two eras map onto the "autonomic" spectrum: the **1.x mechanic** is a governed continuance loop (evidence-driven continue/stop, squad from existing profiles); the **2.0** form becomes genuinely *autonomic* — a **self-recomposing multi-agent goal loop** that adds a missing capability pack to keep pursuing the objective, a step *beyond* the single-agent iterate-until-done loops the pattern usually demonstrates. The word "loop" stays a *description of the discipline*, not the object name (SIP-0086 owns "loop"); the object is **Campaign**.

## 5. Skill / tool reconciliation (feeds the 2.0 umbrella SIP)

The 2.0 skill-mediated-tool-use model must **extend what already ships, not reintroduce it**:

- SquadOps **already has a Capability → Skill → Tool system** (SIP-0040): `Skill` ABC, `SkillRegistry` (with `get_skills_by_capability` + evidence enforcement), `ExecutionEvidence`, per-role skill packages. ~70% of the "skill layer" exists.
- **The genuinely missing work is real tool-wrapping.** Existing skills are internal work units; almost none wrap real external tools. So 2.0's skill work is *"give the existing skill layer real tool adapters + governance (forbidden/approval/budget/evidence-surface),"* not "invent skills." That is a smaller, sharper SIP.
- **Relationship inversion to resolve:** existing `Skill.required_capabilities` (skill → requires → capabilities) vs the proposed `capability.required_skills` (capability → requires → skills). Pick one and reconcile with shipped code.
- **Claude Skills — spike complete (2026-07-01): adopt the *format*, supply our own dispatch.** Agent Skills are now an open standard (agentskills.io, Dec 2025) already adopted by **Ollama-based local agents** and 20+ platforms — `SKILL.md` (YAML `name`/`description` + optional `allowed-tools`/`arguments`) + markdown playbook + bundled resources, three-level progressive disclosure. The verdict splits cleanly: **the format is portable; the auto-invocation runtime is Claude-specific** (and Skills lack execution-context binding, lineage, config inheritance, and model-agnostic dispatch — so they can't *be* the capability model). **Decision:** adopt the `SKILL.md` format for content packaging inside capability packs; SquadOps supplies its own dispatch and keeps the capability/skill layer as the core (routing, context binding, lineage/evidence, versioning). Model-independence preserved — the format already runs under Ollama. **Name collision resolved:** Skill = SquadOps execution unit (SIP-0040); SKILL.md bundles = **skill packs / playbooks** inside a pack.

## 6. Cleanups this reconciliation surfaces

- **SIP-0091 `Targets: v1.3` is stale** — it is a *feature* SIP pinned to a *stabilization* (odd) minor, which the convention forbids. Move to **1.4**. (Separate one-line header fix, not bundled with the 2.0 docs.)
- **`docs/ROADMAP.md` stats block still reads "Framework version: 1.0.6"** while its own timeline shows 1.1.1 current — the exact drift the release plan warned about. Fix when ROADMAP.md is next touched.

## 7. Concept boundary table

| Concept | Release area | Owns | Does not own |
|---|---|---|---|
| RuntimeMode | 1.1/1.2 | Current posture: duty/cycle/ambient | Future assignment, capability, continuance policy |
| Assignment | 1.1–1.4 | Commitment / responsibility | Current focus or capability definition |
| Duty (durable) | 1.4 | Persistent service responsibility, durable across shifts | Cross-cycle continuance policy |
| Cycle | 1.x | Bounded formal work | Long-running duty / autonomy |
| Run | 1.x | Execution attempt | Goal continuance policy |
| Build Convergence / Correction | shipped (0086/0079) | *Intra-run* validation, self-eval, correction paths | Cross-cycle continuance |
| Campaign | late 1.x (mechanic) / 2.0+ (augmentation) | Objective + ordered cycles + per-cycle measurable results + continue/stop/adjust decisions | Runtime mode, duty, agent identity, intra-run correction |
| Capability | 2.0 | Domain-level ability | Agent identity, raw tool authority |
| Skill (SIP-0040) | shipped, extended in 2.0 | Governed, evidence-producing execution unit | Domain-level outcome |
| Tool | 2.0 | Instrument/API/service via ports/adapters | Intent or policy |
| Working Set | 2.0 | Prepared execution context | Durable memory authority |
| Memory | 2.0 | Scoped learned context | Canonical resource authority |
| Capability Pack Plugin | 2.0 | Distributable governance wrapper (contracts, evidence) | Named agent identities |

## 8. Immediate next moves

1. Finish 1.2 (committed: SIP-0095, #231, #233/#244, embodiment P1) — Macbook builds, Spark confirms.
2. Fix SIP-0091's version tag (v1.3 → 1.4) as a standalone note.
3. Land the 2.0 umbrella SIP (`SIP-Capability-Backed-Agents`) as a *design commitment*, splitting into implementation SIPs later.
4. Claude Skills spike — **done** (2026-07-01): adopt the `SKILL.md` format for content packaging, SquadOps supplies its own dispatch (§5).
5. Draft the **Campaign** SIP when the 1.6 slot opens — mechanic only (run cycles to an objective, evaluate measurable results, squad-from-roster); capability-driven squad augmentation deferred to 2.0+.

## 9. Governing principle

> **Do not give agents more autonomy before the runtime can observe, schedule, verify, and govern them.** Harden execution → mature runtime & duty → add cross-cycle continuance → then make agents capability-backed, memory-aware, and tool-governed.
