"""The product's repository, as one rendering for every authoring stage (SIP-0112 E.4.3).

A source-backed run's task is handed a ``source_repository`` input: the map of the product's tree,
its own instruction files, and the current content of the files the task names. Each authoring
stage shows it through the same managed asset (#448), beside the prior-cycle brief.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


async def source_repository_section(renderer: Any, inputs: dict[str, Any]) -> str:
    """The product's repository as an appendix, or ``""`` for a run that has none."""
    repository = inputs.get("source_repository")
    if renderer is None or not isinstance(repository, Mapping):
        return ""
    variables = {"commit": str(repository["commit"]), "repository_map": str(repository["map"])}
    instructions = repository.get("instructions") or {}
    if instructions:
        block = await renderer.render(
            "request.source_repository_instructions_block", {"files": _files(instructions)}
        )
        variables["instructions"] = block.content
    existing = repository.get("existing_files") or {}
    if existing:
        block = await renderer.render(
            "request.source_repository_existing_files_block", {"files": _files(existing)}
        )
        variables["existing_files"] = block.content
    rendered = await renderer.render("request.source_repository_appendix", variables)
    return rendered.content


def _files(files: Mapping[str, str]) -> str:
    return "\n\n".join(f"**{path}:**\n```\n{content}\n```" for path, content in files.items())
