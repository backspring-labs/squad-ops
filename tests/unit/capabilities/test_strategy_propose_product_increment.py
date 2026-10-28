"""``strategy.propose_increment`` on a repository-backed Project (SIP-0109 §24bv point 5), entered at
``handle()``.

The real prompt assets render through the real renderer and assembler; the model is stubbed with
the emissions under test. The task's inputs are the ones its run composes: the ``product_proposal``
input (``execution.product_proposal``, read here from the shared fixture's recorded Tally) and the
``source_repository`` view every task of a source-backed run is given. The change requests are
invented changes to Tally.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import yaml

from adapters.prompts.factory import create_prompt_asset_source, create_prompt_repository
from squadops.capabilities.handlers.planning.proposal import StrategyProposeIncrementHandler
from squadops.execution.product_proposal import profile_view
from squadops.llm.models import ChatMessage
from squadops.projects.derived_profile import parse_profile
from squadops.prompts.assembler import PromptAssembler
from squadops.prompts.renderer import RequestTemplateRenderer
from tests.fixtures.shared_contract.repository import product_files, recorded

_HEAD = "2" * 40
_REQUEST = """\
kind: feature
prd_delta:
  - id: report-totals
    op: add
    text: "The report ends in a line giving the total of its amounts."
footprint:
  - "tally/report.py"
criteria:
  - id: R1
    statement: The report's last line is the total of its amounts
    surface_kind: package
    surface: "tally.report"
    observable: "render([3, 4])'s last line is 'total 7'"
must_not_break: []
"""


def _fenced(doc: str) -> str:
    return f"My proposal.\n\n```yaml:change_request.yaml\n{doc}\n```\n"


def _ctx(*replies: str) -> MagicMock:
    ctx = MagicMock()
    ctx.role_id = "strat"
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(
        side_effect=[ChatMessage(role="assistant", content=r) for r in replies]
    )
    ctx.ports.llm.default_model = "m"
    ctx.ports.llm_observability = None
    ctx.correlation_context = None
    ctx.ports.request_renderer = RequestTemplateRenderer(create_prompt_asset_source("filesystem"))
    ctx.ports.prompt_service = PromptAssembler(create_prompt_repository("filesystem"))
    return ctx


def _inputs(*, product: bool = True) -> dict:
    profile = parse_profile(recorded("derived_profile", "valid"))
    inputs: dict = {
        "resolved_config": {
            "proposal_max_attempts": 2,
            "campaign_proposal": {
                "proposal_id": "prop_tally0001",
                "version": 1,
                "basis": "campaign_branch",
                "baseline_tree": "f" * 64,
                "objective": {
                    "statement": "the report says what it adds up to",
                    "allowed_scope": ["tally/**"],
                    "measurement": "one accepted increment",
                    "requirements": "repo:file:README.md@current",
                },
                "prior_criteria": [],
            },
        },
        "source_repository": {
            "commit": _HEAD,
            "map": "- `tally/report.py` (812 bytes)\n- `checks/check_report.py` (640 bytes)",
            "checks": [{"id": "report", "argv": ["python3", "-m", "unittest"]}],
            "runners": [],
            "instructions": {},
            "existing_files": {},
        },
    }
    if product:
        inputs["product_proposal"] = {
            "head": {"commit": _HEAD, "tree": "f" * 64},
            "profile": profile_view(profile, product_files()),
            "previous_verification": {
                "source": "the calibration record's inherited baseline",
                "commit": _HEAD,
                "checks": [
                    {"id": "report", "result": "PASS"},
                    {"id": "notify", "result": "UNVERIFIED", "reason": "TALLY_SMTP_HOST unset"},
                ],
            },
            "requirements": {
                "ref": f"repo:file:README.md@{_HEAD}",
                "content": "# Tally\n\nTally adds up a ledger and reports it.",
            },
        }
    return inputs


def _prompts(ctx) -> list[str]:
    return [
        "\n".join(m.content for m in call.args[0])
        for call in ctx.ports.llm.chat_stream_with_usage.call_args_list
    ]


async def test_the_product_proposal_sees_the_product_and_emits_a_placed_change_request():
    """Wiring: the real render reaches the model with what §24bv point 5 gives a proposal, and the
    artifact is the rails' typed request. Bugs caught: the product's input composed and never
    rendered (a slot no handler fills, #1289's shape); the sample application's manifest prompt
    sent to a product; a stored request without its placed criterion file or its basis."""
    ctx = _ctx(_fenced(_REQUEST))

    result = await StrategyProposeIncrementHandler().handle(ctx, _inputs())

    assert result.success, result.error
    [prompt] = _prompts(ctx)
    assert f"accepted as it stands at commit `{_HEAD}`" in prompt
    assert "- `unittest` tests `tally/**`: a criterion's test is placed at " in prompt
    assert "`checks/check_criterion_{criterion}.py`" in prompt
    assert "- command: `python3 -m tally`" in prompt
    assert "- missing_environment (notify), on `**`" in prompt
    assert "- `notify`: UNVERIFIED (TALLY_SMTP_HOST unset)" in prompt
    assert f"as `repo:file:README.md@{_HEAD}` reads them" in prompt
    assert "Tally adds up a ledger and reports it." in prompt
    assert "- `tally/report.py` (812 bytes)" in prompt  # the head's tree view
    assert "interface manifest, exactly as it stands" not in prompt
    [artifact] = result.outputs["artifacts"]
    document = yaml.safe_load(artifact["content"])
    assert document["basis"] == "campaign_branch"
    assert document["footprint"] == ["tally/report.py", "checks/check_criterion_R1.py"]
    assert document["criterion_files"] == [
        {"criterion_id": "R1", "path": "checks/check_criterion_R1.py"}
    ]


async def test_a_manifest_delta_on_a_product_is_returned_to_the_proposer_and_revised():
    """Bug caught: the product rail's refusal never reaching the proposer as a reason it can act
    on, so a request carrying a manifest delta is retried blind until its budget is spent."""
    with_delta = yaml.safe_load(_REQUEST)
    with_delta["manifest_delta"] = [{"op": "remove", "target": "entity", "key": "Ledger"}]
    ctx = _ctx(_fenced(yaml.safe_dump(with_delta)), _fenced(_REQUEST))

    result = await StrategyProposeIncrementHandler().handle(ctx, _inputs())

    first, second = _prompts(ctx)
    assert "[manifest_delta_on_product]" not in first
    assert "[manifest_delta_on_product]" in second
    assert result.success


async def test_a_branch_proposal_given_no_product_input_fails_and_never_reads_as_a_manifests():
    """The edge. Bug caught: a campaign-branch proposal with no ``product_proposal`` input read as
    a sample application's, whose rails would refuse it for want of a manifest, or worse, propose
    against an empty one."""
    ctx = _ctx(_fenced(_REQUEST))

    result = await StrategyProposeIncrementHandler().handle(ctx, _inputs(product=False))

    assert not result.success
    assert "was given no product_proposal" in result.error
    ctx.ports.llm.chat_stream_with_usage.assert_not_called()


async def test_a_greenfield_products_approved_manifest_is_rendered_beside_the_tree():
    """Bug caught: the approved manifest composed onto the input (H.1) and never rendered, so the
    proposer is never shown the structure the product was initialized from."""
    inputs = _inputs()
    inputs["product_proposal"]["approved_manifest"] = {
        "stack": "fullstack_fastapi_react",
        "commit": "1" * 40,
        "content": "api:\n  endpoints:\n    - {method: GET, path: /ledger}\n",
    }
    ctx, plain = _ctx(_fenced(_REQUEST)), _ctx(_fenced(_REQUEST))

    await StrategyProposeIncrementHandler().handle(ctx, inputs)
    await StrategyProposeIncrementHandler().handle(plain, _inputs())

    [prompt] = _prompts(ctx)
    assert "### The interface manifest this product was initialized from" in prompt
    assert "- {method: GET, path: /ledger}" in prompt
    assert "initialized from" not in _prompts(plain)[0]
