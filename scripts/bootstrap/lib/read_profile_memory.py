#!/usr/bin/env python3
"""Read ``memory_containment`` from a bootstrap profile YAML as ``key=value`` lines (#1178).

Prints nothing when the profile declares no containment, so a caller can treat "absent"
and "empty" the same way.

Usage:
    python read_profile_memory.py config/profiles/bootstrap/local-spark.yaml
"""

import sys

import yaml


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <profile.yaml>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        profile = yaml.safe_load(f) or {}

    block = profile.get("memory_containment") or {}
    for key in ("daemon", "package", "free_memory_percent", "free_swap_percent", "swappiness"):
        if block.get(key) is not None:
            print(f"{key}={block[key]}")


if __name__ == "__main__":
    main()
