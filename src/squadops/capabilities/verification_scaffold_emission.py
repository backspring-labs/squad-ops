"""Test-scaffold emission — the generator behind the SIP-0104 contract.

Stack-neutral orchestration: resolve the stack's opt-in, run its shell emitter, pin the
result into a ``VerificationScaffoldManifest``, and validate the emission against its own record
before anything downstream may treat it as the run's qa artifact (the lifecycle rule:
expand → emit → **validate** → persist → expose).

Opt-in follows ``ScaffoldStack.verification_scaffold`` (SIP §8: explicit, all-or-nothing): an
unset field means the stack has not opted in and callers *skip* — qa authors exactly as
today, which is safe-and-visible. A set field naming an unregistered emitter means the two
registries disagree — the #838 class — and emission refuses loudly. Asking this module to
emit for an unopted stack is also a refusal: the caller has contradicted the registry.

``GENERATOR_VERSION`` names the emission behavior. Any change that can move a single
emitted byte — templates, inventory rules, ordering — MUST bump it: the byte-equivalence
pin holds per generator version, and enforcement attributes hash mismatches to generator
drift by exactly this number (SIP §4.3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import yaml

from squadops.capabilities.scaffold import (
    criteria_pack_for,
    expand,
    qa_test_namespace,
    verification_scaffold_for,
)
from squadops.capabilities.stack_nextjs_ts import STACK_NAME as _NEXTJS_TS_NAME
from squadops.capabilities.stack_nextjs_ts_tests import emit_nextjs_ts_verification_scaffold
from squadops.capabilities.verification_scaffold import (
    SCAFFOLD_MANIFEST_VERSION,
    BehaviorSlot,
    ScaffoldDerivationError,
    ScaffoldValidationError,
    VerificationScaffoldManifest,
    build_scaffold_file,
    expanded_tree_hash,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from squadops.capabilities.scaffold import InterfaceManifest

#: Bump on ANY emission-affecting change (module docstring). Recorded in every manifest.
#: 2 (#936) — the shell imports `all` alongside `reset`, so a fill can call the helper
#: the appendix teaches without adding an import it is forbidden to add.
GENERATOR_VERSION = 7

#: The stored manifest artifact's filename (the executor persists it beside the contract).
VERIFICATION_SCAFFOLD_MANIFEST_FILENAME = "verification_scaffold_manifest.yaml"
VERIFICATION_SCAFFOLD_MANIFEST_ARTIFACT_TYPE = "verification_scaffold_manifest"

#: stack-emitter registry, reached ONLY via ``ScaffoldStack.verification_scaffold`` — the explicit
#: field the stack-inventory test enumerates, never name convention.
_EMITTERS: dict[
    str,
    Callable[
        [InterfaceManifest, list[dict[str, str]]], list[tuple[str, str, tuple[BehaviorSlot, ...]]]
    ],
] = {
    _NEXTJS_TS_NAME: emit_nextjs_ts_verification_scaffold,
}


@dataclass(frozen=True)
class VerificationScaffoldEmission:
    """One validated-emittable scaffold: the files, their manifest, and its artifact text."""

    files: tuple[dict[str, str], ...]
    manifest: VerificationScaffoldManifest
    manifest_yaml: str


def emit_verification_scaffold(
    manifest: InterfaceManifest, *, expanded: list[dict[str, str]] | None = None
) -> VerificationScaffoldEmission:
    """Emit the test scaffold for ``manifest``'s stack, deterministically.

    ``expanded`` is the tree imports resolve against; by default the expander's own output.
    It is injectable because *disagreement between the manifest and the tree is a defect
    this generator must refuse on* (SIP §7) — enforcement and the mutation tests hand in
    the tree they actually observed.
    """
    declared = verification_scaffold_for(manifest.stack)
    if not declared:
        raise ScaffoldDerivationError(
            f"stack {manifest.stack!r} declares no verification_scaffold — it has not opted in "
            f"(SIP-0104 §8). Callers gate on verification_scaffold_for() and skip; asking for "
            f"emission anyway contradicts the registry."
        )
    emitter = _EMITTERS.get(declared)
    if emitter is None:
        raise ScaffoldDerivationError(
            f"stack {manifest.stack!r} names verification_scaffold {declared!r}, which is not "
            f"registered (known: {sorted(_EMITTERS)}). The two registries disagree — "
            f"register the emitter or remove the declaration; never fall back."
        )
    tree = expanded if expanded is not None else expand(manifest)
    shells = emitter(manifest, tree)

    namespace = qa_test_namespace(manifest)
    for path, _content, _slots in shells:
        if not any(path.startswith(prefix) for prefix in namespace):
            raise ScaffoldValidationError(
                f"emitted scaffold file {path!r} lies outside the stack's qa test "
                f"namespace {namespace} — the scaffold must live where qa files are "
                f"authorized to live (SIP-0100 D1)."
            )

    record = VerificationScaffoldManifest(
        scaffold_manifest_version=SCAFFOLD_MANIFEST_VERSION,
        generator_version=GENERATOR_VERSION,
        stack=manifest.stack,
        interface_manifest_hash=manifest.content_hash(),
        criteria_pack=criteria_pack_for(manifest.stack),
        expanded_tree_hash=expanded_tree_hash(tree),
        files=tuple(build_scaffold_file(path, content, slots) for path, content, slots in shells),
    )
    emission = VerificationScaffoldEmission(
        files=tuple({"name": path, "content": content} for path, content, _ in shells),
        manifest=record,
        manifest_yaml=_manifest_yaml(record),
    )
    validate_emission(emission)
    return emission


def _manifest_yaml(record: VerificationScaffoldManifest) -> str:
    header = (
        "# Test-scaffold manifest — emitted by the scaffold generator (SIP-0104).\n"
        "# The frozen-spine record region enforcement verifies against; regenerate with\n"
        "# the generator, never hand-edit (a tampered record refuses to load).\n"
    )
    return header + yaml.safe_dump(record.to_dict(), sort_keys=False, default_flow_style=False)


def validate_emission(emission: VerificationScaffoldEmission) -> None:
    """The P1 validity gate: the emission must match its own manifest, structurally.

    Catches generator defects (scaffold-invalid, SIP §5) before persistence: a slot table
    disagreeing with emitted content, hash drift between record and bytes, and cross-file
    slot collisions (namespace placement is refused at emission). P2 extends this gate with
    execution-readiness (imports resolve, shells run against the skeleton); nothing may
    weaken it back below this floor.
    """
    recorded = {f.path: f for f in emission.manifest.files}
    emitted = {f["name"]: f["content"] for f in emission.files}
    if set(recorded) != set(emitted):
        raise ScaffoldValidationError(
            f"manifest records files {sorted(recorded)} but the emission carries "
            f"{sorted(emitted)} — the generator's record and output disagree."
        )
    for path, content in emitted.items():
        rebuilt = build_scaffold_file(path, content, recorded[path].slots)
        if rebuilt != recorded[path]:
            raise ScaffoldValidationError(
                f"{path}: the emitted bytes do not reproduce the manifest's record "
                f"(hash or region drift) — a generator defect, not an input problem."
            )
    findings = emission.manifest.lint()
    if findings:
        raise ScaffoldValidationError("scaffold manifest lint failed: " + "; ".join(findings))
