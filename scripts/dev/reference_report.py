#!/usr/bin/env python3
"""An increment's per-mechanism report (SIP-0109 §11a; #1804).

Reads one increment's record through the runtime API: the brownfield reference scenario's, or a
campaign's. From the cycle and its runs' gate decisions, its assessment, and its evaluation
artifact, it reports each brownfield mechanism separately: delta framing, scoped repair,
accumulated acceptance and baseline discrimination, with route rendering and the verdict. The
derivation is ``campaigns.reference.mechanism_report``; this script only fetches. Read-only.

Usage:
    python scripts/dev/reference_report.py --cycle CYCLE_ID [--project group_run] [--json]
        [--proposal-cycle CYCLE_ID]

--proposal-cycle adds the reference scenario's proposal half (§11a, §24af): what the strategy
role proposed on the same baseline and objective, and the supervisor's rating of it.
"""

from __future__ import annotations

import argparse
import json
import sys

from squadops.campaigns.increment_tree import INCREMENT_EVALUATION_ARTIFACT_TYPE


def _evaluation(client, project: str, cycle_id: str) -> dict | None:
    """The cycle's latest evaluation artifact, or ``None`` when it wrote none."""
    listed = client.get(f"/api/v1/projects/{project}/cycles/{cycle_id}/artifacts")
    rows = listed if isinstance(listed, list) else listed.get("artifacts", [])
    evaluations = sorted(
        (a for a in rows if a.get("artifact_type") == INCREMENT_EVALUATION_ARTIFACT_TYPE),
        key=lambda a: str(a.get("created_at") or ""),
    )
    if not evaluations:
        return None
    content, _name = client.download(f"/api/v1/artifacts/{evaluations[-1]['artifact_id']}/download")
    return json.loads(content.decode("utf-8"))


def _latest(client, project: str, cycle_id: str, artifact_type: str) -> str | None:
    """The cycle's newest artifact of ``artifact_type``, as text, or ``None``."""
    listed = client.get(f"/api/v1/projects/{project}/cycles/{cycle_id}/artifacts")
    rows = listed if isinstance(listed, list) else listed.get("artifacts", [])
    found = sorted(
        (a for a in rows if a.get("artifact_type") == artifact_type),
        key=lambda a: str(a.get("created_at") or ""),
    )
    if not found:
        return None
    content, _name = client.download(f"/api/v1/artifacts/{found[-1]['artifact_id']}/download")
    return content.decode("utf-8")


def _rated_markdown(section: dict) -> list[str]:
    lines = ["", "## Proposal half: proposed and rated, not built"]
    if not section["read"]:
        return [*lines, f"- not read: {section['reason']}"]
    lines += [
        f"- `{section['proposal_id']}` v{section['version']}: criteria {section['criteria']}, "
        f"footprint {len(section['footprint'])} path(s)"
    ]
    rating = section["rating"]
    if rating is None:
        return [*lines, f"- {section['rating_note']}"]
    lines += [f"- verdict: {rating['verdict']}, by {rating['rated_by']}: {rating['reason']}"]
    lines += [
        f"  - {name}: {r.get('score')}: {r.get('note')}"
        for name, r in (rating.get("ratings") or {}).items()
    ]
    return lines


def _markdown(report: dict) -> str:
    launched = (
        f"campaign `{report['campaign_id']}`, {report['kind']} cycle"
        if report.get("campaign_id")
        else "the reference scenario (no campaign)"
    )
    lines = [f"# Increment {report['cycle_id']} ({report['status']})", "", f"- {launched}", ""]
    framing = report["delta_framing"]
    lines += [f"## Delta framing: {framing['attempts']} attempt(s)"]
    for gate in framing["gates"]:
        lines.append(f"- `{gate['run_id']}`: {gate['decision']} by {gate['decided_by']}")
        if gate["notes"]:
            lines.append(f"  - {gate['notes']}")
    repair = report["scoped_repair"]
    lines += ["", "## Scoped repair"]
    lines += [f"- {k}: {v}" for k, v in repair.items()]
    for name in ("accumulated_acceptance", "baseline_discrimination", "route_rendering"):
        section = report[name]
        lines += ["", f"## {name.replace('_', ' ').capitalize()}"]
        if not section["read"]:
            lines.append(f"- not read: {section['reason']}")
            continue
        lines += [f"- {json.dumps(row, sort_keys=True)}" for row in section["rows"]]
        if not section["rows"]:
            lines.append(f"- {section['note']}")
    verdict = report["verdict"]
    lines += ["", "## Verdict", f"- increment: {verdict['increment']}, cycle: {verdict['cycle']}"]
    lines += [f"- unmet: {verdict['unmet']}", f"- blocked: {verdict['blocked']}"]
    if "rated_proposal" in report:
        lines += _rated_markdown(report["rated_proposal"])
    return "\n".join(lines)


def main() -> int:
    from squadops.campaigns.reference import mechanism_report
    from squadops.cli.commands.cycles import _get_client

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--project", default="group_run")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--proposal-cycle", help="the proposal half's cycle (§11a)")
    args = parser.parse_args()

    client = _get_client(None)
    base = f"/api/v1/projects/{args.project}/cycles/{args.cycle}"
    cycle = client.get(base)
    try:
        assessment = client.get(f"{base}/assessment")
    except Exception as e:  # noqa: BLE001 — reported as unread, never as a pass
        print(f"warning: the assessment could not be read: {e}", file=sys.stderr)
        assessment = None
    report = mechanism_report(cycle, assessment, _evaluation(client, args.project, args.cycle))
    if args.proposal_cycle:
        from squadops.campaigns.proposal_rating import PROPOSAL_RATING_ARTIFACT_TYPE
        from squadops.campaigns.reference import rated_proposal
        from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE

        report["rated_proposal"] = rated_proposal(
            _latest(client, args.project, args.proposal_cycle, CHANGE_REQUEST_ARTIFACT_TYPE),
            _latest(client, args.project, args.proposal_cycle, PROPOSAL_RATING_ARTIFACT_TYPE),
        )
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else _markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
