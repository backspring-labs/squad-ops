"""Repair handlers for the SIP-0079 correction protocol.

Thin subclasses of _CycleTaskHandler used by the repair-task selector in
cycles/task_plan.py: development.correction_repair (dev),
builder.assemble_repair (builder), and qa.validate_repair (qa).

Issue #100: this file used to define a `DevelopmentRepairHandler` with
`_capability_id = "development.repair"`. That collided with the SIP-0070
pulse-check `DevelopmentRepairHandler` in handlers/repair_tasks.py. The
correction-loop variant is now `DevelopmentCorrectionRepairHandler` with
`_capability_id = "development.correction_repair"` so the pulse-check and
correction-loop flows have distinct, non-overlapping capability ids.
"""

from __future__ import annotations

from typing import Any

from squadops.capabilities.handlers.cycle_tasks import _classify_file, _CycleTaskHandler
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files


def _artifacts_from_fenced_blocks(content: str, fallback_name: str) -> list[dict[str, Any]]:
    """Extract per-file artifacts from fenced code blocks in *content*.

    Repair handlers ask the LLM to emit replacement source files in the
    same fenced format the develop handler uses. Without this extraction
    the base handler wraps the entire response as a single markdown doc
    and the repaired files never land in artifact storage — the failure
    mode that motivated this helper.

    Falls back to a single markdown wrap when no fenced blocks are found
    so the LLM output is not silently dropped.
    """
    extracted = extract_fenced_files(content)
    if not extracted:
        return [
            {
                "name": fallback_name,
                "content": content,
                "media_type": "text/markdown",
                "type": "document",
            },
        ]
    artifacts: list[dict[str, Any]] = []
    for file_rec in extracted:
        artifact_type, media_type = _classify_file(file_rec["filename"])
        artifacts.append(
            {
                "name": file_rec["filename"],
                "content": file_rec["content"],
                "media_type": media_type,
                "type": artifact_type,
            }
        )
    return artifacts


class DevelopmentCorrectionRepairHandler(_CycleTaskHandler):
    """Correction-loop repair handler.

    Reads `failure_evidence`, `failure_analysis`, and `correction_decision`
    from inputs (set by the executor's correction protocol) and asks the
    LLM to author a repair. Distinct from the SIP-0070 pulse-check
    `DevelopmentRepairHandler`, which consumes `verification_context` from
    a different upstream chain.
    """

    _handler_name = "development_correction_repair_handler"
    _capability_id = "development.correction_repair"
    _role = "dev"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        return _artifacts_from_fenced_blocks(content, self._artifact_name)


class BuilderAssembleRepairHandler(_CycleTaskHandler):
    """Correction-loop repair handler for failed builder.assemble tasks.

    Mirrors `DevelopmentCorrectionRepairHandler` but routed to the builder
    role so packaging/handoff failures (e.g. qa_handoff.md missing
    required sections, missing requirements.txt or package.json) get
    repaired by Bob with the build-profile system prompt rather than by
    Neo with the dev system prompt — Neo has no useful context for
    builder.assemble outputs and simply ignores the assignment.
    """

    _handler_name = "builder_assemble_repair_handler"
    _capability_id = "builder.assemble_repair"
    _role = "builder"
    _artifact_name = "repair_output.md"

    def _build_artifacts_from_content(self, content: str) -> list[dict[str, Any]]:
        return _artifacts_from_fenced_blocks(content, self._artifact_name)


class QAValidateRepairHandler(_CycleTaskHandler):
    """Validate repair handler: verifies the repair was successful."""

    _handler_name = "qa_validate_repair_handler"
    _capability_id = "qa.validate_repair"
    _role = "qa"
    _artifact_name = "repair_validation.md"
