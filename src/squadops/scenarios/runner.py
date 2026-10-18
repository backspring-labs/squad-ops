"""What the scenario runner takes and gives (SIP-0113 §4.1; X-3b; #2414, #2421).

The runner stands an evaluated tree up in a disposable copy, by its ``FileTree.identity``, never
by a sandbox revision (SIP-0112 contract 3). It runs a suite's scenarios against it and discards
it.

- **A blueprint Project starts by its stack's environment contract,** with transport-level
  readiness (#520/#622).
- **Any other Project starts by its start declaration** (contract 7), read here into a
  ``DeclaredStart``. Readiness is a 2xx from the declared target.

This SIP never infers how to start a product from a sample application.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from squadops.scenarios.steps import ScenarioRun


class StartUndeclared(ValueError):
    """A start declaration this runner can't read: every scenario is ``blocked_unverified``,
    reason ``no_start_declaration`` (SIP-0112 §8.2.1)."""


@dataclass(frozen=True)
class DeclaredStart:
    """A product's own start (contract 7): setup argvs, then the start argv, in the copy. The
    port is the one the product listens on inside it, and readiness is a 2xx from
    ``ready_path``."""

    start: tuple[str, ...]
    port: int
    ready_path: str
    setup: tuple[tuple[str, ...], ...] = ()
    working_dir: str = "."
    ready_timeout_seconds: float = 30.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": list(self.start),
            "port": self.port,
            "ready_path": self.ready_path,
            "setup": [list(s) for s in self.setup],
            "working_dir": self.working_dir,
            "ready_timeout_seconds": self.ready_timeout_seconds,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> DeclaredStart:
        return cls(
            start=tuple(d["start"]),
            port=int(d["port"]),
            ready_path=str(d["ready_path"]),
            setup=tuple(tuple(s) for s in d.get("setup", ())),
            working_dir=str(d.get("working_dir", ".")),
            ready_timeout_seconds=float(d.get("ready_timeout_seconds", 30.0)),
        )


def declared_start(declaration: Mapping[str, Any] | None) -> DeclaredStart:
    """A Development Configuration's start declaration (SIP-0112 §8.2.1, contract 7), as the
    runner runs it. Its URLs are as the product sees them, loopback on its declared port. The
    runner publishes that port and keeps the path."""
    if not declaration or not declaration.get("start"):
        raise StartUndeclared("the Project declares no start")
    readiness = declaration.get("readiness") or {}
    if readiness.get("kind") != "http":
        raise StartUndeclared(f"no runner for readiness {readiness.get('kind')!r}")
    target = urlsplit(str(readiness.get("target", "")))
    if target.port is None:
        raise StartUndeclared(f"readiness target {readiness.get('target')!r} names no port")
    return DeclaredStart(
        start=tuple(declaration["start"]),
        port=target.port,
        ready_path=target.path or "/",
        setup=tuple(
            tuple(argv) for key in ("install", "build") for argv in declaration.get(key) or ()
        ),
        working_dir=str(declaration.get("working_directory", ".")),
        ready_timeout_seconds=float(readiness.get("timeout_seconds", 30)),
    )


@dataclass(frozen=True)
class TreeEvaluation:
    """One tree's evaluation in the runner. ``started`` False carries why (``start_detail`` and
    the app's own last lines), and then no scenario ran."""

    tree_identity: str
    started: bool
    start_detail: str | None = None
    startup_diagnostics: tuple[str, ...] = ()
    runs: tuple[ScenarioRun, ...] = field(default_factory=tuple)
    duration_seconds: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "tree_identity": self.tree_identity,
            "started": self.started,
            "start_detail": self.start_detail,
            "startup_diagnostics": list(self.startup_diagnostics),
            "runs": [r.as_dict() for r in self.runs],
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> TreeEvaluation:
        return cls(
            tree_identity=d["tree_identity"],
            started=d["started"],
            start_detail=d.get("start_detail"),
            startup_diagnostics=tuple(d.get("startup_diagnostics", ())),
            runs=tuple(ScenarioRun(**r) for r in d.get("runs", ())),
            duration_seconds=d.get("duration_seconds", 0.0),
        )
