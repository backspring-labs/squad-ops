"""
Acceptance Check Engine for validating capability artifacts.

Implements path security (chroot enforcement), template resolution,
and the v1 check types: file_exists, non_empty, json_field_equals.

Async check types (SIP-0070): http_status, process_running, json_schema,
command_exit_code via evaluate_async/evaluate_all_async.

Per SIP-0.8.6 semantics:
- Template syntax: {variable}
- Path security: segment-aware '..' rejection, Path.resolve() + is_relative_to()
- No short-circuit: all checks are evaluated even if some fail
- json_field_equals uses strict type comparison
"""

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from squadops.capabilities.exceptions import (
    PathEscapeError,
    TemplateResolutionError,
)
from squadops.capabilities.models import (
    AcceptanceCheck,
    AcceptanceContext,
    AcceptanceResult,
    CheckType,
    ValidationReport,
)

logger = logging.getLogger(__name__)

# Template variable pattern: {variable_name} or {task.output_name} or {vars.name}
TEMPLATE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")

# Simple (non-dotted) variables that resolve_template() recognises.
# Dot-path prefixes (vars.*, task_id.*) are open-ended and validated separately.
KNOWN_TEMPLATE_VARIABLES: frozenset[str] = frozenset(
    {"cycle_id", "workload_id", "run_root", "run_id"}
)

# Dot-path prefixes that are valid in template resolution.
KNOWN_TEMPLATE_PREFIXES: frozenset[str] = frozenset({"vars"})


def validate_template_variables(template: str) -> list[str]:
    """Return unknown template variables in *template*.

    Known simple variables (cycle_id, run_id, etc.) and known dot-path
    prefixes (vars.*) are accepted.  Everything else is returned as an
    error string suitable for embedding in a ValueError message.
    """
    errors: list[str] = []
    for match in TEMPLATE_PATTERN.finditer(template):
        var = match.group(1)
        if var in KNOWN_TEMPLATE_VARIABLES:
            continue
        parts = var.split(".", 1)
        if len(parts) == 2 and parts[0] in KNOWN_TEMPLATE_PREFIXES:
            continue
        errors.append(var)
    return errors


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

    def resolve_template(self, template: str, context: AcceptanceContext) -> str:
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
            if var_path == "run_id":
                return context.run_id

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

    def validate_and_resolve_path(self, path_template: str, context: AcceptanceContext) -> Path:
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
            raise PathEscapeError(resolved_str, str(self.chroot)) from None

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

    def _check_file_exists(self, path: Path, check: AcceptanceCheck) -> AcceptanceResult:
        """Evaluate file_exists check."""
        exists = path.exists() and path.is_file()
        return AcceptanceResult(
            check=check,
            passed=exists,
            resolved_path=str(path),
            error=None if exists else f"File does not exist: {path}",
        )

    def _check_non_empty(self, path: Path, check: AcceptanceCheck) -> AcceptanceResult:
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

    def _check_json_field_equals(self, path: Path, check: AcceptanceCheck) -> AcceptanceResult:
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
            with open(path, encoding="utf-8") as f:
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
        passed = actual == expected and type(actual) is type(expected)

        error = None
        if not passed:
            if type(actual) is not type(expected):
                error = (
                    f"Type mismatch at '{check.field_path}': "
                    f"expected {type(expected).__name__}({expected!r}), "
                    f"got {type(actual).__name__}({actual!r})"
                )
            else:
                error = (
                    f"Value mismatch at '{check.field_path}': expected {expected!r}, got {actual!r}"
                )

        return AcceptanceResult(
            check=check,
            passed=passed,
            resolved_path=str(path),
            actual_value=actual,
            error=error,
        )

    def evaluate(self, check: AcceptanceCheck, context: AcceptanceContext) -> AcceptanceResult:
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

    # =========================================================================
    # Async check methods (SIP-0070: Pulse Check Verification)
    # =========================================================================

    # Minimal safe PATH baseline for command_exit_code (D3)
    _SAFE_PATH = "/usr/bin:/usr/local/bin"

    async def _check_http_status(
        self,
        check: AcceptanceCheck,
        context: AcceptanceContext,
        timeout: float,
    ) -> AcceptanceResult:
        """Evaluate http_status check via async HTTP GET."""
        import httpx

        resolved_url = self.resolve_template(check.url, context)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(resolved_url, timeout=timeout)
            passed = resp.status_code == check.expected_status
            error = (
                None
                if passed
                else (f"Expected status {check.expected_status}, got {resp.status_code}")
            )
            return AcceptanceResult(
                check=check,
                passed=passed,
                resolved_path=resolved_url,
                actual_value=resp.status_code,
                error=error,
            )
        except httpx.ConnectError as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=resolved_url,
                error=f"Connection error: {e}",
            )
        except httpx.TimeoutException:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=resolved_url,
                error=f"HTTP request timed out after {timeout}s",
            )
        except Exception as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=resolved_url,
                error=f"HTTP check error: {e}",
            )

    async def _check_process_running(
        self,
        check: AcceptanceCheck,
        context: AcceptanceContext,
        timeout: float,
    ) -> AcceptanceResult:
        """Evaluate process_running check via docker inspect."""
        container = self.resolve_template(check.container_name, context)
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "inspect",
                "--format",
                "{{json .State}}",
                container,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                return AcceptanceResult(
                    check=check,
                    passed=False,
                    resolved_path=container,
                    error=f"Container not found: {container}",
                )
            state = json.loads(stdout.decode())
            running = state.get("Running", False)
            health = state.get("Health", {})
            health_status = health.get("Status") if health else None

            if not running:
                return AcceptanceResult(
                    check=check,
                    passed=False,
                    resolved_path=container,
                    actual_value={"running": False, "health": health_status},
                    error=f"Container {container} is not running",
                )

            if health_status and health_status != "healthy":
                return AcceptanceResult(
                    check=check,
                    passed=False,
                    resolved_path=container,
                    actual_value={"running": True, "health": health_status},
                    error=f"Container {container} is running but unhealthy: {health_status}",
                )

            return AcceptanceResult(
                check=check,
                passed=True,
                resolved_path=container,
                actual_value={"running": True, "health": health_status},
            )
        except TimeoutError:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=container,
                error=f"Docker inspect timed out after {timeout}s",
            )
        except Exception as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=container,
                error=f"Process check error: {e}",
            )

    async def _check_json_schema(
        self,
        check: AcceptanceCheck,
        context: AcceptanceContext,
    ) -> AcceptanceResult:
        """Evaluate json_schema check by validating document against schema."""
        import jsonschema

        try:
            doc_path = self.validate_and_resolve_path(check.target, context)
        except (PathEscapeError, TemplateResolutionError) as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=check.target,
                error=str(e),
            )

        schema_path = self.chroot / check.schema
        if not doc_path.exists():
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(doc_path),
                error=f"Document not found: {doc_path}",
            )
        if not schema_path.exists():
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(doc_path),
                error=f"Schema not found: {schema_path}",
            )

        try:
            doc_data = json.loads(doc_path.read_text(encoding="utf-8"))
            schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(doc_path),
                error=f"Invalid JSON: {e}",
            )

        try:
            jsonschema.validate(instance=doc_data, schema=schema_data)
            return AcceptanceResult(
                check=check,
                passed=True,
                resolved_path=str(doc_path),
            )
        except jsonschema.ValidationError as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=str(doc_path),
                error=f"Schema validation failed: {e.message}",
            )

    async def _check_command_exit_code(
        self,
        check: AcceptanceCheck,
        context: AcceptanceContext,
        timeout: float,
        max_output_bytes: int = 65536,
    ) -> AcceptanceResult:
        """Evaluate command_exit_code check via subprocess (D3 security)."""
        # Build env: allowlist-only with safe PATH baseline (no os.environ inheritance)
        cmd_env = {"PATH": self._SAFE_PATH}
        for key, val in check.env:
            cmd_env[key] = self.resolve_template(val, context)

        # Resolve cwd relative to chroot (absolute + .. already rejected by __post_init__)
        cwd = None
        if check.cwd:
            resolved_cwd = self.resolve_template(check.cwd, context)
            cwd = str(self.chroot / resolved_cwd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *check.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env,
            )
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=" ".join(check.command),
                error=f"Command timed out after {timeout}s",
            )
        except FileNotFoundError:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=" ".join(check.command),
                error=f"Command not found: {check.command[0]}",
            )
        except Exception as e:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=" ".join(check.command),
                error=f"Command execution error: {e}",
            )

        # Truncation metadata (D20)
        stdout_bytes = len(stdout_data)
        stderr_bytes = len(stderr_data)
        stdout_truncated = stdout_bytes > max_output_bytes
        stderr_truncated = stderr_bytes > max_output_bytes
        truncated = stdout_truncated or stderr_truncated

        stderr_text = stderr_data[:max_output_bytes].decode("utf-8", errors="replace")

        meta: dict = {}
        if truncated:
            meta = {
                "truncated": True,
                "stdout_bytes": stdout_bytes,
                "stderr_bytes": stderr_bytes,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            }

        passed = proc.returncode == check.expected_exit_code
        error = None
        if not passed:
            error = f"Expected exit code {check.expected_exit_code}, got {proc.returncode}"
            if stderr_text.strip():
                error += f"\nstderr: {stderr_text.strip()[:500]}"

        return AcceptanceResult(
            check=check,
            passed=passed,
            resolved_path=" ".join(check.command),
            actual_value=proc.returncode,
            error=error,
            metadata=meta,
        )

    async def evaluate_async(
        self,
        check: AcceptanceCheck,
        context: AcceptanceContext,
        *,
        max_check_seconds: float = 10,
        max_output_bytes: int = 65536,
    ) -> AcceptanceResult:
        """Evaluate a single acceptance check (async-capable).

        Dispatches to the appropriate check method. For sync check types
        (file_exists, non_empty, json_field_equals), delegates to the
        sync evaluate() method. For async types, uses the async methods.
        """
        if check.check_type in (
            CheckType.FILE_EXISTS,
            CheckType.NON_EMPTY,
            CheckType.JSON_FIELD_EQUALS,
        ):
            return self.evaluate(check, context)

        try:
            if check.check_type == CheckType.HTTP_STATUS:
                return await asyncio.wait_for(
                    self._check_http_status(check, context, max_check_seconds),
                    timeout=max_check_seconds,
                )
            elif check.check_type == CheckType.PROCESS_RUNNING:
                return await asyncio.wait_for(
                    self._check_process_running(check, context, max_check_seconds),
                    timeout=max_check_seconds,
                )
            elif check.check_type == CheckType.JSON_SCHEMA:
                return await self._check_json_schema(check, context)
            elif check.check_type == CheckType.COMMAND_EXIT_CODE:
                return await asyncio.wait_for(
                    self._check_command_exit_code(
                        check, context, max_check_seconds, max_output_bytes
                    ),
                    timeout=max_check_seconds,
                )
            else:
                return AcceptanceResult(
                    check=check,
                    passed=False,
                    resolved_path=check.target,
                    error=f"Unknown check type: {check.check_type}",
                )
        except TimeoutError:
            return AcceptanceResult(
                check=check,
                passed=False,
                resolved_path=check.target,
                error=f"Check timed out after {max_check_seconds}s",
            )

    async def evaluate_all_async(
        self,
        checks: tuple[AcceptanceCheck, ...],
        context: AcceptanceContext,
        *,
        max_suite_seconds: float = 30,
        max_check_seconds: float = 10,
        max_output_bytes: int = 65536,
    ) -> ValidationReport:
        """Evaluate all checks sequentially (no short-circuit, D4).

        Suite-level timeout: remaining checks after timeout are SKIPPED
        with reason_code="suite_timeout". Suite outcome is FAIL when any
        check is skipped due to timeout (D18: incomplete evidence is not PASS).
        """
        results: list[AcceptanceResult] = []
        suite_start = time.monotonic()

        for check in checks:
            elapsed = time.monotonic() - suite_start
            remaining = max_suite_seconds - elapsed
            if remaining <= 0:
                # Suite timeout — SKIP remaining checks (D18)
                results.append(
                    AcceptanceResult(
                        check=check,
                        passed=False,
                        resolved_path=check.target,
                        error="Skipped: suite timeout exceeded",
                        reason_code="suite_timeout",
                    )
                )
                continue

            per_check_timeout = min(max_check_seconds, remaining)
            result = await self.evaluate_async(
                check,
                context,
                max_check_seconds=per_check_timeout,
                max_output_bytes=max_output_bytes,
            )
            results.append(result)
            logger.debug(
                "Acceptance check %s on %s: %s",
                check.check_type.value,
                check.target,
                "PASSED" if result.passed else "FAILED",
            )

        return ValidationReport(results=tuple(results))
