"""Launch the brownfield reference increment (SIP-0109 §11a; #1804).

Reads the scenario (examples/03_group_run/reference_scenario.yaml), reconstructs the baseline's
delivered tree from the vault by the one delivered-tree rule (#1833), builds the three seeds an
approved increment gate stores (the stored change request, the candidate manifest, the contract
derived from it) through the proposal's own rails, checks every input against its pin, uploads
the seeds and creates the cycle on the `campaign-reference` profile.

Usage:
    .venv/bin/python scripts/dev/launch_reference_increment.py [--dry-run] [--write-pins]
        [--proposal] [--squad-profile full-38] [--notes TEXT]

--proposal launches the proposal half instead (§11a, §24af): the strategy role proposes against
the same pinned baseline and objective on `campaign-proposal`, nothing is seeded and nothing is
built, and the supervisor rates the stored change request with `squadops cycles rate`.

--dry-run prints the pins and the cycle request without creating anything. --write-pins records
the current inputs' hashes as the scenario's pins (freezing it); it refuses to overwrite pins
that are already set. Exit 0 = launched (or the dry run's report); 1 = an input drifted; 2 = the
scenario could not be assembled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "examples" / "03_group_run" / "reference_scenario.yaml"
VAULT = ROOT / "data" / "artifacts"


def _sha(data: str | bytes) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def baseline_tree(vault: Path, project: str, cycle_id: str, run_id: str) -> dict[str, bytes]:
    """The baseline's delivered files, by the rule every reader of a delivered tree uses."""
    from squadops.cycles.delivered_tree import StoredArtifact, delivered_files

    src = vault / project / cycle_id / run_id
    if not src.is_dir():
        raise SystemExit(f"no vault directory for {project}/{cycle_id}/{run_id}")
    records = {}
    for meta_path in src.glob("art_*/metadata.json"):
        meta = json.loads(meta_path.read_text())
        records[meta["artifact_id"]] = (meta, meta_path.parent)
    files: dict[str, bytes] = {}
    for name, art_id in delivered_files(
        StoredArtifact.from_record(m) for m, _ in records.values()
    ).items():
        art_dir = records[art_id][1]
        source = art_dir / name
        if not source.exists():
            found = [p for p in art_dir.rglob("*") if p.is_file() and p.name != "metadata.json"]
            if not found:
                continue
            source = found[0]
        files[name] = source.read_bytes()
    return files


def main() -> int:
    from squadops.campaigns.evaluator_trees import FileTree
    from squadops.campaigns.reference import (
        ReferenceDrift,
        check_pins,
        reference_increment,
        reference_proposal_block,
        reference_proposal_request,
    )
    from squadops.contracts.cycle_request_profiles import cycle_request_body

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", default="group_run")
    parser.add_argument("--squad-profile", default="full-38")
    parser.add_argument("--notes", default="brownfield reference increment (SIP-0109 §11a, #1804)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--vault", type=Path, default=VAULT, help="the deploy's artifact vault")
    parser.add_argument("--write-pins", action="store_true")
    parser.add_argument(
        "--proposal", action="store_true", help="launch the proposal half: proposed and rated"
    )
    args = parser.parse_args()

    scenario = yaml.safe_load(SCENARIO.read_text())
    base = scenario["baseline"]
    manifest = (ROOT / base["manifest"]).read_text()
    authored_text = (ROOT / scenario["change_request"]).read_text()
    tree = FileTree.of(baseline_tree(args.vault, args.project, base["cycle_id"], base["run_id"]))
    try:
        seeds = reference_increment(
            yaml.safe_load(authored_text),
            baseline_manifest=manifest,
            baseline_tree=tree.identity,
            stack=scenario["stack"],
            allowed_scope=tuple(scenario["allowed_scope"]),
        )
    except ValueError as e:
        print(f"could not assemble the scenario: {e}", file=sys.stderr)
        return 2
    actual = {
        "baseline_tree": tree.identity,
        "baseline_manifest": _sha(manifest),
        "change_request_authored": _sha(authored_text),
        **seeds.pins,
    }

    if args.write_pins:
        if scenario.get("pins"):
            print("the scenario is already pinned; refusing to overwrite its pins", file=sys.stderr)
            return 2
        text = SCENARIO.read_text().replace(
            "pins: {}", "pins:\n" + "".join(f"  {k}: {v}\n" for k, v in actual.items()).rstrip("\n")
        )
        SCENARIO.write_text(text)
        print(f"pinned {len(actual)} inputs in {SCENARIO.relative_to(ROOT)}")
        return 0
    try:
        check_pins(actual, scenario.get("pins") or {})
    except ReferenceDrift as e:
        print(str(e), file=sys.stderr)
        return 1

    block = reference_proposal_block(
        baseline_tree=tree.identity,
        accepted_cycle_id=base["cycle_id"],
        baseline_manifest=manifest,
        objective=scenario["objective"],
    )
    if args.dry_run:
        print(
            json.dumps(
                {"pins": actual, "campaign_proposal": {**block, "baseline_manifest": "…"}}, indent=2
            )
        )
        return 0

    # The CLI's own transport and cached token, as `squadops cycles create` uses them.
    from squadops.cli.commands.cycles import _get_client

    client = _get_client(None)
    if args.proposal:
        body = reference_proposal_request(
            block, squad_profile_id=args.squad_profile, notes=f"{args.notes} (proposal half)"
        )
        created = client.post(f"/api/v1/projects/{args.project}/cycles", json=body)
        print(json.dumps({"cycle_id": created.get("cycle_id"), "half": "proposal"}, indent=2))
        return 0
    refs = {}
    for name, content, kind, filename, media in (
        (
            "change_request",
            seeds.change_request.encode(),
            "change_request",
            "change_request.yaml",
            "text/yaml",
        ),
        (
            "candidate_manifest",
            seeds.candidate_manifest.encode(),
            "interface_manifest",
            "interface_manifest.yaml",
            "text/yaml",
        ),
        (
            "contract",
            seeds.contract,
            "verification_contract",
            "verification_contract.yaml",
            "text/yaml",
        ),
    ):
        path = Path("/tmp") / f"reference-{name}-{_sha(content)[:12]}.yaml"
        path.write_bytes(content)
        refs[name] = client.upload(
            f"/api/v1/projects/{args.project}/artifacts/ingest",
            file_path=path,
            fields={"artifact_type": kind, "filename": filename, "media_type": media},
        )["artifact_id"]
    body = cycle_request_body(
        "campaign-reference",
        squad_profile_id=args.squad_profile,
        user_values={
            "campaign_proposal": block,
            "plan_artifact_refs": [refs["candidate_manifest"], refs["change_request"]],
            "contract_ref": refs["contract"],
        },
        notes=args.notes,
    )
    created = client.post(f"/api/v1/projects/{args.project}/cycles", json=body)
    print(json.dumps({"cycle_id": created.get("cycle_id"), "seeds": refs}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
