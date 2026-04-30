"""Implementation Plan — control-plane artifact for dynamic build decomposition.

Originally introduced as the build task manifest in SIP-0086 §6.1. Renamed to
"implementation plan" by SIP-0092 to disambiguate from build/CI/Docker manifests
and to align with the artifact's actual role as the squad's plan for the build
phase.

The plan is produced during planning and consumed by generate_task_plan() after
gate approval. It decomposes a build into focused subtasks, each targeting a
specific component with explicit expected artifacts and acceptance criteria.

The approved plan becomes immutable after gate approval (RC-1). Correction-
driven changes are represented as plan changes (SIP-0092 M3), not mutations.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Union

import yaml

from squadops.cycles.acceptance_check_spec import (
    ALLOWED_SEVERITIES,
    CHECK_SPECS,
    reserved_keys_for,
)


# Known task types that may appear in plan tasks.
_KNOWN_BUILD_TASK_TYPES = {
    "development.develop",
    "qa.test",
    "builder.assemble",
}


@dataclass(frozen=True)
class TypedCheck:
    """Canonical internal form of a machine-evaluable acceptance criterion (SIP-0092 M1).

    Authored in YAML as a flat dict with check, severity, description, and
    check-specific param keys. The parser normalizes the flat shape into this
    dataclass so the evaluator framework (M1.2) doesn't need to re-parse the
    raw YAML.

    Attributes:
        check: Vocabulary name. Must be a key in CHECK_SPECS.
        params: Check-specific parameters. Equals the authored dict minus the
            reserved keys ({check, severity, description}).
        severity: One of {error, warning, info}. Defaults to ``error``.
            Per RC-9, only severity=error AND status ∈ {failed, error}
            blocks validation.
        description: Human-readable description for evidence/UI. Optional.
    """

    check: str
    params: dict
    severity: str = "error"
    description: str = ""


@dataclass(frozen=True)
class PlanTask:
    """A single focused build subtask within the plan."""

    task_index: int
    task_type: str
    role: str
    focus: str
    description: str
    expected_artifacts: list[str] = field(default_factory=list)
    # Mixed list: prose strings stay informational; TypedCheck instances are
    # machine-evaluated by the M1.2 framework. The parser normalizes flat-YAML
    # typed entries into TypedCheck (see ImplementationPlan.from_yaml).
    acceptance_criteria: list[Union[str, TypedCheck]] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class PlanSummary:
    """Metadata summary for the plan."""

    total_dev_tasks: int
    total_qa_tasks: int
    total_tasks: int
    estimated_layers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImplementationPlan:
    """Structured build decomposition plan — a control-plane artifact.

    Produced at planning time by GovernanceReviewHandler. Consumed at build
    time by generate_task_plan() to materialize focused build envelopes.
    """

    version: int
    project_id: str
    cycle_id: str
    prd_hash: str
    tasks: list[PlanTask]
    summary: PlanSummary

    @classmethod
    def from_yaml(cls, content: str) -> ImplementationPlan:
        """Parse and validate a plan from YAML string.

        Performs structural validation: required fields, known task types,
        dependency DAG correctness, and non-empty task list.

        Policy validation (min/max subtask counts) is NOT performed here —
        that belongs in the handler/executor using resolved config.

        Raises:
            ValueError: If the YAML is malformed or structurally invalid.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Plan must be a YAML mapping")

        # Required top-level fields
        for key in ("version", "project_id", "cycle_id", "prd_hash", "tasks", "summary"):
            if key not in data:
                raise ValueError(f"Missing required field: {key}")

        tasks_data = data["tasks"]
        if not isinstance(tasks_data, list) or len(tasks_data) == 0:
            raise ValueError("Plan must contain at least one task")

        # Parse tasks
        tasks: list[PlanTask] = []
        seen_indices: set[int] = set()
        for i, td in enumerate(tasks_data):
            if not isinstance(td, dict):
                raise ValueError(f"Task {i} must be a mapping")

            for req in ("task_index", "task_type", "role", "focus", "description"):
                if req not in td:
                    raise ValueError(f"Task {i} missing required field: {req}")

            task_type = td["task_type"]
            if task_type not in _KNOWN_BUILD_TASK_TYPES:
                raise ValueError(
                    f"Task {i}: unknown task_type '{task_type}'. "
                    f"Known types: {', '.join(sorted(_KNOWN_BUILD_TASK_TYPES))}"
                )

            task_index = td["task_index"]
            if task_index in seen_indices:
                raise ValueError(f"Duplicate task_index: {task_index}")
            seen_indices.add(task_index)

            depends_on = td.get("depends_on", [])
            if not isinstance(depends_on, list):
                raise ValueError(f"Task {task_index}: depends_on must be a list")

            raw_criteria = td.get("acceptance_criteria", [])
            if not isinstance(raw_criteria, list):
                raise ValueError(
                    f"Task {task_index}: acceptance_criteria must be a list"
                )
            criteria = _parse_acceptance_criteria(raw_criteria, task_index)

            tasks.append(
                PlanTask(
                    task_index=task_index,
                    task_type=task_type,
                    role=td["role"],
                    focus=td["focus"],
                    description=td["description"],
                    expected_artifacts=td.get("expected_artifacts", []),
                    acceptance_criteria=criteria,
                    depends_on=depends_on,
                )
            )

        # Validate dependency references
        all_indices = {t.task_index for t in tasks}
        for task in tasks:
            for dep in task.depends_on:
                if dep not in all_indices:
                    raise ValueError(
                        f"Task {task.task_index}: depends_on references "
                        f"non-existent task_index {dep}"
                    )

        # Validate no dependency cycles
        _check_dependency_dag(tasks)

        # Parse summary
        summary_data = data["summary"]
        if not isinstance(summary_data, dict):
            raise ValueError("summary must be a mapping")
        summary = PlanSummary(
            total_dev_tasks=summary_data.get("total_dev_tasks", 0),
            total_qa_tasks=summary_data.get("total_qa_tasks", 0),
            total_tasks=summary_data.get("total_tasks", len(tasks)),
            estimated_layers=summary_data.get("estimated_layers", []),
        )

        return cls(
            version=data["version"],
            project_id=data["project_id"],
            cycle_id=data["cycle_id"],
            prd_hash=data["prd_hash"],
            tasks=tasks,
            summary=summary,
        )

    def validate_against_profile(self, profile: object) -> list[str]:
        """Check that all plan roles exist in the squad profile.

        Args:
            profile: A SquadProfile object with an ``agents`` attribute.

        Returns:
            List of validation error strings (empty = valid).
        """
        available_roles = {a.role for a in profile.agents if a.enabled}  # type: ignore[attr-defined]
        errors: list[str] = []
        for task in self.tasks:
            if task.role not in available_roles:
                errors.append(
                    f"Task {task.task_index}: role '{task.role}' not in profile"
                )
        return errors

    def to_dict(self) -> dict:
        """Serialize to dict for YAML/JSON transport.

        TypedCheck entries in ``acceptance_criteria`` are serialized as flat
        authored-form mappings (params spread to top level alongside check /
        severity / description), matching the on-disk YAML schema parsed by
        ``from_yaml``. This makes round-trip ``from_yaml → to_dict → safe_dump
        → from_yaml`` a stable identity, which is load-bearing for the
        canonical-hashing helper SIP-0092 M3 introduces.
        """
        result = dataclasses.asdict(self)
        for task_dict, task in zip(result["tasks"], self.tasks):
            task_dict["acceptance_criteria"] = [
                _serialize_acceptance_criterion(c) for c in task.acceptance_criteria
            ]
        return result


def _check_dependency_dag(tasks: list[PlanTask]) -> None:
    """Validate that task dependencies form a DAG (no cycles).

    Raises:
        ValueError: If a dependency cycle is detected.
    """
    # Build adjacency list
    adj: dict[int, list[int]] = {t.task_index: list(t.depends_on) for t in tasks}
    visited: set[int] = set()
    in_stack: set[int] = set()

    def _visit(node: int) -> None:
        if node in in_stack:
            raise ValueError(f"Dependency cycle detected involving task_index {node}")
        if node in visited:
            return
        in_stack.add(node)
        for dep in adj.get(node, []):
            _visit(dep)
        in_stack.remove(node)
        visited.add(node)

    for task in tasks:
        _visit(task.task_index)


def _serialize_acceptance_criterion(c: Union[str, TypedCheck]) -> Union[str, dict]:
    """Inverse of the parser's flat-YAML normalization.

    str entries pass through unchanged. TypedCheck entries become flat dicts
    with the wrapper keys (check, severity, description) at top level next to
    the check-specific params.
    """
    if isinstance(c, str):
        return c
    flat: dict = {"check": c.check}
    flat.update(c.params)
    flat["severity"] = c.severity
    if c.description:
        flat["description"] = c.description
    return flat


def _parse_acceptance_criteria(
    raw: list, task_index: int
) -> list[Union[str, TypedCheck]]:
    """Parse a mixed acceptance_criteria list per SIP-0092 M1.

    Accepts:
        - str items: kept as-is (informational prose)
        - dict items: normalized into TypedCheck per the flat-YAML rule
          (params = dict minus reserved keys {check, severity, description})

    Authoring-time rejections (RC-11):
        - Unknown check name (not in CHECK_SPECS).
        - Missing required param per CHECK_SPECS[check].required_params.
        - Wrong-type param per CHECK_SPECS[check].param_types.
        - Unknown param key (not in required_params ∪ optional_params).
        - Unknown severity value (not in {error, warning, info}).
        - Path-typed param value containing absolute path or '..' traversal
          (cheap pre-eval rejection; full chrooting still applies at
          evaluation time per RC-10).

    Returns:
        Mixed list of str and TypedCheck instances, preserving authored order.
    """
    parsed: list[Union[str, TypedCheck]] = []
    for j, item in enumerate(raw):
        if isinstance(item, str):
            parsed.append(item)
            continue

        if not isinstance(item, dict):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"each entry must be a string (informational) or mapping (typed)"
            )

        # Typed check — must declare which check
        if "check" not in item:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"typed criterion missing required key 'check'"
            )
        check_name = item["check"]
        if not isinstance(check_name, str):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"'check' must be a string"
            )
        if check_name not in CHECK_SPECS:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"unknown check '{check_name}'. "
                f"Known checks: {', '.join(sorted(CHECK_SPECS))}"
            )

        spec = CHECK_SPECS[check_name]

        # Severity
        severity = item.get("severity", "error")
        if severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): unknown severity '{severity}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_SEVERITIES))}"
            )

        # Description
        description = item.get("description", "")
        if not isinstance(description, str):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): 'description' must be a string"
            )

        # Params = item minus reserved keys
        reserved = reserved_keys_for(check_name)
        params = {k: v for k, v in item.items() if k not in reserved}

        # Required params
        missing = spec.required_params - set(params)
        if missing:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): missing required param(s): "
                f"{', '.join(sorted(missing))}"
            )

        # Unknown params
        allowed_params = spec.required_params | spec.optional_params
        unknown = set(params) - allowed_params
        if unknown:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): unknown param(s): "
                f"{', '.join(sorted(unknown))}. "
                f"Allowed: {', '.join(sorted(allowed_params))}"
            )

        # Param types
        for key, value in params.items():
            expected = spec.param_types.get(key)
            if expected is None:
                continue  # spec didn't declare a type; tolerated
            if not isinstance(value, expected):
                expected_name = (
                    expected.__name__
                    if isinstance(expected, type)
                    else " | ".join(t.__name__ for t in expected)
                )
                raise ValueError(
                    f"Task {task_index}.acceptance_criteria[{j}] "
                    f"({check_name}): param '{key}' must be {expected_name}, "
                    f"got {type(value).__name__}"
                )

        # Path-traversal pre-eval rejection
        for path_key in spec.path_params:
            if path_key in params:
                _reject_unsafe_path(
                    params[path_key], path_key, task_index, j, check_name
                )

        parsed.append(
            TypedCheck(
                check=check_name,
                params=params,
                severity=severity,
                description=description,
            )
        )

    return parsed


def _reject_unsafe_path(
    value: object, key: str, task_index: int, criterion_index: int, check_name: str
) -> None:
    """Cheap pre-evaluation rejection of obviously unsafe paths.

    Full chrooting and symlink rejection still happens at evaluation time
    (M1.2, RC-10). This catches authoring errors at parse time so the squad
    sees feedback at the gate rather than at hour 2 of build.
    """
    if not isinstance(value, str):
        return  # type validation already handled by param_types check
    if value.startswith("/") or value.startswith("\\"):
        raise ValueError(
            f"Task {task_index}.acceptance_criteria[{criterion_index}] "
            f"({check_name}): {key}={value!r} is absolute "
            f"(must be workspace-relative)"
        )
    parts = value.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError(
            f"Task {task_index}.acceptance_criteria[{criterion_index}] "
            f"({check_name}): {key}={value!r} contains '..' traversal"
        )
