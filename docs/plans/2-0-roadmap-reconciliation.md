# 2.0 Roadmap Reconciliation — Campaign, Loop Policy, and Capability-Backed Agents

**Established:** 2026-07-04 · reconciles the two 2.0 planning artifacts added 2026-07-01/02
against the even/odd versioning convention (#281) and the standing 2.0 memory.

This note exists so the analysis from the roadmap-review session is durable. It does
**not** ratify anything into `docs/ROADMAP.md` — it records the intended shape so the
next person (or agent) touching the 2.0 SIPs starts from a reconciled picture instead
of three overlapping drafts.

## Inputs being reconciled

| Artifact | Added | Role |
|---|---|---|
| `sips/proposed/SIP-Capability-Backed-Agents.md` | 2026-07-01 | 2.0 umbrella — *what an agent is* |
| `sips/proposed/SIP-Continuum-Runtime-Console.md` | 2026-07-01 | console runtime-state awareness |
| `docs/ideas/SquadOps-Roadmap-Runtime-Loop-Capability-Backed-Agents.md` | 2026-07-01 | sequencing note; proposes a "Loop Policy" SIP |
| `sips/proposed/SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md` | 2026-07-02 | Campaign + Self-Improvement + Test Bay |

## Finding 1 — "Loop Policy" (Jul 1) and "Campaign" (Jul 2) are the same layer; Campaign wins

The roadmap idea proposes naming the cross-cycle continuance layer **Loop Policy**
(`continue | repair | retry | fork | escalate | stop | summarize | defer`) and explicitly
*not* calling it Campaign. One day later the Campaign SIP proposes **Campaign** and explicitly
*not* calling it Loop ("Loop risks overloading Cycle semantics… the better abstraction is
Campaign"). They describe the **same** cross-cycle continuance layer — the idea's decision set
(§7.7) is exactly the Campaign SIP's continuation decision (§15.5), only better specified.

**Resolution:** the Jul-2 SIP is the successor to the Jul-1 idea's open naming question, and it
matches the standing memory decision ("Campaign… avoid the taken names loop/convergence/continue").
- **Do not write a separate Loop-Policy SIP.**
- Fold the idea's crisp decision vocabulary *into* Campaign's continuation-policy section
  (best architecture from the SIP + best-specified decision model from the idea).
- Note the layering: intra-run convergence already exists (SIP-0086 build convergence, SIP-0079
  correction); cross-run-within-cycle already exists (SIP-0083). The genuinely **new** layer is
  cross-cycle objective continuation = **Campaign** (a sibling to `TaskFlowPolicy`, above the
  intra-run loops).

## Finding 2 — the 2.0 vision resolves into three pillars mapped to the era-split

The vision is currently smeared across three SIPs with overlapping vocabulary. It resolves cleanly:

| Pillar | Answers | Era | Home SIP |
|---|---|---|---|
| **Capability-Backed Agents** | *What an agent IS* — packs, skill-mediated tools, working sets, scoped memory | **2.0** | `SIP-Capability-Backed-Agents` (extends the SIP-0040 Capability/Skill/Tool triad, does not reinvent it) |
| **Campaign** | *How objectives span cycles* — objective envelope + continuation policy | **1.6 mechanic** (reuses existing recruitment unchanged) → 2.0 capability-augmentation | carve from the Campaign SIP |
| **Self-Improvement + Test Bay** | *How the system improves itself* — capstone that uses Campaign to improve Capabilities, proven in Test Bay | **2.0** (depends on both above) | remainder of the Campaign SIP |

## Finding 3 — the Campaign SIP should split before acceptance

`SIP-Campaign-Self-Improvement-and-Test-Bay-Requirements.md` is an excellent **vision anchor** but
bundles 2–3 acceptable units and overlaps the other two 2.0 umbrellas. It should not go to
`accepted` as one 1,500-line tri-pillar doc (SquadOps acceptance = a design commitment a feature
branch implements). Intended split — the SIP's own §22.1 "late-1.x enablers" mark the seam:

1. **Campaign Orchestration SIP → targets 1.6.** The objective envelope + continuation policy
   (with the folded-in Loop-Policy decision vocab). Implementable without capability packs; reuses
   the existing cycle-recruitment coordinator/FocusLease path unchanged (per the 2.0 memory —
   re-recruit per cycle; only holding an agent *across* cycles would need new lease semantics, which
   we avoid). **This is the near-term, acceptable unit.**
2. **Self-Improvement + Test Bay SIP → targets 2.0.** The compounding-improvement apparatus:
   Self-Improvement Campaign types, capability supply chain, staged-autonomy ladder (target L0–L4
   first, defer L5–L6), scorecards, promotion gates, Test Bay. The 2.0 vision anchor. Depends on
   Campaign Orchestration + Capability-Backed Agents.

Pre-acceptance cleanup for either unit:
- Frontmatter added (done — status `proposed`); the maintainer script assigns the number at acceptance.
- Reconcile the boundary with `SIP-Capability-Backed-Agents` and `SIP-Continuum-Runtime-Console` so
  we don't ship **two overlapping 2.0 umbrellas** claiming capability-pack / Continuum territory.
- The 10 candidate roles (§12) are *outputs of Agent-Role-Proposal Campaigns*, not commitments in the
  anchor (the SIP's own §12 intro + Risk 21.7 say roles must be evidence-justified).

## Finding 4 — the roadmap idea's version labels are stale; the layering is not

The Jul-1 idea predates the even/odd convention (#281). Its layered thesis
(*harden → observable presence → durable responsibility → evidence-guided continuance →
capability-backed agents*) and its concept-boundary table (§11) are sound and worth keeping. Its
**version column is stale** and must be remapped before it feeds `docs/ROADMAP.md`:

| Idea says | Reality (even/odd remap) |
|---|---|
| 1.1 = hardening (avoid embodiment) | history |
| 1.2 = embodiment substrate | embodiment **Phase 1 shipped in 1.2.0** |
| 1.3 = duty durability | **1.3 = stabilization (feature-free)**; duty durability → **1.4** (SIP-0091, fix its stale `v1.3` self-tag) |
| late 1.x = Loop Policy | = Campaign continuation policy (Finding 1); mechanic → **1.6** |
| 2.0 = capability-backed agents | unchanged |

## Finding 5 — influence on the hardening & feature lanes

- **Hardening lane gains a purpose.** The Campaign SIP's §22.1 enablers — durable Run records,
  run→source & run→artifact traceability, an artifact store, disposable-workspace lifecycle/cleanup,
  improved Cycle evidence model — are Spark-flavored reliability/persistence work **and**
  prerequisites for Test Bay *and* SIP-0090 embodiment budgets/evidence. Frame the 1.3/1.5
  stabilization backlog around hardening the Run/artifact/evidence substrate *because Campaign will
  stand on it*. (This does **not** disturb the current 1.3 batch — Campaign items are features and
  land on even minors; 1.3 stays feature-free.)
- **Feature lane sharpens:** 1.4 = duty durability (SIP-0091) + possibly embodiment Phase 2 (Discord)
  → **1.6 = Campaign mechanic** → 1.8/2.0 = Capability-Backed Agents + Self-Improvement + Test Bay.
- **Test Bay lane signature:** buildable Macbook-side (repo, artifact store, retention logic — the
  "Macbook builds the whole path" model), but its disk-exhaustion / retention behavior is a
  **Spark confirmation-gate** concern (the SIP flags Spark disk repeatedly).

## Next moves

1. ~~Draft the carved-out **Campaign Orchestration SIP (1.6)**~~ — **done**: `sips/proposed/SIP-Campaign-Orchestration.md`. The near-term acceptable unit: objective envelope + continuation policy, reusing recruitment unchanged, with the Loop-Policy decision vocab folded in. Not yet accepted (proposed). **Update 2026-07-06:** revised per #334 (evidence contract, #288 prerequisite, AC#4 hardening); the Finding-5 feature-lane line is superseded by `docs/plans/1-4-evidence-arc-plan.md` — 1.4 = duty durability **+ Verification Evidence Integrity** (`sips/proposed/SIP-Verification-Evidence-Integrity.md`), which gates Campaign Phase 2.
2. Reconcile the umbrella boundary (Campaign vs Capability-Backed-Agents vs Continuum-Runtime-Console).
3. When `docs/ROADMAP.md` is next touched, apply the Finding-4 remap and the Finding-2 pillar map.
4. Fix SIP-0091's stale `Targets: v1.3` → 1.4.
