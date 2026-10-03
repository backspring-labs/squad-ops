"""Canonical names for cycle-execution artifacts.

Single source of truth for names that are *written* by one component and
*reconstructed* by another. Today: the Prefect flow-run name — produced by the
dispatched flow executor and reconstructed by the cancel routes to find the
flow run to cancel (#77) — and the flow run's tags (#1722), which a Prefect filter
reads back. Keeping the format here means producer and consumer can never silently
drift apart.
"""

from __future__ import annotations


def flow_run_name(project_id: str, cycle_id: str, run_id: str) -> str:
    """Prefect flow-run name for a cycle run: ``<project>/<cyc[:12]>/<run[:12]>``."""
    return f"{project_id}/{cycle_id[:12]}/{run_id[:12]}"


#: The flow-run tag keys (#1722, #1728). Tags are a view — the registry stays the source of truth
#: — so each is ``<key>:<value>`` for a value the cycle already holds. ``deploy:`` is the one to
#: filter on where a campaign's cycles change deploy: ``framework:`` names only the runtime API's
#: commit, the deploy record every service's image and the models' weights (#1720).
TAG_PROJECT = "project"
TAG_FRAMEWORK = "framework"
TAG_DEPLOY = "deploy"
TAG_CAMPAIGN = "campaign"
TAG_REPLAY_OF = "replay-of"


def flow_run_tags(
    *,
    project_id: str,
    framework_git_sha: str | None,
    deploy_id: str | None,
    campaign_id: str | None,
    replay_of: str | None,
) -> list[str]:
    """The Prefect tags for a cycle run: a tag appears only when its value exists — never a
    ``framework:None`` or ``campaign:None`` a filter would have to know to exclude."""
    tags = [f"{TAG_PROJECT}:{project_id}"]
    for key, value in (
        (TAG_FRAMEWORK, framework_git_sha),
        (TAG_DEPLOY, deploy_id),
        (TAG_CAMPAIGN, campaign_id),
        (TAG_REPLAY_OF, replay_of),
    ):
        if value:
            tags.append(f"{key}:{value}")
    return tags
