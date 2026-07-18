#!/usr/bin/env python3
"""Contract emission-time gate — "verify the verifier" (SIP-0098 §6.2).

Three modes, run in CI on the SIP-0099 skeleton gate. Together they guarantee no
criterion can enter the contract that either false-greens on stubs or is unwinnable by
correct code — the structural fix for the criteria lottery.

  lint            The emitted contract lints clean (the 98.1 linter).
  bare-skeleton   Every structural (interface/compile) criterion and the frontend_build
                  guard PASS on the freshly expanded skeleton; the fill-behavior
                  measure (tests_pass) does NOT (no suite exists until the fill). Proves
                  the behavior measures actually measure the fill.
  reference-fill  The FULL contract passes against skeleton + the checked-in reference
                  fill. The winnability proof.
  emit            Write the lint-clean contract to a file for seeding into live cycles
                  (98.5): ingest it (`squadops artifacts ingest --type
                  verification_contract`) and set the returned artifact id as
                  `execution_overrides.contract_ref` at cycle create. Emission is
                  deterministic, so a contract emitted from a gate-green tree IS the
                  gate-validated contract; the printed content_hash is the frozen hash
                  the yield baseline measures against. The contract must pre-exist the
                  cycle — framing consumes its criteria index at proposer dispatch, so
                  it cannot be derived mid-cycle from framing's own manifest.

Refinement of SIP §6.2 (approved 2026-07-17, noted on the PR): a walking skeleton
compiles/builds/boots by design, so compile/build checks are regression guards that
PASS on the bare skeleton; only behavior-exercising checks (tests_pass; probes) fail
on it. As of 98.4 the behavioral probes are executed here too (the probe runner boots
the subject and issues the declared requests): they PASS against the reference fill
(winnability) and must NOT pass on the bare skeleton (its 501 stubs answer nothing).

Usage:
    python scripts/dev/contract_gate.py <lint|bare-skeleton|reference-fill|emit> \
        [--manifest PATH] [--reference-fill DIR] [--out PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from squadops.capabilities.handlers.probe_runner import run_probes
from squadops.capabilities.scaffold import InterfaceManifest, expand
from squadops.capabilities.scaffold_contract import emit_contract_dict, emit_contract_yaml
from squadops.cycles.verification_contract import VerificationContract
from squadops.cycles.verification_contract_runner import (
    FILL_BEHAVIOR_MEASURES,
    evaluate_structural,
    structural_criteria,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MANIFEST = _REPO_ROOT / "examples" / "03_group_run" / "interface_manifest.yaml"
_DEFAULT_REFERENCE_FILL = (
    _REPO_ROOT / "tests" / "fixtures" / "reference_fills" / "fullstack_fastapi_react" / "group_run"
)


class _Result:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, bool]] = []  # (id, got, expected, ok)

    def record(self, criterion_id: str, got: str, expected: str) -> None:
        self.rows.append((criterion_id, got, expected, got == expected))

    def ok(self) -> bool:
        return all(row[3] for row in self.rows)

    def report(self, mode: str) -> None:
        for cid, got, expected, ok in self.rows:
            mark = "ok  " if ok else "FAIL"
            print(f"  [{mark}] {cid:28} got={got:9} expected={expected}")
        verdict = "GREEN" if self.ok() else "RED"
        print(f"{mode}: {verdict} ({sum(r[3] for r in self.rows)}/{len(self.rows)} criteria)")


def _materialize(manifest_path: Path, dest: Path) -> InterfaceManifest:
    manifest = InterfaceManifest.from_yaml(manifest_path.read_text(encoding="utf-8"))
    for f in expand(manifest):
        out = dest / f["name"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(f["content"], encoding="utf-8")
    return manifest


def _overlay(ref_dir: Path, dest: Path) -> None:
    for src in ref_dir.rglob("*"):
        if src.is_file():
            out = dest / src.relative_to(ref_dir)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)


def _run(argv: list[str], cwd: Path) -> bool:
    """True iff the command exits 0. Output streamed so CI logs show failures."""
    print(f"    $ {' '.join(argv)}  (cwd={cwd})")
    return subprocess.run(argv, cwd=cwd).returncode == 0  # noqa: S603 — fixed argv, CI gate


def _tests_pass(workspace: Path) -> bool:
    if not (workspace / "backend" / "tests").is_dir():
        return False  # no suite on the bare skeleton -> tests_pass cannot pass
    return _run([sys.executable, "-m", "pytest", "backend/tests", "-q"], workspace)


def _frontend_build(workspace: Path) -> bool:
    frontend = workspace / "frontend"
    return _run(["npm", "install", "--no-audit", "--no-fund"], frontend) and _run(
        ["npm", "run", "build"], frontend
    )


def _evaluate(contract: VerificationContract, workspace: Path, result: _Result) -> None:
    """Fill structural + frontend_build outcomes (shared by both run modes)."""
    for criterion, fill_file in structural_criteria(contract):
        outcome = evaluate_structural(criterion, workspace, fill_file=fill_file)
        # structural checks pass on both the bare skeleton and the reference fill
        result.record(criterion["id"], outcome.status, "passed")
    build = contract.behavioral.build
    if build:
        got = "passed" if _frontend_build(workspace) else "failed"
        result.record(build[0].id, got, "passed")


def _record_probes(
    contract: VerificationContract, workspace: Path, result: _Result, *, bare: bool
) -> None:
    """Boot the subject and run every behavioral probe (SIP §6.4/§6.5, 98.4).

    Reference-fill: each probe must ``passed``. Bare skeleton: a probe must NOT pass
    (its stubs answer 501/nothing) — a probe that passes on the bare skeleton is a
    false-green admitted at authoring time, exactly what this gate exists to catch."""
    for outcome in run_probes(workspace, contract.behavioral.probes):
        if bare:
            got = "passed" if outcome.status == "passed" else "not_passed"
            result.record(outcome.id, got, "not_passed")
        else:
            result.record(outcome.id, outcome.status, "passed")


def _mode_lint(manifest_path: Path) -> int:
    manifest = InterfaceManifest.from_yaml(manifest_path.read_text(encoding="utf-8"))
    errors = VerificationContract.from_dict(emit_contract_dict(manifest)).lint()
    if errors:
        print("lint: RED")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("lint: GREEN (emitted contract lints clean)")
    return 0


def _mode_bare(manifest_path: Path) -> int:
    result = _Result()
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        manifest = _materialize(manifest_path, workspace)
        contract = VerificationContract.from_dict(emit_contract_dict(manifest))
        _evaluate(contract, workspace, result)
        # fill-behavior measures must NOT pass on the bare skeleton
        for crit in contract.behavioral.suite.checks:
            if crit.check in FILL_BEHAVIOR_MEASURES:
                got = "passed" if _tests_pass(workspace) else "not_passed"
                result.record(crit.id, got, "not_passed")
        _record_probes(contract, workspace, result, bare=True)
    result.report("bare-skeleton")
    return 0 if result.ok() else 1


def _mode_reference_fill(manifest_path: Path, ref_dir: Path) -> int:
    result = _Result()
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        manifest = _materialize(manifest_path, workspace)
        _overlay(ref_dir, workspace)
        contract = VerificationContract.from_dict(emit_contract_dict(manifest))
        _evaluate(contract, workspace, result)
        # with the reference fill in place, every behavior measure must pass
        for crit in contract.behavioral.suite.checks:
            if crit.check in FILL_BEHAVIOR_MEASURES:
                got = "passed" if _tests_pass(workspace) else "failed"
                result.record(crit.id, got, "passed")
        _record_probes(contract, workspace, result, bare=False)
    result.report("reference-fill")
    return 0 if result.ok() else 1


def _mode_emit(manifest_path: Path, out_path: Path) -> int:
    """Write the seeding artifact (98.5): lint-gated, deterministic, hash-reported."""
    manifest = InterfaceManifest.from_yaml(manifest_path.read_text(encoding="utf-8"))
    contract_yaml = emit_contract_yaml(manifest)
    contract = VerificationContract.from_yaml(contract_yaml)
    errors = contract.lint()
    if errors:
        print("emit: RED (refusing to write a contract that fails lint)")
        for e in errors:
            print(f"  - {e}")
        return 1
    out_path.write_text(contract_yaml, encoding="utf-8")
    content_hash = hashlib.sha256(contract_yaml.encode("utf-8")).hexdigest()
    print(f"emit: GREEN -> {out_path} ({len(contract.criterion_ids())} criteria)")
    print(f"  contract content_hash (the frozen yield-baseline hash): {content_hash}")
    print(f"  skeleton.interface_manifest_hash: {manifest.content_hash()}")
    print("Seed it:")
    print(
        f"  squadops artifacts ingest --project <project> "
        f"--type verification_contract --file {out_path}"
    )
    print('  then create the cycle with execution_overrides {"contract_ref": "<artifact_id>"}')
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="SIP-0098 contract emission-time gate")
    parser.add_argument("mode", choices=["lint", "bare-skeleton", "reference-fill", "emit"])
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--reference-fill", type=Path, default=_DEFAULT_REFERENCE_FILL)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("verification_contract.yaml"),
        help="emit mode: output path for the contract artifact",
    )
    args = parser.parse_args(argv)

    if args.mode == "lint":
        return _mode_lint(args.manifest)
    if args.mode == "bare-skeleton":
        return _mode_bare(args.manifest)
    if args.mode == "emit":
        return _mode_emit(args.manifest, args.out)
    return _mode_reference_fill(args.manifest, args.reference_fill)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
