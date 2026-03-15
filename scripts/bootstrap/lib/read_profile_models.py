#!/usr/bin/env python3
"""Read ollama_models from a bootstrap profile YAML and print model names, one per line.

Usage:
    python read_profile_models.py config/profiles/bootstrap/local-spark.yaml

Handles both plain ``name:`` entries and ``required_one_of:`` alternatives (picks first).
"""

import sys

import yaml


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <profile.yaml>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        profile = yaml.safe_load(f)

    for entry in profile.get("ollama_models", []):
        if "name" in entry:
            print(entry["name"])
        elif "required_one_of" in entry:
            # Pick the first alternative
            print(entry["required_one_of"][0])


if __name__ == "__main__":
    main()
