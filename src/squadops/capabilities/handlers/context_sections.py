"""The context slots an authoring prompt shares, rendered once for every stage whose template has
all of them (#448). In the order the slots sit on the template's line: the failed cycle a retry
continues (#1692), the product a source-backed run changes (SIP-0112 E.4.3), this task's
instructions and its project's (SIP-0110 Appendix A §3.6, #2179), then the lessons (SIP-0110
§0.9). A slot the task has nothing for is left out, so the prompt renders as it did before."""

from __future__ import annotations

from typing import Any

from squadops.capabilities.handlers.cross_cycle_lessons import cross_cycle_lessons_section
from squadops.capabilities.handlers.prior_cycle import prior_cycle_section
from squadops.capabilities.handlers.source_repository import source_repository_section
from squadops.capabilities.handlers.task_instructions import (
    project_instructions_section,
    task_instructions_section,
)

_SLOTS = (
    ("prior_cycle_section", prior_cycle_section),
    ("source_repository_section", source_repository_section),
    ("task_instructions_section", task_instructions_section),
    ("project_instructions_section", project_instructions_section),
    ("cross_cycle_lessons_section", cross_cycle_lessons_section),
)


async def context_sections(renderer: Any, inputs: dict[str, Any]) -> dict[str, str]:
    """Each slot's rendered section, keyed by its template variable, for the slots that have one."""
    sections: dict[str, str] = {}
    for variable, render in _SLOTS:
        section = await render(renderer, inputs)
        if section:
            sections[variable] = section
    return sections
