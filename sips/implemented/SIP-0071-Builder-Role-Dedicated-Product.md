---
title: Builder Role — Dedicated Product Builder Agent
status: implemented
author: Jason Ladd
created_at: '2026-02-22T00:00:00Z'
sip_number: 71
updated_at: '2026-02-22T17:10:54.611583Z'
---
# SIP-00XX: Builder Role — Dedicated Product Builder Agent

**Status:** Proposed
**Created:** 2026-02-22
**Owner:** SquadOps Core
**Target Release:** v1.0
**Related:** SIP-0068 (Enhanced Agent Build Capabilities), SIP-0066 (Cycle Execution Pipeline), SIP-0058 (Capability Contracts)
**Derived From:** IDEA-Bob-Dedicated-App-Builder-Agent-DGX-Portable.md, IDEA-QA-First-Test-Strategy-1h-Cycles-group_run.md

---

## 1. Intent

Add a **`builder` role** to SquadOps alongside the existing five (`lead`, `dev`, `strat`, `qa`, `data`). An agent assigned the builder role specializes in producing runnable, testable application artifacts from approved plans — bridging the gap between planning outputs and executable code.

Today, the `dev` role (Neo by default) handles both implementation planning and code generation via SIP-0068's `DevelopmentBuildHandler`. This SIP separates those concerns: `dev` owns planning and integration, `builder` owns artifact production. This improves role clarity, build consistency, and enables QA to validate against a dedicated builder's output contract.

The framework remains agent-identity-agnostic. "Bob" is a default instance name in the reference deployment, just as "Neo" is for `dev`. Project cloners choose their own agent names. No framework code references agent names — only roles and capabilities.

---

## 2. Problem Statement

### 2.1 Role Overload on `dev`

SIP-0068 added build task types (`development.build`, `qa.build_validate`) to the existing pipeline. Both planning (`development.implement`) and building (`development.build`) are handled by the `dev` role agent. This creates:

- **Context switching** — the same agent alternates between analytical planning and concrete implementation
- **Prompt bloat** — system prompts must cover both planning and building concerns
- **No specialization signal** — build quality can't be measured independently from planning quality
- **Scaling friction** — adding build profiles (web, CLI, etc.) further overloads the `dev` role

### 2.2 No Build Profile Abstraction

SIP-0068's `DevelopmentBuildHandler` produces Python CLI artifacts for all projects. There's no mechanism to select a different build profile (static web, web app) based on the project's target. The handler's system prompt is hardcoded to one output shape.

### 2.3 Implicit QA Handoff

Build artifacts are ingested into the artifact vault, but there's no structured handoff artifact that tells QA what was built, how to run it, what to test, and what's known to be incomplete. QA must reverse-engineer the build output.

---

## 3. Goals

1. **New `builder` role** registered in the agent role system alongside `lead`, `dev`, `strat`, `qa`, `data`.
2. **Build profile abstraction** — `python_cli_builder`, `static_web_builder`, `web_app_builder` as selectable profiles that shape the builder's system prompt and output contract.
3. **QA handoff artifact** — a structured artifact type (`qa_handoff`) that the builder emits alongside code, giving QA a consistent validation contract.
4. **Task type migration** — `development.build` becomes `builder.build`, owned by the `builder` role. `qa.build_validate` remains with QA.
5. **Task tag routing** — lightweight tags on task envelopes (`domain`, `requires_pytest`, `interaction`) that the builder consumes to adjust output without requiring new build profiles.
6. **Reference deployment** — a 6th agent container ("Bob" by default) in docker-compose wired to the `builder` role.
7. **Backward compatibility** — existing 5-agent cycle request profiles continue to work. The builder role is opt-in via new profiles.

---

## 4. Non-Goals

- **Deployment profiles** (DGX Spark, AWS, etc.) — future concern (Bob v1.1 per IDEA doc). The builder produces artifacts; where they run is a platform concern.
- **Container-first / Dockerfile generation** — future concern. V1 produces source files only.
- **Sandboxed code execution** — the builder produces code; humans or CI run it.
- **Replacing the `dev` role** — `dev` retains planning, integration, and tooling responsibilities. Builder handles artifact production.
- **Agent name awareness in framework code** — the framework never references "Bob" or any other agent name.

---

## 5. Design

### 5.1 Builder Role Definition

The builder role is registered in the same role system as existing roles. It is a peer, not a sub-role of `dev`.

```yaml
# Agent role definition (in agent config YAML)
role: builder
description: >
  Dedicated product builder. Turns approved plans and specs into runnable,
  testable artifacts. Emits structured QA handoff for every build.
capabilities:
  - builder.build
```

**Mission:** Turn approved specs and tasks into runnable, testable artifacts that QA can validate.

**Primary outputs:**
- Working application source files
- Configuration files (requirements.txt, etc.)
- QA handoff artifact (structured)

**Explicitly not responsible for:**
- Implementation planning (that's `dev`)
- QA validation (that's `qa`)
- Product strategy (that's `strat`)
- Release approval (that's `lead`)

#### Role Boundary: `dev` vs `builder`

| Concern | Owner | Rule |
|---------|-------|------|
| Implementation planning, task decomposition, integration design | `dev` | `dev` produces the approved plan before `builder.build` executes |
| Artifact generation constrained by approved plan + build profile | `builder` | `builder` follows the plan; it does not expand scope |
| Local implementation decisions (variable names, internal structure) | `builder` | `builder` may make local decisions when the plan is silent |
| Architectural decisions that affect integration | `dev` / `lead` | `builder` escalates via task diagnostics; does not decide |
| Build profile selection | cycle request profile | Neither agent chooses the profile at runtime |

**Key rule:** If a decision would change the public interface, file structure, or dependency set beyond what the plan specifies, `builder` must not make it. The boundary is: `builder` implements *within* the plan, never *beyond* it.

### 5.2 Build Profiles

Build profiles control the builder's system prompt template, output file expectations, and artifact types. A build profile is selected via the cycle request profile's `applied_defaults`.

```yaml
# In a cycle request profile
defaults:
  build_profile: python_cli_builder
  build_tasks: [builder.build, qa.build_validate]
```

#### `python_cli_builder` (v1)

- **Output**: Python source files, pytest test expectations, requirements.txt, README.md
- **System prompt**: Instructs LLM to produce CLI-executable Python with fenced code blocks
- **Validation**: Entry point file required, no absolute imports outside project

#### `static_web_builder` (v1)

- **Output**: HTML, CSS, optional JS files
- **System prompt**: Instructs LLM to produce browser-openable static files
- **Validation**: index.html required, no external CDN dependencies unless specified

#### `web_app_builder` (v1 stretch)

- **Output**: Python web app (FastAPI/Flask), templates, static assets, test files
- **System prompt**: Instructs LLM to produce a runnable web server with documented startup
- **Validation**: Server entry point required, documented startup command

Build profiles are implemented as a registry of typed profile definitions (prompt template + output contract + validation rules + QA handoff expectations), not as separate handler classes. The `BuilderBuildHandler` selects the appropriate profile at task execution time.

```python
@dataclass(frozen=True)
class BuildProfile:
    """Typed build profile definition."""
    name: str                              # e.g. "python_cli_builder"
    system_prompt_template: str            # Jinja2 template for builder system prompt
    required_files: list[str]              # Files that MUST appear in output (validation fails otherwise)
    optional_files: list[str]              # Files that MAY appear (no validation failure if absent)
    validation_rules: list[str]            # Named rules applied post-build (e.g. "no_absolute_imports")
    artifact_output_mode: str              # "multi_file" (default) | "single_file" | "structured_bundle"
    qa_handoff_expectations: list[str]     # Hints interpolated into QA handoff template
    default_task_tags: dict[str, str]      # Default tags applied when cycle request profile omits them

BUILD_PROFILES: dict[str, BuildProfile] = {
    "python_cli_builder": BuildProfile(
        name="python_cli_builder",
        system_prompt_template="...",
        required_files=["main.py"],
        optional_files=["requirements.txt", "README.md"],
        validation_rules=["no_absolute_imports", "syntax_check"],
        artifact_output_mode="multi_file",
        qa_handoff_expectations=["pytest runnable", "CLI entry point documented"],
        default_task_tags={"requires_pytest": "true"},
    ),
    "static_web_builder": BuildProfile(
        name="static_web_builder",
        system_prompt_template="...",
        required_files=["index.html"],
        optional_files=["style.css", "app.js"],
        validation_rules=["no_external_cdn_unless_specified", "valid_html"],
        artifact_output_mode="multi_file",
        qa_handoff_expectations=["browser-openable", "no server required"],
        default_task_tags={},
    ),
}
```

### 5.3 Task Type: `builder.build`

Replaces `development.build` as the primary build task type. Owned by the `builder` role.

| Aspect | `development.build` (SIP-0068) | `builder.build` (this SIP) |
|--------|-------------------------------|---------------------------|
| Role | `dev` | `builder` |
| Profile | Implicit (Python CLI only) | Explicit via `build_profile` |
| Handoff | Artifacts only | Artifacts + `qa_handoff` |
| Handler | `DevelopmentBuildHandler` | `BuilderBuildHandler` |

**Migration path:** `development.build` is retained as an alias that routes to `BuilderBuildHandler` when a builder agent is present in the squad profile, or falls back to the existing `DevelopmentBuildHandler` when no builder is configured. This preserves backward compatibility for existing 5-agent profiles.

**Routing semantics (deterministic):**

1. Routing is resolved at **task plan generation time**, not at dispatch or handler resolution time.
2. The task plan generator checks the squad profile for a `builder` role agent.
3. If present: `development.build` → `builder.build` (resolved task type written to plan).
4. If absent: `development.build` → `development.build` (unchanged, routed to `DevelopmentBuildHandler`).
5. Every routing decision MUST be logged with: resolved task type, resolved role, resolved handler, and reason (alias/fallback).
6. If a builder role agent exists in the squad profile but is unhealthy/unavailable at dispatch time, the task fails with a clear error — it does NOT silently fall back to `dev`. Silent fallback would mask operational issues.

**Input resolution:** Same as SIP-0068 — the handler resolves plan artifact content from `ArtifactVaultPort` via accumulated `artifact_refs`. The `_BUILD_ARTIFACT_FILTER` mapping is extended to include `builder.build`.

### 5.4 Task Tags

Task tags are optional key-value pairs on the task envelope's `experiment_context` (existing field, no schema change) that provide domain hints to the builder without requiring new build profiles.

```yaml
experiment_context:
  domain: game
  interaction: interactive_prompt
  requires_pytest: true
```

The builder's prompt template interpolates these tags to adjust output. For example, `domain=game` adds game-specific guidance to the system prompt; `requires_pytest=true` ensures test file generation.

**Tag rules (v1):**

- **Tags cannot weaken profile constraints.** The build profile's `required_files` and `validation_rules` are authoritative. Tags can add prompt guidance and optional output behavior, but cannot remove requirements or disable validation.
- **Unknown tags** are ignored with a warning log (not fatal). No reserved namespace in v1 — defer formalization to a future SIP if tag usage grows.

### 5.5 QA Handoff Artifact

Every `builder.build` task emits a `qa_handoff` artifact alongside the source artifacts. This is a structured markdown document with canonical section headings.

**Required sections** (QA handler fails if any are absent):

| Section | Purpose |
|---------|---------|
| `## How to Run` | Exact command(s) to execute the built artifact |
| `## How to Test` | Exact command(s) to run tests / validate behavior |
| `## Expected Behavior` | Observable outcomes QA should verify |

**Optional sections** (QA handler degrades gracefully if absent):

| Section | Purpose |
|---------|---------|
| `## Files Created` | Manifest of emitted files with one-line descriptions |
| `## Implemented Scope` | What was built (positive scope statement) |
| `## Known Limitations` | What was intentionally omitted or deferred |
| `## Build Results` | Lint, syntax check, self-validation results |

**Example:**

```markdown
# QA Handoff — {project_id}

## Files Created
- main.py — entry point
- game.py — game logic
- display.py — terminal rendering

## How to Run
python main.py

## How to Test
pytest test_game.py -v

## Expected Behavior
- App starts and displays a welcome message
- User can play tic-tac-toe against AI opponent
- Game detects win/loss/draw conditions

## Implemented Scope
- 3x3 board with X/O markers
- Random AI opponent
- Win detection for rows, columns, diagonals

## Known Limitations
- AI uses random moves (no minimax)
- No save/load game state

## Build Results
- Lint: passed
- Self-check: all files parse without syntax errors
```

**Handler behavior:**
- `QABuildValidateHandler` parses required sections and executes its validation flow using them directly — no reverse-engineering of source layout.
- If a required section is missing, `QABuildValidateHandler` emits a validation failure artifact citing the missing section(s).
- If the entire `qa_handoff` artifact is missing, `QABuildValidateHandler` falls back to the existing SIP-0068 reverse-engineering path (source-only validation) and logs a warning.

The `qa_handoff` artifact type is added to the artifact type registry.

### 5.6 Squad Profile Changes

New 6-agent squad profile:

```yaml
# profiles/squad/full-squad-with-builder.yaml
agents:
  - role: lead
  - role: strat
  - role: dev
  - role: builder
  - role: qa
  - role: data
```

The existing `full-squad` (5-agent) profile is unchanged. Cycle request profiles that include `builder.build` in `build_tasks` should reference a squad profile that includes the builder role.

### 5.7 Task Plan Generator Changes

The task plan generator (extended in SIP-0068) gains a new mapping:

```python
BUILD_TASK_STEPS = [
    ("builder.build", "builder"),      # was ("development.build", "dev")
    ("qa.build_validate", "qa"),
]
```

When the cycle's squad profile includes a `builder` role agent, the generator uses `builder.build`. When it does not (5-agent squad), the generator falls back to `development.build` for backward compatibility.

### 5.8 Docker Wiring

A 6th agent container is added to docker-compose, following the existing pattern:

```yaml
bob:
  build:
    context: .
    dockerfile: src/squadops/agents/Dockerfile
    args:
      AGENT_ROLE: builder
  container_name: squadops-bob
  environment:
    SQUADOPS__AGENT__NAME: bob
    SQUADOPS__AGENT__ROLE: builder
    # ... standard agent env vars
```

The container name `squadops-bob` is a reference deployment convenience. The framework identifies the agent by its role, not its container name.

---

## 6. Backward Compatibility

**Parity guarantee for 5-agent mode:** existing 5-agent deployments experience zero behavioral change. Specifically:

- **No config changes required.** Existing cycle request profiles, squad profiles, and environment variables work unchanged.
- **Same task plan generation.** The task plan generator produces the same task sequence for 5-agent squads as it does today. `development.build` routes to `DevelopmentBuildHandler` when no builder role is in the squad profile.
- **Same artifact types emitted.** The legacy build path emits the same artifact types as before. The `qa_handoff` artifact is only emitted by `BuilderBuildHandler` — never injected into the legacy path.
- **Same QA validation path.** `QABuildValidateHandler` behavior for legacy builds is unchanged. It only consumes `qa_handoff` when one is present; absence triggers the existing source-only validation path.
- **No additive diagnostics on legacy path.** The routing diagnostics (resolved handler, alias reason) are emitted for all `development.build` executions, but this is observability-only — no behavioral change.

---

## 7. Implementation Phases

### Phase 1: Builder Role + Handler + Routing

- Register `builder` role in agent role system
- Create `BuilderBuildHandler` for `builder.build` task type
- Implement build profile registry with `python_cli_builder` profile
- Implement `qa_handoff` artifact generation (required/optional sections)
- Add `builder.build` → `BuilderBuildHandler` to handler registry
- Unit tests for handler, profile selection, and handoff generation
- Then: implement alias routing semantics for `development.build` (deterministic, logged)
- Then: implement routing diagnostics (resolved handler, role, reason on every execution)
- Unit tests for routing logic

### Phase 2: Task Plan Generator + Profiles + Tags

- Update task plan generator for builder role awareness (fallback to `dev` when absent)
- Create `full-squad-with-builder` squad profile
- Create new cycle request profiles referencing builder
- Add `static_web_builder` profile
- Add `web_app_builder` profile (stretch)
- Implement task tag interpolation in prompt templates
- Unit tests for each profile and tag combinations

### Phase 3: Docker Wiring + Reference Deployment

- Add builder agent container to docker-compose (default name: "bob")
- Build agent package via `build_agent.py builder`
- Create/update cycle request profiles for 6-agent squad
- E2E validation: `play_game` build cycle with builder agent
- Update `hello_squad` and `group_run` cycle request profiles

### Phase 4: Validation + Documentation

- E2E: `hello_squad` with `static_web_builder` profile produces openable HTML
- E2E: `play_game` with `python_cli_builder` profile produces runnable CLI
- E2E: `group_run` with `python_cli_builder` or `web_app_builder` profile
- Validate QA handoff artifact consumed by `QABuildValidateHandler`
- Validate routing diagnostics appear in task metadata for alias executions
- Update SIP-0068 docs to reference builder role
- Regression suite passes (all existing tests green)

---

## 8. Open Questions

1. **Profile selection granularity**: Should build profiles live in the cycle request profile YAML (proposed) or in a separate registry that the cycle request profile references by name? The former is simpler; the latter allows sharing profiles across cycle request profiles.

2. **`development.build` deprecation timeline**: The alias preserves backward compatibility, but should we set a version target for removing the alias and requiring `builder.build` explicitly?

3. **Builder + Dev overlap for small projects**: For trivial projects like `hello_squad`, is a 6th agent justified? The squad profile mechanism already handles this (use 5-agent profile for simple builds, 6-agent for dedicated builder workflows), but we should document the guidance.

4. **QA handoff schema enforcement**: Should the `qa_handoff` artifact have a validated schema (JSON/YAML) or remain freeform markdown? Markdown is simpler for v1 and LLM-friendly; structured schema enables programmatic consumption later. (V1 decision: markdown with required section headings; see section 5.5.)

5. **Build profile extensibility**: Should third-party / user-defined build profiles be supported in v1, or only the three built-in profiles? User-defined profiles would require a plugin/registry mechanism.

6. **Failure and retry ownership**: If `builder.build` fails (LLM produces unparseable output, validation rules fail, required files missing):
   - Does the builder retry with the same plan inputs?
   - Does failure escalate to `dev` for plan refinement?
   - Does `lead` decide retry vs scope cut?
   - How many retries before fallback/escalation?
   - This directly affects long-run autonomy and should be decided before Phase 1 implementation.

---

## 9. Operational Diagnostics

Every `builder.build` and aliased `development.build` execution MUST emit the following structured diagnostics in task metadata:

| Field | Example |
|-------|---------|
| `resolved_role` | `builder` or `dev` |
| `resolved_handler` | `BuilderBuildHandler` or `DevelopmentBuildHandler` |
| `resolved_task_type` | `builder.build` or `development.build` |
| `routing_reason` | `"builder_role_present"` or `"fallback_no_builder"` |
| `build_profile` | `python_cli_builder` |
| `task_tags_received` | `{"domain": "game", "requires_pytest": "true"}` |
| `artifacts_emitted` | `["art_abc123", "art_def456"]` |
| `qa_handoff_emitted` | `true` or `false` |
| `validation_summary` | `{"required_files": "pass", "syntax_check": "pass"}` |

These diagnostics provide enough observability to answer "Why did this cycle route `development.build` to Neo instead of Bob?" without requiring a telemetry redesign.

---

## 10. Success Criteria

1. A cycle using `builder.build` with the `python_cli_builder` profile produces a runnable artifact set that passes the same validation checks used for the current `play_game` legacy build path.
2. Every `builder.build` task emits a `qa_handoff` artifact with all required sections present. `QABuildValidateHandler` parses the required sections and executes its validation flow using them directly — no reverse-engineering of source layout.
3. Existing 5-agent cycles (`full-squad` profile) continue to work with zero regression: no config changes, same task plan, same artifact types, same QA validation behavior.
4. The `static_web_builder` profile produces a browser-openable `hello_squad` from a build cycle.
5. The task plan generator correctly routes `builder.build` to the builder role agent and falls back to `dev` when no builder is present.
6. Build profile selection is driven entirely by cycle request profile configuration — no hardcoded profile logic in handler code.
7. No framework code references agent instance names ("Bob", "Neo", etc.) — only roles.
8. Alias/fallback routing decisions are emitted in structured task diagnostics for every `development.build` execution (see section 9).
