"""Whether the latest deploy record describes what runs (#2193), writing nothing:
``python -m squadops.api.runtime.deploy_check < facts.json``, as ``record_deploy.sh --check`` runs
it.

The facts on stdin are ``record_deploy``'s, read by the host. Exit 0 when the record names every
running service's image. Exit 1, naming each service, when it does not: a service rebuilt or
recreated after the record was written, one started since, or one recorded that no longer runs.
Every cycle created on the deploy references that record, so a stale one misdescribes all of them.
Exit 2 when the facts are unreadable.

It is its own module, not a flag of ``record_deploy``, so that an image older than it fails to find
it and writes nothing. That older ``record_deploy`` ignores its arguments and would record a deploy.
"""

from __future__ import annotations

import asyncio
import json
import sys

from squadops.api.runtime.record_deploy import compose_and_check
from squadops.cycles.deploy_record import DeployFactsError


def main() -> int:
    try:
        record, why = asyncio.run(compose_and_check(json.load(sys.stdin)))
    except (json.JSONDecodeError, DeployFactsError) as exc:
        print(f"deploy_check: refused: {exc}", file=sys.stderr)
        return 2
    if why:
        name = record.deploy_id if record else "the deploy record"
        print(f"{name} does not describe what runs: " + "; ".join(why))
        return 1
    assert record is not None  # no record is a reason, above
    print(f"{record.deploy_id} describes what runs: {len(record.services)} services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
