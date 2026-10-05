#!/usr/bin/env python3
"""Which tracked campaign definition produced which campaign, reconciled against the stored record (#1941).

A campaign definition (the file ``squadops campaigns create --file`` reads) is called the **record** of
a campaign only when its semantic fields reconcile with that campaign's stored object: the same
``project_id``, the same objective, and the same policy, compared as the domain objects the runtime
builds (``CampaignObjective``, ``CampaignPolicy.from_stored``), so a policy stored before §24al's one
supervisor bound reconciles exactly as the registry maps it. A file that reconciles with no campaign
is an example, not evidence (the crew's rule on #1941).

For each campaign the script records the definitions that reconcile with it, each one's sha256, and
the identity of the campaign's close-time evidence package (``campaign_evidence``, ``part=package``),
the canonical record the definition is matched to. A campaign still running has no package yet.

**A campaign created since #1954 names its file:** its creation row records the path and sha256
``campaigns create --file`` read. Then provenance is that lookup, and the reconciliation is its
check: ``recorded_reconciles`` says whether a definition with the recorded sha256 reconciles with
the campaign. ``false`` is a finding (the file was edited since, or is not tracked here); ``null``
means nothing was recorded.

    python scripts/dev/campaign_definition_provenance.py examples/03_group_run/campaigns          # print
    python scripts/dev/campaign_definition_provenance.py examples/03_group_run/campaigns --write  # provenance.yaml

It reads the registry through ``psql`` in the postgres container and the vault's metadata inside the
runtime-api container (the vault is root-owned); it writes nothing but ``provenance.yaml``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from squadops.campaigns.models import CampaignObjective, CampaignPolicy

PROVENANCE = "provenance.yaml"


@dataclass(frozen=True)
class Definition:
    path: str
    sha256: str
    spec: dict


@dataclass(frozen=True)
class StoredCampaign:
    campaign_id: str
    project_id: str
    objective: dict
    policy: dict
    created: str
    state: str
    outcome: str
    reason: str
    #: The definition the creation row records (#1954): ``{path, sha256}``, or ``None``.
    recorded: dict | None = None


def _objective(data: Mapping[str, Any]) -> CampaignObjective:
    return CampaignObjective(
        statement=data["statement"],
        allowed_scope=tuple(data["allowed_scope"]),
        measurement=data["measurement"],
        target_accepted_increments=data.get("target_accepted_increments"),
    )


def differences(spec: Mapping[str, Any], stored: StoredCampaign) -> list[str]:
    """The semantic fields on which a definition and a stored campaign differ, by name. Empty when
    they reconcile. A field the runtime cannot build from either side is a difference too."""
    diffs = []
    if spec.get("project_id") != stored.project_id:
        diffs.append("project_id")
    try:
        mine, theirs = _objective(spec["objective"]), _objective(stored.objective)
        diffs += [f"objective.{k}" for k, v in asdict(mine).items() if asdict(theirs)[k] != v]
    except (KeyError, TypeError, ValueError) as e:
        diffs.append(f"objective (unbuildable: {e})")
    try:
        mine, theirs = (
            CampaignPolicy.from_stored(spec["policy"]),
            CampaignPolicy.from_stored(stored.policy),
        )
        diffs += [f"policy.{k}" for k, v in asdict(mine).items() if asdict(theirs)[k] != v]
    except (KeyError, TypeError, ValueError) as e:
        diffs.append(f"policy (unbuildable: {e})")
    return diffs


def reconcile(
    definitions: Sequence[Definition],
    campaigns: Sequence[StoredCampaign],
    packages: Mapping[str, dict],
) -> dict:
    """The provenance document: per campaign, the definitions that reconcile with it; and the
    definitions that reconcile with none."""
    records, matched = [], set()
    for c in campaigns:
        hits = [d for d in definitions if not differences(d.spec, c)]
        matched |= {d.path for d in hits}
        package = packages.get(c.campaign_id) or {}
        recorded_reconciles = (
            None if c.recorded is None else any(d.sha256 == c.recorded["sha256"] for d in hits)
        )
        records.append(
            {
                "campaign_id": c.campaign_id,
                "created": c.created,
                "state": c.state,
                "outcome": c.outcome,
                "create_reason": c.reason,
                "recorded_definition": c.recorded,
                "recorded_reconciles": recorded_reconciles,
                "definitions": [{"path": d.path, "sha256": d.sha256} for d in hits],
                "package_identity": package.get("identity"),
                "package_artifact": package.get("artifact_id"),
            }
        )
    return {
        "rule": (
            "a definition is the record of a campaign only when its project_id, objective and "
            "policy reconcile with the stored campaign (#1941)"
        ),
        "campaigns": records,
        "examples_only": sorted(d.path for d in definitions if d.path not in matched),
    }


# ---------------------------------------------------------------------------------------------
# The reads
# ---------------------------------------------------------------------------------------------


def load_definitions(folder: Path, repo: Path) -> list[Definition]:
    out = []
    for path in sorted(folder.glob("*.yaml")):
        if path.name == PROVENANCE:
            continue
        raw = path.read_bytes()
        out.append(
            Definition(
                str(path.resolve().relative_to(repo)),
                hashlib.sha256(raw).hexdigest(),
                yaml.safe_load(raw),
            )
        )
    return out


def stored_campaigns() -> list[StoredCampaign]:
    sql = (
        "select json_build_object('campaign_id', c.campaign_id, 'project_id', c.project_id, "
        "'objective', c.objective, 'policy', c.policy, 'created', c.created_at, "
        "'state', c.state, 'outcome', coalesce(c.outcome, ''), 'reason', l.reason, "
        "'recorded', l.binding -> 'definition') "
        "from campaigns c join campaign_control_log l on l.campaign_id = c.campaign_id and l.seq = 1 "
        "order by c.created_at"
    )
    out = subprocess.run(
        ["docker", "exec", "squadops-postgres", "psql", "-U", "squadops", "-d", "squadops"]
        + ["-At", "-c", sql],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        r = json.loads(line)
        rows.append(
            StoredCampaign(
                r["campaign_id"],
                r["project_id"],
                r["objective"] if isinstance(r["objective"], dict) else json.loads(r["objective"]),
                r["policy"] if isinstance(r["policy"], dict) else json.loads(r["policy"]),
                str(r["created"]),
                r["state"],
                r["outcome"],
                r["reason"],
                r.get("recorded"),
            )
        )
    return rows


_PACKAGES = r"""
import glob, json
latest = {}
for meta in glob.glob("/app/data/artifacts/**/metadata.json", recursive=True):
    try:
        m = json.load(open(meta))
    except Exception:
        continue
    md = m.get("metadata") or {}
    if m.get("artifact_type") != "campaign_evidence" or md.get("part") != "package":
        continue
    cid = md.get("campaign_id")
    if cid and (cid not in latest or m.get("created_at", "") > latest[cid]["created_at"]):
        latest[cid] = {"identity": md.get("identity"), "artifact_id": m.get("artifact_id"),
                       "created_at": m.get("created_at", "")}
print(json.dumps(latest))
"""


def package_identities() -> dict[str, dict]:
    out = subprocess.run(
        ["docker", "exec", "-i", "squadops-runtime-api", "python", "-"],
        input=_PACKAGES,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return {
        k: {"identity": v["identity"], "artifact_id": v["artifact_id"]}
        for k, v in json.loads(out).items()
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path, help="the tracked definitions' folder")
    parser.add_argument("--write", action="store_true", help=f"write {PROVENANCE} into the folder")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    doc = reconcile(load_definitions(args.folder, repo), stored_campaigns(), package_identities())
    text = yaml.safe_dump(doc, sort_keys=False, width=100)
    if args.write:
        (args.folder / PROVENANCE).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
