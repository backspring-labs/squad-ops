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

import pytest
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
                # §24dr item 4: every repository-backed launch pins one, empty for none.
                "accepted_pages": [],
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


# --- SIP-0109 §24cp (#2779): a page criterion names its view's anchor where the change adds it --

_ADDS_A_PAGE = """\
kind: feature
prd_delta:
  - id: report-totals-page
    op: add
    text: "A totals page shows the ledger's total."
footprint:
  - "tally/report.py"
criteria:
  - id: R1
    statement: The totals page shows the ledger's total
    surface_kind: client_route
    surface: "/totals"
    observable: "the page reads 'total 7' for amounts 3 and 4"
must_not_break: []
"""


def _with_pages() -> dict:
    """Tally's input with a UI base its start serves, and its profile judging two pages."""
    inputs = _inputs()
    profile = inputs["product_proposal"]["profile"]
    profile["public_surfaces"].append({"kind": "ui_base", "url": "http://127.0.0.1:18408/"})
    profile["client_routes"] = ["/", "*"]
    return inputs


async def test_a_page_the_change_adds_is_returned_for_its_anchor_and_stored_with_it():
    """Wiring at ``handle()``: the profile's judged pages and the anchor rule reach the proposer
    through their assets, the rails read the judged pages from the input the run composed
    (``product_context``), the refusal reaches the revision, and the stored request carries the
    anchor acceptance will read. Bugs caught: the rule taught nowhere, so every added page is
    refused blind; ``client_routes`` composed and never read, so a page the profile already
    judges is refused for its missing anchor; the anchor dropped from the stored document."""
    revised = yaml.safe_load(_ADDS_A_PAGE)
    revised["criteria"][0]["anchor"] = "totals-view"
    ctx = _ctx(_fenced(_ADDS_A_PAGE), _fenced(yaml.safe_dump(revised, sort_keys=False)))

    result = await StrategyProposeIncrementHandler().handle(ctx, _with_pages())

    assert result.success, result.error
    first, second = _prompts(ctx)
    assert "**The pages acceptance already reads.**" in first
    assert "\n- `/`\n- `*`\n" in first
    assert "**A criterion on a page this change adds names its view's `anchor`.**" in first
    assert 'anchor: "export-view"' in first  # the example
    assert "[anchor_required]" in second and "/totals, a page this change adds" in second
    [artifact] = result.outputs["artifacts"]
    [criterion] = yaml.safe_load(artifact["content"])["criteria"]
    assert (criterion["surface"], criterion["anchor"]) == ("/totals", "totals-view")


async def test_a_page_criterion_on_a_judged_page_is_accepted_without_an_anchor():
    """The edge: the pages the profile judges come from the run's input. Bug caught: the rails
    reading no judged pages from it, so a criterion on an existing page is refused for an anchor
    the rule says it must not name."""
    on_the_list = _ADDS_A_PAGE.replace('surface: "/totals"', 'surface: "/"')
    ctx = _ctx(_fenced(on_the_list))

    result = await StrategyProposeIncrementHandler().handle(ctx, _with_pages())

    assert result.success, result.error
    [artifact] = result.outputs["artifacts"]
    assert "anchor" not in yaml.safe_load(artifact["content"])["criteria"][0]


async def test_a_product_whose_profile_judges_no_page_is_shown_none():
    """Bug caught: the judged-pages section rendered empty for a product with no client routes
    (Tally, which has no blueprint), telling the proposer every page is judged by nothing."""
    ctx = _ctx(_fenced(_REQUEST))

    await StrategyProposeIncrementHandler().handle(ctx, _inputs())

    assert "The pages acceptance already reads" not in _prompts(ctx)[0]


async def test_an_added_parameterized_page_is_refused_and_never_stored_for_a_build():
    """The outside review of #2780 (P2 1), end to end under the supervisor's refusal: an added
    page whose path needs a seed is refused at every attempt, so no change request is stored and
    nothing is built to block at delivery. The proposer is told the rule before its first attempt
    and why at its second. Bugs caught: the rule taught nowhere; the refusal reaching no revision;
    a request stored anyway, so the supervisor rules on, and the squad builds, a page acceptance
    can never read."""
    unseedable = yaml.safe_load(_ADDS_A_PAGE)
    unseedable["criteria"][0].update(surface="/reports/:report_id", anchor="report-view")
    reply = _fenced(yaml.safe_dump(unseedable, sort_keys=False))
    ctx = _ctx(reply, reply)

    result = await StrategyProposeIncrementHandler().handle(ctx, _with_pages())

    first, second = _prompts(ctx)
    assert "a page this change adds\nwhose path has a parameter" in first
    assert "[added_route_unseedable]" in second
    assert "/reports/:report_id, a page this change adds" in second
    assert not result.success
    assert not result.outputs.get("artifacts")


async def test_an_added_page_reusing_a_pinned_views_anchor_is_returned_and_revised():
    """The outside review's final round (P2), at ``handle()``: the rails read every anchor of the
    approved manifest from the input the run composed (``product_context``), so a page this change
    adds that reuses the home view's root is returned for revision, and only an anchor of its own
    is stored. Bug caught: the manifest's anchors composed and never read, so the reuse passes and
    a page never built reads held where the app's fallback renders the home view."""
    from tests.unit.campaigns.test_product_routes import MANIFEST

    inputs = _with_pages()
    inputs["product_proposal"]["approved_manifest"] = {
        "stack": "fullstack_fastapi_react",
        "commit": "1" * 40,
        "content": MANIFEST,
    }
    reusing = yaml.safe_load(_ADDS_A_PAGE)
    reusing["criteria"][0]["anchor"] = "shelf-list"  # the home view's root, in MANIFEST
    own = yaml.safe_load(_ADDS_A_PAGE)
    own["criteria"][0]["anchor"] = "totals-view"
    ctx = _ctx(
        _fenced(yaml.safe_dump(reusing, sort_keys=False)),
        _fenced(yaml.safe_dump(own, sort_keys=False)),
    )

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    first, second = _prompts(ctx)
    assert "Give each page its own anchor, one no other page carries" in first
    assert "[anchor_not_unique]" in second
    assert "anchor 'shelf-list' for /totals, a page this change adds, and / already" in second
    assert result.success, result.error
    [artifact] = result.outputs["artifacts"]
    assert yaml.safe_load(artifact["content"])["criteria"][0]["anchor"] == "totals-view"


def _after_totals(pages: list) -> dict:
    """Tally with a UI base and no blueprint, so no approved manifest and no judged page, launched
    with the inventory ``increment_launch`` pins (§24dq): ``/totals``, an earlier increment's."""
    inputs = _inputs()
    inputs["product_proposal"]["profile"]["public_surfaces"].append(
        {"kind": "ui_base", "url": "http://127.0.0.1:18408/"}
    )
    inputs["resolved_config"]["campaign_proposal"]["accepted_pages"] = pages
    return inputs


async def test_a_page_reusing_an_earlier_increments_anchor_is_returned_and_revised():
    """SIP-0109 §24dq, at ``handle()`` with the real assets, on a product with no approved
    manifest: the launch block's inventory reaches the proposer, who is shown ``/totals`` and the
    ids its page carried, and the rails, which return ``/summary`` reusing ``totals-row``. Bugs
    caught: the inventory pinned and never read, so the reuse passes and ``/summary``, never built,
    holds where the fallback renders the totals view; or the proposer told nothing, so it guesses
    an anchor and spends a revision learning it was taken."""
    page = {"route": "/totals", "anchor": "totals-view", "testids": ["totals-view", "totals-row"]}
    reusing = yaml.safe_load(_ADDS_A_PAGE)
    reusing["criteria"][0].update(surface="/summary", anchor="totals-row")
    own = yaml.safe_load(_ADDS_A_PAGE)
    own["criteria"][0].update(surface="/summary", anchor="summary-view")
    ctx = _ctx(
        _fenced(yaml.safe_dump(reusing, sort_keys=False)),
        _fenced(yaml.safe_dump(own, sort_keys=False)),
    )

    result = await StrategyProposeIncrementHandler().handle(ctx, _after_totals([page]))

    first, second = _prompts(ctx)
    assert "**The pages acceptance already reads.**" in first
    assert (
        "\n- `/totals`, added by an earlier increment: its page carries `totals-view`, "
        "`totals-row`\n" in first
    )
    assert "[anchor_not_unique]" in second
    assert "anchor 'totals-row' for /summary, a page this change adds, and /totals" in second
    assert result.success, result.error
    [artifact] = result.outputs["artifacts"]
    assert yaml.safe_load(artifact["content"])["criteria"][0]["anchor"] == "summary-view"


async def test_an_inventory_the_proposal_cant_read_fails_it_and_proposes_nothing():
    """The edge: a page with no anchor can't be held against. Bug caught: it skipped, so the
    proposal runs with that page's anchor free to reuse."""
    ctx = _ctx(_fenced(_ADDS_A_PAGE))

    result = await StrategyProposeIncrementHandler().handle(ctx, _after_totals([{"route": "/t"}]))

    assert not result.success
    assert "names no route or no anchor" in result.error
    ctx.ports.llm.chat_stream_with_usage.assert_not_awaited()


async def test_a_block_an_old_runtime_api_launched_with_no_inventory_fails_the_proposal():
    """SIP-0109 §24dr item 4, the skew a mixed deploy makes: a runtime-api from before §24dq
    launched the proposal, so its block names no inventory. Bug caught: the new nat reading it as
    an empty one, so a page reusing an accepted page's anchor passes the rails, as before #2783."""
    ctx = _ctx(_fenced(_ADDS_A_PAGE))
    inputs = _after_totals([])
    del inputs["resolved_config"]["campaign_proposal"]["accepted_pages"]

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    assert not result.success
    assert "the accepted-page inventory can't be read: the launch pinned none" in result.error
    ctx.ports.llm.chat_stream_with_usage.assert_not_awaited()


# --- SIP-0115 §5.2, §5.3: a goal-set Campaign's proposal (SIP-0109 §24cy) ---

#: The ``goals`` input ``execution.product_proposal`` composes, for an invented goal set on Tally:
#: the first item accepted, the second abandoned, so the third is next.
_GOALS = {
    "revision": 4,
    "reads": "current",
    "goal": "Tally tells a reader what their ledger adds up to",
    "expected_results": [
        {
            "id": "ER-total",
            "statement": "The report ends in the total of its amounts",
            "surface": {"kind": "package_interface", "ref": "tally.report"},
        },
        {
            "id": "ER-plain",
            "statement": "The report reads plainly",
            "surface": {"kind": "none", "reason": "judged by the owner"},
        },
    ],
    "constraints": ["No network access"],
    "out_of_scope": ["Currencies"],
    "backlog": [
        {"id": "B-1", "title": "Parse amounts", "description": "", "serves": ["ER-total"],
         "status": "accepted"},
        {"id": "B-2", "title": "Round totals", "description": "", "serves": ["ER-total"],
         "status": "abandoned", "reason": "§10 row 13: its increment was abandoned"},
        {"id": "B-3", "title": "Report totals", "description": "The report's last line totals it.",
         "serves": ["ER-total"], "status": "pending"},
    ],
    "next_item": "B-3",
}  # fmt: skip


def _on_goals() -> dict:
    inputs = _inputs()
    product = inputs["product_proposal"]
    del product["requirements"]
    product["goals"] = _GOALS
    objective = inputs["resolved_config"]["campaign_proposal"]["objective"]
    del objective["requirements"]
    objective["goals"] = {"goal_set": "prj-tally", "revision": "current"}
    return inputs


def _naming(item: str | None) -> str:
    request = yaml.safe_load(_REQUEST)
    del request["prd_delta"]
    if item is not None:
        request["backlog_item"] = item
    return _fenced(yaml.safe_dump(request, sort_keys=False))


async def test_a_goal_set_proposal_is_shown_the_goal_set_and_names_the_next_item():
    """Wiring (anti-pattern 6a), entered at ``handle()`` with the input the run composes. Bugs
    caught: the goal set composed and never rendered, so the proposer is shown no requirements at
    all; the abandoned item's reason or an item's status dropped (§5.2); the next item computed
    and not shown, so the proposer guesses; the stored request without its item or its revision,
    so the submission binds the proposal to nothing (§5.5a)."""
    ctx = _ctx(_naming("B-3"))

    result = await StrategyProposeIncrementHandler().handle(ctx, _on_goals())

    assert result.success, result.error
    [prompt] = _prompts(ctx)
    assert "### The product's goal set, revision 4" in prompt
    assert "**The goal:** Tally tells a reader what their ledger adds up to" in prompt
    assert "- `ER-total`: The report ends in the total of its amounts (package_interface " in prompt
    assert "- `ER-plain`: The report reads plainly (not observed: judged by the owner)" in prompt
    assert "- No network access" in prompt and "- Currencies" in prompt
    assert "1. `B-1` Parse amounts: **accepted** (serves ER-total)" in prompt
    assert "2. `B-2` Round totals: **abandoned** (serves ER-total). §10 row 13: its" in prompt
    assert "**Your proposal serves B-3, and only it:** Report totals." in prompt
    assert "backlog_item: B-3" in prompt
    assert "requirements, as `repo:file" not in prompt  # no requirements source is named
    [artifact] = result.outputs["artifacts"]
    stored = yaml.safe_load(artifact["content"])
    assert (stored["backlog_item"], stored["goals_revision"]) == ("B-3", 4)


@pytest.mark.parametrize(
    ("readings", "shown"),
    [(['play: {"wins": 43}'], True), ([], False)],
    ids=["a reading", "no increment read yet"],
)
async def test_a_goal_set_proposal_is_shown_the_products_latest_reading(readings, shown):
    """§24dk, entered at ``handle()``. Bugs caught: the reading composed and not rendered, so the
    squad never sees how its work played; a heading with nothing under it on a Campaign's first
    proposal, which reads as a measure of nothing."""
    ctx = _ctx(_naming("B-3"))
    inputs = _on_goals()
    inputs["product_proposal"]["goals"] = {**_GOALS, "latest_readings": readings}

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    assert result.success, result.error
    [prompt] = _prompts(ctx)
    assert ("How the product measured" in prompt) is shown
    assert ('- play: {"wins": 43}' in prompt) is shown


@pytest.mark.parametrize(
    ("named", "why"),
    [
        (None, "names no backlog item"),
        ("B-2", "names backlog_item 'B-2', which is abandoned"),
        ("B-1", "names backlog_item 'B-1', which is accepted"),
        ("B-9", "names backlog_item 'B-9', which the backlog doesn't hold"),
    ],
    ids=["names none", "names the abandoned item", "names an accepted item", "names no such item"],
)
async def test_a_proposal_naming_any_but_the_next_item_is_returned_before_a_cycle_is_spent(
    named, why
):
    """§5.3's rail, judged in the proposal task by the real rails on the real input. Bugs caught:
    a proposal naming no item, or an earlier, abandoned or unknown one, reaching the increment
    gate and spending a ruling and a cycle; the refusal not naming the item to propose, so the
    revision guesses again."""
    ctx = _ctx(_naming(named), _naming("B-3"))

    result = await StrategyProposeIncrementHandler().handle(ctx, _on_goals())

    _first, second = _prompts(ctx)
    assert "[not_the_next_backlog_item]" in second
    assert why in second and "backlog_item: B-3" in second
    assert result.success, result.error
    [artifact] = result.outputs["artifacts"]
    assert yaml.safe_load(artifact["content"])["backlog_item"] == "B-3"


async def test_a_requirements_campaigns_proposal_naming_an_item_is_returned():
    """The edge: no goal set. Bug caught: a ``backlog_item`` stored on a Campaign with no backlog,
    so a submission binds it to an item nothing reads."""
    ctx = _ctx(_naming("B-3"), _fenced(_REQUEST))

    result = await StrategyProposeIncrementHandler().handle(ctx, _inputs())

    _first, second = _prompts(ctx)
    assert "this Campaign works from no goal set" in second
    assert result.success, result.error
    assert "backlog_item" not in yaml.safe_load(result.outputs["artifacts"][0]["content"])


async def test_a_product_proposal_is_shown_that_a_half_already_true_stays_in_one_criterion():
    """#2935, through the real render. Bug caught: BT-2's proposal wrote the half of its item the
    head already met as its own criterion, and that criterion's pass abandoned a sound increment
    at row 19. The rule alone didn't prevent it, so the request shows the case, as a split of the
    example's two halves into one criterion."""
    ctx = _ctx(_naming("B-3"))

    await StrategyProposeIncrementHandler().handle(ctx, _on_goals())

    [prompt] = _prompts(ctx)
    assert "**What the product already does stays inside the criterion that changes it.**" in prompt
    assert "this is one criterion, not\ntwo:" in prompt


async def test_a_scenario_proposal_emits_what_each_scenario_observes_for_its_ruling():
    """#3044, entered at the handler's ``handle()``, as the proposal task runs it. Bugs caught:
    a reviewer ruling on a scenario criterion from raw YAML, never shown which assertion is the
    criterion's or what it observes; or the review folded into the stored request, moving the
    hash the ruling binds to."""
    from adapters.remote_execution.fixture_operation_runner import VOCABULARY
    from squadops.campaigns.change_request import SCENARIO_REVIEW_FILENAME
    from tests.unit.campaigns.test_scenario_criterion import _request as scenario_request

    inputs = _inputs()
    inputs["product_proposal"]["scenario_vocabulary"] = VOCABULARY.to_document()
    ctx = _ctx(_fenced(yaml.safe_dump(scenario_request(), sort_keys=False)))

    result = await StrategyProposeIncrementHandler().handle(ctx, inputs)

    assert result.success, result.error
    request, review = result.outputs["artifacts"]
    assert "scenario_review" not in request["content"]
    assert (review["name"], review["media_type"]) == (SCENARIO_REVIEW_FILENAME, "text/markdown")
    assert "## C-2: Clicking the panel's button opens the door" in review["content"]
    assert (
        "| `door-open` (named) | property (path=`Workspace.Door`, name=`CanCollide`) | server "
        "| equals `false` |"
    ) in review["content"]
    assert "| `spawned` (precondition) |" in review["content"]
