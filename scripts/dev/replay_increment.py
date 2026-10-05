#!/usr/bin/env python3
"""Replay a campaign increment outside its campaign, on the current deploy (#1959).

The outer loop's comparison: approve a framework change, run the same increments again on the new
deploy, and compare (the Nostromo IDEA §8 step 7). This generalizes the reference launcher (#1804)
from one pinned increment to any increment of any campaign, and re-derives nothing. An increment
cycle already stores every input its replay needs:

- its ``campaign_proposal`` block: the accepted cycle it built on, whose recorded accepted tree is
  the composed baseline (#1887; the preceding PROMOTE row's ``tree_ref``), the baseline's manifest,
  the objective, and the frozen criteria pinned at launch, bundles and all;
- its approved proposal run's promoted seeds: the change request the ruling bound, the candidate
  manifest and the contract derived from it (``increment_seed``, #1840).

The replay is a fresh cycle on ``campaign-reference``, outside every campaign and with no gate,
carrying those inputs: the same artifact ids, so the same bytes. The squad generates again on the
current deploy. Nothing is written to the source campaign. The notes name the source.

    python scripts/dev/replay_increment.py --cycle CYC [--dry-run]
    python scripts/dev/replay_increment.py --campaign CMP --increment N [--dry-run]

``--increment`` counts the campaign's increment cycles from 1, in launch order. Needs a logged-in
``squadops`` CLI. The replay pauses at ``campaign-reference``'s plan-review gate after framing, as
the reference cycle does, for its supervisor to rule; nothing approves it on its own. Compare the
two with the per-increment scorecard (#1960).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VAULT = ROOT / "data" / "artifacts"
#: The seed types an approved increment gate promotes on its proposal run (``increment_seed``).
SEED_TYPES = ("interface_manifest", "change_request", "verification_contract")


def approved_seeds(records: list[dict]) -> dict[str, str]:
    """The promoted seed of each type, the latest of each, from a proposal run's artifact records
    (``metadata.json``): ``{artifact_type: artifact_id}``. Raises when one is missing, since a
    replay without its approved change request would replay nothing."""
    chosen: dict[str, dict] = {}
    for r in records:
        if r.get("artifact_type") in SEED_TYPES and r.get("promotion_status") == "promoted":
            held = chosen.get(r["artifact_type"])
            if held is None or str(r.get("created_at")) > str(held.get("created_at")):
                chosen[r["artifact_type"]] = r
    missing = [t for t in SEED_TYPES if t not in chosen]
    if missing:
        raise SystemExit(
            f"the approved proposal run promoted no {', '.join(missing)}: nothing to replay"
        )
    return {t: chosen[t]["artifact_id"] for t in SEED_TYPES}


def replay_request(
    source_cycle: str, block: dict, seeds: dict[str, str], *, squad_profile_id: str, campaign: str
) -> dict:
    """The cycle request: ``campaign-reference`` carrying the source increment's block (under a
    replay's own proposal id) and its approved seeds by artifact id."""
    from squadops.contracts.cycle_request_profiles import cycle_request_body

    if not block.get("accepted_cycle_id"):
        raise SystemExit(f"{source_cycle} carries no accepted cycle: it is not an increment")
    replayed = {**block, "proposal_id": f"{block['proposal_id']}-replay", "max_revisions": 0}
    return cycle_request_body(
        "campaign-reference",
        squad_profile_id=squad_profile_id,
        user_values={
            "campaign_proposal": replayed,
            "plan_artifact_refs": [seeds["interface_manifest"], seeds["change_request"]],
            "contract_ref": seeds["verification_contract"],
        },
        notes=(
            f"replay of {campaign} increment cycle {source_cycle} (#1959): its baseline, approved "
            f"change request ({seeds['change_request']}) and frozen criteria, on the current deploy"
        ),
    )


def _increment_cycle(client, project: str, campaign: str, n: int) -> str:
    cycles = [
        c
        for c in client.get(f"/api/v1/projects/{project}/cycles")
        if c.get("campaign_id") == campaign and c.get("kind") == "increment"
    ]
    cycles.sort(key=lambda c: c.get("created_at", ""))
    if not 1 <= n <= len(cycles):
        raise SystemExit(
            f"{campaign} has {len(cycles)} increment cycles; there is no increment {n}"
        )
    return cycles[n - 1]["cycle_id"]


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cycle")
    p.add_argument("--campaign")
    p.add_argument("--increment", type=int)
    p.add_argument("--project", default="group_run")
    p.add_argument("--squad-profile", default="full-38")
    p.add_argument("--vault", type=Path, default=VAULT)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    from squadops.cli.commands.cycles import _get_client

    client = _get_client(None)
    if a.cycle is None:
        if not (a.campaign and a.increment):
            raise SystemExit("name --cycle, or --campaign with --increment")
        a.cycle = _increment_cycle(client, a.project, a.campaign, a.increment)
    row = client.get(f"/api/v1/projects/{a.project}/cycles/{a.cycle}")
    block = (row.get("execution_overrides") or {}).get("campaign_proposal") or {}
    runs = client.get(f"/api/v1/projects/{a.project}/cycles/{a.cycle}/runs")
    proposals = [
        r for r in runs if r.get("workload_type") == "proposal" and r.get("status") == "completed"
    ]
    if not proposals:
        raise SystemExit(f"{a.cycle} has no completed proposal run: nothing was approved")
    approved = max(proposals, key=lambda r: r.get("run_number", 0))
    records = [
        json.loads(m.read_text())
        for m in (a.vault / a.project / a.cycle / approved["run_id"]).glob("art_*/metadata.json")
    ]
    seeds = approved_seeds(records)
    body = replay_request(
        a.cycle,
        block,
        seeds,
        squad_profile_id=a.squad_profile,
        campaign=row.get("campaign_id") or "?",
    )
    if a.dry_run:
        shown = json.loads(json.dumps(body))
        shown.get("execution_overrides", {}).get("campaign_proposal", {})["baseline_manifest"] = "…"
        print(json.dumps({"source": a.cycle, "seeds": seeds, "request": shown}, indent=2))
        return 0
    created = client.post(f"/api/v1/projects/{a.project}/cycles", json=body)
    print(
        json.dumps(
            {"replay_cycle": created.get("cycle_id"), "source": a.cycle, "seeds": seeds}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
