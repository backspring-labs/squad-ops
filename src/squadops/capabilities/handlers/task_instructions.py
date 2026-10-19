"""Task instructions' one rendering (SIP-0110 Appendix A §3.6; #2178): every authoring seam handed task
instructions on ``TASK_INSTRUCTIONS_INPUT`` shows them through the same managed asset, in a slot of their
own, before the lessons (the slot's precedence: authoritative records, task instructions, lessons)."""

from __future__ import annotations

from typing import Any

from squadops.memory.task_instructions import TASK_INSTRUCTIONS_INPUT


async def task_instructions_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The task's instructions as a section, or ``""`` when none were handed, so a task with none
    renders exactly the prompt it rendered before. The section brings its own paragraph breaks, as
    the lessons' does, since its slot shares a line with a neighbouring slot."""
    handed = inputs.get(TASK_INSTRUCTIONS_INPUT)
    instructions = handed.get("instructions") if isinstance(handed, dict) else None
    if renderer is None or not instructions:
        return ""
    lines = "\n".join(f"{n}. {i['text']}" for n, i in enumerate(instructions, start=1))
    rendered = await renderer.render(
        "request.task_instructions_section", {"instruction_lines": lines}
    )
    return "\n\n" + rendered.content.strip("\n") + "\n"
