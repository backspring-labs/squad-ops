"""Plan authoring service (SIP-0093 PR 93.0).

Function-style service that produces the canonical ``implementation_plan.yaml``
from planning context (PRD + planning artifact + resolved config). The body is
extracted verbatim from ``GovernanceReviewPlanHandler._produce_plan`` so the
SIP-0093 propose/merge cutover (PR 93.3) can reuse one implementation: the
merger calls this service for sole-author cycles (configured empty
contributors, or all proposals failed), and PR 93.0 keeps the current
``governance.review_plan`` route running unchanged by calling the service
inline.

This module is deliberately stateless — every dependency is passed in. The
only knobs that came from the handler instance are ``role``, ``handler_name``,
and ``chat_kwargs``; the caller computes those once and hands them in.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any

from squadops.capabilities.handlers.cycle_tasks import (
    _PRD_COVERAGE_DISCIPLINE_SECTION,
    _rewrite_manifest_identifiers,
)
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.cycles.implementation_plan import (
    ImplementationPlan,
    planner_build_task_types,
)
from squadops.llm.models import ChatMessage

if TYPE_CHECKING:
    from squadops.capabilities.handlers.context import ExecutionContext

logger = logging.getLogger(__name__)


async def produce_plan(
    context: ExecutionContext,
    inputs: dict[str, Any],
    planning_content: str,
    resolved_config: dict[str, Any],
    *,
    role: str,
    handler_name: str,
    chat_kwargs: dict[str, Any],
) -> dict[str, Any] | None:
    """Generate the canonical ``implementation_plan.yaml`` artifact.

    Returns the manifest artifact dict (``{name, content, media_type, type}``)
    on success, or ``None`` on graceful fallback when the LLM cannot produce a
    valid plan within the retry budget (RC-4).

    Verbatim equivalence with the pre-extraction ``_produce_plan`` is the gate
    for PR 93.0 — same seeded LLM responses must produce the same parsed
    ``ImplementationPlan``.
    """

    prd = inputs.get("prd", "")

    profile_roles = inputs.get("profile_roles") or []
    has_builder = "builder" in profile_roles
    roles_section = (
        f"Available roles (use ONLY these; do NOT invent new ones): {', '.join(profile_roles)}\n\n"
        if profile_roles
        else ""
    )

    # Only offer task types the squad can actually execute: builder.assemble
    # needs the builder role, so a builder-less squad must not be offered it
    # (else the LLM authors a task that aborts at dispatch with
    # "No handler for capability: builder.assemble").
    allowed_task_types = sorted(planner_build_task_types(has_builder=has_builder))
    task_types_section = (
        f"Available task_types (use ONLY these; do NOT invent new ones): "
        f"{', '.join(allowed_task_types)}\n\n"
    )

    if has_builder:
        builder_guideline = (
            "- Route packaging, entrypoints, requirements.txt/package.json, "
            "Dockerfile/startup scripts, and qa_handoff.md to `builder.assemble` "
            "tasks (role: builder). Place AFTER all `development.develop` tasks "
            "and BEFORE any `qa.test` tasks.\n"
        )
        qa_handoff_guideline = ""
        builder_example = (
            "  - task_index: 1\n"
            "    task_type: builder.assemble\n"
            "    role: builder\n"
            '    focus: "Package build output and produce qa_handoff.md"\n'
            "    description: |\n"
            "      Assemble packaging (entrypoints, requirements/manifest, "
            "Dockerfile if applicable) and write qa_handoff.md summarizing "
            "how to run and test the build.\n"
            "    expected_artifacts:\n"
            '      - "qa_handoff.md"\n'
            "    acceptance_criteria:\n"
            '      - "..."\n'
            "    depends_on: [0]\n"
        )
        summary_builder_line = "  total_builder_tasks: P\n"
        total_tasks_expr = "N+M+P"
    else:
        builder_guideline = ""
        qa_handoff_guideline = "- Put QA handoff last\n"
        builder_example = ""
        summary_builder_line = ""
        total_tasks_expr = "N+M"

    typed_acceptance_section = (
        "\n## Typed Acceptance Criteria (SIP-0092)\n\n"
        "Acceptance criteria entries can be either:\n"
        "- **Prose strings** — informational only, never block validation. Use for goals "
        "that cannot be machine-checked.\n"
        "- **Typed checks** — machine-evaluated against the produced artifacts. "
        "A `severity: error` typed check that fails BLOCKS the build (triggers self-eval / correction).\n\n"
        "Typed-check shape: a flat YAML map with `check`, optional `severity` (`error` "
        "default | `warning` | `info`), optional `description`, plus check-specific keys.\n\n"
        "**Vocabulary (one example each):**\n\n"
        "```yaml\n"
        "# endpoint_defined — FastAPI route presence (stack: fastapi)\n"
        "- check: endpoint_defined\n"
        "  severity: error\n"
        '  description: "Backend exposes the user CRUD routes"\n'
        "  file: backend/main.py\n"
        '  methods_paths: ["GET /users", "POST /users", "DELETE /users/{uid}"]\n'
        "\n"
        "# import_present — Python import (or .ts/.js with frontend flag)\n"
        "- check: import_present\n"
        '  description: "Pydantic is wired in for request models"\n'
        "  file: backend/main.py\n"
        "  module: pydantic\n"
        "  symbol: BaseModel\n"
        "\n"
        "# field_present — class fields on a Python dataclass / Pydantic v2 model\n"
        "- check: field_present\n"
        '  description: "User model carries id and email"\n'
        "  file: backend/models.py\n"
        "  class_name: User\n"
        "  fields: [id, email]\n"
        "\n"
        "# regex_match — pattern present count_min times in a file (stack-agnostic)\n"
        "- check: regex_match\n"
        '  description: "At least three test functions exist"\n'
        "  file: tests/test_users.py\n"
        # Single-quote regex patterns: double quotes interpret backslash escapes
        # (\w, \.) and break yaml.safe_load. See acceptance_check_spec.CHECK_SPECS.
        "  pattern: 'def test_\\w+'\n"
        "  count_min: 3\n"
        "\n"
        "# count_at_least — glob match count under workspace (stack-agnostic)\n"
        "- check: count_at_least\n"
        '  description: "Non-trivial component coverage on the frontend"\n'
        '  glob: "frontend/src/components/**/*.tsx"\n'
        "  min_count: 3\n"
        "\n"
        "# command_exit_zero — argv-only safelist of static checkers; cannot run shell strings\n"
        "- check: command_exit_zero\n"
        '  description: "Backend file syntactically valid"\n'
        "  argv: [python, -m, py_compile, backend/main.py]\n"
        "```\n\n"
        "**Safety rules for `command_exit_zero`:**\n"
        '- `argv` MUST be a YAML list, not a string. `"ruff check src/"` is rejected.\n'
        "- Only safelisted argv shapes run: `python -m py_compile <file>`, `python -m mypy <args>`, "
        "`node --check <file>`, `ruff check <args>`, `tsc --noEmit`, `eslint <args>`, `pyflakes <file>`. "
        "Anything else (notably `python -c`, `python -m pip`, shell strings) errors at evaluation time — "
        "treat the safelist as the universe.\n"
        "- Per-command timeout is bounded; do not author long-running builds as acceptance checks.\n\n"
        "**Check-selection hierarchy — behavioral > structural > textual:**\n"
        "- Prefer checks that execute or parse code (`command_exit_zero`, `endpoint_defined`, "
        "`import_present`, `field_present`) over `regex_match`. Executing verifies what the "
        "code DOES; a regex only verifies how it is written.\n"
        "- `regex_match` patterns MUST NOT depend on stylistic choices the developer is free "
        "to vary: quote style, whitespace, attribute order, import aliasing. Example: "
        "`pattern: to='/runs/` fails correct JSX that uses double quotes — write a "
        "quote-agnostic class (`to=[\"']/runs/`) or assert the outcome behaviorally instead.\n"
        "- A regex that asserts how code is written rather than what it must do should be "
        "`severity: info` or prose, never a blocking `error`.\n\n"
        '**When in doubt, prefer typed checks over prose.** Prose like "User model exists" '
        "is a good candidate to typed-encode as `field_present` against the actual class.\n"
    )

    template_variables = {
        "prd": prd,
        "planning_content": planning_content,
        "typed_acceptance_section": typed_acceptance_section,
        "prd_coverage_discipline": _PRD_COVERAGE_DISCIPLINE_SECTION,
        "project_id": context.project_id or "(unknown)",
        "cycle_id": context.cycle_id or "(unknown)",
        "prd_hash": hashlib.sha256(prd.encode()).hexdigest() if prd else "(unknown)",
        "total_tasks_expr": total_tasks_expr,
        "roles_section": roles_section,
        "task_types_section": task_types_section,
        "builder_guideline": builder_guideline,
        "qa_handoff_guideline": qa_handoff_guideline,
        "builder_example": builder_example,
        "summary_builder_line": summary_builder_line,
    }

    # Issue #140 / SIP-0084: the registered template is the authoritative
    # source in production. The inline fallback below matches the surrounding
    # planning_tasks.py pattern — test contexts that don't inject a renderer
    # exercise the fallback. When the broader SIP-0084 migration retires
    # renderer=None test contexts, this fallback goes away.
    renderer = getattr(context.ports, "request_renderer", None)
    if renderer is not None:
        rendered = await renderer.render(
            "request.governance_review_plan_manifest",
            template_variables,
        )
        manifest_prompt = rendered.content
    else:
        manifest_prompt = _build_manifest_user_prompt_inline(template_variables)

    assembled = context.ports.prompt_service.assemble(
        role=role,
        hook="agent_start",
        task_type="governance.review_plan_manifest",
    )
    min_subtasks = resolved_config.get("min_build_subtasks", 3)
    max_subtasks = resolved_config.get("max_build_subtasks", 15)

    max_attempts = int(resolved_config.get("manifest_max_attempts", 2))
    messages = [
        ChatMessage(role="system", content=assembled.content),
        ChatMessage(role="user", content=manifest_prompt),
    ]

    for attempt in range(1, max_attempts + 1):
        try:
            response = await context.ports.llm.chat_stream_with_usage(messages, **chat_kwargs)
        except Exception as exc:
            logger.warning(
                "%s: manifest LLM call failed on attempt %d/%d (%s)",
                handler_name,
                attempt,
                max_attempts,
                exc,
            )
            if attempt >= max_attempts:
                return None
            messages = messages[:2]
            continue

        extracted = extract_fenced_files(response.content)
        manifest_files = [f for f in extracted if f["filename"] == "implementation_plan.yaml"]
        if manifest_files:
            yaml_content = manifest_files[0]["content"]
        else:
            yaml_content = _find_manifest_yaml(response.content)

        manifest, error_msg = _validate_manifest_candidate(
            yaml_content, min_subtasks, max_subtasks, profile_roles
        )

        if error_msg is None and manifest is not None:
            logger.info(
                "%s: produced build task manifest with %d subtasks on attempt %d",
                handler_name,
                len(manifest.tasks),
                attempt,
            )
            yaml_content = _rewrite_manifest_identifiers(
                yaml_content,
                project_id=context.project_id,
                cycle_id=context.cycle_id,
                prd_hash=hashlib.sha256(prd.encode()).hexdigest() if prd else "",
                handler_name=handler_name,
            )
            return {
                "name": "implementation_plan.yaml",
                "content": yaml_content,
                "media_type": "text/yaml",
                "type": "control_implementation_plan",
            }

        logger.warning(
            "%s: manifest attempt %d/%d failed (%s)",
            handler_name,
            attempt,
            max_attempts,
            error_msg,
        )
        if attempt >= max_attempts:
            logger.warning(
                "%s: exhausted %d manifest attempts, falling back to static task steps",
                handler_name,
                max_attempts,
            )
            return None

        messages = [
            *messages,
            ChatMessage(role="assistant", content=response.content),
            ChatMessage(role="user", content=error_msg),
        ]

    return None


def _build_manifest_user_prompt_inline(v: dict[str, str]) -> str:
    """Inline reproduction of ``request.governance_review_plan_manifest``.

    Kept in sync with the registered template at
    ``src/squadops/prompts/request_templates/request.governance_review_plan_manifest.md``.
    Used only when ``context.ports.request_renderer`` is unavailable — see the
    SIP-0084 migration note at the call site. Production cycles always have
    a renderer injected; tests that exercise this path are exercising the
    fallback contract, not production behavior.
    """
    return (
        "Based on the following PRD and planning artifact, produce a build task "
        "manifest that decomposes the upcoming build into focused subtasks.\n\n"
        f"{v['roles_section']}"
        f"{v['task_types_section']}"
        f"## PRD\n{v['prd']}\n\n"
        f"## Planning Artifact\n{v['planning_content']}\n\n"
        "Each subtask should:\n"
        "1. Have a clear, narrow focus (e.g., 'Backend data models' not 'Build the app')\n"
        "2. List the specific files it should produce\n"
        "3. Declare dependencies on prior subtasks by task_index\n"
        "4. Define acceptance criteria — prefer typed checks; see the section below\n"
        "5. Be completable in a single focused LLM generation (~2-10 minutes)\n\n"
        "Decomposition guidelines:\n"
        "- Separate backend and frontend into distinct tasks\n"
        "- Separate models/data from API endpoints/routes\n"
        "- Separate UI shell/routing from individual view components\n"
        "- Put integration config (CORS, proxy, requirements) in its own task\n"
        "- Put tests after the code they test\n"
        f"{v['builder_guideline']}"
        f"{v['qa_handoff_guideline']}"
        f"{v['typed_acceptance_section']}"
        "\n"
        f"{v['prd_coverage_discipline']}"
        "\n"
        "Output ONLY the manifest as a YAML code block with filename tag. "
        "The first three fields below are pre-filled with the cycle's "
        "authoritative values — copy them verbatim, do not invent or "
        "modify them:\n"
        "```yaml:implementation_plan.yaml\n"
        "version: 1\n"
        f"project_id: {v['project_id']}\n"
        f"cycle_id: {v['cycle_id']}\n"
        f"prd_hash: {v['prd_hash']}\n"
        "tasks:\n"
        "  - task_index: 0\n"
        "    task_type: development.develop\n"
        "    role: dev\n"
        '    focus: "..."\n'
        "    description: |\n"
        "      ...\n"
        "    expected_artifacts:\n"
        '      - "path/to/file"\n'
        "    acceptance_criteria:\n"
        '      - "..."\n'
        "    depends_on: []\n"
        f"{v['builder_example']}"
        "summary:\n"
        "  total_dev_tasks: N\n"
        "  total_qa_tasks: M\n"
        f"{v['summary_builder_line']}"
        f"  total_tasks: {v['total_tasks_expr']}\n"
        "  estimated_layers: [backend, frontend, test, config]\n"
        "```\n"
    )


def _validate_manifest_candidate(
    yaml_content: str | None,
    min_subtasks: int,
    max_subtasks: int,
    profile_roles: list[str],
) -> tuple[Any | None, str | None]:
    """Validate a candidate plan YAML. Returns ``(plan, error_msg)``.

    ``error_msg`` is ``None`` iff the plan is valid; in that case the first
    return is the parsed ``ImplementationPlan``. Otherwise ``error_msg`` is the
    corrective feedback appended to the next LLM attempt.
    """
    if yaml_content is None:
        return None, (
            "Your response did not contain a fenced YAML block tagged "
            "implementation_plan.yaml. Reply with ONLY the fenced block."
        )

    try:
        manifest = ImplementationPlan.from_yaml(yaml_content, enforce_command_safelist=True)
    except ValueError as exc:
        return None, (
            f"The previous plan YAML failed validation: {exc}. "
            "Produce a corrected implementation_plan.yaml. "
            "Quote every file path; do not put parenthetical comments "
            "after quoted strings on list items."
        )

    n = len(manifest.tasks)
    if n < min_subtasks or n > max_subtasks:
        return None, (
            f"The previous manifest had {n} subtasks; bounds are "
            f"{min_subtasks}-{max_subtasks}. Produce a corrected "
            "implementation_plan.yaml within bounds."
        )

    if profile_roles:
        allowed = set(profile_roles)
        bad = sorted({t.role for t in manifest.tasks if t.role not in allowed})
        if bad:
            return None, (
                f"The previous manifest used role(s) not in the "
                f"squad profile: {', '.join(bad)}. "
                f"Use ONLY these roles: {', '.join(profile_roles)}. "
                "Produce a corrected implementation_plan.yaml."
            )

    return manifest, None


def _find_manifest_yaml(content: str) -> str | None:
    """Search for an untagged ```yaml block whose body looks like a manifest."""
    for match in re.finditer(r"```yaml\s*\n(.*?)```", content, re.DOTALL):
        block = match.group(1).strip()
        if "task_index" in block and "task_type" in block and "focus" in block:
            return block
    return None
