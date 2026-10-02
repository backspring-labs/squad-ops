"""The prior-cycle brief's one rendering (#1692; SIP-0109 §10a): every authoring stage that is
handed a ``prior_cycle_brief`` shows it through the same managed asset (#448)."""

from __future__ import annotations

from typing import Any


async def prior_cycle_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The failed prior cycle's record as an appendix, or ``""`` when there is none."""
    lines = str(inputs.get("prior_cycle_brief") or "")
    if renderer is None or not lines.strip():
        return ""
    rendered = await renderer.render("request.prior_cycle_brief_appendix", {"brief_lines": lines})
    return rendered.content
