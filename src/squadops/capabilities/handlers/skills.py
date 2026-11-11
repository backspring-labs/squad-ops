"""A task's skills' one rendering (SIP-0116 §7): every authoring seam handed skills on
``SKILLS_INPUT`` shows them through the same managed asset, in a slot of their own, after its
project's instructions and before the lessons.

The skills are the task's equipment, handed by the runtime from its cycle's kept copy. A task
handed skills that can't be shown raises: a prompt that went out without them would read as
one that had them."""

from __future__ import annotations

from typing import Any

from squadops.capabilities.handlers.task_instructions import fence_for
from squadops.capabilities.skillsets import SKILL_FILE, SKILLS_INPUT
from squadops.prompts.frontmatter import FrontmatterError, parse_frontmatter


async def skills_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The task's skills as a section, or ``""`` when it was handed none, so a task with none
    renders exactly the prompt it rendered before. The section brings its own paragraph
    breaks, since its slot shares a line with its neighbours."""
    handed = inputs.get(SKILLS_INPUT)
    if not handed:
        return ""
    if renderer is None:
        raise ValueError(
            f"this task was handed {len(handed)} skills and has no renderer to show them with"
        )
    blocks = [await _skill_block(renderer, skill) for skill in handed]
    rendered = await renderer.render(
        "request.skills_section", {"skill_blocks": "\n\n".join(blocks)}
    )
    return "\n\n" + rendered.content.strip("\n") + "\n"


async def _skill_block(renderer: Any, skill: dict[str, Any]) -> str:
    """One skill: its name, the body of its ``SKILL.md``, and each resource beside it under
    its path. The front matter's description is for whoever chooses skills, which no model
    does here (§7), so it isn't shown."""
    where = f"skill {skill['skillset']}/{skill['skill']}"
    files = skill["files"]
    if SKILL_FILE not in files:
        raise ValueError(f"{where} was handed with no {SKILL_FILE}")
    try:
        header, body = parse_frontmatter(files[SKILL_FILE])
    except FrontmatterError as exc:
        raise ValueError(f"{where}: {SKILL_FILE} front matter: {exc}") from exc
    name = str(header.get("name") or "").strip()
    if not name:
        raise ValueError(f"{where}: {SKILL_FILE} front matter gives no name")
    resources = []
    for path in sorted(p for p in files if p != SKILL_FILE):
        shown = await renderer.render(
            "request.skill_resource",
            {"path": path, "fence": fence_for(files[path]), "content": files[path].rstrip("\n")},
        )
        resources.append("\n\n" + shown.content.strip("\n"))
    block = await renderer.render(
        "request.skill",
        {"name": name, "body": body.strip("\n"), "resources": "".join(resources)},
    )
    return block.content.strip("\n")
