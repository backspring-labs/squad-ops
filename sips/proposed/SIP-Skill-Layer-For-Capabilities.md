# SIP: Skill Layer for Capabilities (Capability → Skill → Tool)

**Status**: Proposed (concept reservation — no implementation planned)
**Author**: SquadOps Team
**Created**: 2026-07-11
**Related**: #401 (removal of the first incarnation), SIP-0060/SIP-0.8.8 (the first incarnation), SIP-0096 (integration contract a revival must satisfy)

## Summary

Reserve the three-tier execution vocabulary — **capability → skill → tool** —
as the intended shape for a future reusable-operation layer, and record why
the first incarnation (SIP-0.8.8) was removed rather than repaired, so a
second incarnation starts from today's architecture instead of resurrecting
five-month-old dormant code.

This SIP intentionally proposes **no implementation**. It exists so the
concept survives the #401 deletion with its lessons attached.

## The vision

- **Capability** — a task-level contract (`development.develop`,
  `qa.test`, `builder.assemble`): what a role can be asked to do. Routed by
  task type, fulfilled by a handler, gated by acceptance checks.
- **Skill** — a reusable atomic operation a capability composes
  (query an LLM with a managed prompt, read/write an artifact, recall
  memory): the unit of *reuse* between capabilities, each execution emitting
  its own evidence.
- **Tool** — the thing a skill executes against: a hexagonal port
  (LLMPort, FileSystemPort, MemoryPort) or, in a future where agents drive
  function-calling/MCP-style tools, an externally-described tool interface.
  *(The first incarnation only ever meant "ports"; a revival should decide
  this explicitly.)*

## What happened to incarnation one (and why it was deleted)

SIP-0.8.8 built exactly this layering: `CapabilityHandler` →
`context.execute_skill()` → `SkillContext` over `PortsBundle`. It died of
disuse, not by decision:

- When the real cycle pipeline was built (SIP-0066 onward), its handlers
  went **straight to ports** — prompt renderer → LLM port → parse →
  filesystem port. At that grain of work, no reuse seam was needed between
  handler and port.
- The skill layer was never dispatched again: by 2026-07 nothing produced
  any skill-backed capability's task type, and the layer's own quality had
  rotted relative to the mainline (naive `json.loads` with silent fabricated
  fallbacks — #394 — versus the mainline's robust extraction).
- Removed in #400 (three analysis skills) and #401 (the remaining layer:
  skills, skill registry/context threading, warmboot's skill consumers).

Lesson: **a reuse layer must be pulled into existence by at least two real
consumers, not built ahead of them.** Speculative middle tiers rot into
landmines (silent-fallback parsing shipped inside dormant code).

## Contract for incarnation two

A revived skill layer MUST integrate with what now defines a well-behaved
unit of work, none of which existed when incarnation one was written:

1. **Verification evidence integrity (SIP-0096)** — a skill execution that
   constitutes verification evidence emits `CheckResult`s through the
   integrity choke point. No bespoke evidence records (incarnation one's
   `SkillExecutionRecord` was an unwired producer of exactly the kind #376
   catalogs).
2. **Prompt registry** — any LLM-calling skill renders through the managed
   prompt registry (hash-stamped, drift-guarded); no inline prompt-constant
   strings.
3. **Robust output handling** — LLM output parsing goes through the shared
   extractors (`extract_first_json_object` / fenced parsing); a parse
   failure is a *failed execution*, never a silently fabricated default
   (#394's anti-pattern).
4. **LLM observability** — skill executions carry `CorrelationContext` and
   surface as spans under the owning task's trace (SIP-0061).
5. **Pull, don't push** — the layer is (re)introduced only when concrete
   capabilities demonstrably duplicate an operation worth extracting. The
   likeliest trigger is ambient/duty work (SIP-0088/0090/0091), where agents
   need a shared toolbox of small operations, unlike bespoke per-task-type
   cycle handlers.

## Non-goals

- Reintroducing any of the deleted code. Incarnation one's value is fully
  captured by this document; the implementation was structurally obsolete.
- Blocking or gating other work. This SIP carries no implementation
  obligation and no version target.
