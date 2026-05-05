"""Shared helpers for plan-authoring handlers (SIP-0093).

Multi-role plan authoring routes through three handler families:

- ``*.propose_plan_tasks`` — per-role proposers (dev, qa, builder)
  emit ``proposed_plan_tasks.yaml`` scoped to their domain.
- ``governance.merge_plan`` — the lead merges proposals into the
  canonical ``implementation_plan.yaml`` + ``merge_decisions.yaml``
  + ``planning_artifact.md``.

Each handler runs a retry-with-corrective-feedback LLM loop and emits
fenced YAML in a known filename. The loop body, fenced extraction,
and prompt-building are shared between all three so behavior stays
aligned and a fix to one path doesn't drift away from the others.

This module is intentionally function-style (no service class). The
handlers are the agents; this module is their toolbox.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from squadops.capabilities.handlers.fenced_parser import extract_fenced_files
from squadops.llm.exceptions import LLMError
from squadops.llm.models import ChatMessage

logger = logging.getLogger(__name__)


def extract_named_yaml(content: str, filename: str) -> str | None:
    """Pull the first fenced ``yaml:filename`` block from a response.

    Falls back to a tag-less ``yaml`` block if no filename-tagged one
    is found — the LLM occasionally drops the tag and we don't want
    to throw away an otherwise-valid proposal.
    """
    extracted = extract_fenced_files(content)
    matches = [f for f in extracted if f["filename"] == filename]
    if matches:
        return matches[0]["content"]

    import re

    pattern = r"```yaml\s*\n(.*?)```"
    for match in re.finditer(pattern, content, re.DOTALL):
        block = match.group(1).strip()
        if block:
            return block
    return None


async def retry_yaml_call(
    llm: Any,
    chat_kwargs: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    parse_and_validate: Callable[[str | None], tuple[Any | None, str | None]],
    max_attempts: int,
    handler_name: str,
) -> tuple[Any | None, str | None, str | None]:
    """Drive an LLM call with up to ``max_attempts`` retries.

    On each attempt, ``parse_and_validate(yaml_or_none)`` returns
    ``(parsed_obj, error_msg)``. ``error_msg is None`` means accept;
    otherwise the message becomes corrective feedback for the next
    attempt.

    Returns ``(parsed_obj, last_yaml, last_error)``. ``parsed_obj`` is
    ``None`` if all attempts failed; ``last_yaml`` carries the most
    recent raw YAML for diagnostic logging.
    """
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]
    last_yaml: str | None = None
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = await llm.chat_stream_with_usage(messages, **chat_kwargs)
        except LLMError as exc:
            logger.warning(
                "%s: LLM call failed on attempt %d/%d (%s)",
                handler_name,
                attempt,
                max_attempts,
                exc,
            )
            last_error = str(exc)
            if attempt >= max_attempts:
                return None, last_yaml, last_error
            messages = messages[:2]
            continue

        content = response.content
        # Each handler tells us which filename to expect via the
        # closure in parse_and_validate; this layer just hands over the
        # raw YAML or None.
        last_yaml = _first_yaml_block_or_none(content)

        parsed, err = parse_and_validate(last_yaml)
        if err is None and parsed is not None:
            logger.info("%s: produced valid output on attempt %d", handler_name, attempt)
            return parsed, last_yaml, None

        logger.warning(
            "%s: attempt %d/%d failed: %s",
            handler_name,
            attempt,
            max_attempts,
            err,
        )
        last_error = err
        if attempt >= max_attempts:
            return None, last_yaml, last_error

        messages = [
            *messages,
            ChatMessage(role="assistant", content=content),
            ChatMessage(role="user", content=err or "Please correct the previous output."),
        ]

    return None, last_yaml, last_error


def _first_yaml_block_or_none(content: str) -> str | None:
    """Best-effort YAML extraction without a known filename. Used by
    ``retry_yaml_call`` when the parse_and_validate callback handles
    filename-specific shape itself."""
    import re

    extracted = extract_fenced_files(content)
    if extracted:
        for f in extracted:
            if f["filename"].endswith(".yaml") or f["filename"].endswith(".yml"):
                return f["content"]
    pattern = r"```yaml\s*\n(.*?)```"
    for match in re.finditer(pattern, content, re.DOTALL):
        block = match.group(1).strip()
        if block:
            return block
    return None


# ---------------------------------------------------------------------------
# Propose-prompt construction
# ---------------------------------------------------------------------------


_PROPOSE_BASE_INSTRUCTIONS = """\
You are proposing the build-phase tasks that fall within YOUR role's
domain. Other roles will propose their own tasks in parallel; the
governance lead will merge all proposals into the canonical
implementation plan.

Constraints on YOUR proposal:

- Propose ONLY tasks for the listed task_type(s) below — leave other
  domains to their owning roles.
- Each task must have a clear, narrow ``focus`` (e.g. "Backend models"
  not "Build the app"). The ``focus`` is your task's identity and
  serves as the dependency reference key for other proposers.
- ``focus`` must be unique within your proposal.
- For cross-role dependencies (e.g. your QA test depends on a dev
  task), reference them by ``"{role}:{focus}"`` in
  ``depends_on_focus`` — e.g. ``"dev:backend api"``. The merger will
  resolve these to numeric task_indices after combining all proposals.
- Acceptance criteria: prefer machine-evaluable typed checks (SIP-0092
  M1 vocabulary) over prose strings. Each typed check is a flat YAML
  map with ``check`` plus check-specific keys.
- Be concrete about file paths in ``expected_artifacts``. Filename
  drift across proposers is the merger's biggest source of conflict.
"""


_TYPED_ACCEPTANCE_HINT = """\

## Typed Acceptance Criteria (SIP-0092 vocabulary)

Each typed check is a flat YAML map. Examples (one per shape):

```yaml
- check: regex_match
  description: "At least three test functions exist"
  file: tests/test_users.py
  pattern: "def test_"
  count_min: 3

- check: endpoint_defined
  description: "Backend exposes the user CRUD routes"
  file: backend/main.py
  methods_paths: ["GET /users", "POST /users", "DELETE /users/{uid}"]

- check: field_present
  description: "User model carries id and email"
  file: backend/models.py
  class_name: User
  fields: [id, email]

- check: import_present
  description: "Pydantic is wired in for request models"
  file: backend/main.py
  module: pydantic
  symbol: BaseModel
```

Strings (e.g. ``"Backend runs cleanly"``) stay as informational prose
and never block validation. Typed checks with ``severity: error``
(default) DO block the build when failed.
"""


_PROPOSE_OUTPUT_SHAPE = """\

Output ONLY a fenced YAML block tagged ``proposed_plan_tasks.yaml``
with this shape:

```yaml:proposed_plan_tasks.yaml
version: 1
proposing_role: {proposing_role}
tasks:
  - task_type: {primary_task_type}
    role: {proposing_role}
    focus: "Short identity for this task"
    description: |
      Detailed description.
    expected_artifacts:
      - "path/to/file"
    acceptance_criteria:
      - check: regex_match
        file: "path/to/file"
        pattern: "..."
        count_min: 1
    depends_on_focus: []
```

If you have nothing to propose for your role (e.g. the build is so
simple your role has no testable surface), emit ``tasks: []`` — the
merger will absorb the empty proposal and proceed.
"""


def build_propose_prompt(
    *,
    role: str,
    primary_task_type: str,
    role_domain_description: str,
    prd: str,
    planning_content: str,
    profile_roles: list[str],
    profile_has_builder: bool,
) -> str:
    """Assemble the per-role propose-task prompt.

    ``role_domain_description`` is the role-specific scope sentence
    (e.g. "Decompose the build's QA work into focused test
    subtasks") — provided by each propose handler so the shared body
    can stay generic.
    """
    builder_section = ""
    if profile_has_builder and role != "builder":
        builder_section = (
            "\n\n## Builder role present\n\n"
            "This squad includes a dedicated builder role. Do NOT propose "
            "packaging, requirements files, Dockerfile, startup scripts, or "
            "qa_handoff.md tasks — those are the builder's domain. Reference "
            "builder tasks via ``depends_on_focus`` if your tasks need their "
            "outputs."
        )

    roles_section = ""
    if profile_roles:
        roles_section = (
            f"\n\n## Available roles in this squad\n\n"
            f"{', '.join(profile_roles)}\n\n"
            f"You are proposing as the **{role}** role. Reference other "
            f"roles by id when expressing cross-role dependencies."
        )

    return (
        f"{_PROPOSE_BASE_INSTRUCTIONS}"
        f"\n\n## Your scope\n\n"
        f"{role_domain_description} Restrict your proposed tasks to "
        f"task_type ``{primary_task_type}``."
        f"{roles_section}"
        f"{builder_section}"
        f"\n\n## PRD\n\n{prd}\n"
        f"\n## Planning artifacts (from upstream framing tasks)\n\n"
        f"{planning_content}\n"
        f"{_TYPED_ACCEPTANCE_HINT}"
        f"{_PROPOSE_OUTPUT_SHAPE.format(proposing_role=role, primary_task_type=primary_task_type)}"
    )
