#!/usr/bin/env python3
"""Emit the authored-mode window's design-quality diagnostics (SIP-0103 §5c.7).

**Operator-run, deliberately.** The reference manifest is excluded from squad inputs (§4,
§5c.1), so the comparison happens here — after a window, outside any cycle — rather than in a
pipeline stage that would make the reference an input and contaminate authored mode.

Nothing in 1.6 consumes the output. It exists because M4 removed the mandatory manifest review
on the argument that design quality moves to *sampling, not gating*, and this is half of what
that argument spends. FAY is blind to it: V4 roll 2 flattened the reference's typed
``Participant`` entity into an untyped list and still delivered a working app.

Usage:
    .venv/bin/python scripts/dev/emit_manifest_diagnostics.py AUTHORED.yaml [AUTHORED.yaml ...] \
        [--reference examples/03_group_run/interface_manifest.yaml] [--out report.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from squadops.capabilities.scaffold import InterfaceManifest  # noqa: E402
from squadops.cycles.manifest_diagnostics import render, structural_diff  # noqa: E402

_DEFAULT_REFERENCE = REPO_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", type=Path, help="authored manifest YAML files")
    parser.add_argument("--reference", type=Path, default=_DEFAULT_REFERENCE)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    reference = InterfaceManifest.from_yaml(args.reference.read_text(encoding="utf-8"))

    sections: list[str] = []
    for path in args.manifests:
        authored = InterfaceManifest.from_yaml(path.read_text(encoding="utf-8"))
        sections.append(f"<!-- {path} -->\n" + render(structural_diff(authored, reference)))

    output = "\n---\n\n".join(sections)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"wrote {args.out} ({len(args.manifests)} manifest(s))")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
