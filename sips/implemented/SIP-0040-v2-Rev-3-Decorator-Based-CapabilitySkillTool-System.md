---
sip_uid: "17642554775961541"
sip_number: 40
title: "Rev-3-Decorator-Based-CapabilitySkillTool-System"
status: "implemented"
author: "SquadOps Build Partner"
approver: "None"
created_at: "2025-01-XX"
updated_at: "2025-11-27T10:12:48.901774Z"
original_filename: "SIP-040-REV3-DECORATOR-SYSTEM.md"
---

# SIP-040 Rev 3: Decorator-Based Capability/Skill/Tool System

**Author:** SquadOps Build Partner  
**Date:** 2025-01-XX  
**Status:** Draft - **Future Enhancement**  
**Relates:** SIP-040 (Capability System MVP), SIP-040 Rev 2 Phase 0 (Architectural Fixes)  
**Prerequisites:** SIP-040 Rev 2 Phase 0 must be completed first

---

## 1) Purpose

Refactor the SquadOps capability/skill/tool system to use **decorators** for:
- **Auto-registration**: Eliminate manual `CAPABILITY_MAP` dictionary maintenance
- **Metadata attachment**: Version, description, inputs/outputs declared in code
- **Cross-cutting concerns**: Telemetry, validation, logging via decorators
- **Dependency injection**: Replace manual wiring with declarative dependencies

**Priority:** **FUTURE ENHANCEMENT** - Defer until after multi-agent expansion and core production SIPs (SIP-003, SIP-005, SIP-007, SIP-010, SIP-012).

---

## 2) Scope

### 2.1 Decorator Infrastructure

**Components:**
- Capability decorators (`@capability()`)
- Skill decorators (`@skill()`)
- Tool decorators (`@tool()`)
- Cross-cutting decorators (`@telemetry()`, `@validate_inputs()`, `@validate_outputs()`, `@log()`)
- Dependency injection decorators (`@inject()`)

### 2.2 Affected Files

**All capability classes (15+):**
- Add `@capability()` decorator with metadata
- Add cross-cutting decorators where appropriate

**All skill classes (5+):**
- Add `@skill()` decorator with metadata

**All tool classes (4+):**
- Add `@tool()` decorator with metadata

**Core Infrastructure:**
- `CapabilityLoader` - Remove `CAPABILITY_MAP`, use decorator registry
- Create `agents/decorators/` module with registry and decorators

---

## 3) Motivation

### 3.1 Current Problems

**Manual Registration:**
- `CAPABILITY_MAP` dictionary requires manual maintenance (15 entries)
- Easy to forget to register new capabilities
- No single source of truth

**Metadata Duplication:**
- Capability metadata in `catalog.yaml`
- Implementation details in code
- Version tracking disconnected

**Cross-Cutting Concerns:**
- Telemetry/logging/validation scattered across code
- Inconsistent implementation
- Difficult to add new concerns

**Dependency Injection:**
- Manual wiring (`TaskCreator.set_build_requirements_generator()`)
- Hardcoded special cases in `CapabilityLoader`
- Not declarative

### 3.2 Benefits

1. **Eliminates Manual Maintenance**: No more `CAPABILITY_MAP` dictionary
2. **Single Source of Truth**: Metadata in code, not separate YAML
3. **Better Discoverability**: Auto-discovery via decorators
4. **Cleaner Code**: Less boilerplate, declarative dependencies
5. **Cross-Cutting Concerns**: Telemetry/validation/logging via decorators
6. **Dependency Injection**: Declarative, not hardcoded
7. **Version Tracking**: Metadata attached to classes
8. **Easier Testing**: Decorators can be mocked/tested independently

---

## 4) Specification

### 4.1 Capability Decorator

```python
@capability(
    name="build.artifact",
    version="1.0.0",
    description="Build application artifacts from specifications",
    result_keys=["artifact_uri", "commit", "files_generated", "manifest_uri"],
    dependencies=["dev.developer_prompt", "dev.squadops_constraints", "app_builder", "docker_manager", "file_manager"]
)
class BuildArtifact:
    @telemetry(operation="build_artifact")
    @validate_outputs(result_keys=["artifact_uri", "commit", "files_generated", "manifest_uri"])
    async def build(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        # Implementation
```

**Parameters:**
- `name`: Capability identifier (e.g., "build.artifact")
- `version`: Capability version (e.g., "1.0.0")
- `description`: Human-readable description
- `result_keys`: List of expected result dictionary keys
- `dependencies`: List of skill/tool names to inject

### 4.2 Skill Decorator

```python
@skill(
    name="dev.architect_prompt",
    version="1.0.0",
    description="Architecture reasoning pattern for generating build manifests",
    role="dev",
    inputs=["app_name", "version", "prd_analysis", "features", "constraints"],
    outputs=["prompt"]
)
class ArchitectPrompt:
    def load(self, **kwargs) -> str:
        # Implementation
```

**Parameters:**
- `name`: Skill identifier (e.g., "dev.architect_prompt")
- `version`: Skill version
- `description`: Human-readable description
- `role`: Role that owns this skill (e.g., "dev", "lead")
- `inputs`: List of input parameter names
- `outputs`: List of output names

### 4.3 Tool Decorator

```python
@tool(
    name="app_builder",
    version="1.0.0",
    description="Builds application artifacts using JSON-based LLM workflow",
    category="llm"
)
class AppBuilder:
    @telemetry(operation="generate_manifest")
    async def generate_manifest_json(self, prompt: str, requirements: Dict[str, Any] = None) -> Dict[str, Any]:
        # Implementation
```

**Parameters:**
- `name`: Tool identifier
- `version`: Tool version
- `description`: Human-readable description
- `category`: Tool category (e.g., "llm", "docker", "filesystem")

### 4.4 Cross-Cutting Decorators

**Telemetry:**
```python
@telemetry(operation="build_artifact", record_prompt=True)
async def build(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
    # Automatically creates span, logs LLM calls, records metrics
```

**Validation:**
```python
@validate_inputs(schema="build.artifact.inputs")
@validate_outputs(result_keys=["artifact_uri", "commit", "files_generated"])
async def build(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
    # Automatically validates inputs/outputs
```

**Logging:**
```python
@log(level="info", include_args=True)
async def build(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
    # Automatically logs method entry/exit with args/results
```

### 4.5 Dependency Injection

**Current Problem:**
```python
# CapabilityLoader.execute() - hardcoded special case
if capability_name == 'task.create' and hasattr(capability_instance, 'set_build_requirements_generator'):
    build_req_gen = build_req_gen_class(agent_instance)
    capability_instance.set_build_requirements_generator(build_req_gen)
```

**Solution:**
```python
@capability(
    name="task.create",
    dependencies=["build.requirements.generate"]  # Auto-injected
)
class TaskCreator:
    def __init__(self, agent_instance, build_requirements_generator=None):
        # build_requirements_generator auto-injected if available
```

---

## 5) Implementation Plan

### Phase 1: Infrastructure (Foundation)

1. Create `agents/decorators/registry.py` - Central registry for capabilities/skills/tools
2. Create `agents/decorators/capability.py` - `@capability()` decorator
3. Create `agents/decorators/skill.py` - `@skill()` decorator
4. Create `agents/decorators/tool.py` - `@tool()` decorator
5. Update `CapabilityLoader` to use registry for discovery
6. Add backward compatibility layer (fallback to `CAPABILITY_MAP`)

### Phase 2: Cross-Cutting Decorators

7. Create `agents/decorators/telemetry.py` - `@telemetry()` decorator
8. Create `agents/decorators/validation.py` - Validation decorators
9. Create `agents/decorators/logging.py` - `@log()` decorator
10. Test decorators independently

### Phase 3: Dependency Injection

11. Create `agents/decorators/injection.py` - `@inject()` decorator
12. Update `CapabilityLoader.execute()` to resolve and inject dependencies
13. Remove hardcoded `TaskCreator` special case

### Phase 4: Migration - Skills

14. Migrate all skills to use `@skill()` decorator:
    - `agents/skills/dev/architect_prompt.py`
    - `agents/skills/dev/developer_prompt.py`
    - `agents/skills/dev/squadops_constraints.py`
    - `agents/skills/lead/prd_analysis_prompt.py`
    - `agents/skills/lead/build_requirements_prompt.py`

### Phase 5: Migration - Tools

15. Migrate all tools to use `@tool()` decorator:
    - `agents/tools/app_builder.py`
    - `agents/tools/file_manager.py`
    - `agents/tools/docker_manager.py`
    - `agents/tools/version_manager.py`

### Phase 6: Migration - Capabilities

16. Migrate all capabilities to use `@capability()` decorator:
    - All existing capabilities (15+)
    - New capabilities from Phase 0 (governance, task completion, documentation)

### Phase 7: Apply Cross-Cutting Decorators

17. Add `@telemetry()` to capability methods that need it
18. Add `@validate_inputs()` / `@validate_outputs()` to capabilities
19. Add `@log()` decorators where appropriate

### Phase 8: Cleanup & Testing

20. Remove `CAPABILITY_MAP` dictionary from `CapabilityLoader`
21. Update unit tests to use decorator-based discovery
22. Update integration tests
23. Verify all capabilities still work
24. Update documentation

---

## 6) Key Files

### New Files

**Decorator Infrastructure:**
- `agents/decorators/__init__.py`
- `agents/decorators/registry.py`
- `agents/decorators/capability.py`
- `agents/decorators/skill.py`
- `agents/decorators/tool.py`
- `agents/decorators/telemetry.py`
- `agents/decorators/validation.py`
- `agents/decorators/logging.py`
- `agents/decorators/injection.py`

### Modified Files

**Core:**
- `agents/capabilities/loader.py` - Use registry instead of `CAPABILITY_MAP`

**Capabilities (15+):**
- All capability files - Add `@capability()` decorator

**Skills (5+):**
- All skill files - Add `@skill()` decorator

**Tools (4+):**
- All tool files - Add `@tool()` decorator

**Tests:**
- `tests/unit/test_app_builder_json.py` - Update for decorators
- `tests/integration/test_workflow.py` - Update for decorators

---

## 7) Code Reduction Estimate

### Agents (After Phase 0)
- Manual validation: ~4 lines → 0 lines (decorators)
- Manual argument mapping: ~15 lines → 0 lines (decorators)
- **Total: ~19 lines reduced**

### CapabilityLoader
- `CAPABILITY_MAP` dictionary: ~15 entries → 0 entries (auto-discovery)
- Manual registration maintenance eliminated

---

## 8) Risks & Mitigation

**Risk 1: Import-time side effects**
- **Mitigation:** Registry is thread-safe, lazy initialization

**Risk 2: Circular dependencies**
- **Mitigation:** Dependency injection resolves lazily

**Risk 3: Breaking existing code**
- **Mitigation:** Backward compatibility layer during migration

**Risk 4: Performance impact**
- **Mitigation:** Registry uses caching, decorators are lightweight

---

## 9) Success Criteria

- ✅ All capabilities auto-discovered via decorators
- ✅ No `CAPABILITY_MAP` dictionary needed
- ✅ Telemetry/validation/logging work via decorators
- ✅ Dependency injection works declaratively
- ✅ All existing tests pass
- ✅ No performance regression
- ✅ Documentation updated

---

## 10) Migration Strategy

1. **Backward Compatible**: Keep `CAPABILITY_MAP` during migration
2. **Incremental**: Migrate one capability/skill/tool at a time
3. **Test Continuously**: Run tests after each migration step
4. **Remove Legacy**: Delete `CAPABILITY_MAP` only after all migrations complete

---

## 11) Related Work

- **SIP-040 MVP**: Original capability system implementation
- **SIP-040 Rev 2 Phase 0**: Critical architectural fixes (prerequisite)
- **SIP-046**: Agent specs and configuration

---

## 12) Timeline

**Estimated Effort:** 6-10 days

**Breakdown:**
- Phase 1-3 (Infrastructure): 2-3 days
- Phase 4-6 (Migration): 3-5 days
- Phase 7-8 (Polish & Testing): 2-3 days

**When to Start:** After multi-agent expansion and core production SIPs are complete

---

**Status:** Draft - **Future Enhancement** - Defer until after multi-agent expansion


