"""The Spark lane's recorded evaluation reference joins the fixture it names (contract 5, #2407).

An ``OutcomeEvaluationRef`` names trees only by SIP-0109's ``FileTree.identity``, never by Git
commit or sandbox revision (SIP-0113 §4.1); a commit is reached through the MacBook lane's
workspace-to-commit mapping (contract 4). These checks keep the recording on the trees the fixture
builds and on the mapping recorded beside it. A reference that named a tree the fixture no longer
builds, or a cycle the mapping doesn't know, would let a Project history join pass against nothing.
"""

from __future__ import annotations

import re

import pytest

from squadops.campaigns.evaluator_trees import FileTree
from tests.fixtures.shared_contract.repository import (
    OUTCOME_REF_FORMS,
    recorded,
    tracked_files,
)

_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")


def _commits_for(tree_identity: str) -> list[str]:
    """Resolve a tree identity to its commits through the recorded mapping, as a reader must."""
    mapping = recorded("workspace_commit_mapping", "valid")
    return [e["commit"] for e in mapping["entries"] if e["tree_identity"] == tree_identity]


def test_the_reference_names_the_trees_the_fixture_builds(repository):
    reference = recorded("outcome_evaluation_ref", "valid")

    def identity(commit: str) -> str:
        return FileTree.of(tracked_files(repository.path, commit)).identity

    assert reference["evaluated_tree_identity"] == identity(repository.second_commit)
    assert reference["previous_accepted_tree_identity"] == identity(repository.first_commit)


def test_the_reference_joins_the_recorded_cycle_and_its_commits(repository):
    reference = recorded("outcome_evaluation_ref", "valid")
    mapping = recorded("workspace_commit_mapping", "valid")
    context = recorded("project_source_context", "valid")

    assert (reference["project_id"], reference["campaign_id"], reference["cycle_id"]) == (
        mapping["project_id"],
        mapping["campaign_id"],
        mapping["cycle_id"],
    )
    assert reference["project_id"] == context["project_id"]
    assert _commits_for(reference["evaluated_tree_identity"]) == [
        context["development_baseline_commit"]
    ]
    assert _commits_for(reference["previous_accepted_tree_identity"]) == [repository.first_commit]


def test_the_stale_reference_resolves_to_the_first_commit_never_the_baseline(repository):
    stale = recorded("outcome_evaluation_ref", "stale_commit")
    baseline = recorded("project_source_context", "valid")["development_baseline_commit"]

    commits = _commits_for(stale["evaluated_tree_identity"])

    assert commits == [repository.first_commit]
    assert baseline not in commits


def test_the_calibration_form_names_the_baseline_commits_tree_and_no_previous_one(repository):
    """SIP-0113 §10l, SIP-0112 H.14. A calibration record is written at the Project's development
    baseline, so its reading's tree is that commit's, reached through the mapping, and it builds on
    nothing. Bug caught: the recorded form naming a tree the fixture doesn't build, or the record's
    commit by a hash a Project history join can't resolve."""
    form = recorded("outcome_evaluation_ref", "calibration_record")
    context = recorded("project_source_context", "valid")

    assert (
        form["evaluated_tree_identity"]
        == FileTree.of(tracked_files(repository.path, repository.second_commit)).identity
    )
    assert _commits_for(form["evaluated_tree_identity"]) == [context["development_baseline_commit"]]
    assert (form["cycle_id"], form["previous_accepted_tree_identity"]) == (None, None)


@pytest.mark.parametrize("form", OUTCOME_REF_FORMS)
def test_no_form_names_a_tree_by_commit_or_sandbox_revision(form):
    reference = recorded("outcome_evaluation_ref", form)
    revisions = {
        e["sandbox_revision_id"] for e in recorded("workspace_commit_mapping", "valid")["entries"]
    }

    for key, value in reference.items():
        assert not (isinstance(value, str) and _GIT_COMMIT.fullmatch(value)), key
        assert value not in revisions, key
