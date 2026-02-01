# SIP-0.8.9 Test Suite Modernization Plan

**Status:** Draft
**Target Version:** 0.8.9
**Depends On:** SIP-0.8.8 (Agent Migration)
**Created:** 2026-02-01

---

## 1. Executive Summary

This plan details the test suite modernization required after SIP-0.8.8 completes the production code migration and deletes `_v0_legacy/`. The goal is to:

1. **Prune** tests that are no longer relevant (testing retired patterns)
2. **Migrate** tests that verify still-needed behavior but use legacy imports
3. **Reconcile** to eliminate redundancy between old and new tests
4. **Consolidate** oversized test files into domain-focused modules
5. **Enable scoped execution** via domain markers for faster development iteration
6. **Refactor Health Check** app to use new architecture (ports, config)
7. **Stack Validation integration test** — verify agents are built, running, and chattable
8. **Build infrastructure cleanup** — update build scripts, Dockerfiles, docker-compose paths

**Current State:**
| Metric | Value |
|--------|-------|
| Total test files | 121 |
| Total test lines | ~37,000 |
| Legacy-importing tests | 80 files (~28,000 lines) |
| New architecture tests | 31 files (~6,000 lines) |
| Hybrid tests | 2 files |

**Target State:**
| Metric | Value |
|--------|-------|
| Total test files | ~90-100 |
| Total test lines | ~30,000-32,000 |
| Legacy imports | 0 |
| Redundant tests | 0 |
| Domain markers | 11 domains |
| Scoped run time (single domain) | 5-20s |
| Full suite run time | 60-90s |

---

## 2. Test Inventory Analysis

### 2.1 Current Directory Structure

```
tests/
├── conftest.py                    # 652 lines - HEAVY LEGACY DEPS
├── unit/                          # 98 files, ~29,000 lines
│   ├── [63 root-level test files] # Mostly legacy
│   ├── adapters/                  # 2 files - new arch
│   ├── capabilities/              # 3 files - new arch
│   ├── core/                      # 2 files - new arch
│   ├── cycle_data/                # 2 files - new arch
│   ├── embeddings/                # 2 files - new arch
│   ├── llm/                       # 3 files - new arch
│   ├── memory/                    # 7 files - new arch
│   ├── prompts/                   # 3 files - new arch
│   ├── tasks/                     # 3 files - new arch
│   ├── telemetry/                 # 4 files - new arch
│   └── tools/                     # 4 files - new arch
├── integration/                   # 19 files, ~5,000 lines
│   ├── [15 root-level test files]
│   ├── adapters/                  # 2 files
│   ├── capabilities/              # 1 file
│   └── prompts/                   # 1 file
├── regression/                    # 2 files, ~600 lines
└── smoke/                         # 1 file, ~150 lines
```

### 2.2 Import Pattern Summary

| Pattern | Files | Lines | Action |
|---------|-------|-------|--------|
| `from agents.*` only | 80 | ~23,000 | Migrate or prune |
| `from squadops.*` only | 31 | ~6,000 | Keep as-is |
| Hybrid (both) | 2 | ~800 | Migrate |
| `from _v0_legacy.*` | 1 | ~500 | Migrate |
| No domain imports | 7 | ~1,200 | Keep as-is |

---

## 3. Pruning Analysis: Tests to Delete

### 3.1 Criteria for Pruning

A test file should be **pruned** if:
- It tests functionality that no longer exists post-migration
- It tests legacy-specific patterns replaced by new architecture
- It duplicates coverage now provided by newer tests
- It tests internal implementation details that changed

### 3.2 Recommended Deletions

#### Category A: Legacy Pattern Tests (~4,500 lines)

| File | Lines | Reason |
|------|-------|--------|
| `test_warmboot_memory_handler.py` | ~400 | Legacy warmboot pattern replaced by MemoryPort |
| `test_agent_message_model.py` | ~300 | Legacy message format, replaced by TaskEnvelope |
| `test_task_message_model.py` | ~250 | Duplicate of task_envelope tests |
| `test_loader.py` | 445 | Legacy module loader, replaced by DI |
| `test_capability_loader.py` | ~600 | Legacy capability loading, replaced by CapabilityDispatcher |
| `test_skill_loader.py` | ~350 | Legacy skill loading, replaced by SkillRegistry |
| `test_agent_specs.py` | ~400 | Legacy agent specs, replaced by AgentRole models |
| `test_llm_client_legacy.py` | ~300 | Legacy LLM client, replaced by LLMPort/adapters |
| `test_config_legacy.py` | ~350 | Legacy config format tests |
| `test_task_queue_legacy.py` | ~400 | Legacy queue handling, replaced by QueuePort |

**Subtotal: ~3,800 lines**

#### Category B: Superseded by New Architecture Tests (~3,200 lines)

| Legacy Test | Superseded By | Lines to Delete |
|-------------|---------------|-----------------|
| `test_base_agent.py` (partial) | `test_base_agent_aci_contract.py` | ~800 |
| `test_dev_agent.py` (partial) | `unit/capabilities/test_runner.py` | ~400 |
| `test_qa_agent.py` (partial) | `unit/capabilities/test_acceptance.py` | ~600 |
| `test_secrets_providers.py` (partial) | `unit/core/test_secrets.py` | ~400 |
| `test_memory_storage.py` | `unit/memory/test_*.py` | ~500 |
| `test_telemetry_client.py` | `unit/telemetry/test_adapters.py` | ~500 |

**Subtotal: ~3,200 lines**

#### Category C: Integration Tests for Retired Flows (~1,000 lines)

| File | Lines | Reason |
|------|-------|--------|
| `test_legacy_agent_init.py` | ~300 | Tests legacy initialization flow |
| `test_v0_config_profiles.py` | ~400 | Tests legacy config profile format |
| `test_legacy_task_routing.py` | ~300 | Tests legacy task routing |

**Subtotal: ~1,000 lines**

### 3.3 Pruning Summary

| Category | Files | Lines |
|----------|-------|-------|
| Legacy pattern tests | 10 | ~3,800 |
| Superseded tests | 6 (partial) | ~3,200 |
| Retired integration flows | 3 | ~1,000 |
| **Total to Prune** | **~15-19** | **~8,000** |

---

## 4. Migration Analysis: Tests to Update

### 4.1 Criteria for Migration

A test file should be **migrated** if:
- It tests behavior that still exists post-migration
- Only the import paths need to change
- The test logic remains valid

### 4.2 Import Path Migrations

#### Agent Tests → squadops.agents

| Current Import | New Import |
|----------------|------------|
| `from agents.base_agent import BaseAgent` | `from squadops.agents.base import BaseAgent` |
| `from agents.roles.lead.agent import LeadAgent` | `from squadops.agents.roles.lead import LeadAgent` |
| `from agents.roles.dev.agent import DevAgent` | `from squadops.agents.roles.dev import DevAgent` |
| `from agents.roles.qa.agent import QAAgent` | `from squadops.agents.roles.qa import QAAgent` |
| `from agents.roles.data.agent import DataAgent` | `from squadops.agents.roles.data import DataAgent` |
| `from agents.roles.strat.agent import StratAgent` | `from squadops.agents.roles.strat import StratAgent` |
| `from agents.factory import AgentFactory` | `from squadops.agents.factory import AgentFactory` |

#### Skill Tests → squadops.agents.skills

| Current Import | New Import |
|----------------|------------|
| `from agents.skills.shared.*` | `from squadops.agents.skills.shared.*` |
| `from agents.skills.dev.*` | `from squadops.agents.skills.dev.*` |
| `from agents.skills.qa.*` | `from squadops.agents.skills.qa.*` |
| `from agents.skills.registry import SkillRegistry` | `from squadops.agents.skills.registry import SkillRegistry` |

#### Capability Tests → squadops.capabilities

| Current Import | New Import |
|----------------|------------|
| `from agents.capabilities.loader import *` | `from squadops.capabilities.dispatcher import *` |
| `from agents.capabilities.* import *Handler` | `from squadops.capabilities.handlers.* import *Handler` |
| `from agents.tasks.models import TaskEnvelope` | `from squadops.tasks.models import TaskEnvelope` |
| `from agents.tasks.models import TaskResult` | `from squadops.tasks.models import TaskResult` |

#### Config Tests → squadops.config

| Current Import | New Import |
|----------------|------------|
| `from infra.config.loader import *` | `from squadops.config.loader import *` |
| `from infra.config.schema import *` | `from squadops.config.models import *` |

### 4.3 Files Requiring Migration

| File | Lines | Migration Complexity |
|------|-------|---------------------|
| `test_lead_agent.py` | 3,897 | High - many imports, fixture deps |
| `test_dev_agent.py` | 1,192 | Medium |
| `test_qa_agent.py` | 5,656 | High |
| `test_data_agent.py` | 8,237 | High |
| `test_strat_agent.py` | 5,656 | High |
| `test_base_agent_aci_contract.py` | 6,338 | Medium - mostly ACI focused |
| `test_base_agent_memory.py` | 6,465 | Medium |
| `test_agent_factory.py` | 450 | Low |
| `test_governance_*.py` (3 files) | ~900 | Low |
| `test_task_*.py` (5 files) | ~1,500 | Medium |
| `test_build_agent.py` | 10,518 | High - many legacy deps |
| `test_config_loader.py` | 735 | Low |
| `test_docker_*.py` (4 files) | ~1,500 | Medium |
| `test_file_manager.py` | 668 | Low |
| `test_version_manager.py` | 542 | Low |
| `test_manifest_generator.py` | ~400 | Medium |

**Total requiring migration: ~50 files**

> **Note on line counts:** The table above shows total lines per file, not lines requiring changes. The ~28,000 lines figure in the Executive Summary represents lines in files that import from legacy paths. Actual import statement changes will be a fraction of this. Track progress by files migrated, not lines changed.

### 4.4 conftest.py Migration

The main `tests/conftest.py` (652 lines) requires significant updates:

```python
# BEFORE (Legacy)
from agents.base_agent import BaseAgent
from agents.capabilities.loader import AgentConfig
from agents.roles.dev.agent import DevAgent
from agents.roles.lead.agent import LeadAgent
from agents.tools.app_builder import AppBuilder

# AFTER (New Architecture)
from squadops.agents.base import BaseAgent
from squadops.agents.factory import AgentFactory
from squadops.agents.roles.dev import DevAgent
from squadops.agents.roles.lead import LeadAgent
# AppBuilder moves to adapters.tools or squadops.tools
```

**Key fixture changes:**
- `mock_dev_agent()` → Use `AgentFactory` with mock ports
- `mock_lead_agent()` → Use `AgentFactory` with mock ports
- `mock_app_builder()` → Use tool port mocks
- `sample_task_envelope()` → Use `squadops.tasks.models`

---

## 5. Reconciliation Analysis: Eliminating Redundancy

### 5.1 Identified Redundancies

#### A. Agent Lifecycle Tests

| Redundant Set | Keep | Delete/Merge |
|---------------|------|--------------|
| `test_base_agent.py` + `test_base_agent_aci_contract.py` | `test_base_agent_aci_contract.py` | Merge unique cases from `test_base_agent.py` |
| `test_lead_agent.py` + `test_governance_*.py` | `test_governance_*.py` | Extract governance tests from `test_lead_agent.py` |

**Recommendation:** `test_base_agent.py` contains 1,825 lines, but `test_base_agent_aci_contract.py` (6,338 lines) is more comprehensive and aligned with SIP-0058. Merge ~200 unique test cases, delete rest.

#### B. Configuration Tests

| Redundant Set | Resolution |
|---------------|------------|
| `test_config_loader.py` + `test_config_regression.py` + `test_config_profiles.py` | Consolidate into single `test_config.py` with sections |

**Recommendation:** Create `tests/unit/config/test_loader.py` and `tests/integration/config/test_profiles.py`. Delete redundant root-level files.

#### C. Task/Message Tests

| Redundant Set | Resolution |
|---------------|------------|
| `test_task_envelope_model.py` + `test_task_envelope_codec.py` + `test_task_message_model.py` | Consolidate into `tests/unit/tasks/test_envelope.py` |

**Recommendation:** New tasks directory already has `test_models.py`. Merge envelope/codec tests there.

#### D. Build/Docker Tests

| Redundant Set | Resolution |
|---------------|------------|
| `test_build_agent.py` (10,518 lines!) | Split into domain modules |
| `test_docker_*.py` (4 files) | Keep separate but ensure no overlap |

**Recommendation:** `test_build_agent.py` is too large. Split into:
- `tests/unit/build/test_packaging.py`
- `tests/unit/build/test_metadata.py`
- `tests/unit/build/test_validation.py`

#### E. Memory Tests

| Redundant Set | Resolution |
|---------------|------------|
| `test_warmboot_memory_handler.py` + `test_base_agent_memory.py` + `unit/memory/*.py` | Keep `unit/memory/*.py`, migrate relevant cases from others |

**Recommendation:** `unit/memory/` has proper port-based tests. Migrate any unique warmboot scenarios, delete legacy memory tests.

### 5.2 Reconciliation Summary

| Action | Files Affected | Lines Reduced |
|--------|----------------|---------------|
| Merge base_agent tests | 2 → 1 | ~1,500 |
| Consolidate config tests | 3 → 2 | ~400 |
| Consolidate task tests | 3 → 1 | ~300 |
| Split build_agent tests | 1 → 3 | 0 (reorganization) |
| Merge memory tests | 3 → 7 (existing) | ~800 |
| Extract governance from lead_agent | 1 → 3 (existing) | ~500 |

**Total lines reduced through reconciliation: ~3,500**

---

## 6. Target Directory Structure

```
tests/
├── conftest.py                    # Modernized - no legacy imports
├── unit/
│   ├── agents/                    # NEW - agent domain tests
│   │   ├── test_base.py           # BaseAgent with ports
│   │   ├── test_factory.py        # AgentFactory DI
│   │   ├── test_models.py         # Agent, AgentRole, AgentContext
│   │   └── roles/
│   │       ├── test_lead.py
│   │       ├── test_dev.py
│   │       ├── test_qa.py
│   │       ├── test_data.py
│   │       └── test_strat.py
│   ├── skills/                    # NEW - skill domain tests
│   │   ├── test_registry.py
│   │   ├── test_base.py
│   │   └── shared/
│   │       └── test_*.py
│   ├── capabilities/              # EXISTS - expand
│   │   ├── test_dispatcher.py     # NEW
│   │   ├── test_runner.py
│   │   ├── test_acceptance.py
│   │   ├── test_models.py
│   │   └── handlers/
│   │       └── test_*.py
│   ├── api/                       # NEW - API domain tests
│   │   ├── test_app.py
│   │   ├── test_deps.py
│   │   └── routes/
│   │       ├── test_tasks.py
│   │       ├── test_agents.py
│   │       └── test_health.py
│   ├── orchestration/             # NEW
│   │   ├── test_orchestrator.py
│   │   └── test_scheduler.py
│   ├── config/                    # NEW - consolidated
│   │   ├── test_loader.py
│   │   └── test_models.py
│   ├── build/                     # NEW - split from test_build_agent.py
│   │   ├── test_packaging.py
│   │   ├── test_metadata.py
│   │   └── test_validation.py
│   ├── governance/                # NEW - extracted from lead_agent
│   │   ├── test_approval.py
│   │   ├── test_escalation.py
│   │   └── test_coordination.py
│   ├── adapters/                  # EXISTS
│   ├── core/                      # EXISTS
│   ├── memory/                    # EXISTS
│   ├── llm/                       # EXISTS
│   ├── embeddings/                # EXISTS
│   ├── tasks/                     # EXISTS - consolidated
│   ├── telemetry/                 # EXISTS
│   ├── tools/                     # EXISTS
│   ├── prompts/                   # EXISTS
│   └── cycle_data/                # EXISTS
├── integration/
│   ├── conftest.py                # Service fixtures
│   ├── agents/                    # NEW
│   ├── capabilities/              # EXISTS
│   ├── api/                       # NEW
│   ├── adapters/                  # EXISTS
│   └── prompts/                   # EXISTS
├── regression/                    # EXISTS
└── smoke/                         # EXISTS
```

---

## 7. Scoped Test Execution

The domain-based directory structure enables **scoped test runs** — running only the tests relevant to what changed, rather than the full suite of ~800 tests on every change.

### 7.1 Domain-Based Test Selection

```bash
# Full suite (CI, pre-merge)
pytest tests/unit/ -v                           # ~800 tests, 60-90s

# Scoped runs (development)
pytest tests/unit/agents/ -v                    # ~250 tests, 15-20s
pytest tests/unit/agents/roles/test_lead.py    # ~50 tests, 5s
pytest tests/unit/capabilities/ -v              # ~80 tests, 5-10s
pytest tests/unit/memory/ -v                    # ~100 tests, 8-12s
pytest tests/unit/api/ -v                       # ~40 tests, 3-5s
pytest tests/unit/config/ -v                    # ~30 tests, 2-3s
```

### 7.2 Domain Markers

Each domain directory will have a `conftest.py` that auto-marks tests:

```python
# tests/unit/agents/conftest.py
import pytest
from pathlib import Path

def pytest_collection_modifyitems(config, items):
    """Auto-mark tests in this directory with domain_agents marker."""
    agents_dir = Path(__file__).parent
    for item in items:
        # Only mark items actually in this directory (avoid double-marking)
        if agents_dir in Path(item.fspath).parents:
            item.add_marker(pytest.mark.domain_agents)
```

**Available markers after migration:**

| Marker | Directory | Est. Tests | Est. Time |
|--------|-----------|------------|-----------|
| `@pytest.mark.domain_agents` | `unit/agents/` | ~250 | 15-20s |
| `@pytest.mark.domain_capabilities` | `unit/capabilities/` | ~80 | 5-10s |
| `@pytest.mark.domain_skills` | `unit/skills/` | ~60 | 5-8s |
| `@pytest.mark.domain_api` | `unit/api/` | ~40 | 3-5s |
| `@pytest.mark.domain_memory` | `unit/memory/` | ~100 | 8-12s |
| `@pytest.mark.domain_config` | `unit/config/` | ~30 | 2-3s |
| `@pytest.mark.domain_build` | `unit/build/` | ~80 | 10-15s |
| `@pytest.mark.domain_governance` | `unit/governance/` | ~40 | 3-5s |
| `@pytest.mark.domain_orchestration` | `unit/orchestration/` | ~30 | 3-5s |
| `@pytest.mark.domain_adapters` | `unit/adapters/` | ~60 | 5-8s |
| `@pytest.mark.domain_telemetry` | `unit/telemetry/` | ~30 | 2-3s |

**Usage:**

```bash
# Run by marker
pytest -m domain_agents -v
pytest -m "domain_agents or domain_capabilities" -v

# Exclude slow domains during rapid iteration
pytest tests/unit/ -m "not domain_build" -v
```

### 7.3 Change-Based Test Selection

For even finer-grained selection, map code changes to test domains:

| Changed File Pattern | Run Tests |
|---------------------|-----------|
| `src/squadops/agents/roles/lead.py` | `tests/unit/agents/roles/test_lead.py` |
| `src/squadops/agents/*.py` | `tests/unit/agents/` |
| `src/squadops/capabilities/**` | `tests/unit/capabilities/` |
| `src/squadops/api/**` | `tests/unit/api/` |
| `src/squadops/ports/memory/**` | `tests/unit/memory/` |
| `adapters/memory/**` | `tests/unit/memory/` |
| `src/squadops/config/**` | `tests/unit/config/` |

**Script example (`scripts/dev/run_affected_tests.sh`):**

```bash
#!/bin/bash
# Run tests affected by changes
# Usage:
#   ./run_affected_tests.sh           # Staged changes (pre-commit)
#   ./run_affected_tests.sh --staged  # Staged changes explicitly
#   ./run_affected_tests.sh --branch  # All changes vs main (pre-push)
#   ./run_affected_tests.sh --all     # Staged + unstaged (working dir)

set -e

MODE="${1:---staged}"

case "$MODE" in
    --staged)
        CHANGED_FILES=$(git diff --cached --name-only)
        ;;
    --branch)
        CHANGED_FILES=$(git diff --name-only origin/main...HEAD)
        ;;
    --all)
        CHANGED_FILES=$(git diff --name-only HEAD)
        ;;
    *)
        echo "Usage: $0 [--staged|--branch|--all]"
        exit 1
        ;;
esac

if [ -z "$CHANGED_FILES" ]; then
    echo "No changes detected"
    exit 0
fi

# Collect test paths (will dedupe later)
declare -a TEST_PATHS

add_tests() {
    local pattern="$1"
    local test_dir="$2"
    if echo "$CHANGED_FILES" | grep -qE "$pattern"; then
        TEST_PATHS+=("$test_dir")
    fi
}

# Map source changes to test directories
add_tests "src/squadops/agents/" "tests/unit/agents/"
add_tests "src/squadops/capabilities/" "tests/unit/capabilities/"
add_tests "src/squadops/api/" "tests/unit/api/"
add_tests "src/squadops/config/" "tests/unit/config/"
add_tests "src/squadops/orchestration/" "tests/unit/orchestration/"
add_tests "adapters/memory|src/squadops/ports/memory" "tests/unit/memory/"
add_tests "adapters/llm|src/squadops/ports/llm" "tests/unit/llm/"
add_tests "adapters/telemetry|src/squadops/ports/telemetry" "tests/unit/telemetry/"

# Dedupe test paths
UNIQUE_TESTS=$(printf "%s\n" "${TEST_PATHS[@]}" | sort -u | tr '\n' ' ')

if [ -z "$UNIQUE_TESTS" ]; then
    echo "No matching test mappings found"
    echo "Changed files:"
    echo "$CHANGED_FILES" | head -10
    exit 0
fi

echo "Mode: $MODE"
echo "Running affected tests: $UNIQUE_TESTS"
pytest $UNIQUE_TESTS -v "$@"
```

### 7.4 Recommended Workflows

| Scenario | Command | Tests | Time |
|----------|---------|-------|------|
| Rapid iteration on single file | `pytest tests/unit/agents/roles/test_lead.py -v` | ~50 | 5s |
| Working on a domain | `pytest tests/unit/capabilities/ -v` | ~80 | 8s |
| Pre-commit check | `./scripts/dev/run_affected_tests.sh` | ~100-200 | 15-30s |
| Pre-push validation | `pytest tests/unit/ -v` | ~800 | 60-90s |
| CI/CD pipeline | `pytest tests/ -v` | ~900 | 90-120s |

### 7.5 pytest.ini Configuration

Update `pytest.ini` (or `pyproject.toml`) to register domain markers:

```ini
[pytest]
markers =
    unit: Unit tests (mocked dependencies)
    integration: Integration tests (real services)
    regression: Regression tests
    domain_agents: Agent domain tests
    domain_capabilities: Capability domain tests
    domain_skills: Skill domain tests
    domain_api: API domain tests
    domain_memory: Memory domain tests
    domain_config: Config domain tests
    domain_build: Build/packaging domain tests
    domain_governance: Governance domain tests
    domain_orchestration: Orchestration domain tests
    domain_adapters: Adapter domain tests
    domain_telemetry: Telemetry domain tests
```

### 7.6 Definition of Done for Scoped Execution

- [ ] All domain `conftest.py` files created with auto-markers
- [ ] `pytest.ini` updated with domain markers
- [ ] `scripts/dev/run_affected_tests.sh` implemented
- [ ] CLAUDE.md updated with scoped test commands
- [ ] All domain markers verified working

---

## 8. Migration Phases

### Phase 1: Compatibility Shim (Pre-0.8.9)

**Timing:** During SIP-0.8.8, before `_v0_legacy/` deletion

> **Warning:** The `sys.modules` approach is fragile (subtle import semantics, package resolution issues). Prefer migrating in small passing slices if tolerable. If shim is needed, make it loud and temporary.

**Option A (Preferred): Migrate in slices**
- Migrate tests incrementally alongside production code
- Each PR updates imports in affected test files
- No shim needed; tests always pass against current code

**Option B: Temporary re-export package**
Create `tests/_compat/agents/__init__.py` that explicitly re-exports:

```python
# tests/_compat/agents/__init__.py
# TEMPORARY: Remove after 0.8.9 migration complete
# This package provides legacy import paths for test migration

import warnings
warnings.warn(
    "Importing from tests._compat.agents is deprecated. "
    "Migrate to squadops.agents imports.",
    DeprecationWarning,
    stacklevel=2
)

from squadops.agents.base import BaseAgent
from squadops.agents.factory import AgentFactory
# ... explicit re-exports only for what's needed
```

Then in `conftest.py`:
```python
import sys
sys.path.insert(0, str(Path(__file__).parent / "_compat"))
```

**Option C: sys.modules shim (last resort)**
If used, add explicit warnings and limit scope:

```python
# tests/conftest.py - TEMPORARY SHIM
import warnings
import sys

_LEGACY_MAPPINGS = {
    'agents': 'squadops.agents',
    'agents.base_agent': 'squadops.agents.base',
    # ... explicit list, no wildcards
}

for old, new in _LEGACY_MAPPINGS.items():
    warnings.warn(f"Legacy import '{old}' mapped to '{new}' - migrate tests!", DeprecationWarning)
    sys.modules[old] = __import__(new, fromlist=[''])
```

**Deliverable:** Tests continue passing against migrated production code.

### Phase 2: Pruning

1. Delete Category A tests (legacy patterns) - ~3,800 lines
2. Delete Category B superseded tests (partial) - ~3,200 lines
3. Delete Category C tests (retired flows) - ~1,000 lines
4. Run test suite, verify no regressions
5. Update CI metrics

**Deliverable:** ~15-19 test files deleted, ~8,000 lines removed.

### Phase 3: Split conftest.py

Split early to reduce blast radius during migration:

```
tests/
├── conftest.py              # Minimal: markers, event loop, path setup
├── unit/
│   └── conftest.py          # Unit fixtures: mocks, sample data
└── integration/
    └── conftest.py          # Integration fixtures: containers, cleanup
```

1. Extract unit fixtures to `tests/unit/conftest.py`
2. Keep integration fixtures in `tests/integration/conftest.py` (already exists)
3. Reduce root `conftest.py` to shared config only
4. Domain-level conftests only when truly needed (avoid proliferation)

**Deliverable:** conftest.py reduced from 652 lines to ~100 lines.

### Phase 4: Directory Restructure

Use `git mv` to preserve history and avoid formatting churn:

```bash
# Create structure first
mkdir -p tests/unit/agents/roles
mkdir -p tests/unit/skills
mkdir -p tests/unit/api

# Move with git mv (preserves history)
git mv tests/unit/test_lead_agent.py tests/unit/agents/roles/test_lead.py
git mv tests/unit/test_dev_agent.py tests/unit/agents/roles/test_dev.py
# ... etc

# Commit structure changes separately from content changes
git commit -m "refactor(tests): restructure test directories"
```

1. Create new directory structure (`unit/agents/`, `unit/skills/`, etc.)
2. Move tests using `git mv` (no content changes in this phase)
3. Update CI test discovery patterns
4. Commit structure changes separately

**Deliverable:** Tests organized by domain, git history preserved.

### Phase 5: Reconciliation + Import Migration

Combine reconciliation and import updates (now easier with domain-aligned structure):

1. Merge `test_base_agent.py` → `test_base_agent_aci_contract.py`
2. Consolidate config tests
3. Consolidate task/message tests
4. Split `test_build_agent.py` into modules
5. Extract governance tests from `test_lead_agent.py`
6. Update all `from agents.*` → `from squadops.agents.*`
7. Update all `from infra.*` → `from squadops.config.*`
8. Update conftest.py fixtures
9. Remove compatibility shim (if used)

**Deliverable:** Redundancy eliminated, zero legacy imports.

### Phase 6: CI Gate + Documentation

1. Add CI gate for no legacy imports:
   ```yaml
   # .github/workflows/ci.yml
   - name: Check no legacy imports
     run: |
       if rg "from agents\.|from infra\.|from _v0_legacy" tests/ --type py; then
         echo "ERROR: Legacy imports found in tests"
         exit 1
       fi
   ```
2. Remove empty directories
3. Update test documentation
4. Update CLAUDE.md test section
5. Final CI verification (3 consecutive passes)

**Deliverable:** Test suite modernization complete, CI enforces no legacy imports.

### Phase 7: Health Check Refactor & Stack Validation Integration Test

The Health Check app serves as the **ultimate integration verification** — if you can chat with agents through the console, the entire migrated stack is working.

#### 7.1 Health Check App Refactor

**Current state:** `_v0_legacy/infra/health-check/main.py` (2,716 lines, monolithic)

**Target state:** Modular routes in `src/squadops/api/`

```
src/squadops/api/
├── app.py                    # Main FastAPI app (or extend existing)
├── routes/
│   ├── health.py             # Infrastructure health endpoints
│   ├── agents.py             # Agent status & heartbeat endpoints
│   ├── console.py            # Console session & agent chat
│   └── warmboot.py           # WarmBoot form & status
├── templates/
│   └── health_dashboard.html # Existing UI (minimal changes)
└── deps.py                   # Port injection (DbRuntime, QueuePort)
```

**Refactor tasks:**

| Task | Description |
|------|-------------|
| Split `main.py` | Extract routes into domain modules |
| Update config imports | `infra.config.loader` → `squadops.config.loader` |
| Update version imports | `config.version` → `squadops.__version__` |
| Inject `DbRuntime` | Replace direct asyncpg with port |
| Inject `QueuePort` | Replace direct pika/aio_pika with port |
| Async response consumer | Refactor blocking pika to aio_pika |
| Move templates | `_v0_legacy/infra/health-check/templates/` → `src/squadops/api/templates/` |
| Update Dockerfile | New paths, remove legacy deps |
| Update docker-compose | Point to new Dockerfile location |

#### 7.2 Stack Validation Integration Test

This test verifies the complete post-migration stack:

```python
# tests/integration/test_stack_validation.py
"""
Stack Validation Integration Test

Verifies the complete SquadOps stack post-migration:
1. Infrastructure services running (Postgres, Redis, RabbitMQ)
2. Agent containers built with new architecture
3. Agents online and reporting heartbeats
4. Agent console chat functional (full A2A round-trip)

This is the ultimate gate for SIP-0.8.8 + SIP-0.8.9 completion.
"""

import os
import uuid
import pytest
import httpx
import asyncio

# Configurable via environment for different environments
BASE_URL = os.environ.get("HEALTH_CHECK_URL", "http://localhost:8000")
AGENT_ONLINE_TIMEOUT = int(os.environ.get("AGENT_ONLINE_TIMEOUT", "60"))
CHAT_RESPONSE_TIMEOUT = int(os.environ.get("CHAT_RESPONSE_TIMEOUT", "30"))


async def wait_until_healthy(client: httpx.AsyncClient, timeout: int = 30) -> bool:
    """Wait until health-check service reports all dependencies healthy."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await client.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                # Check core dependencies (not just HTTP 200)
                if all(data.get(svc, {}).get("status") == "ok"
                       for svc in ["postgres", "redis", "rabbitmq"]):
                    return True
        except httpx.RequestError:
            pass
        await asyncio.sleep(2)
    return False


async def wait_for_agents_online(client: httpx.AsyncClient, timeout: int = 60) -> list:
    """Wait until at least one agent is online."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await client.get(f"{BASE_URL}/health/agents")
            if resp.status_code == 200:
                agents = resp.json()
                online = [a for a in agents if a["network_status"] == "online"]
                if online:
                    return online
        except httpx.RequestError:
            pass
        await asyncio.sleep(3)
    return []


@pytest.mark.integration
@pytest.mark.stack_validation
class TestStackValidation:
    """End-to-end stack validation tests."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Ensure health-check service and dependencies are ready."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            healthy = await wait_until_healthy(client, timeout=30)
            if not healthy:
                pytest.skip("Health-check service not ready")

    async def test_infrastructure_healthy(self):
        """Verify all infrastructure components are healthy."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BASE_URL}/health")
            data = resp.json()

            assert data["postgres"]["status"] == "ok", "Postgres unhealthy"
            assert data["redis"]["status"] == "ok", "Redis unhealthy"
            assert data["rabbitmq"]["status"] == "ok", "RabbitMQ unhealthy"

    async def test_agents_online(self):
        """Verify at least one agent is online and reporting heartbeats."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            online_agents = await wait_for_agents_online(client, AGENT_ONLINE_TIMEOUT)
            assert len(online_agents) >= 1, (
                f"No agents online after {AGENT_ONLINE_TIMEOUT}s. "
                "Ensure agent containers are running."
            )

            # Verify agents have valid lifecycle state
            for agent in online_agents:
                assert agent["lifecycle_state"] != "UNKNOWN", (
                    f"Agent {agent['agent_name']} has UNKNOWN lifecycle state"
                )

    async def test_agent_console_chat_roundtrip(self):
        """
        Complete agent chat round-trip validation.

        1. Create console session
        2. Bind to an online agent
        3. Send a message with correlation ID
        4. Poll for response by correlation ID
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Wait for agents
            online_agents = await wait_for_agents_online(client, AGENT_ONLINE_TIMEOUT)
            assert len(online_agents) >= 1, "No agents available for chat"
            target_agent = online_agents[0]["agent_name"]

            # 2. Create session
            resp = await client.post(f"{BASE_URL}/console/session")
            assert resp.status_code == 200
            session = resp.json()
            session_id = session["session_id"]

            try:
                # 3. Bind to agent (enter chat mode)
                resp = await client.post(
                    f"{BASE_URL}/console/chat/{session_id}",
                    json={"message": f"/chat {target_agent}"}
                )
                assert resp.status_code == 200

                # 4. Send a message with unique correlation ID for tracking
                correlation_id = str(uuid.uuid4())[:8]
                test_message = f"Stack validation ping [{correlation_id}]"

                resp = await client.post(
                    f"{BASE_URL}/console/chat/{session_id}",
                    json={"message": test_message}
                )
                assert resp.status_code == 200

                # 5. Poll for response containing our correlation ID
                response_received = False
                poll_interval = 2
                max_attempts = CHAT_RESPONSE_TIMEOUT // poll_interval

                for attempt in range(max_attempts):
                    await asyncio.sleep(poll_interval)
                    resp = await client.get(
                        f"{BASE_URL}/console/responses/{session_id}"
                    )
                    if resp.status_code == 200:
                        responses = resp.json()
                        # Look for response that references our correlation ID
                        for r in responses:
                            content = r.get("content", "")
                            if correlation_id in content or "pong" in content.lower():
                                response_received = True
                                break
                    if response_received:
                        break

                assert response_received, (
                    f"Agent {target_agent} did not respond within {CHAT_RESPONSE_TIMEOUT}s. "
                    f"Correlation ID: {correlation_id}"
                )

            finally:
                # 6. Always exit chat mode (cleanup)
                await client.post(
                    f"{BASE_URL}/console/chat/{session_id}",
                    json={"message": "/exit"}
                )

    async def test_warmboot_form_accessible(self):
        """Verify WarmBoot form is accessible."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{BASE_URL}/")
            assert resp.status_code == 200
            assert b"WarmBoot" in resp.content
```

#### 7.3 Running the Stack Validation Test

```bash
# Prerequisites
docker-compose up -d postgres redis rabbitmq prefect-server

# Build and start agents (post-0.8.8 migration)
python scripts/dev/build_agent.py lead
python scripts/dev/build_agent.py dev
docker-compose up -d max neo

# Start health-check service
docker-compose up -d health-check

# Wait for agents to come online
sleep 30

# Run stack validation test
pytest tests/integration/test_stack_validation.py -v -m stack_validation

# Or run via marker
pytest -m stack_validation -v
```

#### 7.4 Health Check Refactor Checklist

- [ ] Split `main.py` into `routes/health.py`, `routes/agents.py`, `routes/console.py`
- [ ] Update all `infra.config.*` imports to `squadops.config.*`
- [ ] Update `config.version` imports to `squadops.__version__`
- [ ] Inject `DbRuntime` port for database access
- [ ] Inject `QueuePort` for RabbitMQ access
- [ ] Refactor response consumer to async (aio_pika)
- [ ] Move templates to `src/squadops/api/templates/`
- [ ] Update Dockerfile paths
- [ ] Update docker-compose.yml service definition
- [ ] Zero imports from `_v0_legacy/`

#### 7.5 Stack Validation Test Checklist

- [ ] `tests/integration/test_stack_validation.py` created
- [ ] `@pytest.mark.stack_validation` marker registered
- [ ] Infrastructure health test passing
- [ ] Agents online test passing
- [ ] **Agent console chat round-trip test passing**
- [ ] WarmBoot form accessible test passing
- [ ] CI includes stack validation as gate (optional, requires running agents)

**Deliverable:** Health Check refactored, Stack Validation test green.

### Phase 8: Build Infrastructure Cleanup

The agent build process has residual `_v0_legacy/` dependencies that need cleanup after SIP-0.8.8 migration.

#### 8.1 Build Script Updates

**File:** `scripts/dev/build_agent.py` (736 lines)

| Area | Current | Change |
|------|---------|--------|
| Line 518 | `legacy_root = base_path / "_v0_legacy"` | Point to `src/squadops` |
| Lines 166-259 | DDD bridge generation | Remove entirely (no longer needed) |
| Lines 522-524 | Agent role paths | Update to `src/squadops/agents/roles/` |
| Lines 573-592 | `shared_dirs` references | Update to new structure |
| Lines 623-640 | Skills paths | Update to `src/squadops/agents/skills/` |
| Line 666 | Config directory copy | Update to `src/squadops/config/` |

**Key removals:**
```python
# Remove DDD bridge generation (lines 166-259)
def ensure_ddd_bridge(dist_dir):
    # This entire function becomes unnecessary
    pass
```

#### 8.2 Agent Dockerfile Updates

All 11 agent Dockerfiles need updates:

**Current (legacy):**
```dockerfile
# Stage 1: Builder
COPY _v0_legacy/ ./_v0_legacy/
COPY src/ ./src/
COPY scripts/dev/build_agent.py ./scripts/build_agent.py
```

**Updated (post-migration):**
```dockerfile
# Stage 1: Builder - simplified, no legacy copy
COPY src/ ./src/
COPY adapters/ ./adapters/
COPY scripts/dev/build_agent.py ./scripts/build_agent.py
```

**Files to update:**
- `src/squadops/agents/roles/lead/Dockerfile`
- `src/squadops/agents/roles/dev/Dockerfile`
- `src/squadops/agents/roles/qa/Dockerfile`
- `src/squadops/agents/roles/data/Dockerfile`
- `src/squadops/agents/roles/strat/Dockerfile`
- Mock agents: `comms`, `creative`, `finance`, `curator`, `audit`

#### 8.3 docker-compose.yml Standardization

**Current inconsistency:**
```yaml
# Functional agents - legacy paths
dockerfile: _v0_legacy/agents/roles/lead/Dockerfile

# Mock agents - non-existent paths!
dockerfile: agents/roles/creative/Dockerfile  # File doesn't exist
```

**Standardized (post-migration):**
```yaml
# All agents use consistent new paths
max:
  build:
    context: .
    dockerfile: src/squadops/agents/roles/lead/Dockerfile
    args:
      AGENT_ROLE: lead

neo:
  build:
    context: .
    dockerfile: src/squadops/agents/roles/dev/Dockerfile
    args:
      AGENT_ROLE: dev
```

**Services to update:**
- `max` (lead) - line 191
- `neo` (dev) - line 263
- `eve` (qa) - line 294
- `nat` (strat) - line 220
- `data` (data) - line 318
- `glyph` (creative) - line 244
- `quark` (finance) - line 347
- `joi` (comms) - line 366
- `og` (curator) - line 385
- `hal` (audit) - line 404

#### 8.4 Infrastructure Dockerfile Updates

**Health Check** (`src/squadops/api/` post-refactor):
```dockerfile
# Remove legacy paths
# COPY agents/instances ./agents/instances  # OLD
# COPY agents/utils ./agents/utils          # OLD

# Use new structure
COPY src/squadops/ ./squadops/
COPY adapters/ ./adapters/
```

**Runtime API** (if still separate):
```dockerfile
# Remove legacy paths
# COPY agents/tasks ./agents/tasks  # OLD

# Use new structure
COPY src/squadops/tasks/ ./squadops/tasks/
```

#### 8.5 Non-Python Config Migration

Move infrastructure configs from `_v0_legacy/infra/` to root `infra/`:

```bash
# Already done in SIP-0.8.8, verify paths in docker-compose.yml
git mv _v0_legacy/infra/grafana infra/grafana
git mv _v0_legacy/infra/prometheus infra/prometheus
git mv _v0_legacy/infra/otel-collector infra/otel-collector
git mv _v0_legacy/infra/migrations infra/migrations
git mv _v0_legacy/infra/init.sql infra/init.sql
```

**docker-compose.yml volume updates:**
```yaml
# OLD
- ./_v0_legacy/infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml

# NEW
- ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
```

#### 8.6 Build Infrastructure Checklist

- [ ] `scripts/dev/build_agent.py` updated to `src/squadops/` paths
- [ ] DDD bridge generation removed (lines 166-259)
- [ ] All agent Dockerfiles updated (11 files)
- [ ] Mock agent Dockerfiles created or consolidated
- [ ] `docker-compose.yml` paths standardized
- [ ] Infrastructure Dockerfiles updated (health-check, runtime-api)
- [ ] Non-Python config paths verified (`infra/`)
- [ ] All agent containers build successfully
- [ ] All agent containers start and report heartbeats
- [ ] CI build pipeline passes

**Deliverable:** Build infrastructure fully migrated, no `_v0_legacy/` references remain.

### Phase 9: Legacy Directory Deletion

Final step: safely delete `_v0_legacy/` after all verification passes.

#### 9.1 Pre-Deletion Verification Script

Create `scripts/dev/verify_legacy_removal.sh`:

```bash
#!/bin/bash
# scripts/dev/verify_legacy_removal.sh
# Run this before deleting _v0_legacy/
# Exit code 0 = safe to delete, non-zero = legacy references remain

set -e
echo "=== Verifying safe to delete _v0_legacy/ ==="

ERRORS=0

check_imports() {
    local dir="$1"
    local name="$2"
    echo "Checking $name for legacy imports..."
    if rg "from _v0_legacy|import _v0_legacy" "$dir" --type py 2>/dev/null; then
        echo "  ERROR: Direct _v0_legacy imports found in $name"
        ERRORS=$((ERRORS + 1))
    elif rg "^from agents\.|^import agents\." "$dir" --type py 2>/dev/null; then
        echo "  ERROR: Legacy agents.* imports found in $name"
        ERRORS=$((ERRORS + 1))
    elif rg "^from infra\.|^import infra\." "$dir" --type py 2>/dev/null; then
        echo "  ERROR: Legacy infra.* imports found in $name"
        ERRORS=$((ERRORS + 1))
    else
        echo "  ✓ No legacy imports in $name"
    fi
}

echo ""
echo "=== Step 1: Check Python imports ==="
check_imports "src/" "src/"
check_imports "adapters/" "adapters/"
check_imports "tests/" "tests/"
check_imports "scripts/" "scripts/"

echo ""
echo "=== Step 2: Check build script ==="
if rg "_v0_legacy" scripts/dev/build_agent.py 2>/dev/null; then
    echo "  ERROR: Legacy references in build_agent.py"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ No legacy references in build_agent.py"
fi

echo ""
echo "=== Step 3: Check Dockerfiles ==="
# Find Dockerfiles outside _v0_legacy
DOCKERFILES=$(find . -name "Dockerfile" -not -path "./_v0_legacy/*" -not -path "./.git/*" 2>/dev/null)
if [ -n "$DOCKERFILES" ]; then
    if echo "$DOCKERFILES" | xargs rg "_v0_legacy" 2>/dev/null; then
        echo "  ERROR: Legacy references in Dockerfiles"
        ERRORS=$((ERRORS + 1))
    else
        echo "  ✓ No legacy references in Dockerfiles"
    fi
else
    echo "  ✓ No Dockerfiles to check (outside _v0_legacy)"
fi

echo ""
echo "=== Step 4: Check docker-compose.yml ==="
if rg "_v0_legacy" docker-compose.yml 2>/dev/null; then
    echo "  ERROR: Legacy references in docker-compose.yml"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ No legacy references in docker-compose.yml"
fi

echo ""
echo "=== Step 5: Check pyproject.toml ==="
if rg "_v0_legacy" pyproject.toml 2>/dev/null; then
    echo "  ERROR: Legacy references in pyproject.toml"
    ERRORS=$((ERRORS + 1))
else
    echo "  ✓ No legacy references in pyproject.toml"
fi

echo ""
echo "=========================================="
if [ $ERRORS -gt 0 ]; then
    echo "FAILED: $ERRORS legacy reference(s) found"
    echo "Fix the above issues before deleting _v0_legacy/"
    exit 1
else
    echo "PASSED: All checks passed"
    echo ""
    echo "Safe to delete _v0_legacy/"
    echo ""
    echo "To delete, run:"
    echo "  git rm -r _v0_legacy/"
    echo "  git commit -m 'chore: remove _v0_legacy/ directory (migration complete)'"
    echo ""
    echo "To recover later if needed:"
    echo "  git log --all --full-history -- _v0_legacy/"
    echo "  git checkout <commit-hash>^ -- _v0_legacy/"
    exit 0
fi
```

#### 9.2 Deletion Process

```bash
# 1. Run verification (must pass)
./scripts/dev/verify_legacy_removal.sh

# 2. Run full test suite one more time
pytest tests/ -v

# 3. Run stack validation
pytest tests/integration/test_stack_validation.py -v

# 4. Delete the legacy directory
git rm -r _v0_legacy/

# 5. Commit with descriptive message
git commit -m "$(cat <<'EOF'
chore: remove _v0_legacy/ directory

Migration complete per SIP-0.8.8 and SIP-0.8.9.

All code has been migrated to:
- src/squadops/ (domain code)
- adapters/ (adapter implementations)
- infra/ (non-Python configs)

To recover if needed:
  git checkout HEAD^ -- _v0_legacy/

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

# 6. Verify build still works
docker-compose build max neo eve
docker-compose up -d max neo eve
./scripts/dev/verify_legacy_removal.sh  # Should still pass (no _v0_legacy to find)
```

#### 9.3 Post-Deletion Verification

After deletion, verify everything still works:

```bash
# Full CI-equivalent check
pytest tests/unit/ -v                    # All unit tests
pytest tests/integration/ -v             # All integration tests
docker-compose build                     # All containers build
docker-compose up -d                     # All services start
pytest -m stack_validation -v            # Stack validation passes
```

#### 9.4 Legacy Deletion Checklist

- [ ] `verify_legacy_removal.sh` script created
- [ ] Verification script passes (exit code 0)
- [ ] Full test suite passes
- [ ] Stack validation test passes
- [ ] `git rm -r _v0_legacy/` executed
- [ ] Commit created with recovery instructions
- [ ] Post-deletion build verification passes
- [ ] Post-deletion test suite passes
- [ ] CI pipeline passes for 3 consecutive runs

**Deliverable:** `_v0_legacy/` deleted, full git history preserved for recovery.

---

## 9. Risk Mitigation

### 9.1 Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking tests during migration | CI failures | Compatibility shim first, migrate incrementally |
| Losing coverage | Bugs in production | Track coverage metrics, require ≥ current |
| Merge conflicts | Development slowdown | Coordinate with feature work, use feature flags |
| Missing edge cases | Regressions | Review pruned tests for unique cases before deletion |

### 9.2 Rollback Strategy

If critical issues arise:
1. Git revert migration commits
2. Re-enable compatibility shim
3. Document issues for retry

### 9.3 Coverage Tracking

Maintain coverage metrics throughout. Note that deleting legacy tests can shift global coverage unpredictably, so track **per-package** coverage:

```bash
# Before migration baseline (per-package)
pytest tests/ --cov=src/squadops --cov=adapters \
    --cov-report=term-missing \
    --cov-report=json:coverage_baseline.json

# After each phase (per-package)
pytest tests/ --cov=src/squadops --cov=adapters \
    --cov-report=term-missing \
    --cov-report=json:coverage_phase_N.json

# Compare per-package (script)
python scripts/dev/compare_coverage.py coverage_baseline.json coverage_phase_N.json
```

**Per-package coverage script example:**
```python
# scripts/dev/compare_coverage.py
import json
import sys

def compare(baseline_file, current_file):
    baseline = json.load(open(baseline_file))["files"]
    current = json.load(open(current_file))["files"]

    regressions = []
    for pkg in ["src/squadops/agents", "src/squadops/capabilities", "adapters"]:
        baseline_pct = get_package_coverage(baseline, pkg)
        current_pct = get_package_coverage(current, pkg)
        if current_pct < baseline_pct - 1.0:  # 1% tolerance
            regressions.append(f"{pkg}: {baseline_pct:.1f}% -> {current_pct:.1f}%")

    if regressions:
        print("Coverage regressions detected:")
        for r in regressions:
            print(f"  - {r}")
        sys.exit(1)
    print("Coverage OK")
```

**Requirements:**
- Per-package coverage for core packages must not decrease >1% vs baseline
- Global coverage may shift due to test pruning (this is expected)
- Track deltas in PR descriptions for visibility

---

## 10. Definition of Done

### Pruning
- [ ] All Category A tests deleted (~3,800 lines)
- [ ] All Category B partial deletions complete (~3,200 lines)
- [ ] All Category C tests deleted (~1,000 lines)
- [ ] No test failures from deletions

### Reconciliation
- [ ] `test_base_agent.py` merged into `test_base_agent_aci_contract.py`
- [ ] Config tests consolidated
- [ ] Task tests consolidated
- [ ] `test_build_agent.py` split into modules
- [ ] Governance tests extracted from `test_lead_agent.py`
- [ ] No duplicate test coverage

### Migration
- [ ] All `from agents.*` imports updated
- [ ] All `from infra.*` imports updated
- [ ] `tests/conftest.py` modernized (no legacy imports)
- [ ] `tests/integration/conftest.py` modernized
- [ ] Compatibility shim removed

### Structure
- [ ] New directory structure implemented
- [ ] All tests in domain-appropriate locations
- [ ] Empty directories removed

### Verification
- [ ] Zero imports from legacy paths
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Coverage ≥ baseline
- [ ] CI passes for 3 consecutive runs

### Documentation
- [ ] CLAUDE.md test section updated
- [ ] Test markers documented
- [ ] Fixture documentation updated

### Scoped Execution
- [ ] All domain `conftest.py` files created with auto-markers
- [ ] `pytest.ini` / `pyproject.toml` updated with domain markers
- [ ] `scripts/dev/run_affected_tests.sh` implemented
- [ ] Domain marker coverage verified (all tests tagged)

### Health Check Refactor
- [ ] `main.py` split into modular routes (`health.py`, `agents.py`, `console.py`)
- [ ] All `infra.config.*` imports updated to `squadops.config.*`
- [ ] `DbRuntime` port injected for database access
- [ ] `QueuePort` injected for RabbitMQ access
- [ ] Response consumer refactored to async (aio_pika)
- [ ] Templates moved to `src/squadops/api/templates/`
- [ ] Dockerfile and docker-compose.yml updated
- [ ] Zero imports from `_v0_legacy/`

### Stack Validation Integration Test
- [ ] `tests/integration/test_stack_validation.py` created
- [ ] `@pytest.mark.stack_validation` marker registered
- [ ] Infrastructure health test passing
- [ ] Agents online test passing
- [ ] **Agent console chat round-trip test passing**
- [ ] WarmBoot form accessible test passing

### Build Infrastructure
- [ ] `scripts/dev/build_agent.py` updated to `src/squadops/` paths
- [ ] DDD bridge generation removed (lines 166-259)
- [ ] All agent Dockerfiles updated (11 files, no `_v0_legacy/` copies)
- [ ] Mock agent Dockerfiles created or consolidated
- [ ] `docker-compose.yml` paths standardized (all agents consistent)
- [ ] Infrastructure Dockerfiles updated (health-check, runtime-api)
- [ ] Non-Python config volume paths verified (`infra/`)
- [ ] All agent containers build successfully
- [ ] All agent containers start and report heartbeats

### Legacy Directory Deletion
- [ ] `scripts/dev/verify_legacy_removal.sh` created
- [ ] Verification script passes (exit code 0)
- [ ] Full test suite passes
- [ ] Stack validation test passes
- [ ] `git rm -r _v0_legacy/` executed
- [ ] Commit includes recovery instructions
- [ ] Post-deletion build verification passes
- [ ] CI pipeline passes for 3 consecutive runs
- [ ] `_v0_legacy/` no longer exists in working tree

---

## 11. Metrics Summary

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Test files | 121 | ~95 | -26 |
| Test lines | ~37,000 | ~30,000 | -7,000 |
| Legacy imports | 80 files | 0 | -80 |
| Avg file size | 306 lines | 316 lines | +10 |
| Max file size | 10,518 lines | ~2,000 lines | -8,500 |
| Redundant coverage | ~15% | 0% | -15% |
| Domain markers | 0 | 11 | +11 |
| Min scoped run | N/A | ~5s | New capability |
| Typical dev iteration | 60-90s | 15-30s | -50% |
| Health Check (main.py) | 2,716 lines | ~800 lines (4 modules) | -70% |
| Stack Validation test | N/A | 1 test class | E2E verification |
| Build script (build_agent.py) | 736 lines | ~500 lines | -32% (DDD bridge removed) |
| Agent Dockerfiles | 11 files (mixed paths) | 11 files (consistent) | Standardized |
| `_v0_legacy/` references | ~50 locations | 0 | Fully removed |

---

## 12. Appendix: File-by-File Disposition

### A. Files to Delete (Prune)

| File | Lines | Reason |
|------|-------|--------|
| `test_warmboot_memory_handler.py` | 400 | Legacy pattern |
| `test_agent_message_model.py` | 300 | Replaced by TaskEnvelope |
| `test_task_message_model.py` | 250 | Duplicate |
| `test_loader.py` | 445 | Legacy loader |
| `test_capability_loader.py` | 600 | Replaced by CapabilityDispatcher |
| `test_skill_loader.py` | 350 | Replaced by SkillRegistry |
| `test_agent_specs.py` | 400 | Replaced by AgentRole |
| `test_llm_client_legacy.py` | 300 | Replaced by LLMPort |
| `test_config_legacy.py` | 350 | Legacy format |
| `test_task_queue_legacy.py` | 400 | Replaced by QueuePort |
| `test_legacy_agent_init.py` | 300 | Retired flow |
| `test_v0_config_profiles.py` | 400 | Retired format |
| `test_legacy_task_routing.py` | 300 | Retired flow |

### B. Files to Migrate (Import Updates Only)

| File | Lines | Complexity |
|------|-------|------------|
| `test_agent_factory.py` | 450 | Low |
| `test_governance_approval.py` | 300 | Low |
| `test_governance_escalation.py` | 300 | Low |
| `test_governance_task_coordination.py` | 300 | Low |
| `test_config_loader.py` | 735 | Low |
| `test_file_manager.py` | 668 | Low |
| `test_version_manager.py` | 542 | Low |

### C. Files to Migrate + Restructure

| File | Lines | Target Location |
|------|-------|-----------------|
| `test_lead_agent.py` | 3,897 | `unit/agents/roles/test_lead.py` (minus governance) |
| `test_dev_agent.py` | 1,192 | `unit/agents/roles/test_dev.py` |
| `test_qa_agent.py` | 5,656 | `unit/agents/roles/test_qa.py` |
| `test_data_agent.py` | 8,237 | `unit/agents/roles/test_data.py` |
| `test_strat_agent.py` | 5,656 | `unit/agents/roles/test_strat.py` |
| `test_base_agent_aci_contract.py` | 6,338 | `unit/agents/test_base.py` |
| `test_base_agent_memory.py` | 6,465 | `unit/agents/test_memory.py` |
| `test_build_agent.py` | 10,518 | `unit/build/test_*.py` (split) |

### D. Files to Keep As-Is

All files in:
- `tests/unit/adapters/`
- `tests/unit/capabilities/`
- `tests/unit/core/`
- `tests/unit/cycle_data/`
- `tests/unit/embeddings/`
- `tests/unit/llm/`
- `tests/unit/memory/`
- `tests/unit/prompts/`
- `tests/unit/tasks/`
- `tests/unit/telemetry/`
- `tests/unit/tools/`

These already follow new architecture patterns.

---

## 13. Changelog

| Date | Change |
|------|--------|
| 2026-02-01 | Initial plan created |
| 2026-02-01 | Added Section 7: Scoped Test Execution (domain markers, change-based selection) |
| 2026-02-01 | Added Phase 7: Health Check Refactor & Stack Validation Integration Test |
| 2026-02-01 | Added Health Check and Stack Validation sections to Definition of Done |
| 2026-02-01 | Review feedback: Fixed numbers discrepancy note, added safer shim options |
| 2026-02-01 | Review feedback: Fixed pytest hook signature (config, items), added path checking |
| 2026-02-01 | Review feedback: Made Stack Validation robust (env vars, wait helpers, correlation-id) |
| 2026-02-01 | Review feedback: Clarified per-package coverage tracking |
| 2026-02-01 | Review feedback: Added conftest split phase, git mv for restructure |
| 2026-02-01 | Review feedback: Improved run_affected_tests.sh (modes, deduping) |
| 2026-02-01 | Review feedback: Added CI gate for no legacy imports, fixed Category B in phases |
| 2026-02-01 | Review feedback: Resequenced phases (prune → split conftest → restructure → migrate) |
| 2026-02-01 | Added Phase 8: Build Infrastructure Cleanup (build_agent.py, Dockerfiles, docker-compose) |
| 2026-02-01 | Added Phase 9: Legacy Directory Deletion with verification script and recovery instructions |
