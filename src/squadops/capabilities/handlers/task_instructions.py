"""Task instructions' one rendering (SIP-0110 Appendix A §3.6; #2178): every authoring seam handed task
instructions on ``TASK_INSTRUCTIONS_INPUT`` shows them through the same managed asset, in a slot of their
own, before the lessons (the slot's precedence: authoritative records, task instructions, lessons)."""

from __future__ import annotations

import re
from typing import Any

from squadops.memory.project_instructions import PROJECT_INSTRUCTIONS_INPUT
from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT


async def task_instructions_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The task's instructions as a section, or ``""`` when none were handed, so a task with none
    renders exactly the prompt it rendered before. The section brings its own paragraph breaks, as
    the lessons' does, since its slot shares a line with a neighbouring slot."""
    handed = inputs.get(TASK_INSTRUCTIONS_INPUT)
    instructions = handed.get("instructions") if isinstance(handed, dict) else None
    if renderer is None or not instructions:
        return ""
    rendered = await renderer.render(
        "request.task_instructions_section",
        {"instruction_lines": await _instruction_lines(renderer, instructions)},
    )
    return "\n\n" + rendered.content.strip("\n") + "\n"


async def project_instructions_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The project instructions the task's unit pinned that apply to it (#2179), as a section after
    the task's own and before the lessons, or ``""`` when none applies."""
    handed = inputs.get(PROJECT_INSTRUCTIONS_INPUT)
    instructions = handed.get("instructions") if isinstance(handed, dict) else None
    if renderer is None or not instructions:
        return ""
    rendered = await renderer.render(
        "request.project_instructions_section",
        {"instruction_lines": await _instruction_lines(renderer, instructions)},
    )
    return "\n\n" + rendered.content.strip("\n") + "\n"


async def _instruction_lines(renderer: Any, instructions: list[dict[str, Any]]) -> str:
    """Each instruction numbered, and after it the content of each reference it was handed, read
    at the revision its unit bound (#2179), so the task works from the record the instruction
    names. An instruction handed no content renders its one line, as it did before."""
    lines = "\n".join(f"{n}. {i['text']}" for n, i in enumerate(instructions, start=1))
    shown = []
    for n, instruction in enumerate(instructions, start=1):
        for reference in instruction.get("references") or ():
            if "content" not in reference:
                continue
            block = await renderer.render(
                "request.instruction_reference",
                {
                    "number": str(n),
                    "ref": reference["ref"],
                    "fence": _fence_for(reference["content"]),
                    "content": reference["content"].rstrip("\n"),
                },
            )
            shown.append(block.content.strip("\n"))
    return "\n\n".join([lines, *shown])


def _fence_for(content: str) -> str:
    """A backtick fence longer than any run of backticks in ``content``, so a file holding its own
    fenced blocks is shown whole."""
    longest = max((len(run) for run in re.findall(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)
