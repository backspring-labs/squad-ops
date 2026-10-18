"""The registry cutover's refusals (SIP-0112 FR-03, E.5, R3; #2408)."""

import pytest

from squadops.projects.cutover import (
    CutoverProblem,
    RegistryCutoverRefused,
    problems_after_seeding,
    problems_on_the_config_provider,
    unknown_project_ids,
)
from squadops.projects.models import ProjectProvenance

SEEDED = ProjectProvenance.SEEDED
REGISTERED = ProjectProvenance.REGISTERED
CONFIG = ["hello_squad", "group_run", "play_game"]


@pytest.mark.parametrize(
    ("records", "expected"),
    [
        (
            {
                "hello_squad": SEEDED,
                "group_run": SEEDED,
                "play_game": SEEDED,
                "prj-tally": REGISTERED,
            },
            [],
        ),
        (
            {"hello_squad": SEEDED, "play_game": SEEDED},
            [
                CutoverProblem(
                    "group_run", "named by config/projects.yaml, absent from the registry"
                )
            ],
        ),
        (
            {"hello_squad": SEEDED, "group_run": REGISTERED, "play_game": SEEDED},
            [
                CutoverProblem(
                    "group_run",
                    "named by config/projects.yaml and registered separately: reconcile it",
                )
            ],
        ),
    ],
    ids=["all-seeded-beside-a-registration", "one-missing", "one-shadowed-by-a-registration"],
)
def test_the_writable_registry_serves_only_with_every_config_project_seeded(records, expected):
    """Bugs caught: an existing project missing after the cutover (IR-1 reads it as 404), or a
    registered Project of the same ID silently standing in for the sample application."""
    assert problems_after_seeding(CONFIG, records) == expected


def test_the_config_provider_refuses_to_hide_a_registered_project():
    """R3. Bug caught: a rollback to the config file making a Project registered after the
    cutover disappear from every reader."""
    records = {"hello_squad": SEEDED, "prj-zeta": REGISTERED, "prj-alpha": REGISTERED}

    problems = problems_on_the_config_provider(records)

    assert [p.project_id for p in problems] == ["prj-alpha", "prj-zeta"]
    assert problems_on_the_config_provider({"hello_squad": SEEDED}) == []


def test_the_refusal_names_every_problem():
    refused = RegistryCutoverRefused(
        [CutoverProblem("a", "absent"), CutoverProblem("b", "registered")]
    )

    assert str(refused) == "the project registry refuses to serve: a: absent; b: registered"
    assert [p.project_id for p in refused.problems] == ["a", "b"]


def test_unknown_project_ids_are_those_no_record_holds():
    """FR-03: reported, never deleted. Bug caught: a cycle's project dropped from the report
    because it matched a record by prefix or case."""
    assert unknown_project_ids(
        {"play_game", "Play_Game", "play", "retired_app"}, {"play_game": SEEDED}
    ) == ["Play_Game", "play", "retired_app"]
