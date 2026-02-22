# SIP-0.8.7 Implementation Plan: Infrastructure Ports Migration

**Last Updated**: 2026-01-31 (rev 4)
**Status**: Planning (pre-implementation)

---

## Summary

Migrate remaining infrastructure from `_v0_legacy/` to hexagonal architecture:
- **5 Bounded Contexts**: Telemetry, LLM, Tools, Memory, Tasks
- **Pattern**: Domain models → Port interfaces → Adapters → Tests
- **Phased delivery**: 3 phases with validation checkpoints

---

## Implementation Strategy

Phased approach aligned with SIP Section 10.1 migration order:

| Phase | Contexts | Rationale |
|-------|----------|-----------|
| Phase 1 | Telemetry | No dependencies; enables observability for all subsequent phases |
| Phase 2 | Tools + LLM | Tools heavily used; LLM high-value (both depend on Telemetry) |
| Phase 3 | Memory + Tasks | Most complex; depends on all above |

**Note**: SIP §10.1 specifies Telemetry → Tools → Memory → LLM → Tasks. This plan groups contexts by dependency safety:
- **LLM with Tools (Phase 2)**: LLM depends only on Telemetry; does not rely on Tools/Memory. Safe to parallelize.
- **Tasks with Memory (Phase 3)**: Tasks depends on all above. Internal checkpoint: Memory adapters must pass integration tests before Tasks migration begins.

**Proposed SIP §10.1 clarification**: "Contexts may be implemented in parallel when dependencies permit; the listed order expresses dependency constraints, not a required sequence."

### Milestones

- After Phase 1: Promote SIP to accepted
- After Phase 3: Promote SIP to implemented, bump version to 0.8.7

### Phase Exit Criteria (SIP §8.3 gates)

| Phase | Exit (commit gate) | Release (0.8.7 tag gate) |
|-------|-------------------|--------------------------|
| Phase 1 | Unit tests green; deprecation shims in place; no new legacy imports | — |
| Phase 2 | Unit tests green; `scripts/ci/check_legacy_imports.py` enforced in CI | Integration tests for Ollama/Docker pass in CI |
| Phase 3 | Unit tests green; PostgreSQL integration pass | All integration tests pass; legacy imports match allowlist |

### Integration Test Policy

- **Exit phase**: Unit tests required; integration tests may be skipped locally
- **Before tagging 0.8.7**: Integration tests MUST pass in CI (or documented manual checklist)
- **Minimum**: at least one real environment verified (CI nightly or staging)

---

## Design Decisions

### Decision #1 — EventPort Span API Alignment

SIP defines `start_span()`/`end_span()` methods. Plan provides both:

```python
class EventPort(ABC):
    # SIP-specified methods (REQUIRED for adapters)
    @abstractmethod
    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None
    ) -> Span: ...

    @abstractmethod
    def end_span(self, span: Span) -> None: ...

    @abstractmethod
    def emit(self, event: StructuredEvent) -> None: ...

    # Convenience wrapper (NON-ABSTRACT, provided by port base for ergonomics)
    @contextmanager
    def span(self, name: str, attributes: dict[str, str] | None = None) -> Iterator[Span]:
        """Context manager wrapping start_span/end_span. Adapters do NOT implement this."""
        s = self.start_span(name, attributes=attributes)
        try:
            yield s
        finally:
            self.end_span(s)
```

**Adapter responsibility**: Adapters implement ONLY `emit`, `start_span`, `end_span`. The `span()` contextmanager is provided by the base class and tested to verify it calls start/end correctly with attributes passed through.

---

### Decision #2 — Factory + Secret Mechanism (SIP §7.6)

**Normative API clarification**:
- `SecretProvider` (from `src/squadops/ports/secrets.py`) is the port contract (ABC)
- `SecretManager` (from `src/squadops/core/secret_manager.py`) is the canonical façade that wraps providers
- Factories accept `SecretManager` (not raw `SecretProvider`)
- Remove/avoid "SecretStorePort" terminology to prevent contradiction

**Proposed SIP §7.6 amendment**: "Factories MUST resolve `secret://` refs via SecretManager (SIP-0054). SecretManager is the canonical façade; SecretProvider is the underlying provider contract."

**Factory secret requirements by domain**:

| Domain | Needs secrets? | Reason |
|--------|---------------|--------|
| Telemetry | No | OTel config is env vars; Console/Null have no secrets |
| LLM | Yes | Ollama URL may be `secret://` for cloud deployments |
| Tools | Yes | Docker registry auth, Git credentials |
| Memory | Yes | LanceDB path credentials (future S3 backend) |
| Tasks | Yes | PostgreSQL connection string |

```python
# adapters/llm/factory.py
from squadops.core.secret_manager import SecretManager

def create_llm_provider(
    provider: str = "ollama",
    secret_manager: SecretManager | None = None,
    **config
) -> LLMPort:
    """Create LLM provider, resolving secret:// refs via SecretManager."""
    base_url = config.get("base_url", "http://localhost:11434")
    if secret_manager and base_url.startswith("secret://"):
        base_url = secret_manager.resolve(base_url[9:])
    if provider == "ollama":
        return OllamaAdapter(base_url=base_url, **config)
    raise ValueError(f"Unknown LLM provider: {provider}")
```

---

### Decision #3 — Tools Path Validation Policy (SIP §7.2)

**Pattern**: Wrapper/decorator over adapters (composition over inheritance):

```python
# src/squadops/tools/security.py
from pathlib import Path

class PathSecurityError(Exception):
    """Raised when path validation fails."""
    pass

class PathSecurityPolicy:
    """Shared path validation for all tool ports."""

    def __init__(self, allowed_roots: tuple[Path, ...]):
        # REQUIRED: Must be explicitly configured, no default cwd
        if not allowed_roots:
            raise ValueError("allowed_roots must be explicitly configured")
        # Resolve roots once at construction (normalize for comparison)
        self._allowed_roots = tuple(root.resolve() for root in allowed_roots)

    def validate(self, path: Path) -> Path:
        """Validate and resolve path. Raises PathSecurityError on violation."""
        # Rule 0: Input MUST be absolute (no implicit cwd resolution)
        if not path.is_absolute():
            raise PathSecurityError(f"Path must be absolute, got relative: {path}")

        # Rule 1: No '..' segments in original path (before resolution)
        if ".." in path.parts:
            raise PathSecurityError(f"Path traversal not allowed: {path}")

        # Rule 2: Resolve symlinks for security check
        resolved = path.resolve()

        # Rule 3: Must be under allowed roots (symlinks resolved first)
        if not any(self._is_under(resolved, root) for root in self._allowed_roots):
            raise PathSecurityError(f"Path outside allowed roots: {path}")

        return resolved

    def _is_under(self, path: Path, root: Path) -> bool:
        """Check if path is under root. Both must be resolved absolute paths."""
        # Use is_relative_to (Python 3.9+) or fallback
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
```

**Enforcement via wrapper** (adapters remain simple):

```python
class PathValidatedFileSystem(FileSystemPort):
    """Wrapper that validates paths before delegating to underlying adapter."""

    def __init__(self, delegate: FileSystemPort, policy: PathSecurityPolicy):
        self._delegate = delegate
        self._policy = policy

    def read(self, path: Path) -> str:
        return self._delegate.read(self._policy.validate(path))
    # ... same pattern for write, exists, etc.
```

**Bypass prevention**:
- Rename raw adapter: `_UnsafeLocalFileSystemAdapter` (underscore prefix signals "internal only")
- Docstring: "DO NOT use directly; always wrap with PathValidatedFileSystem"
- Wiring exports only the validated wrapper (never the raw adapter)
- Unit test in wiring: Verify `infrastructure_bundle.filesystem` is `PathValidatedFileSystem` instance

**Runtime requirement**: `allowed_roots` MUST be configured explicitly (e.g., `repo_root`, `run_root`). Factory raises if not provided in production mode.

---

### Decision #4 — VCS Path Security

Reuse `PathSecurityPolicy` for `repo_path`. Wrapper pattern:

```python
class PathValidatedVCS(VersionControlPort):
    """Validates repo_path is under allowed_roots before any VCS action."""
```

- `repo_path` must be under `allowed_roots`
- VCS adapter operates on repo root only (subpaths validated via FileSystemPort)

---

### Decision #5 — Telemetry Non-Blocking Semantics

**Definition (testable contract)**:
1. **Must not perform network I/O on caller thread** (OTel uses batch processors with background export)
2. **Must not raise exceptions outward** (all adapters swallow and log internally)
3. **Must return quickly** (no retry loops, no unbounded waits)

**Adapter-specific rules**:
- **OTelAdapter**: Uses `BatchSpanProcessor` (not `SimpleSpanProcessor`); queue bounded (max 2048 items, 5s export interval); on overflow drop + increment `telemetry_dropped` counter
- **ConsoleAdapter**: **DEV MODE ONLY** — stdout writes can block (pipes, CI, logging handlers). Explicitly scoped to local development; not recommended for production. Best-effort blocking risk accepted.
- **NullAdapter**: Test-only; no-op implementation; does nothing

**Contract enforcement (unit tests required per adapter)**:

```python
# tests/unit/telemetry/test_adapters.py
import sys

# Test fixtures (to be implemented in conftest.py or test file)
class BrokenExporter:
    """Exporter that raises on every call."""
    def export(self, *args, **kwargs):
        raise RuntimeError("Simulated exporter failure")

class BrokenWriter:
    """File-like object that raises on write."""
    def write(self, *args):
        raise IOError("Simulated stdout failure")
    def flush(self):
        raise IOError("Simulated flush failure")

def test_otel_adapter_does_not_raise_on_exporter_failure():
    """OTelAdapter must swallow exceptions from broken exporter."""
    adapter = OTelAdapter(span_exporter=BrokenExporter(), metric_exporter=BrokenExporter())
    adapter.counter("test", 1)  # Must not raise
    adapter.emit(StructuredEvent(name="test", message="msg"))  # Must not raise

def test_console_adapter_does_not_raise_on_io_error():
    """ConsoleAdapter must swallow output stream errors."""
    adapter = ConsoleAdapter(output=BrokenWriter())
    adapter.counter("test", 1)  # Must not raise

def test_null_adapter_does_not_raise():
    """NullAdapter must be a no-op that never raises."""
    adapter = NullAdapter()
    adapter.counter("test", 1)
    adapter.emit(StructuredEvent(name="test", message="msg"))
```

---

### Decision #6 — TaskEnvelope Model Strategy (Lower-Risk Alternative)

**Risk**: Converting Pydantic → frozen dataclasses breaks existing code.

**Decision**: Keep Pydantic in `_v0_legacy`; create explicit compatibility bridge.

**Single-source type alias** (centralizes legacy import):

```python
# src/squadops/tasks/types.py
"""Compatibility bridge for 0.8.7. Full migration in 0.8.8."""
from _v0_legacy.agents.tasks.models import TaskEnvelope, TaskResult, TaskState, FlowState

__all__ = ["TaskEnvelope", "TaskResult", "TaskState", "FlowState"]
```

**Ports import from types.py** (not directly from legacy):

```python
# src/squadops/ports/tasks/registry.py
from squadops.tasks.types import TaskEnvelope  # Single import point

class TaskRegistryPort(ABC):
    @abstractmethod
    async def create(self, envelope: TaskEnvelope) -> str: ...
```

**CI rule**: Legacy imports are controlled by explicit allowlist in `check_legacy_imports.py`. The allowlist is the source of truth (uses **prefix matching**):
- `src/squadops/tasks/types.py` — TaskEnvelope compatibility bridge (`_v0_legacy.agents.tasks.models*`)
- `src/squadops/runtime/config.py` — UnifiedConfig typed view (`_v0_legacy.infra.config*`)
- `adapters/capabilities/aci_executor.py` — ACI integration (`_v0_legacy.agents.tasks.models*`)

Import linter enforces this for ALL code including tests. Any file not in the allowlist that imports from `_v0_legacy` will fail CI.

**Convention (enforced)**:
- ✅ `from squadops.tasks.types import TaskEnvelope`
- ❌ `from _v0_legacy.agents.tasks.models import TaskEnvelope`

**Formal compatibility note**: "In 0.8.7, TaskRegistryPort uses legacy TaskEnvelope as interim contract; 0.8.8 will introduce domain-native frozen dataclasses and eliminate legacy imports."

---

### Decision #7 — PrefectTaskAdapter Scope

**Decision**: Explicitly defer to 0.8.8.

**SIP Amendments**:
- Section 4 "Not Addressed": Add "PrefectTaskAdapter implementation (stub only; full implementation in 0.8.8)"
- Section 12 "Definition of Done": Change Prefect checkbox to "PrefectTaskAdapter stub present + raises NotImplementedError + documented deferral to 0.8.8"

**Implementation**:

```python
# adapters/tasks/prefect.py
"""Prefect adapter stub. Full implementation in 0.8.8.

IMPORTANT: This module MUST NOT import Prefect at module level.
Prefect is not a required dependency in 0.8.7.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from squadops.ports.tasks.registry import TaskRegistryPort
from squadops.tasks.types import TaskEnvelope, TaskState

# Only import Prefect for type hints (not at runtime)
if TYPE_CHECKING:
    pass  # Future: from prefect import ... for type hints only


class PrefectTaskAdapter(TaskRegistryPort):
    """Stub adapter for Prefect. Full implementation in 0.8.8.

    All methods raise NotImplementedError. This stub exists to:
    1. Reserve the adapter slot in the factory
    2. Allow type checking without runtime Prefect dependency
    3. Document the deferred scope
    """

    async def create(self, envelope: TaskEnvelope) -> str:
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")

    async def get(self, task_id: str) -> TaskEnvelope | None:
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")

    async def update_status(self, task_id: str, status: TaskState, result: dict | None = None) -> None:
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")

    async def list_pending(self, agent_id: str | None = None) -> list[TaskEnvelope]:
        raise NotImplementedError("PrefectTaskAdapter deferred to 0.8.8")
```

**No Prefect dependency**: The stub MUST NOT `import prefect` at module level. CI will fail if Prefect becomes a required dependency before 0.8.8.

**Tests**: Prefect integration tests marked `@pytest.mark.skip(reason="PrefectTaskAdapter deferred to 0.8.8")`

---

### Decision #8 — Deprecation Shims + CI Policy

**Staged approach**:

1. Phase 1: Add `DeprecationWarning` shims to legacy modules
2. CI Gate: Import linter with explicit allowlist

**Explicit enforcement scope (all paths checked)**:

```python
# scripts/ci/check_legacy_imports.py
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()

CHECKED_PATHS = [
    "src/",
    "adapters/",
    "tests/",
    "scripts/",  # if they import runtime modules
]

# Keys are repo-relative POSIX paths (normalized, no OS differences)
# Values are PREFIX patterns (any import starting with these is allowed)
ALLOWED_LEGACY_IMPORTS = {
    "src/squadops/tasks/types.py": ["_v0_legacy.agents.tasks.models"],
    "src/squadops/runtime/config.py": ["_v0_legacy.infra.config"],
    "adapters/capabilities/aci_executor.py": ["_v0_legacy.agents.tasks.models"],
}

def get_imports_via_ast(file_path: Path) -> list[str]:
    """Parse imports using ast (not regex) for accuracy."""
    source = file_path.read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports

def normalize_path(file_path: Path) -> str:
    """Convert to repo-relative POSIX path for consistent allowlist matching."""
    return file_path.resolve().relative_to(REPO_ROOT).as_posix()

def is_allowed_import(imp: str, allowed_prefixes: list[str]) -> bool:
    """Check if import matches any allowed prefix."""
    return any(imp.startswith(prefix) for prefix in allowed_prefixes)

def check_file(file_path: Path) -> list[str]:
    """Check file for disallowed legacy imports. Returns violations."""
    rel_path = normalize_path(file_path)
    allowed_prefixes = ALLOWED_LEGACY_IMPORTS.get(rel_path, [])
    imports = get_imports_via_ast(file_path)
    violations = []
    for imp in imports:
        if imp.startswith("_v0_legacy") and not is_allowed_import(imp, allowed_prefixes):
            violations.append(f"{rel_path}: disallowed import '{imp}'")
    return violations

def main() -> int:
    """Main entry point. Returns exit code (0 = pass, 1 = violations found)."""
    all_violations = []
    for checked_path in CHECKED_PATHS:
        base = REPO_ROOT / checked_path
        if not base.exists():
            continue
        for py_file in base.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            violations = check_file(py_file)
            all_violations.extend(violations)

    if all_violations:
        print("Legacy import violations found:")
        for v in all_violations:
            print(f"  {v}")
        return 1
    print("No legacy import violations.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Additional policy (transitive imports)**:
- No new modules may be added under `_v0_legacy/`
- No new symbols may be re-exported from `_v0_legacy/` except intentional shims
- The CI script checks direct imports only; transitive contamination is prevented by the "no new modules" rule
- Optionally: add secondary check that scans `_v0_legacy/` for new files added after migration start date

3. pytest warning filter:

```ini
# pyproject.toml or pytest.ini
# ONLY ignore warnings from intentionally shimmed modules (explicit list)
filterwarnings =
    ignore::DeprecationWarning:_v0_legacy.agents.llm
    ignore::DeprecationWarning:_v0_legacy.agents.telemetry
    ignore::DeprecationWarning:_v0_legacy.agents.tools
    ignore::DeprecationWarning:_v0_legacy.agents.memory
    ignore::DeprecationWarning:_v0_legacy.agents.tasks
# NOTE: Keep warnings visible in CI to catch accidental new legacy imports.
# Only use this filter for local dev convenience.
```

---

### Decision #9 — Embedding Provider Boundary (Memory/LLM)

**Problem**: Baking Ollama HTTP calls into LanceDBAdapter creates:
- Duplicated HTTP/retry/telemetry/error semantics inside Memory
- Hard-coded dependency that must be unwound when EmbeddingsPort arrives in 0.8.8

**Solution**: Add embedding callable seam (no new port required)

```python
# adapters/memory/lancedb.py
from typing import Callable, Awaitable
import asyncio

# Type alias for async embedding function
EmbedFn = Callable[[str], Awaitable[list[float]]]

class LanceDBAdapter(MemoryPort):
    """LanceDB-backed memory with pluggable async embedding function."""

    def __init__(
        self,
        db_path: str,
        embed_fn: EmbedFn | None = None,
        **config
    ):
        self._db_path = db_path
        self._embed_fn = embed_fn or self._default_ollama_embed_async
        # ...

    async def _default_ollama_embed_async(self, text: str) -> list[float]:
        """Legacy Ollama embedding call wrapped for async. Preserved for backward compat."""
        # Wrap sync HTTP call to avoid blocking event loop
        return await asyncio.to_thread(self._ollama_embed_sync, text)

    def _ollama_embed_sync(self, text: str) -> list[float]:
        """Sync Ollama HTTP call (runs in thread pool)."""
        # Existing HTTP call to Ollama /api/embeddings
        # (copied from _v0_legacy/agents/memory/lancedb_adapter.py)
        ...

    async def store(self, entry: MemoryEntry) -> str:
        embedding = await self._embed_fn(entry.content)
        # ...

    async def search(self, query: MemoryQuery) -> list[MemoryResult]:
        query_embedding = await self._embed_fn(query.text)
        # ...
```

**Wiring (0.8.7 default behavior preserved)**:

```python
# adapters/memory/factory.py
from typing import Callable, Awaitable

EmbedFn = Callable[[str], Awaitable[list[float]]]

def create_memory_provider(
    provider: str = "lancedb",
    embed_fn: EmbedFn | None = None,
    **config
) -> MemoryPort:
    if provider == "lancedb":
        return LanceDBAdapter(embed_fn=embed_fn, **config)
    raise ValueError(f"Unknown memory provider: {provider}")
```

**0.8.7 Wiring Requirements**:

In 0.8.7, wiring passes `embed_fn=None` (uses default legacy Ollama embed). This must be tested:

```python
# tests/integration/memory/test_lancedb_adapter.py
import os
import pytest
import httpx

from adapters.memory.lancedb import LanceDBAdapter
from squadops.memory.models import MemoryEntry, MemoryQuery


def ollama_available() -> bool:
    """Check if Ollama is reachable."""
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("RUN_OLLAMA_TESTS") and not ollama_available(),
    reason="Ollama not available; set RUN_OLLAMA_TESTS=1 to require"
)
async def test_lancedb_default_embedding_path(tmp_path):
    """Verify default embed_fn (legacy Ollama) works end-to-end.

    Args:
        tmp_path: pytest fixture providing temporary directory

    Requires: Ollama running locally for embeddings.
    Skipped in CI unless RUN_OLLAMA_TESTS=1 is set.
    """
    adapter = LanceDBAdapter(db_path=str(tmp_path / "test.lancedb"), embed_fn=None)
    memory_id = await adapter.store(MemoryEntry(content="test content"))
    results = await adapter.search(MemoryQuery(text="test"))
    assert len(results) > 0
```

**CI configuration**: Integration tests requiring external services are skipped by default. To run:
- Local dev with Ollama: tests run automatically if Ollama is reachable
- CI pipeline: set `RUN_OLLAMA_TESTS=1` in jobs that have Ollama available

**0.8.8 upgrade path (no adapter refactor needed)**:

```python
# Future: inject EmbeddingsPort via async embed_fn
async def embed_via_port(text: str) -> list[float]:
    return await embeddings_port.embed(text)

memory = create_memory_provider("lancedb", embed_fn=embed_via_port, db_path=...)
```

---

### Decision #10 — Config Contract

**Problem**: Plan introduces InfraConfig alongside existing UnifiedConfig, risking:
- Two parallel config systems with subtle mismatches
- Debugging wiring instead of ports
- Inconsistent defaults (production_mode, allowed_roots, secrets resolution)

**Decision for 0.8.7**: InfraConfig is a **typed view** over UnifiedConfig (no duplication)

```python
# src/squadops/runtime/config.py
from dataclasses import dataclass
from pathlib import Path
from _v0_legacy.infra.config.schema import UnifiedConfig

@dataclass
class LLMConfig:
    provider: str
    base_url: str

@dataclass
class TelemetryConfig:
    metrics_provider: str
    events_provider: str

@dataclass
class ToolsConfig:
    allowed_roots: tuple[Path, ...]

@dataclass
class MemoryConfig:
    provider: str
    db_path: str

@dataclass
class TasksConfig:
    provider: str
    connection_string: str

@dataclass
class InfraConfig:
    """Typed view over UnifiedConfig for infrastructure wiring.

    Does NOT duplicate config storage. Reads from UnifiedConfig fields.
    """

    @classmethod
    def from_unified(cls, uc: UnifiedConfig) -> "InfraConfig":
        """Extract infrastructure config from canonical UnifiedConfig."""
        return cls(
            llm=LLMConfig(
                provider=uc.llm.provider,
                base_url=uc.llm.base_url,
            ),
            telemetry=TelemetryConfig(
                metrics_provider=uc.telemetry.metrics_provider,
                events_provider=uc.telemetry.events_provider,
            ),
            tools=ToolsConfig(
                allowed_roots=tuple(Path(p) for p in uc.tools.allowed_roots),
            ),
            memory=MemoryConfig(
                provider=uc.memory.provider,
                db_path=uc.memory.db_path,
            ),
            tasks=TasksConfig(
                provider=uc.tasks.provider,
                connection_string=uc.tasks.connection_string,
            ),
            production_mode=uc.production_mode,
        )

    llm: LLMConfig
    telemetry: TelemetryConfig
    tools: ToolsConfig
    memory: MemoryConfig
    tasks: TasksConfig
    production_mode: bool = False
```

**Wiring uses InfraConfig, loaded from UnifiedConfig**:

```python
# src/squadops/runtime/wiring.py
def wire_infrastructure(
    unified_config: UnifiedConfig,
    secret_manager: SecretManager
) -> InfrastructureBundle:
    config = InfraConfig.from_unified(unified_config)
    # ... build adapters from config ...
```

**Canonical source**: UnifiedConfig remains the single source of truth. InfraConfig provides typed access for wiring without creating a parallel config system.

**Hard rule to prevent drift**: No new config fields may be introduced in `InfraConfig` unless they exist in `UnifiedConfig`. Enforce with unit test:

```python
# tests/unit/config/test_infra_config.py
def test_infra_config_covers_all_unified_fields():
    """InfraConfig.from_unified() must map all infra-relevant UnifiedConfig fields."""
    uc = UnifiedConfig(...)  # with all fields populated
    ic = InfraConfig.from_unified(uc)
    # Verify no UnifiedConfig.llm/telemetry/tools/memory/tasks fields are ignored
    assert ic.llm.provider == uc.llm.provider
    assert ic.llm.base_url == uc.llm.base_url
    # ... (exhaustive field check)
```

---

### Decision #11 — LLMRouter Domain Service

**Decision**: Include as pass-through; used by runtime bundle as sole LLM interface.

```python
# src/squadops/llm/router.py
class LLMRouter:
    """Route LLM requests to appropriate provider. Real policy in 0.8.8."""

    def __init__(self, provider: LLMPort):
        self._provider = provider

    async def generate(self, request: LLMRequest) -> LLMResponse:
        # 0.8.7: Pass-through to single provider
        # 0.8.8: Add model selection based on request metadata / task type
        return await self._provider.generate(request)
```

**Wiring ensures router is used**: `InfrastructureBundle.llm` returns `LLMRouter`, not raw adapter. This ensures router is exercised even with single provider.

**Unit test**: Verify router delegates to provider correctly.

---

### Decision #12 — Deprecation Shim Behavior

**Strategy**: Warn + re-export (gradual migration, not breaking).

```python
# _v0_legacy/agents/llm/__init__.py
import warnings
warnings.warn(
    "Importing from _v0_legacy.agents.llm is deprecated. "
    "Use squadops.llm or adapters.llm instead.",
    DeprecationWarning, stacklevel=2
)

# Re-export canonical symbols for backwards compatibility
from adapters.llm.factory import create_llm_provider
from squadops.llm.models import LLMRequest, LLMResponse, ChatMessage

__all__ = ["create_llm_provider", "LLMRequest", "LLMResponse", "ChatMessage"]
```

**Per-module re-exports**:

| Legacy Module | Re-exported Symbols |
|---------------|---------------------|
| `_v0_legacy.agents.llm` | `create_llm_provider`, `LLMRequest`, `LLMResponse`, `ChatMessage` |
| `_v0_legacy.agents.telemetry` | `create_metrics_provider`, `create_event_provider` |
| `_v0_legacy.agents.tools` | `create_filesystem_provider`, `create_container_provider` |
| `_v0_legacy.agents.memory` | `create_memory_provider`, `MemoryEntry`, `MemoryQuery` |
| `_v0_legacy.agents.tasks` | (bridge via `squadops.tasks.types`) |

---

### Decision #13 — Atomic Writes

`LocalFileSystemAdapter.write()` uses temp file + rename for atomic writes (SIP §7.2 requirement).

---

### Decision #14 — Migration Order

Telemetry → (Tools + LLM) → (Memory + Tasks); phases grouped by dependency safety.

---

### Decision #15 — Legacy Import Gate Scope

**Explicit enforcement across all paths**:
- `src/`
- `adapters/`
- `tests/`
- `scripts/` (if they import runtime modules)

---

### Decision #16 — Ports Naming Consistency

**Rule**: All port files follow consistent naming pattern to prevent drift:

| Domain | Port File | Port Class |
|--------|-----------|------------|
| Telemetry | `metrics.py` | `MetricsPort` |
| Telemetry | `events.py` | `EventPort` |
| LLM | `provider.py` | `LLMPort` |
| Tools | `filesystem.py` | `FileSystemPort` |
| Tools | `container.py` | `ContainerPort` |
| Tools | `vcs.py` | `VersionControlPort` |
| Memory | `store.py` | `MemoryPort` |
| Tasks | `registry.py` | `TaskRegistryPort` |

**Convention**: `{domain}.py` → `{Domain}Port` class. No `_port.py` suffix on files. Enforce via code review.

---

### Decision #17 — Exception Naming (Avoid Built-in Collisions)

**Problem**: Domain exceptions like `FileNotFoundError` collide with Python built-ins.

**Rule**: All domain exceptions MUST be prefixed with domain name to avoid collision:

| Domain | Exception | NOT |
|--------|-----------|-----|
| Tools | `ToolFileNotFoundError` | `FileNotFoundError` |
| Tools | `ToolPermissionError` | `PermissionError` |
| Tools | `ToolIOError` | `IOError` |
| LLM | `LLMConnectionError` | `ConnectionError` |
| LLM | `LLMTimeoutError` | `TimeoutError` |
| Memory | `MemoryStoreError` | `MemoryError` (built-in!) |
| Memory | `MemoryNotFoundError` | `NotFoundError` |
| Tasks | `TaskNotFoundError` | `NotFoundError` |

**Implementation**: Each domain's `exceptions.py` defines prefixed exceptions. Never re-export at package root without prefix.

---

### Decision #18 — Performance Guarantee (SIP §9)

**Proposed SIP §9 Amendment**:

~~Adapter overhead must be negligible (<1ms per call)~~

Adapter overhead excluding underlying I/O should be small relative to the call (serialization + validation only). Where meaningful, benchmark and record baseline latency for:
- LLM generate (expected: seconds)
- Memory search (expected: 10-100ms)
- Task create (expected: 1-10ms)

---

## Phase 1: Telemetry (Observability Foundation)

### 1.1 Domain Layer — Telemetry

```
src/squadops/telemetry/
├── __init__.py
├── models.py          # StructuredEvent, Span, MetricType (frozen dataclasses)
└── exceptions.py      # TelemetryError
```

**Models**:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"

@dataclass(frozen=True)
class Span:
    """Distributed tracing span."""
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    attributes: tuple[tuple[str, str], ...] = ()

@dataclass(frozen=True)
class StructuredEvent:
    """Structured log/event for EventPort.emit()."""
    name: str
    message: str
    level: str = "info"  # debug, info, warning, error
    attributes: tuple[tuple[str, Any], ...] = ()
    timestamp: datetime | None = None
    span_id: str | None = None  # Optional correlation to active span
```

**Note on MetricEvent**: The `MetricsPort` uses primitive method signatures (`counter()`, `gauge()`, `histogram()`) rather than a `MetricEvent` model. This is intentional — adapters convert to their native metric format internally. If a unified `MetricEvent` is needed later (e.g., for buffering), it can be added as an internal adapter detail, not a port contract.

### 1.2 Port Interfaces — Telemetry

```
src/squadops/ports/telemetry/
├── __init__.py
├── metrics.py         # MetricsPort
└── events.py          # EventPort
```

**MetricsPort**:

```python
class MetricsPort(ABC):
    @abstractmethod
    def counter(self, name: str, value: float = 1, labels: dict[str, str] | None = None) -> None: ...

    @abstractmethod
    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None: ...

    @abstractmethod
    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None: ...
```

**EventPort** (SIP-compliant with convenience wrapper):

```python
class EventPort(ABC):
    @abstractmethod
    def emit(self, event: StructuredEvent) -> None: ...

    @abstractmethod
    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict[str, str] | None = None
    ) -> Span: ...

    @abstractmethod
    def end_span(self, span: Span) -> None: ...

    # Convenience wrapper (non-abstract, uses above methods)
    @contextmanager
    def span(self, name: str, attributes: dict[str, str] | None = None) -> Iterator[Span]:
        s = self.start_span(name, attributes=attributes)
        try:
            yield s
        finally:
            self.end_span(s)
```

### 1.3 Adapters — Telemetry

```
adapters/telemetry/
├── __init__.py
├── console.py         # ConsoleAdapter (debug logging, bounded formatting)
├── otel.py            # OTelAdapter (OpenTelemetry SDK)
├── null.py            # NullAdapter (TEST-ONLY, no-op implementation)
└── factory.py         # No secret_manager param (telemetry uses env vars)
```

**Source**: `_v0_legacy/agents/telemetry/providers/null_client.py`

**Non-blocking contract**: Production telemetry adapters (OTelAdapter, NullAdapter) MUST be non-blocking — enqueue/buffer, do not block caller thread, swallow exceptions internally. **ConsoleAdapter is DEV-ONLY and exempt** (stdout may block; accepted risk for local development).

**Production mode guard** (enforced in factory):

```python
# adapters/telemetry/factory.py
DEV_ONLY_ADAPTERS = {"console"}

def create_metrics_provider(
    provider: str = "otel",
    production_mode: bool = False,
) -> MetricsPort:
    if production_mode and provider in DEV_ONLY_ADAPTERS:
        raise ValueError(
            f"Adapter '{provider}' is DEV-ONLY and cannot be used in production mode. "
            f"Use 'otel' or 'null' instead."
        )
    if provider == "otel":
        return OTelAdapter()
    if provider == "console":
        return ConsoleAdapter()
    if provider == "null":
        return NullAdapter()
    raise ValueError(f"Unknown telemetry provider: {provider}")
```

**Wiring requirement**: `production_mode` is passed from `InfraConfig.production_mode` to all factories.

**Production mode guard unit test** (required, prevents regression):

```python
# tests/unit/telemetry/test_factory.py
import pytest
from adapters.telemetry.factory import create_metrics_provider

def test_production_mode_rejects_console_adapter():
    """Production mode MUST reject dev-only adapters."""
    with pytest.raises(ValueError, match="DEV-ONLY"):
        create_metrics_provider(provider="console", production_mode=True)

def test_production_mode_allows_otel_adapter():
    """Production mode allows production-ready adapters."""
    adapter = create_metrics_provider(provider="otel", production_mode=True)
    assert adapter is not None

def test_production_mode_allows_null_adapter():
    """Production mode allows null adapter (for testing)."""
    adapter = create_metrics_provider(provider="null", production_mode=True)
    assert adapter is not None

def test_dev_mode_allows_console_adapter():
    """Dev mode (default) allows all adapters."""
    adapter = create_metrics_provider(provider="console", production_mode=False)
    assert adapter is not None
```

**Constructor injection (for testability)**:

```python
# adapters/telemetry/otel.py
from opentelemetry.sdk.trace.export import SpanExporter
from opentelemetry.sdk.metrics.export import MetricExporter

class OTelAdapter(MetricsPort, EventPort):
    """OpenTelemetry adapter with injectable exporters for testing."""

    def __init__(
        self,
        span_exporter: SpanExporter | None = None,
        metric_exporter: MetricExporter | None = None,
        service_name: str = "squadops",
    ):
        """
        Args:
            span_exporter: Custom span exporter (default: OTLPSpanExporter from env)
            metric_exporter: Custom metric exporter (default: OTLPMetricExporter from env)
            service_name: Service name for telemetry

        Injection allows unit tests to pass BrokenExporter to verify error handling.
        """
        self._span_exporter = span_exporter or self._default_span_exporter()
        self._metric_exporter = metric_exporter or self._default_metric_exporter()
        # ... setup BatchSpanProcessor, etc.
```

**ConsoleAdapter** (similar pattern for stdout injection):

```python
# adapters/telemetry/console.py
from typing import TextIO
import sys

class ConsoleAdapter(MetricsPort, EventPort):
    """Console adapter with injectable output stream for testing."""

    def __init__(self, output: TextIO | None = None):
        """
        Args:
            output: Output stream (default: sys.stdout)

        Injection allows unit tests to pass BrokenWriter to verify error handling.
        """
        self._output = output or sys.stdout
```

### 1.4 Tests — Phase 1

```
tests/unit/telemetry/
├── test_models.py
├── test_ports.py
├── test_adapters.py
└── test_factory.py      # Production mode guard tests
```

### 1.5 Deprecation Shims — Telemetry

```python
# _v0_legacy/agents/telemetry/__init__.py
import warnings
warnings.warn(
    "Importing from _v0_legacy.agents.telemetry is deprecated. "
    "Use squadops.ports.telemetry and adapters.telemetry instead.",
    DeprecationWarning, stacklevel=2
)
```

---

## Phase 2: Tools + LLM

### 2.1 Domain Layer — LLM

```
src/squadops/llm/
├── __init__.py
├── models.py          # LLMRequest, LLMResponse, ChatMessage
├── router.py          # LLMRouter (pass-through for 0.8.7)
└── exceptions.py      # LLMError, LLMModelNotFoundError, LLMRateLimitError
```

**Models**:

```python
@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4000
    format: str | None = None  # "json" for structured output
    timeout_seconds: float = 180.0

@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str
```

### 2.2 Port Interfaces — LLM

```
src/squadops/ports/llm/
├── __init__.py
└── provider.py        # LLMPort
```

**LLMPort**:

```python
class LLMPort(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], model: str | None = None) -> ChatMessage: ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models (sync, returns cached list).
        Adapters MUST cache and return synchronously. Use refresh_models() to update cache."""
        ...

    @abstractmethod
    async def refresh_models(self) -> list[str]:
        """Refresh and return available models (async, performs HTTP if needed).
        Updates the internal cache. Call periodically or on demand."""
        ...

    @abstractmethod
    async def health(self) -> dict[str, Any]: ...

# NOTE: list_models() remains sync to avoid breaking change.
# New async refresh_models() added for explicit cache refresh.
#
# Cache semantics (no hidden I/O):
# - list_models() returns cached list (empty until refresh_models() called)
# - refresh_models() performs HTTP call and updates cache
# - Adapters MUST NOT perform network I/O in __init__ (can't await in constructor)
# - Wiring is responsible for: await provider.refresh_models() after construction
# - Alternative: factory accepts pre_fetched_models list for explicit initialization
```

### 2.3 Adapters — LLM

```
adapters/llm/
├── __init__.py
├── ollama.py          # OllamaAdapter
└── factory.py         # with SecretManager integration per SIP §7.6
```

**Source**: `_v0_legacy/agents/llm/providers/ollama.py`

**Key implementation details**:
- Timeout handling (180s default)
- Token usage extraction from response
- JSON format parameter support
- Error handling with retry logic

### 2.4 Domain Layer — Tools

```
src/squadops/tools/
├── __init__.py
├── models.py          # FileOperation, ContainerSpec, ContainerResult
├── exceptions.py      # ToolError, ToolFileNotFoundError, ToolContainerError
└── security.py        # PathSecurityPolicy (shared validation per SIP §7.2)
```

**Models**:

```python
@dataclass(frozen=True)
class ContainerSpec:
    """Specification for running a container."""
    image: str
    command: list[str] | None = None
    env: tuple[tuple[str, str], ...] = ()
    volumes: tuple[tuple[str, str], ...] = ()  # (host_path, container_path)
    working_dir: str | None = None
    timeout_seconds: float = 300.0

# NOTE: Container volume host paths are NOT validated against PathSecurityPolicy in 0.8.7.
# This is an explicit deferral — container security is handled by Docker's own isolation.
# If host volume validation is needed, add PathValidatedContainerPort wrapper in 0.8.8.

@dataclass(frozen=True)
class ContainerResult:
    """Result of a container run."""
    container_id: str
    exit_code: int
    stdout: str
    stderr: str

@dataclass(frozen=True)
class VCSStatus:
    """Status of a version-controlled repository."""
    branch: str
    is_clean: bool
    modified_files: tuple[str, ...] = ()
    untracked_files: tuple[str, ...] = ()
    ahead: int = 0
    behind: int = 0
```

### 2.5 Port Interfaces — Tools

```
src/squadops/ports/tools/
├── __init__.py
├── filesystem.py      # FileSystemPort
├── container.py       # ContainerPort
└── vcs.py             # VersionControlPort
```

**FileSystemPort** (simple interface; validation via wrapper):

```python
class FileSystemPort(ABC):
    @abstractmethod
    def read(self, path: Path) -> str: ...
    @abstractmethod
    def write(self, path: Path, content: str) -> None: ...
    @abstractmethod
    def exists(self, path: Path) -> bool: ...
    @abstractmethod
    def list_dir(self, path: Path, pattern: str | None = None) -> list[Path]: ...
    @abstractmethod
    def mkdir(self, path: Path, parents: bool = True) -> None: ...
    @abstractmethod
    def delete(self, path: Path) -> None: ...
```

`LocalFileSystemAdapter` atomicity: `write()` uses temp file + rename for atomic writes (SIP §7.2 requirement).

**ContainerPort**:

```python
class ContainerPort(ABC):
    @abstractmethod
    async def run(self, spec: ContainerSpec) -> ContainerResult: ...
    @abstractmethod
    async def stop(self, container_id: str) -> None: ...
    @abstractmethod
    async def logs(self, container_id: str, tail: int | None = None) -> str: ...
    @abstractmethod
    async def health(self) -> dict[str, Any]: ...
```

**VersionControlPort**:

```python
class VersionControlPort(ABC):
    @abstractmethod
    def status(self, repo_path: Path) -> VCSStatus: ...

    @abstractmethod
    def commit(self, repo_path: Path, message: str, files: list[str] | None = None) -> str:
        """Commit changes to repository.

        Args:
            repo_path: Absolute path to repository root (validated via PathSecurityPolicy)
            message: Commit message
            files: Repo-relative POSIX paths (e.g., "src/main.py", "tests/test_foo.py").
                   If None, commits all staged changes.
                   Paths are validated: must not escape repo root (no ".." traversal).

        Returns:
            Commit hash
        """
        ...

    @abstractmethod
    def push(self, repo_path: Path, remote: str = "origin", branch: str | None = None) -> None: ...
```

**VCS file path contract**:
- `repo_path`: Absolute path, validated via `PathSecurityPolicy` wrapper
- `files`: Repo-relative POSIX strings (not `Path`), validated by adapter:
  - Must not contain `..` segments
  - Resolved as `repo_path / file` internally
  - No `PathSecurityPolicy` call needed (already under validated repo root)

### 2.6 Adapters — Tools

```
adapters/tools/
├── __init__.py
├── local_filesystem.py   # LocalFileSystemAdapter
├── docker.py             # DockerAdapter
├── git.py                # GitAdapter
└── factory.py            # with SecretManager integration
```

**Sources**:
- `_v0_legacy/agents/tools/file_manager.py`
- `_v0_legacy/agents/tools/docker_manager.py`
- `_v0_legacy/agents/tools/version_manager.py`

### 2.7 Tests — Phase 2

```
tests/unit/llm/
├── test_models.py
├── test_ports.py
└── test_ollama_adapter.py  # with mocked HTTP

tests/unit/tools/
├── test_models.py
├── test_security.py        # PathSecurityPolicy tests
├── test_filesystem_port.py
├── test_container_port.py
└── test_vcs_port.py

tests/integration/llm/
└── test_ollama_integration.py  # requires Ollama

tests/integration/tools/
├── test_local_filesystem.py
└── test_docker_adapter.py  # requires Docker daemon
```

### 2.8 Deprecation Shims — Phase 2

```python
# _v0_legacy/agents/llm/__init__.py
# _v0_legacy/agents/tools/__init__.py
import warnings
warnings.warn("...", DeprecationWarning, stacklevel=2)
```

---

## Phase 3: Memory + Tasks

### 3.1 Domain Layer — Memory

```
src/squadops/memory/
├── __init__.py
├── models.py          # MemoryEntry, MemoryQuery, MemoryResult
└── exceptions.py      # MemoryStoreError, MemoryEmbeddingError
```

**Models**:

```python
@dataclass(frozen=True)
class MemoryEntry:
    content: str
    namespace: str = "role"
    agent_id: str | None = None
    cycle_id: str | None = None
    tags: tuple[str, ...] = ()
    importance: float = 0.7
    metadata: tuple[tuple[str, Any], ...] = ()

@dataclass(frozen=True)
class MemoryQuery:
    text: str
    limit: int = 8
    threshold: float = 0.7
    namespace: str | None = None
    tags: tuple[str, ...] = ()

@dataclass(frozen=True)
class MemoryResult:
    entry: MemoryEntry
    memory_id: str
    score: float
```

### 3.2 Domain Layer — Tasks

```
src/squadops/tasks/
├── __init__.py
├── types.py           # Compatibility bridge (single legacy import point)
├── models.py          # TaskIdentity (frozen), re-exports from legacy
└── exceptions.py      # TaskError, TaskNotFoundError
```

**Lower-risk approach** (per Design Decision #6):
- Keep Pydantic TaskEnvelope/TaskResult in `_v0_legacy` for now
- Create TaskIdentity frozen dataclass for immutable identity subset
- Ports use TaskEnvelope from compatibility bridge
- Full migration to frozen dataclasses deferred to 0.8.8 with agent migration

**Models**:

```python
# src/squadops/tasks/models.py
from dataclasses import dataclass

@dataclass(frozen=True)
class TaskIdentity:
    """Immutable identity subset of TaskEnvelope for internal use."""
    task_id: str
    task_type: str
    source_agent: str
    target_agent: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    trace_id: str | None = None
```

```python
# src/squadops/tasks/types.py (compatibility bridge, per Decision #6)
"""Compatibility bridge for 0.8.7. Full migration in 0.8.8."""
from _v0_legacy.agents.tasks.models import TaskEnvelope, TaskResult, TaskState, FlowState

# Type alias for documentation clarity
LegacyTaskEnvelope = TaskEnvelope

__all__ = ["TaskEnvelope", "TaskResult", "TaskState", "FlowState", "LegacyTaskEnvelope"]
```

### 3.3 Port Interfaces

```
src/squadops/ports/memory/
├── __init__.py
└── store.py           # MemoryPort

src/squadops/ports/tasks/
├── __init__.py
└── registry.py        # TaskRegistryPort
```

**MemoryPort**:

```python
class MemoryPort(ABC):
    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str: ...
    @abstractmethod
    async def search(self, query: MemoryQuery) -> list[MemoryResult]: ...
    @abstractmethod
    async def get(self, memory_id: str) -> MemoryEntry | None: ...
    @abstractmethod
    async def delete(self, memory_id: str) -> bool: ...
```

**TaskRegistryPort**:

```python
class TaskRegistryPort(ABC):
    @abstractmethod
    async def create(self, envelope: TaskEnvelope) -> str: ...
    @abstractmethod
    async def get(self, task_id: str) -> TaskEnvelope | None: ...
    @abstractmethod
    async def update_status(self, task_id: str, status: TaskState, result: dict | None = None) -> None: ...
    @abstractmethod
    async def list_pending(self, agent_id: str | None = None) -> list[TaskEnvelope]: ...
```

### 3.4 Adapters

```
adapters/memory/
├── __init__.py
├── lancedb.py         # LanceDBAdapter (with embed_fn seam)
└── factory.py         # with SecretManager integration

adapters/tasks/
├── __init__.py
├── sql.py             # SQLTaskAdapter (migrated from legacy)
├── prefect.py         # PrefectTaskAdapter (stub - raises NotImplementedError)
└── factory.py
```

**Sources**:
- `_v0_legacy/agents/memory/lancedb_adapter.py` (534 lines - most complex)
- `_v0_legacy/agents/tasks/sql_adapter.py` (735 lines)

**Embedding provider boundary** (per Decision #9):
- LanceDBAdapter accepts `embed_fn: Callable[[str], Awaitable[list[float]]] | None`
- Default `embed_fn` wraps legacy sync Ollama call via `asyncio.to_thread()` (non-blocking)
- 0.8.8: Inject `EmbeddingsPort` via async `embed_fn` parameter

**PrefectTaskAdapter**: Stub only in 0.8.7. Raises `NotImplementedError` on all methods. Full implementation deferred to 0.8.8.

### 3.5 Tests — Phase 3

```
tests/unit/memory/
├── test_models.py
└── test_port.py

tests/unit/tasks/
├── test_models.py
└── test_registry_port.py

tests/integration/memory/
└── test_lancedb_adapter.py

tests/integration/tasks/
└── test_sql_adapter.py  # requires PostgreSQL
```

---

## File Count Summary

| Phase | Domain Files | Port Files | Adapter Files | Test Files | Total Files |
|-------|--------------|------------|---------------|------------|-------------|
| Phase 1 (Telemetry) | 3 | 3 | 5 | 4 | 15 |
| Phase 2 (Tools + LLM) | 7 | 6 | 8 | 10 | 31 |
| Phase 3 (Memory + Tasks) | 6 | 4 | 8 | 8 | 26 |
| **Total** | **16** | **13** | **21** | **22** | **72** |

*Note: "Domain Files" = models.py, exceptions.py, etc. under `src/squadops/{context}/`. "Port Files" = ABC interfaces under `src/squadops/ports/`. "Adapter Files" = implementations under `adapters/`.*

Plus 1 CI script (`scripts/ci/check_legacy_imports.py`) and minor SIP amendments.

---

## Verification

```bash
# Phase 1
pytest tests/unit/telemetry -v

# Phase 2
pytest tests/unit/llm tests/unit/tools -v
pytest tests/integration/llm -v  # requires Ollama
pytest tests/integration/tools -v  # requires Docker

# Phase 3
pytest tests/unit/memory tests/unit/tasks -v
# Start Postgres via project docker-compose (see docker-compose.yml)
docker compose up -d postgres
pytest tests/integration/memory tests/integration/tasks -v

# Full suite
pytest tests/ -v --cov=src/squadops --cov=adapters
```

---

## SIP Lifecycle

1. **Now**: SIP exists in `sips/proposed/` (unnumbered draft)
2. **After Phase 1 complete**:
   ```bash
   export SQUADOPS_MAINTAINER=1
   python scripts/maintainer/update_sip_status.py \
       sips/proposed/SIP-Infrastructure-Ports-Migration.md accepted
   ```
   → SIP gets assigned number (e.g., SIP-0059) during promotion
3. **After Phase 3 complete**:
   ```bash
   export SQUADOPS_MAINTAINER=1
   python scripts/maintainer/update_sip_status.py \
       sips/accepted/SIP-XXXX-Infrastructure-Ports-Migration.md implemented
   python scripts/maintainer/version_cli.py bump patch
   # → 0.8.7
   ```
   → Update CLAUDE.md, README.md with new version

---

## Key Design Decisions Summary

| # | Decision | Approach |
|---|----------|----------|
| 1 | EventPort API | SIP-compliant start_span/end_span **with attributes**; convenience span() as non-abstract wrapper |
| 2 | Secret mechanism | SecretManager is façade; SecretProvider is port; no "SecretStorePort" |
| 3 | Path validation | **Complete impl**: `_is_under()` defined, absolute input required **before** resolution (rejects relative paths), roots resolved once at construction |
| 4 | VCS validation | Reuse PathSecurityPolicy for repo_path; wrapper pattern |
| 5 | Telemetry non-blocking | **Testable contract**: no network I/O on caller, no raise outward, return quickly; Console is DEV MODE ONLY |
| 6 | TaskEnvelope | Single-source types.py; CI rule covers all code including tests |
| 7 | PrefectAdapter | Stub only; tests marked @pytest.mark.skip |
| 8 | Deprecation shims | Warn + re-export; **ast-based import check, normalized POSIX paths** |
| 9 | Embedding boundary | **async embed_fn seam** (`Callable[[str], Awaitable[list[float]]]`); default uses `asyncio.to_thread()` wrapper; 0.8.8 injects EmbeddingsPort |
| 10 | Config contract | **InfraConfig is typed view**; hard rule: no new fields unless in UnifiedConfig; unit test enforces |
| 11 | LLMRouter | Pass-through but always used (bundle returns router, not raw adapter) |
| 12 | Deprecation shim behavior | Warn + re-export (not breaking); per-module symbol table |
| 13 | Atomic writes | LocalFileSystemAdapter.write() uses temp+rename |
| 14 | Migration order | Telemetry → (Tools + LLM) → (Memory + Tasks); phases by dependency |
| 15 | Legacy import gate | **Explicit scope**: src/, adapters/, tests/, scripts/ — ast parsing, normalized paths |
| 16 | Ports naming | Consistent pattern: `{domain}.py` → `{Domain}Port`; no `_port.py` suffix |
| 17 | Exception naming | **Domain-prefixed** to avoid built-in collisions (e.g., `ToolFileNotFoundError`) |
| 18 | Performance guarantee | Adapter overhead small relative to call; benchmark critical paths |
| 19 | Production mode guard | Factories reject dev-only adapters (e.g., `ConsoleAdapter`) when `production_mode=True` |
| 20 | VCS files contract | Repo-relative POSIX strings; validated for `..` traversal; resolved as `repo_path / file` |
| 21 | Container volume security | Explicitly deferred to 0.8.8; Docker isolation is baseline for 0.8.7 |
| 22 | Prefect stub isolation | No runtime Prefect import; `TYPE_CHECKING` guard prevents dependency leak |
| 23 | Integration test CI safety | Ollama tests skip by default; `RUN_OLLAMA_TESTS=1` to require |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| LanceDB embedding mismatch | Dimension validation + multi-model support |
| Large TaskAdapter interface (15 methods) | Keep as-is; consider split in 0.8.8 |
| Legacy import contamination | check_legacy_imports.py CI gate with allowlist; **ast parsing, normalized paths** |
| Ollama timeout | Configurable timeout with 180s default |
| TaskEnvelope Pydantic breakage | Keep Pydantic, add thin domain wrappers only |
| Performance guarantee too strict | Amend SIP §9 language |
| Memory/LLM coupling | **async embed_fn seam** prevents hard-coded dependency; default wraps sync Ollama call via `asyncio.to_thread()` to avoid blocking event loop |
| Config drift | **InfraConfig wraps UnifiedConfig**; hard rule + unit test prevents new fields |
| PathSecurityPolicy incomplete | **Full impl**: `_is_under()` defined, absolute **input** required (checked before resolve), roots normalized at construction |
| Console telemetry blocking | **DEV MODE ONLY** scope; accept best-effort blocking risk |
| Exception name collisions | **Domain-prefixed** exceptions (e.g., `ToolFileNotFoundError`) |
| Allowlist path brittleness | **Normalized POSIX paths** + ast import parsing |
| LLMPort.list_models() breaking change | Avoided: kept sync with cache, added async `refresh_models()`; no hidden I/O in `__init__` |
| Telemetry adapter testability | Constructor injection for exporters/output streams; tests use `BrokenExporter`/`BrokenWriter` |
| Dev-only adapters in production | Factory guards reject `ConsoleAdapter` when `production_mode=True` |
| VCS files param ambiguity | Contract: repo-relative POSIX strings, validated for `..` traversal |
| Container volume security | Explicitly deferred; Docker isolation is baseline; wrapper can be added in 0.8.8 |
| UnifiedConfig legacy import | Allowlist permits `src/squadops/runtime/config.py`; migration to non-legacy deferred |
| Allowlist exact vs prefix | Uses prefix matching (`startswith`) for robustness to submodule changes |
| Prefect stub dependency leak | Stub uses `TYPE_CHECKING` guard; no runtime Prefect import |
| Integration tests fail in CI | Ollama tests skip unless `RUN_OLLAMA_TESTS=1` or service reachable |
| Production mode guard untested | Dedicated unit test verifies factory rejects dev-only adapters |

---

## Proposed SIP Amendments

1. **Section 4 "Not Addressed"**: Add "PrefectTaskAdapter implementation (stub only; full implementation in 0.8.8)"
2. **Section 7.6 Factories**: Clarify "Factories MUST resolve secret:// refs via the SIP-0054 secret mechanism (SecretManager/SecretProvider)"
3. **Section 9 Performance**: Change "<1ms adapter overhead" to "Adapter overhead excluding underlying I/O should be small (serialization + validation only). Benchmark critical paths."
4. **Section 10.1 Migration Order**: Add "Contexts may be implemented in parallel when dependencies permit; the listed order expresses dependency constraints, not a required sequence."
5. **Section 12 Definition of Done**: Change Prefect checkbox to "PrefectTaskAdapter stub present + raises NotImplementedError + documented deferral"

---

## Out of Scope [DEFERRED to 0.8.8]

- Agent role migrations
- Runtime API migration
- New LLM providers (Anthropic, OpenAI)
- PromotionService migration (complex memory workflow)
- AppBuilder migration (depends on multiple ports)
- PrefectTaskAdapter full implementation
- TaskEnvelope/TaskResult full migration to frozen dataclasses
- EmbeddingsPort (seam in place for clean upgrade)
- Container volume host path validation (Docker provides isolation; wrapper can be added later)
- UnifiedConfig migration out of `_v0_legacy` (allowlist permits import for now)
