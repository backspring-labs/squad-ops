"""The approved lessons' one rendering (SIP-0110 §0.9): every authoring seam handed lessons on
``LESSONS_INPUT`` shows them through the same managed asset, in a slot of their own (#448)."""

from __future__ import annotations

from typing import Any

from squadops.memory.recall import LESSONS_INPUT


async def cross_cycle_lessons_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The supplied lessons as a section, or ``""`` when none were supplied, so a task handed none
    renders exactly the prompt it rendered before memory existed. The section brings its own
    paragraph breaks, before and after: its slot shares a line with a neighbouring slot, so it adds
    no line of its own when it is empty."""
    supplied = inputs.get(LESSONS_INPUT)
    lessons = supplied.get("lessons") if isinstance(supplied, dict) else None
    if renderer is None or not lessons:
        return ""
    lines = "\n".join(f"{n}. {lesson['text']}" for n, lesson in enumerate(lessons, start=1))
    rendered = await renderer.render("request.cross_cycle_lessons_section", {"lesson_lines": lines})
    return "\n\n" + rendered.content.strip("\n") + "\n"
