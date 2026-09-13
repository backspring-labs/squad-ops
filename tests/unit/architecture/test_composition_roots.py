"""Composition roots — the guard docs/architecture/composition-roots.md §6.6 specifies.

This module carries **assertion 1, import purity (R3)**. Assertions 2–4 — factory-only
construction, expected bindings present, selectors required — become true with #301 and land
with it; a guard asserting them before the queue/A2A/filesystem factories exist would be
red on main for the whole of §3.3, which is a guard nobody reads.

The root list is ``test_forbidden_imports.COMPOSITION_ROOTS`` — imported, not duplicated,
so a root added there is asserted here the same day (the ``_COUNTING_SETS`` lesson). Each
root maps to the module a process actually imports to start it.

Bug class guarded: a composition root that does work at import. #286 is the instance —
``squadops.api.runtime.main`` called ``load_config()`` at module scope, so a bare import
resolved secrets, validated the deployment profile and failed with
``ConfigValidationError: secret:// references found`` in any environment but the deployed
one. Every consumer that only needed a symbol (the CLI integration tests) grew a
``sys.modules``-and-env workaround, and #637's lock-and-import job could not exist.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.unit.architecture.test_forbidden_imports import COMPOSITION_ROOTS

pytestmark = [pytest.mark.unit]

#: The module a process imports to start each root. A root in COMPOSITION_ROOTS with no
#: entry here fails the completeness test below rather than silently going unasserted.
_ENTRY_MODULE = {
    "squadops.api.runtime": "squadops.api.runtime.main",
    "squadops.agents.entrypoint": "squadops.agents.entrypoint",
    "squadops.sandbox.main": "squadops.sandbox.main",
    "squadops.bootstrap": "squadops.bootstrap",
}


def test_every_root_has_an_entry_module():
    assert set(_ENTRY_MODULE) == set(COMPOSITION_ROOTS), (
        "COMPOSITION_ROOTS and _ENTRY_MODULE disagree — a root was added to one and not the other"
    )


@pytest.mark.parametrize("module", sorted(_ENTRY_MODULE.values()))
def test_a_bare_import_reads_no_environment(module):
    """A subprocess with an EMPTY environment — no ``SQUADOPS__*``, no ``.env`` — must import
    the root and exit 0. Same interpreter, so site-packages resolve; nothing else."""
    proc = subprocess.run(  # noqa: S603 — fixed argv, our own interpreter
        [sys.executable, "-c", f"import {module}"],
        env={},
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, (
        f"`import {module}` with an empty environment failed — the root does work at import:\n"
        f"{proc.stderr[-1500:]}"
    )


# --------------------------------------------------------------------------- #
# §6.6 assertions 2–4 — land with #301, which makes them true
# --------------------------------------------------------------------------- #

import ast  # noqa: E402

from tests.unit.architecture.test_forbidden_imports import SRC, _iter_py  # noqa: E402

#: The five sites #301 closed, kept BY PATTERN the way `test_the_two_named_leaks_are_closed`
#: keeps #154's — a general allowlist must never readmit them. Line numbers are not used
#: because #286 moved them; the vendor construction is the invariant.
_CLOSED_VENDOR_CONSTRUCTIONS = (
    "RabbitMQAdapter(",
    "A2AClientAdapter(",
    "A2AServerAdapter(",
    "LocalFileSystemAdapter(",
)


@pytest.mark.parametrize("root", sorted(_ENTRY_MODULE))
def test_the_five_named_vendor_constructions_stay_closed(root):
    for py in _iter_py(_root_dir(root)):
        text = py.read_text(encoding="utf-8")
        for vendor in _CLOSED_VENDOR_CONSTRUCTIONS:
            assert vendor not in text, (
                f"{py.relative_to(SRC.parent)} constructs {vendor} — #301 closed this"
            )


def _root_dir(root: str):
    rel = root.split(".")[1:]
    path = SRC.joinpath(*rel)
    return (
        path
        if path.is_dir()
        else path.with_suffix(".py").parent
        if not path.with_suffix(".py").exists()
        else path.with_suffix(".py")
    )


def _iter_root_modules(root: str):
    p = _root_dir(root)
    return [p] if p.is_file() else list(_iter_py(p))


def _adapter_class_constructions(py) -> list[tuple[int, str, str]]:
    """(line, callee, imported-from) for every call to a NAME imported from a non-factory
    `adapters.<pkg>.<module>` — assertion 2's technique: construction of an adapter class
    outside its factory. Factory-function imports (`create_*`, `build_*`, `resolve_*`) and
    imports from a package's own `factory` module are not violations by definition."""
    tree = ast.parse(py.read_text(encoding="utf-8"))
    origin: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("adapters."):
            parts = node.module.split(".")
            if parts[-1] == "factory":
                continue
            for a in node.names:
                name = a.asname or a.name
                if name.startswith(("create_", "build_", "resolve_")):
                    continue
                origin[name] = node.module
    hits = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in origin
        ):
            if node.func.id[:1].isupper():  # a class, by naming — the technique, not the rule
                hits.append((node.lineno, node.func.id, origin[node.func.id]))
    return hits


#: Assertion 2's named exceptions, built from the first run's 24 findings rather than from
#: expectation (#1217), each with its composition-roots.md §3 category and reason. Adding an
#: entry is a deliberate decision recorded here — the COMPOSITION_ROOTS precedent.
_SUBSTRATE = "substrate-bound: stateless over a pool/client the root already built through its factory (#577)"
_READER = "bootstrap/config reader: reads config/squad-profiles.yaml; no vendor behind it"
_COMPOSER = "root-internal composer: assembles ports the root already holds"
_NOOP = "always-inject NoOp fallback (CLAUDE.md key pattern): the absent-binding case, not a vendor"
_CONSTRUCTION_EXCEPTIONS: dict[str, str] = {
    "PostgresAssignment": _SUBSTRATE,
    "PostgresRuntimeActivity": _SUBSTRATE,
    "PostgresFocusLease": _SUBSTRATE,
    "PostgresRuntimeState": _SUBSTRATE,
    "PostgresRuntimeTransaction": _SUBSTRATE,
    "ChatRepository": _SUBSTRATE,
    "ChatSessionCache": _SUBSTRATE + " (Redis)",
    "ConfigSquadProfile": _READER,
    "ReplyRouter": _COMPOSER + " (over the queue port, SIP-0094)",
    "ChatAgentExecutor": _COMPOSER + " (the A2A executor over the agent, SIP-0085)",
    "AgentCardConfig": "a config dataclass, not an adapter — the CamelCase technique over-matches it",
    "LoggingRuntimeEventPublisher": _NOOP + " (logging sink)",
    "NoOpCycleEventBus": _NOOP,
    "NoOpWorkflowTracker": _NOOP,
    # The one entry that is a factory-shaped gap rather than a category: a vendor (httpx)
    # reporter built directly inside the root's _create_heartbeat_reporter. Tabled so #301
    # closes on its four bindings, and named on the PR as the follow-on it is.
    "HealthCheckHttpReporter": _COMPOSER
    + " — CANDIDATE FOLLOW-ON: deserves adapters/observability/factory",
}


def _all_constructions() -> list[tuple[str, str]]:
    return [
        (callee, f"{py.relative_to(SRC.parent)}:{line}")
        for root in _ENTRY_MODULE
        for py in _iter_root_modules(root)
        for line, callee, _mod in _adapter_class_constructions(py)
    ]


def test_no_adapter_is_constructed_outside_its_factory_except_the_named_ones():
    """Assertion 2 (R1). A class imported from a non-factory `adapters.<pkg>.<module>` and
    called inside a root is a vendor binding bypassing its factory — the #301 shape — unless
    it is in the table above with a category. A NEW class fails here by name."""
    untabled = sorted(
        {
            f"{c} at {where}"
            for c, where in _all_constructions()
            if c not in _CONSTRUCTION_EXCEPTIONS
        }
    )
    assert not untabled, (
        "adapter constructed outside its factory and not in the exception table:\n  "
        + "\n  ".join(untabled)
    )


def test_every_named_exception_is_still_real():
    """The other direction: an exception nobody constructs any more is a stale allowlist that
    would readmit a future bypass under an old name (the _COUNTING_SETS lesson)."""
    live = {c for c, _ in _all_constructions()}
    stale = sorted(set(_CONSTRUCTION_EXCEPTIONS) - live)
    assert not stale, f"exception entries no root constructs any more — delete them: {stale}"


#: Assertion 3 — the bindings each root is EXPECTED to perform, per §6.6, transcribed from the
#: standard rather than from grep, so a binding that vanishes fails as surely as one that
#: bypasses its factory.
_EXPECTED_FACTORY_CALLS: dict[str, dict[str, int]] = {
    "squadops.api.runtime": {
        "create_llm_provider": 1,
        "create_queue_adapter": 1,
        "create_a2a_client": 1,
        "create_project_registry": 1,
        "create_cycle_registry": 1,
        "create_squad_profile_port": 2,
        "create_artifact_vault": 1,
        "create_workflow_tracker": 1,
        "create_cycle_event_bus": 1,
        "create_llm_observability_provider": 1,
        "create_flow_executor": 1,
        "create_auth_provider": 1,
    },
    "squadops.agents.entrypoint": {
        "create_llm_provider": 1,
        "create_queue_adapter": 1,
        "create_filesystem_provider": 1,
        "create_memory_provider": 1,
        "create_prompt_repository": 1,
        "create_prompt_asset_source": 2,
        "create_telemetry_provider": 1,
        "create_llm_observability_provider": 1,
        "create_a2a_server": 1,
    },
    "squadops.sandbox.main": {"create_sandbox_service": 1},
    # secret_provider_for is DEFINED here and called by the other roots; the binding this
    # package performs is the secrets adapter, through adapters.secrets.factory.
    "squadops.bootstrap": {"create_provider": 1},
}


def _factory_call_counts(root: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for py in _iter_root_modules(root):
        for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                counts[node.func.id] = counts.get(node.func.id, 0) + 1
    return counts


@pytest.mark.parametrize("root", sorted(_EXPECTED_FACTORY_CALLS))
def test_every_expected_binding_enters_through_its_factory(root):
    """Positive presence (R1): 'no direct construction' also passes when a binding is deleted
    outright. Counts are CALL SITES; a 2 is a documented if/else over one selector."""
    counts = _factory_call_counts(root)
    missing = {f: n for f, n in _EXPECTED_FACTORY_CALLS[root].items() if counts.get(f, 0) != n}
    actual = {k: counts.get(k, 0) for k in missing}
    assert not missing, (
        f"{root}: factory call sites differ from the declared bindings — "
        f"declared {missing}, actual {actual}"
    )


#: Assertion 4 — every selector a root's factory reads is REQUIRED in the schema (R2).
_SELECTORS = (
    ("LLMConfig", "provider"),
    ("QueueConfig", "provider"),
    ("A2AConfig", "provider"),
    ("FilesystemToolConfig", "provider"),
)


@pytest.mark.parametrize(("model", "field"), _SELECTORS)
def test_every_selector_is_required_not_defaulted(model, field):
    from squadops.config import schema

    assert getattr(schema, model).model_fields[field].is_required(), (
        f"{model}.{field} has a default — a defaulted selector is a masking fallback (R2)"
    )
