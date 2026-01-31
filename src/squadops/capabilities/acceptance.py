"""
Acceptance Check Engine for validating capability artifacts.

Implements path security (chroot enforcement), template resolution,
and the v1 check types: file_exists, non_empty, json_field_equals.

Per SIP-0.8.6 semantics:
- Template syntax: {variable}
- Path security: segment-aware '..' rejection, Path.resolve() + is_relative_to()
- No short-circuit: all checks are evaluated even if some fail
- json_field_equals uses strict type comparison
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from squadops.capabilities.models import (
    AcceptanceCheck,
    AcceptanceContext,
    AcceptanceResult,
    CheckType,
    ValidationReport,
)
from squadops.capabilities.exceptions import (
    PathEscapeError,
    TemplateResolutionError,
)

logger = logging.getLogger(__name__)

# Template variable pattern: {variable_name} or {task.output_name} or {vars.name}
TEMPLATE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


class AcceptanceCheckEngine:
    """
    Engine for evaluating acceptance checks against artifacts.

    Provides template resolution, path security validation, and
    check execution with no short-circuit behavior.
    """

    def __init__(self, chroot: Path | str):
        """
        Initialize the acceptance check engine.

        Args:
            chroot: Root directory boundary for path security
        """
        self.chroot = Path(chroot).resolve()

    def resolve_template(
        self, template: str, context: AcceptanceContext
    ) -> str:
        """
        Resolve {variable} placeholders in a template string.

        Supported variables:
        - {cycle_id}: Current cycle identifier
        - {workload_id}: Workload identifier
        - {run_root}: Run root directory
        - {vars.name}: Workload variable
        - {task_id.output_name}: Task output value

        Args:
            template: Template string with {variable} placeholders
            context: Acceptance context with values for resolution

        Returns:
            Resolved string with all placeholders replaced

        Raises:
            TemplateResolutionError: If a variable cannot be resolved
        """

        def replace_match(match: re.Match) -> str:
            var_path = match.group(1)

            # Simple variables
            if var_path == "cycle_id":
                return context.cycle_id
            if var_path == "workload_id":
                return context.workload_id
            if var_path == "run_root":
                return context.run_root

            # Dot-path variables
            parts = var_path.split(".", 1)
            if len(parts) == 2:
                prefix, name = parts

                # {vars.name} - workload variables
                if prefix == "vars":
                    value = context.get_var(name)
                    if value is None:
                        raise TemplateResolutionError(template, var_path)
                    return str(value)

                # {task_id.output_name} - task outputs
                for task_id, outputs in context.task_outputs:
                    if task_id == prefix and name in outputs:
                        return str(outputs[name])

            raise TemplateResolutionError(template, var_path)

        return TEMPLATE_PATTERN.sub(replace_match, template)

    def validate_and_resolve_path(
        self, path_template: str, context: AcceptanceContext
    ) -> Path:
        """
        Resolve and validate a path template with chroot enforcement.

        Security checks:
        1. Reject '..' as a path segment (escape attempt)
        2. Resolve the path and verify it's within chroot

        Note: '..' as a substring within a segment name is allowed
        (e.g., 'file..name.txt' is valid).

        Args:
            path_template: Path template with {variable} placeholders
            context: Acceptance context for template resolution

        Returns:
            Resolved and validated Path

        Raises:
            PathEscapeError: If path attempts to escape chroot
            TemplateResolutionError: If template cannot be resolved
        """
        # Resolve template variables
        resolved_str = self.resolve_template(path_template, context)

        # Check for '..' as a path segment (escape attempt)
        # Split on both forward and back slashes
        segments = re.split(r"[/\\]", resolved_str)
        for segment in segments:
            if segment == "..":
                raise PathEscapeError(resolved_str, str(self.chroot))

        # Build and resolve the path
        resolved_path = (self.chroot / resolved_str).resolve()

        # Verify path is within chroot
        try:
            resolved_path.relative_to(self.chroot)
        except ValueError:
            raise PathEscapeError(resolved_str, str(self.chroot))

        return resolved_path

    def _get_json_field(self, data: Any, field_path: str) -> tuple[bool, Any]:
        """
        Navigate to a field in JSON data using dot-path notation.

        Args:
            data: JSON data (dict or nested structure)
            field_path: Dot-separated path (e.g., "metadata.status")

        Returns:
            Tuple of (found: bool, value: Any)
        """
        parts = field_path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False, None

        return True, current

    def _check_file_exists(
        self, path: Path, check: AcceptanceCheck
    ) -> AcceptanceResult:
        """Evaluate file_exists check."""
        exists = path.exists() and path.is_file()
        return AcceptanceResult(
            check=check,
            passed=exists,
            resolved_path=str(path),
            error=None if exists else f"File does not exist: {path}",
        )

    def _check_non_empty(
        self, path: Path, check: AcceptanceCheck
    ) -> AcceptanceResult:
        """Evaluate non_empty check."""
        if not path.exists():
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                error=f"File does not exist: {path}",
            )

        if not path.is_file():
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                error=f"Not a file: {path}",
            )

        size = path.stat().st_size
        passed = size > 0
        return AcceptanceResult(
            check=check,
            passed=passed,
            resolved_path=str(path),
            error=None if passed else f"File is empty: {path}",
        )

    def _check_json_field_equals(
        self, path: Path, check: AcceptanceCheck
    ) -> AcceptanceResult:
        """
        Evaluate json_field_equals check with strict type comparison.

        Type comparison is strict:
        - int 1 != float 1.0
        - string "true" != boolean True
        """
        if not path.exists():
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                error=f"File does not exist: {path}",
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                error=f"Invalid JSON: {e}",
            )
        except Exception as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                error=f"Failed to read file: {e}",
            )

        found, actual = self._get_json_field(data, check.field_path)

        if not found:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                actual_value=None,
                error=f"Field not found: {check.field_path}",
            )

        # Strict type comparison
        expected = check.expected_value
        passed = actual == expected and type(actual) == type(expected)

        error = None
        if not passed:
            if type(actual) != type(expected):
                error = (
                    f"Type mismatch at '{check.field_path}': "
                    f"expected {type(expected).__name__}({expected!r}), "
                    f"got {type(actual).__name__}({actual!r})"
                )
            else:
                error = (
                    f"Value mismatch at '{check.field_path}': "
                    f"expected {expected!r}, got {actual!r}"
                )

        return AcceptanceResult(
            check=check,
            passed=passed,
            resolved_path=str(path),
            actual_value=actual,
            error=error,
        )

    def evaluate(
        self, check: AcceptanceCheck, context: AcceptanceContext
    ) -> AcceptanceResult:
        """
        Evaluate a single acceptance check.

        Args:
            check: The acceptance check to evaluate
            context: Acceptance context for template resolution

        Returns:
            AcceptanceResult with pass/fail status
        """
        try:
            path = self.validate_and_resolve_path(check.target, context)
        except PathEscapeError as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=check.target,
                error=str(e),
            )
        except TemplateResolutionError as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=check.target,
                error=str(e),
            )

        if check.check_type == CheckType.FILE_EXISTS:
            return self._check_file_exists(path, check)
        elif check.check_type == CheckType.NON_EMPTY:
            return self._check_non_empty(path, check)
        elif check.check_type == CheckType.JSON_FIELD_EQUALS:
            return self._check_json_field_equals(path, check)
        else:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(path),
                error=f"Unknown check type: {check.check_type}",
            )

    def evaluate_all(
        self, checks: tuple[AcceptanceCheck, ...], context: AcceptanceContext
    ) -> ValidationReport:
        """
        Evaluate all acceptance checks without short-circuit.

        All checks are evaluated even if some fail, providing a
        complete validation report.

        Args:
            checks: Tuple of acceptance checks to evaluate
            context: Acceptance context for template resolution

        Returns:
            ValidationReport with all results
        """
        results = []
        for check in checks:
            result = self.evaluate(check, context)
            results.append(result)
            logger.debug(
                f"Acceptance check {check.check_type.value} on {check.target}: "
                f"{'PASSED' if result.passed else 'FAILED'}"
            )

        return ValidationReport(results=tuple(results))
