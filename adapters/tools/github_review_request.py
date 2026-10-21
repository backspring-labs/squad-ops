"""Review requests on GitHub: a pull request (SIP-0112 FR-06; E.4.3).

The repository is read from the Project's locator (``https://github.com/<owner>/<repo>[.git]``),
and the request is made with the Project's repository-scoped token, which never reaches a log
or an error. An open pull request for the same head is returned rather than duplicated, so a
retry opens one.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import httpx

from squadops.ports.projects.review_request import ReviewRequestFailed, ReviewRequestPort

_REPO_PATH = re.compile(r"^/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def repository_of(repo_uri: str, host: str) -> tuple[str, str]:
    """The owner and name of a repository on ``host``, from an https locator."""
    url = urlsplit(repo_uri)
    match = _REPO_PATH.match(url.path) if url.scheme == "https" else None
    if url.hostname != host or match is None:
        raise ReviewRequestFailed(f"{repo_uri} is not an https repository on {host}")
    return match["owner"], match["repo"]


class GitHubReviewRequests(ReviewRequestPort):
    def __init__(
        self,
        *,
        api_base: str = "https://api.github.com",
        host: str = "github.com",
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._host = host
        self._timeout = timeout_seconds
        self._transport = transport

    async def open_review_request(
        self, *, repo_uri: str, head: str, base: str, title: str, body: str, token: str
    ) -> str:
        owner, repo = repository_of(repo_uri, self._host)
        pulls = f"{self._api_base}/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(
            timeout=self._timeout, headers=headers, transport=self._transport
        ) as client:
            try:
                existing = await client.get(
                    pulls, params={"head": f"{owner}:{head}", "base": base, "state": "open"}
                )
                _raise_for(existing, "listing the open pull requests")
                if existing.json():
                    return str(existing.json()[0]["html_url"])
                opened = await client.post(
                    pulls, json={"title": title, "head": head, "base": base, "body": body}
                )
                _raise_for(opened, "opening the pull request")
            except httpx.HTTPError as e:
                raise ReviewRequestFailed(f"GitHub could not be reached: {type(e).__name__}") from e
            return str(opened.json()["html_url"])


def _raise_for(response: httpx.Response, doing: str) -> None:
    if response.is_success:
        return
    detail: Any
    try:
        detail = response.json().get("message")
    except ValueError:
        detail = None
    raise ReviewRequestFailed(
        f"GitHub answered {response.status_code} {doing}" + (f": {detail}" if detail else "")
    )
