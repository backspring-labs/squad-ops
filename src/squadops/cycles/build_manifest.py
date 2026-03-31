"""Build Task Manifest — control-plane artifact for dynamic build decomposition (SIP-0086 §6.1).

The manifest is produced by GovernanceReviewHandler during planning and consumed
by generate_task_plan() after gate approval. It decomposes a build into focused
subtasks, each targeting a specific component with explicit expected artifacts
and acceptance criteria.

The approved manifest becomes immutable after gate approval (RC-1). Correction-
driven changes are represented as delta overlays, not mutations.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

import yaml


# Known task types that may appear in manifest tasks.
_KNOWN_BUILD_TASK_TYPES = {
    "development.develop",
    "qa.test",
    "builder.assemble",
}


@dataclass(frozen=True)
class ManifestTask:
    """A single focused build subtask within the manifest."""

    task_index: int
    task_type: str
    role: str
    focus: str
    description: str
    expected_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ManifestSummary:
    """Metadata summary for the manifest."""

    total_dev_tasks: int
    total_qa_tasks: int
    total_tasks: int
    estimated_layers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BuildTaskManifest:
    """Structured build decomposition plan — a control-plane artifact.

    Produced at planning time by GovernanceReviewHandler. Consumed at build
    time by generate_task_plan() to materialize focused build envelopes.
    """

    version: int
    project_id: str
    cycle_id: str
    prd_hash: str
    tasks: list[ManifestTask]
    summary: ManifestSummary

    @classmethod
    def from_yaml(cls, content: str) -> BuildTaskManifest:
        """Parse and validate a manifest from YAML string.

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
            raise ValueError("Manifest must be a YAML mapping")

        # Required top-level fields
        for key in ("version", "project_id", "cycle_id", "prd_hash", "tasks", "summary"):
            if key not in data:
                raise ValueError(f"Missing required field: {key}")

        tasks_data = data["tasks"]
        if not isinstance(tasks_data, list) or len(tasks_data) == 0:
            raise ValueError("Manifest must contain at least one task")

        # Parse tasks
        tasks: list[ManifestTask] = []
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

            tasks.append(
                ManifestTask(
                    task_index=task_index,
                    task_type=task_type,
                    role=td["role"],
                    focus=td["focus"],
                    description=td["description"],
                    expected_artifacts=td.get("expected_artifacts", []),
                    acceptance_criteria=td.get("acceptance_criteria", []),
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
        summary = ManifestSummary(
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
        """Check that all manifest roles exist in the squad profile.

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
        """Serialize to dict for YAML/JSON transport."""
        return dataclasses.asdict(self)


def _check_dependency_dag(tasks: list[ManifestTask]) -> None:
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
