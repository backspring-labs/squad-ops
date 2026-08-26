"""Static execution-readiness gate for the test scaffold — SIP-0104 P2 (Gate 2).

The §4.4 self-check's deterministic half: before an emitted scaffold may become part of a
run, every mechanical claim its bytes make must hold against the authoritative sources.
The dynamic half — actually executing the shells against the walking skeleton — lives in
``handlers.scaffold_execution`` (it needs a Node toolchain; this module needs nothing).

**Every check reads the EMITTED BYTES, never the generator's intent.** P1's derivation
checks prove what the generator *meant* to reference; a generator bug is precisely a gap
between what it meant and what it wrote. The decisive Gate 2 case — internally consistent
inputs, wrong emitted import path — is invisible to intent-level checks and caught here,
as ``scaffold-invalid`` (SIP §5: a generator defect, never an LLM repair target).

Checks, each against its authoritative source (the contract's precedence):

- **imports resolve** — every ``@/…`` specifier maps to a file in the expanded tree; every
  bare specifier is a declared dependency in the tree's ``package.json`` (the roll-9
  ``supertest`` class, closed deterministically for the spine);
- **referenced symbols exist** — every named import and every ``alias.MEMBER`` usage of a
  namespace import is exported by the resolved tree file (the roll-14 wrong-module class);
- **asserted statuses exist in the contract** — every spine status assertion is a status
  the manifest declares (success statuses per endpoint, defaults matching the probe
  deriver, plus the error contract's HTTP codes);
- **criterion identity survives** — each slot's ``slot_id`` and bound ``probe_id`` appear
  literally in the emitted file, so failure evidence can be traced back without a join
  through generator state;
- **placement is collectable** — every file lies where the stack's runner include pattern
  will find it (the #884 "No test files found" class, closed before a runner exists).

Findings accumulate (the ``manifest_gates`` posture: one report, not one-per-revision);
:func:`validate_execution_readiness` raises ``ScaffoldValidationError`` carrying them all.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from squadops.capabilities.verification_scaffold import ScaffoldValidationError

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from squadops.capabilities.scaffold import InterfaceManifest
    from squadops.capabilities.verification_scaffold_emission import (
        VerificationScaffoldEmission,
    )

_NAMESPACE_IMPORT_RE = re.compile(r"^import \* as (?P<alias>\w+) from '(?P<spec>[^']+)'$")
_NAMED_IMPORT_RE = re.compile(r"^import \{(?P<names>[^}]*)\} from '(?P<spec>[^']+)'$")
_STATUS_ASSERT_RE = re.compile(r"expect\(\w+\.status\)\.toBe\((?P<status>\d{3})\)")

#: Where the stack's runner looks (vitest include ``**/__tests__/**/*.test.ts``). A file
#: outside this surface collects as nothing and reads as "no test files found" (#884).
_COLLECTABLE_PREFIX = "__tests__/"
_COLLECTABLE_SUFFIX = ".test.ts"


def _exports(content: str, name: str) -> bool:
    return bool(
        re.search(rf"export (?:async )?(?:function|const|class|interface|type) {name}\b", content)
    )


def _resolve_alias(spec: str, tree: dict[str, str]) -> str | None:
    """A ``@/…`` specifier's tree file, or None. Mirrors the runner's ``@`` alias (root)."""
    stem = spec[2:]
    for candidate in (f"{stem}.ts", f"{stem}.tsx", stem):
        if candidate in tree:
            return candidate
    return None


def _declared_packages(tree: dict[str, str]) -> set[str]:
    try:
        pkg = json.loads(tree.get("package.json", "") or "{}")
    except ValueError:
        return set()
    return set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))


def _allowed_statuses(manifest: InterfaceManifest) -> set[int]:
    """Statuses the contract declares — through the deriver's own seam (#772), plus the
    error contract."""
    allowed: set[int] = set()
    from squadops.capabilities.scaffold import success_status_for

    for ep in manifest.api.endpoints:
        allowed.add(success_status_for(ep))
    contract = manifest.api.error_contract
    for code in contract.codes if contract else ():
        allowed.add(code.http)
    return allowed


def _placement_findings(path: str) -> list[str]:
    if path.startswith(_COLLECTABLE_PREFIX) and path.endswith(_COLLECTABLE_SUFFIX):
        return []
    return [
        f"{path}: outside the runner's collection surface "
        f"({_COLLECTABLE_PREFIX}**/*{_COLLECTABLE_SUFFIX}) — the suite would run "
        f"without it and read as covered"
    ]


def _import_findings(
    path: str, content: str, tree_by_name: dict[str, str], packages: set[str]
) -> tuple[list[str], dict[str, str]]:
    """Import-resolution findings, plus the file's resolved namespace aliases."""
    findings: list[str] = []
    aliases: dict[str, str] = {}
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("import "):
            continue
        ns = _NAMESPACE_IMPORT_RE.match(stripped)
        named = _NAMED_IMPORT_RE.match(stripped)
        spec = (ns or named).group("spec") if (ns or named) else ""
        if not spec:
            findings.append(f"{path}: unparseable import line {stripped!r}")
        elif spec.startswith("@/"):
            resolved = _resolve_alias(spec, tree_by_name)
            if resolved is None:
                findings.append(
                    f"{path}: import {spec!r} resolves to no file in the expanded "
                    f"tree — the suite dies at collection"
                )
            elif ns:
                aliases[ns.group("alias")] = resolved
            else:
                for name in named.group("names").split(","):
                    name = name.strip()
                    if name and not _exports(tree_by_name[resolved], name):
                        findings.append(
                            f"{path}: imports {name!r} from {spec!r}, which "
                            f"{resolved} does not export"
                        )
        elif spec.startswith("."):
            findings.append(
                f"{path}: relative import {spec!r} — the spine imports via the "
                f"stack's `@` alias only"
            )
        elif spec not in packages:
            findings.append(
                f"{path}: bare import {spec!r} is not a declared dependency in "
                f"package.json — the suite dies at collection (the roll-9 class)"
            )
    return findings, aliases


def _handler_findings(
    path: str, content: str, aliases: dict[str, str], tree_by_name: dict[str, str]
) -> list[str]:
    return [
        f"{path}: invokes {alias}.{member} but {aliases[alias]} does not export "
        f"{member!r} — a TypeError at execution"
        for alias, member in re.findall(r"\b(\w+)\.([A-Z]{2,})\b", content)
        if alias in aliases and not _exports(tree_by_name[aliases[alias]], member)
    ]


def _status_findings(path: str, content: str, allowed: set[int]) -> list[str]:
    return [
        f"{path}: asserts status {status}, which the contract does not "
        f"declare (allowed: {sorted(allowed)})"
        for status in _STATUS_ASSERT_RE.findall(content)
        if int(status) not in allowed
    ]


def _identity_findings(emission: VerificationScaffoldEmission) -> list[str]:
    """Slot and probe identity must survive into the bytes (plan P2)."""
    findings: list[str] = []
    emitted = {f["name"]: f["content"] for f in emission.files}
    for record in emission.manifest.files:
        content = emitted.get(record.path, "")
        for slot in record.slots:
            if slot.slot_id not in content:
                findings.append(
                    f"{record.path}: slot id {slot.slot_id!r} does not appear in the "
                    f"emitted file — evidence could not be traced to its slot"
                )
            if slot.probe_id and slot.probe_id not in content.replace(slot.slot_id, ""):
                findings.append(
                    f"{record.path}: bound probe id {slot.probe_id!r} does not survive "
                    f"into the emitted file — the §5 dedup rule would have nothing to "
                    f"join on"
                )
    return findings


def assess_execution_readiness(
    emission: VerificationScaffoldEmission,
    tree: list[dict[str, str]],
    manifest: InterfaceManifest,
) -> list[str]:
    """Every readiness claim the emitted bytes fail, as accumulated findings."""
    tree_by_name = {f["name"]: f["content"] for f in tree}
    packages = _declared_packages(tree_by_name)
    allowed = _allowed_statuses(manifest)
    findings: list[str] = []
    for f in emission.files:
        path, content = f["name"], f["content"]
        findings.extend(_placement_findings(path))
        import_findings, aliases = _import_findings(path, content, tree_by_name, packages)
        findings.extend(import_findings)
        findings.extend(_handler_findings(path, content, aliases, tree_by_name))
        findings.extend(_status_findings(path, content, allowed))
    findings.extend(_identity_findings(emission))
    return findings


def validate_execution_readiness(
    emission: VerificationScaffoldEmission,
    tree: list[dict[str, str]],
    manifest: InterfaceManifest,
) -> None:
    """Raise ``ScaffoldValidationError`` (scaffold-invalid) unless the emission is ready."""
    findings = assess_execution_readiness(emission, tree, manifest)
    if findings:
        raise ScaffoldValidationError(
            "scaffold failed the execution-readiness gate (scaffold-invalid, a generator "
            "defect — never an LLM repair target): " + "; ".join(findings)
        )
