#!/usr/bin/env python3
"""The facts of a deploy that only the host can read, as the recorder's stdin (#1720).

    python3 scripts/dev/ops/deploy_facts.py "<recorded_by>" "<source_revision>"

For every running service of this compose project: the image its container runs and that image's
``org.opencontainers.image.revision`` label. The runtime API has no Docker access, and a container
cannot reliably read its own image ID, so this is gathered here and handed to
``squadops.api.runtime.record_deploy`` in the runtime image (``record_deploy.sh``).

Standard library only: it runs on the host's ``python3``, as ``rebuild_and_deploy.sh``'s other
host steps do, and a one-click install carries no ``jq``.
"""

from __future__ import annotations

import json
import subprocess
import sys

REVISION_LABEL = "org.opencontainers.image.revision"


def _docker(*args: str) -> str:
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout


def running_services() -> list[tuple[str, str]]:
    """``(service, container_id)`` for each running service. ``docker compose ps`` prints a JSON
    array on older Compose releases and one JSON object per line on newer ones."""
    out = _docker("compose", "ps", "--format", "json").strip()
    rows = (
        json.loads(out)
        if out.startswith("[")
        else [json.loads(line) for line in out.splitlines() if line]
    )
    return [(r["Service"], r["ID"]) for r in rows if r.get("State") == "running"]


def facts(
    services: list[tuple[str, str]],
    image_of: dict[str, str],
    labels_of: dict[str, dict[str, str] | None],
    recorded_by: str,
    source_revision: str,
) -> dict:
    """The document the recorder reads: each service, its image, and the image's revision label
    (``None`` when the image carries none — an infrastructure image, or one built without the
    deploy script)."""
    return {
        "recorded_by": recorded_by,
        "source_revision": source_revision or None,
        "services": [
            {
                "service": service,
                "image_id": image_of[container],
                "revision": (labels_of.get(image_of[container]) or {}).get(REVISION_LABEL) or None,
            }
            for service, container in sorted(services)
        ],
    }


def main(argv: list[str]) -> int:
    recorded_by = argv[1] if len(argv) > 1 else "record_deploy.sh"
    source_revision = argv[2] if len(argv) > 2 else ""
    services = running_services()
    if not services:
        print("deploy_facts: no running services in this compose project", file=sys.stderr)
        return 1
    image_of = {c: _docker("inspect", "--format", "{{.Image}}", c).strip() for _, c in services}
    labels_of = {
        image: json.loads(_docker("image", "inspect", "--format", "{{json .Config.Labels}}", image))
        for image in set(image_of.values())
    }
    print(json.dumps(facts(services, image_of, labels_of, recorded_by, source_revision)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
