"""Shared validation heuristics, prompt sections, and file classification
for cycle task handlers (SIP-0086). Split from cycle_tasks.py (#152).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SIP-0086: Output validation framework
# ---------------------------------------------------------------------------

_STUB_THRESHOLD_BYTES = 100
_STUB_PATTERNS = ("# This file is kept empty", "# TODO", "pass\n", "# placeholder")

# Heuristic keyword mapping for legacy monolithic stack layer detection.
# These are bounded heuristics — not semantic truth. They catch obvious
# incompleteness (e.g., missing frontend for a PRD that says "React").
_STACK_INDICATORS: dict[str, dict[str, Any]] = {
    "backend": {
        "keywords": ["fastapi", "flask", "django", "uvicorn", "backend", "api endpoint"],
        "extensions": (".py",),
    },
    "frontend": {
        "keywords": ["react", "vue", "vite", "frontend", "jsx", "tsx", "component"],
        "extensions": (".jsx", ".tsx", ".js", ".ts", ".html", ".css"),
    },
    "test": {
        "keywords": ["pytest", "test", "jest", "vitest"],
        "extensions": (".py", ".js", ".ts"),
    },
    "config": {
        "keywords": ["requirements.txt", "package.json", "dockerfile"],
        "extensions": (".txt", ".json", ".yaml", ".yml", ".toml"),
    },
}


@dataclass
class ValidationResult:
    """Outcome of handler output validation (SIP-0086 §6.2)."""

    passed: bool
    checks: list[dict] = field(default_factory=list)
    missing_components: list[str] = field(default_factory=list)
    coverage_ratio: float = 1.0
    summary: str = ""


def _detect_stubs(artifacts: list[dict], threshold: int = _STUB_THRESHOLD_BYTES) -> list[str]:
    """Return filenames of stub artifacts (non-boilerplate files with trivial content)."""
    stubs = []
    for art in artifacts:
        content = art.get("content", "")
        name = art.get("name", "")
        if name.endswith("__init__.py"):
            continue
        if len(content) < threshold:
            if any(pat in content for pat in _STUB_PATTERNS) or not content.strip():
                stubs.append(name)
    return stubs


def _detect_expected_layers(prd: str, impl_plan: str | None = None) -> dict[str, tuple[str, ...]]:
    """Heuristic: detect required stack layers from PRD keywords.

    Returns dict of layer_name → file extensions for that layer.
    This is a bounded heuristic for catching obvious incompleteness,
    not a semantic truth engine.
    """
    combined = (prd + "\n" + (impl_plan or "")).lower()
    expected: dict[str, tuple[str, ...]] = {}
    for layer, indicators in _STACK_INDICATORS.items():
        if any(kw in combined for kw in indicators["keywords"]):
            expected[layer] = indicators["extensions"]
    return expected


def _estimate_min_artifacts(prd: str, impl_plan: str | None = None) -> int:
    """Heuristic: estimate minimum artifact count from PRD complexity.

    Rough estimate — catches extreme shortfalls (3 files for a full-stack app)
    but should not be treated as a precise requirement.
    """
    layers = _detect_expected_layers(prd, impl_plan)
    # At least 2 files per detected layer, minimum 3 total
    return max(3, len(layers) * 2)


# Issue #112: shared prompt section that drills the framing-time plan
# author on PRD-coverage discipline. Lives at module scope so BOTH
# manifest-producing prompts use the same source-of-truth text:
#   - GovernanceReviewHandler._MANIFEST_PROMPT_EXTENSION (this file)
#   - GovernanceReviewAssessReadinessHandler._produce_plan in
#     planning_tasks.py — the one the framing flow actually invokes
# Keeping the original PR #113 patch in cycle_tasks.py while ALSO wiring
# planning_tasks.py is defense-in-depth: any present-or-future caller of
# either prompt path gets the discipline.
def _rewrite_manifest_identifiers(
    yaml_content: str,
    project_id: str,
    cycle_id: str,
    prd_hash: str,
    handler_name: str,
) -> str:
    """Overwrite the top-level identifier fields with authoritative values.

    Issue #109: LLMs (especially small models) fabricate plausible-looking
    project_id / cycle_id / prd_hash values when asked to fill them in.
    These are facts the executor owns, so we rewrite them on the parsed
    YAML before persisting. Logs a structured warning when the LLM-emitted
    value disagreed so the rewrite stays observable.
    """
    import re

    rewritten = yaml_content
    fields = (
        ("project_id", project_id),
        ("cycle_id", cycle_id),
        ("prd_hash", prd_hash),
    )
    version_line_re = re.compile(r"^version:[ \t]*.*$", re.MULTILINE)
    for field_name, authoritative in fields:
        if not authoritative:
            continue
        pattern = re.compile(
            rf"^(?P<indent>[ \t]*){re.escape(field_name)}:[ \t]*(?P<value>.*)$",
            re.MULTILINE,
        )
        match = pattern.search(rewritten)
        if match is None:
            # Field missing entirely — inject after the version line so
            # the manifest validates downstream. Pre-pend if no version
            # line exists; from_yaml will surface the structural error.
            insertion = f"{field_name}: {authoritative}"
            v_match = version_line_re.search(rewritten)
            if v_match is None:
                rewritten = insertion + "\n" + rewritten
            else:
                end = v_match.end()
                rewritten = rewritten[:end] + "\n" + insertion + rewritten[end:]
            logger.warning(
                "%s: implementation_plan.yaml missing %s — injected authoritative value",
                handler_name,
                field_name,
            )
            continue
        emitted = match.group("value").strip()
        if emitted != authoritative:
            logger.warning(
                "%s: implementation_plan.yaml %s mismatch (LLM emitted %r, rewritten to %r)",
                handler_name,
                field_name,
                emitted[:64],
                authoritative,
            )
            rewritten = pattern.sub(
                f"{match.group('indent')}{field_name}: {authoritative}",
                rewritten,
                count=1,
            )
    return rewritten


_PRD_COVERAGE_DISCIPLINE_SECTION = (
    "## PRD Coverage Discipline (load-bearing)\n\n"
    "Before emitting the manifest, perform an explicit PRD ↔ acceptance_criteria "
    "coverage pass. This catches a recurring class of defect where the PRD mandates "
    "structural sub-requirements for a deliverable (e.g. required markdown sections, "
    "required model fields, required API endpoints, required config keys) but the "
    "plan's acceptance_criteria check only a subset, letting downstream agents ship "
    "files that pass the typed checks while violating the PRD.\n\n"
    "Procedure:\n"
    "1. List every deliverable file the PRD requires.\n"
    "2. For each deliverable, scan the PRD for structural sub-requirements stated "
    "about it. Common shapes:\n"
    "   - Markdown documents (`qa_handoff.md`, `README.md`): required section headers, "
    'e.g. "must contain ## How to Test and ## Expected Behavior sections".\n'
    "   - Data models / schemas: required fields, required field types.\n"
    "   - APIs / route maps: required endpoints (method + path), required status codes.\n"
    "   - Config files: required keys, required env vars.\n"
    "3. For every sub-requirement enumerated in step 2, ensure the manifest task that "
    "produces that deliverable has at least one acceptance_criteria typed check "
    "covering it. Pick the right check type for the shape:\n"
    "   - Required markdown section → `regex_match` on the section header pattern "
    '(e.g. `pattern: "## How to Test"`, `count_min: 1`).\n'
    "   - Required model field → `field_present` with the class_name and fields list.\n"
    "   - Required endpoint → `endpoint_defined` with methods_paths.\n"
    "   - Required import/symbol → `import_present` with module and symbol.\n"
    "   - Required config key → `regex_match` with the key pattern.\n"
    "4. If a sub-requirement has no covering typed check, ADD one to the manifest "
    "before emitting it. Do not emit a manifest with known coverage gaps.\n"
    "5. Surface the coverage mapping as a brief 'PRD Coverage' section in your output "
    "(in the governance review document if one is being produced; otherwise as a "
    "comment block at the top of the manifest YAML). This is the audit trail for "
    "the gate evaluator.\n\n"
    "Concrete worked example. PRD says:\n"
    "  > §10. The qa_handoff.md document must contain `## How to Test`, "
    "`## Expected Behavior`, and `## Known Limitations` sections.\n\n"
    "The manifest task producing `qa_handoff.md` must include three typed checks:\n"
    "```yaml\n"
    "acceptance_criteria:\n"
    "  - check: regex_match\n"
    '    description: "Contains How to Test section"\n'
    "    file: qa_handoff.md\n"
    '    pattern: "## How to Test"\n'
    "    count_min: 1\n"
    "  - check: regex_match\n"
    '    description: "Contains Expected Behavior section"\n'
    "    file: qa_handoff.md\n"
    '    pattern: "## Expected Behavior"\n'
    "    count_min: 1\n"
    "  - check: regex_match\n"
    '    description: "Contains Known Limitations section"\n'
    "    file: qa_handoff.md\n"
    '    pattern: "## Known Limitations"\n'
    "    count_min: 1\n"
    "```\n\n"
    'A pattern-only check like `pattern: "how to test|how to run"` is NOT '
    "sufficient — it can match running prose and lets the deliverable ship without "
    "the actual section header.\n"
)


def _build_typed_check_evaluation_artifact(
    validation_checks: list[dict],
    task_index: Any,
    task_type: str,
) -> dict | None:
    """Issue #114: serialize typed-acceptance evaluation rows for the gate evaluator.

    Returns an artifact dict suitable for ``outputs["artifacts"]``, or
    None when this task evaluated no typed checks (legacy monolithic
    flow, typed_acceptance disabled in resolved config, or prose-only
    acceptance criteria). Per the issue spec, absent is preferred over
    an empty artifact so the gate evaluator can distinguish "no checks
    ran" from "checks ran and all passed".
    """
    typed_rows = [
        c
        for c in validation_checks
        if isinstance(c.get("check"), str) and c["check"].startswith("acceptance:")
    ]
    if not typed_rows:
        return None

    payload = {
        "version": 1,
        "task_index": task_index,
        "task_type": task_type,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "evaluations": typed_rows,
    }
    suffix = f"_task_{task_index}" if task_index is not None else ""
    return {
        "name": f"typed_check_evaluation{suffix}.json",
        "content": json.dumps(payload, indent=2),
        "media_type": "application/json",
        "type": "typed_check_evaluation",
    }


# ---------------------------------------------------------------------------
# Extension → artifact type / media type mapping (D5)
# ---------------------------------------------------------------------------

_EXT_MAP: dict[str, tuple[str, str]] = {
    ".py": ("source", "text/x-python"),
    ".js": ("source", "text/javascript"),
    ".jsx": ("source", "text/javascript"),
    ".ts": ("source", "text/typescript"),
    ".tsx": ("source", "text/typescript"),
    ".mjs": ("source", "text/javascript"),
    ".css": ("source", "text/css"),
    ".html": ("source", "text/html"),
    ".md": ("document", "text/markdown"),
    ".txt": ("config", "text/plain"),
    ".yaml": ("config", "text/yaml"),
    ".yml": ("config", "text/yaml"),
    ".toml": ("config", "application/toml"),
    ".json": ("config", "application/json"),
}

# Special-cased filenames (checked before extension)
_FILENAME_MAP: dict[str, tuple[str, str]] = {
    "requirements.txt": ("config", "text/plain"),
    "package.json": ("config", "application/json"),
    "vite.config.js": ("config", "text/javascript"),
    "tsconfig.json": ("config", "application/json"),
}

_DEFAULT_TYPE = ("source", "application/octet-stream")


def _classify_file(filename: str) -> tuple[str, str]:
    """Derive (artifact_type, media_type) from filename."""
    import os

    basename = os.path.basename(filename)

    # Special-case filenames first
    if basename in _FILENAME_MAP:
        return _FILENAME_MAP[basename]

    _, ext = os.path.splitext(filename)
    return _EXT_MAP.get(ext.lower(), _DEFAULT_TYPE)


def _is_test_file(path: str, patterns: tuple[str, ...]) -> bool:
    """Check if *path* matches any test file pattern or resides in __tests__/.

    Uses fnmatch for glob-style pattern matching (D4).
    """
    from fnmatch import fnmatch
    from pathlib import PurePosixPath

    name = PurePosixPath(path).name
    return any(fnmatch(name, pat) for pat in patterns) or "/__tests__/" in path
