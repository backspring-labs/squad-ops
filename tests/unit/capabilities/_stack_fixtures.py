"""One reference design, expressed for whichever stack is under test.

Every stack test derives its manifest from `examples/03_group_run/interface_manifest.yaml`
by swapping `stack:`. That works only while the *rest* of the document is stack-neutral,
and #859 found the point where it stops being.

The reference declares its API at `/runs` and a page at `/runs/:id`. On stack #1 those live
in different trees (`backend/` and `frontend/src/`) and cannot interfere. On App Router both
are directories under `app/`, so the same two declarations ask Next to serve one path from
two files — which it refuses, and which `_assert_routing_tree_is_coherent` now refuses at
framing rather than four hours into a run.

So declaring API endpoints under `/api` is a **requirement of stack #2**, not decoration.
That is what `manifest_for_stack` applies, and applying it in one place means a third stack
adds its own clause here rather than each test growing a private workaround.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from squadops.capabilities.scaffold import InterfaceManifest

REFERENCE_PATH = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)

#: Stacks whose API handlers and pages share one routing tree, so an API path must be
#: distinguishable from a page path. Empty prefix = the stack keeps them in separate trees
#: and the reference's paths work unmodified.
_API_PREFIX: dict[str, str] = {"nextjs_ts": "/api"}


def reference_dict() -> dict[str, Any]:
    return yaml.safe_load(REFERENCE_PATH.read_text(encoding="utf-8"))


def manifest_dict_for_stack(stack: str) -> dict[str, Any]:
    """The reference design as `stack` requires it to be declared."""
    raw = reference_dict()
    raw["stack"] = stack
    prefix = _API_PREFIX.get(stack, "")
    if prefix:
        for ep in raw["api"]["endpoints"]:
            ep["path"] = prefix + ep["path"]
    return raw


def manifest_for_stack(stack: str) -> InterfaceManifest:
    return InterfaceManifest.from_yaml(
        yaml.safe_dump(manifest_dict_for_stack(stack), sort_keys=False)
    )
