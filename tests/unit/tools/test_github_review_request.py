"""A review_request contribution's pull request on GitHub (SIP-0112 FR-06; E.4.3), against a
mock transport. Bugs caught:
- a retry opening a second pull request for the same branch;
- the request made against the wrong repository, head or base, or without the token;
- the token reaching an error a log keeps;
- a repository on another forge sent to GitHub's API.
"""

from __future__ import annotations

import json

import httpx
import pytest

from adapters.tools.github_review_request import GitHubReviewRequests
from squadops.ports.projects.review_request import ReviewRequestFailed

TOKEN = "github_pat_s3cr3t"


def _forge(handler):
    return GitHubReviewRequests(transport=httpx.MockTransport(handler))


async def _open(forge, repo_uri="https://github.com/owner/tally.git"):
    return await forge.open_review_request(
        repo_uri=repo_uri, head="squadops/cyc_1", base="main", title="T", body="B", token=TOKEN
    )


async def test_one_request_is_opened_against_the_projects_repository_and_base():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(201, json={"html_url": "https://github.com/owner/tally/pull/7"})

    url = await _open(_forge(handler))

    assert url == "https://github.com/owner/tally/pull/7"
    listing, opened = seen
    assert listing.url.params["head"] == "owner:squadops/cyc_1"
    assert opened.url.path == "/repos/owner/tally/pulls"
    assert json.loads(opened.content) == {
        "title": "T",
        "head": "squadops/cyc_1",
        "base": "main",
        "body": "B",
    }
    assert {r.headers["authorization"] for r in seen} == {f"Bearer {TOKEN}"}


async def test_an_open_request_for_the_branch_is_returned_not_duplicated():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "a second pull request was opened"
        return httpx.Response(200, json=[{"html_url": "https://github.com/owner/tally/pull/7"}])

    assert await _open(_forge(handler)) == "https://github.com/owner/tally/pull/7"


@pytest.mark.parametrize(
    ("repo_uri", "status", "message"),
    [
        ("https://gitlab.com/owner/tally.git", None, "not an https repository on github.com"),
        ("git@github.com:owner/tally.git", None, "not an https repository on github.com"),
        ("https://github.com/owner/tally.git", 401, "GitHub answered 401"),
        ("https://github.com/owner/tally.git", 422, "Validation Failed"),
    ],
    ids=["another-forge", "ssh-locator", "token-refused", "refused-request"],
)
async def test_a_refusal_is_named_and_never_carries_the_token(repo_uri, status, message):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(status or 500, json={"message": "Validation Failed"})

    with pytest.raises(ReviewRequestFailed, match=message) as refused:
        await _open(_forge(handler), repo_uri)

    assert TOKEN not in str(refused.value)


async def test_an_open_request_is_recovered_by_its_repository_head_and_base():
    """SIP-0109 §24cn: a Campaign's push that crashed after the forge opened its request recovers
    it by calling again, so the lookup must name the repository, the head and the base. Bugs
    caught: a lookup by head alone, recovering a request against another base; a closed request
    recovered as open; a second request opened."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET", "a second pull request was opened"
        seen.append((request.url.path, dict(request.url.params)))
        return httpx.Response(200, json=[{"html_url": "https://github.com/owner/tally/pull/9"}])

    url = await _forge(handler).open_review_request(
        repo_uri="https://github.com/owner/tally.git", head="squadops/cmp_review000001",
        base="main", title="t", body="b", token="tok_invented",
    )  # fmt: skip

    assert url == "https://github.com/owner/tally/pull/9"
    assert seen == [
        (
            "/repos/owner/tally/pulls",
            {"head": "owner:squadops/cmp_review000001", "base": "main", "state": "open"},
        )
    ]
