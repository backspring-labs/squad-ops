"""Every variable a request template declares must be produced by its handler (#1289).

**The bug this catches, which shipped and ran for weeks.** `request.cycle_repair_task`
declares `failing_cases_section` and `client_surface_section` as optional variables and
references both in its body. `QATestRepairHandler.handle` builds both blocks and threads
them onto `inputs` — and `_build_render_variables` never passed them to the renderer, so
both placeholders rendered EMPTY on every repair the framework has ever run. #1123's
"REPAIR SCOPE (authoritative)" brief never reached a model, and neither did #668's frozen
client surface, while the runner's log line kept reporting the brief's case count.

Nothing checked it, because the section was *computed* — so every trace of it existed
except the one that mattered. This is the fourth instance in the 1.7.x lines of a fact
computed and dropped (#999, #1052, #597's parity comment, this), and each previous one was
found by a roll rather than by a test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.domain_contracts]

_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
)


def _declared(template_id: str) -> tuple[set[str], str]:
    """The template's declared variables and its body."""
    text = (_TEMPLATES / f"{template_id}.md").read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front)
    declared = set(meta.get("required_variables") or []) | set(meta.get("optional_variables") or [])
    return declared, body


#: ``(handler class, template id)`` for every handler that renders a request template with
#: a ``_build_render_variables`` of its own. A handler added without an entry here is not
#: covered — which is why the pairing is asserted against the class attribute, not typed
#: out twice.
def _handler_template_pairs():
    from squadops.capabilities.handlers.impl.repair_handlers import (
        BuilderAssembleRepairHandler,
        DevelopmentCorrectionRepairHandler,
        QATestRepairHandler,
    )

    return [
        QATestRepairHandler,
        DevelopmentCorrectionRepairHandler,
        BuilderAssembleRepairHandler,
    ]


@pytest.mark.parametrize("handler_cls", _handler_template_pairs(), ids=lambda c: c.__name__)
def test_every_variable_the_template_declares_is_supplied_by_the_handler(handler_cls):
    handler = handler_cls()
    declared, body = _declared(handler._request_template_id)
    supplied = set(
        handler._build_render_variables(
            "a prd",
            None,
            # Every declared name offered as an input, so a variable the handler forwards
            # is forwarded and one it never reads is still absent from `supplied`.
            {name: f"<{name}>" for name in declared} | {"failed_task_type": "qa.test"},
        )
    )
    missing = sorted(name for name in declared if name not in supplied)
    assert not missing, (
        f"{handler_cls.__name__} renders {handler._request_template_id}, which declares "
        f"{missing} and references them in its body — the placeholders render empty and "
        f"whatever the handler computed for them is dropped (#1289)"
    )


@pytest.mark.parametrize("handler_cls", _handler_template_pairs(), ids=lambda c: c.__name__)
def test_every_placeholder_in_the_body_is_declared(handler_cls):
    """The other direction: a body referencing an undeclared name renders it empty too,
    and the declaration is what this suite reads."""
    import re

    declared, body = _declared(handler_cls()._request_template_id)
    referenced = set(re.findall(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}", body))
    undeclared = sorted(referenced - declared)
    assert not undeclared, (
        f"{handler_cls()._request_template_id} references {undeclared}, which it does "
        "not declare — an undeclared placeholder renders empty"
    )


def test_the_repair_brief_and_client_surface_are_the_regression():
    """Named explicitly: these two are what #1289 dropped, and a future refactor that
    reorganises the variable dict must not quietly lose them again."""
    from squadops.capabilities.handlers.impl.repair_handlers import QATestRepairHandler

    supplied = QATestRepairHandler()._build_render_variables(
        "prd", None, {"failing_cases_section": "SCOPE", "client_surface_section": "CLIENT"}
    )
    assert supplied["failing_cases_section"] == "SCOPE"
    assert supplied["client_surface_section"] == "CLIENT"


async def test_the_repair_brief_renders_through_the_real_renderer():
    """The appendix's own variables, through the real renderer — not a mock.

    `test_repair_dom_anchor` asserts what the handler passes with the renderer stubbed, so
    it could not see that `case_count` was an int and that the renderer raises TypeError on
    one. Two tests, one mocked seam between them, and the contract unexercised.
    """
    from adapters.prompts.factory import create_prompt_asset_source
    from squadops.prompts.renderer import RequestTemplateRenderer

    renderer = RequestTemplateRenderer(create_prompt_asset_source(provider="filesystem"))
    for template_id in (
        "request.qa_test_repair_failing_cases_appendix",
        "request.qa_test_retained_cases_appendix",
    ):
        rendered = await renderer.render(
            template_id,
            {"case_lines": "- `a.py:1` › a case — it failed", "case_count": str(1)},
        )
        assert "a case" in rendered.content
