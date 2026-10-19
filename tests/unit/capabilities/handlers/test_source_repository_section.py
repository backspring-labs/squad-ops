"""The product's repository in an authoring prompt (SIP-0112 E.4.3), with the real renderer and
the shipped assets: a renamed placeholder or an undeclared variable fails here, rather than
rendering an empty section in production."""

from __future__ import annotations

from typing import Any

from adapters.prompts.factory import DEFAULT_TEMPLATES_PATH, create_prompt_asset_source
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.source_repository import source_repository_section
from squadops.prompts.renderer import RequestTemplateRenderer

COMMIT = "962858eb0e321ed084463637c9faf661c179a41e"
REPOSITORY = {
    "commit": COMMIT,
    "map": "- `tally/__main__.py` (700 bytes)\n- `CONTRIBUTING.md` (500 bytes)",
    "instructions": {"CONTRIBUTING.md": "Build first: `python3 tools/build.py`."},
    "existing_files": {"tally/__main__.py": "import argparse\n"},
}


def _renderer():
    return RequestTemplateRenderer(
        asset_source=create_prompt_asset_source(
            provider="filesystem", templates_path=DEFAULT_TEMPLATES_PATH
        )
    )


def _handler() -> DevelopmentDevelopHandler:
    handler = DevelopmentDevelopHandler()
    handler._resolved_config = {}  # as handle() sets it before the prompt is built
    return handler


def _inputs(**extra: Any) -> dict[str, Any]:
    return {
        "prd": "Add a --json flag to the counters listing.",
        "subtask_focus": "--json output",
        "subtask_description": "Print the counters as JSON when --json is given.",
        "expected_artifacts": ["tally/__main__.py"],
        "acceptance_criteria": [],
        "artifact_contents": {},
        "resolved_config": {},
        **extra,
    }


async def test_the_developer_is_shown_the_product_its_instructions_and_the_file_it_changes():
    prompt = await _handler()._build_focused_prompt(
        _inputs(source_repository=REPOSITORY), _renderer()
    )

    assert "THE PRODUCT YOU ARE CHANGING" in prompt and COMMIT in prompt
    assert "- `tally/__main__.py` (700 bytes)" in prompt
    assert "Build first: `python3 tools/build.py`." in prompt
    assert "**tally/__main__.py:**\n```\nimport argparse\n" in prompt
    assert "{{" not in prompt


async def test_a_run_without_a_product_renders_no_section():
    """Bug caught: every scaffolded run's prompt carrying an empty product heading."""
    prompt = await _handler()._build_focused_prompt(_inputs(), _renderer())

    assert "THE PRODUCT YOU ARE CHANGING" not in prompt
    assert await source_repository_section(_renderer(), {}) == ""
    assert await source_repository_section(None, {"source_repository": REPOSITORY}) == ""


async def test_only_the_parts_a_task_has_are_rendered():
    section = await source_repository_section(
        _renderer(), {"source_repository": {**REPOSITORY, "instructions": {}, "existing_files": {}}}
    )

    assert "instructions for contributors" not in section
    assert "current content of the files" not in section
    assert "- `CONTRIBUTING.md` (500 bytes)" in section
