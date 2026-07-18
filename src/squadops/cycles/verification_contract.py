"""Verification contract schema, loader, and linter (SIP-0098 phase 98.1).

A *verification contract* is a first-class, roll-invariant artifact authored once
by the expander alongside the skeleton (SIP-0099) and **bound — not authored — by
framing**. It states, purely declaratively, what must be true of a filled
skeleton: the frozen surface that fills may not rewire, the per-file interface and
implementation criteria, and the behavioral checks/probes that are the last word on
the deliverable. See ``sips/accepted/SIP-0098-Verification-Contracts-Contract-Owned-Acceptance.md``.

This module owns three things and nothing else (phase 98.1 is deliberately pure —
no orchestration, no I/O beyond parsing a YAML string):

- **Schema** — frozen dataclasses mirroring ``verification_contract.yaml`` (§6.1).
- **Loader** — ``VerificationContract.from_yaml`` / ``from_dict`` (tolerant: builds a
  best-effort structure from partial data so ``lint`` can report *all* defects;
  raises only on gross structural malformation, i.e. YAML that isn't a contract).
- **Linter** — ``lint()`` returns ``list[str]``, one message per defect, catching
  every §2 defect class expressible at schema level. It is the emission-time "verify
  the verifier" gate's first job (§6.2 job 1); the bare-skeleton and reference-fill
  runs (jobs 2–3) are empirical and land in phase 98.2.

Single-sourcing: the typed-check vocabulary, command safelist, and the #464
document-only rule for ``regex_match`` all come from ``acceptance_check_spec``; the
behavioral framework-check identities and the ``node`` tooling id come from
``check_registry``. This module reuses those primitives and never restates them —
the same discipline ``implementation_plan.validate_criteria_scope`` follows.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

from squadops.cycles.acceptance_check_spec import (
    CHECK_SPECS,
    argv_matches_safelist,
    command_safelist_names,
    regex_target_is_document,
)
from squadops.cycles.check_registry import TOOL_NODE, framework_check_ids

# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

CONTRACT_VERSION = 1

# A *capability* is a toolchain the contract's executable checks REQUIRE (§6.1). It
# is a fact about the check, not about infrastructure — where a capability runs is
# the execution profile's concern (§6.5, phase 98.4). ``node`` is the one
# provisionable tool already registered (``check_registry.TOOL_NODE``, #306);
# ``python`` is the always-present base runtime (``py_compile``, pytest). This owns
# only the vocabulary the contract may declare and the linter validates ``requires``
# against — not the capability→environment mapping.
CAP_PYTHON = "python"
KNOWN_CAPABILITIES: frozenset[str] = frozenset({CAP_PYTHON, TOOL_NODE})

# Which typed checks may appear in each criterion class (§6.1 "criteria are classed").
# INTERFACE checks are style-free structural presence checks that pass on the frozen
# skeleton (the frozen decorators make ``endpoint_defined`` true pre-fill).
# IMPLEMENTATION checks measure the fill. ``regex_match`` is in NEITHER: it is
# document-only (#464) and fill files are source, so textual criteria against fill
# files are rejected by construction rather than by a runtime guard.
INTERFACE_CHECK_NAMES: frozenset[str] = frozenset(
    {"endpoint_defined", "import_present", "field_present"}
)
IMPLEMENTATION_CHECK_NAMES: frozenset[str] = frozenset({"command_exit_zero"})

# Keys owned by the criterion wrapper; everything else on a criterion mapping is a
# check param. (Contract criteria carry ``id``/``requires``; plan criteria carry
# ``severity``/``description`` — a distinct vocabulary, hence a distinct reserved set.)
_CRITERION_RESERVED: frozenset[str] = frozenset({"check", "id", "requires"})

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


def _path_is_safe_relative(value: object) -> bool:
    """True when ``value`` is a relative workspace path with no ``..`` traversal."""
    if not isinstance(value, str) or not value:
        return False
    if value.startswith("/"):
        return False
    parts = value.replace("\\", "/").split("/")
    return ".." not in parts


# --------------------------------------------------------------------------- #
# Schema (frozen dataclasses mirroring verification_contract.yaml)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Criterion:
    """A single typed criterion: a ``check`` name, a stable ``id``, its params, and
    an optional capability ``requires``. The target file, when the check needs one,
    is the parent ``fill_files`` key — not an inline param (unlike a plan TypedCheck)."""

    check: str
    id: str
    params: dict[str, Any] = field(default_factory=dict)
    requires: str | None = None

    @classmethod
    def from_dict(cls, raw: Any) -> Criterion:
        if not isinstance(raw, dict):
            raise ValueError(f"criterion must be a mapping, got {type(raw).__name__}")
        requires = raw.get("requires")
        return cls(
            check=str(raw.get("check", "")),
            id=str(raw.get("id", "")),
            params={k: v for k, v in raw.items() if k not in _CRITERION_RESERVED},
            requires=str(requires) if requires is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"check": self.check, "id": self.id, **self.params}
        if self.requires is not None:
            out["requires"] = self.requires
        return out


@dataclass(frozen=True)
class Probe:
    """A behavioral probe: boot the ``subject``, issue ``request``, assert ``expect``
    (§6.4). Declarative request/expect only — boot/retry/timeout are the execution
    profile's concern, so the same probe drives the qa container today and the
    sandbox later (§6.5)."""

    id: str
    subject: str
    request: dict[str, Any]
    expect: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: Any) -> Probe:
        if not isinstance(raw, dict):
            raise ValueError(f"probe must be a mapping, got {type(raw).__name__}")
        request = raw.get("request", {})
        expect = raw.get("expect", {})
        return cls(
            id=str(raw.get("id", "")),
            subject=str(raw.get("subject", "")),
            request=dict(request) if isinstance(request, dict) else {},
            expect=dict(expect) if isinstance(expect, dict) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "request": self.request,
            "expect": self.expect,
        }


@dataclass(frozen=True)
class FrozenFile:
    """A non-fill skeleton file pinned by content hash (§6.1 ``frozen``, P7)."""

    path: str
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256}


@dataclass(frozen=True)
class FillFile:
    """A fill slot with its interface and implementation criteria (§6.1)."""

    path: str
    interface: tuple[Criterion, ...] = ()
    implementation: tuple[Criterion, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "interface": [c.to_dict() for c in self.interface],
            "implementation": [c.to_dict() for c in self.implementation],
        }


@dataclass(frozen=True)
class Suite:
    """The test contract (§6.1 ``behavioral.suite``): behavioral checks plus the
    coverage expectations consumed by qa.test prompting (P6).

    Canonicalization note: SIP §6.1 sketches the ``tests_pass`` check and
    ``coverage_expectations`` adjacently under ``suite:``; that is not valid YAML (a
    sequence cannot carry a sibling mapping key). Phase 98.1 settles the schema:
    ``suite`` is a mapping ``{checks: [...], coverage_expectations: [...]}``."""

    checks: tuple[Criterion, ...] = ()
    coverage_expectations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [c.to_dict() for c in self.checks],
            "coverage_expectations": list(self.coverage_expectations),
        }


@dataclass(frozen=True)
class Behavioral:
    """Behavioral section: build checks, the suite, and probes (§6.1)."""

    build: tuple[Criterion, ...] = ()
    suite: Suite = field(default_factory=Suite)
    probes: tuple[Probe, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "build": [c.to_dict() for c in self.build],
            "suite": self.suite.to_dict(),
            "probes": [p.to_dict() for p in self.probes],
        }


@dataclass(frozen=True)
class Skeleton:
    """Binds the contract to the exact skeleton it was authored against (§6.1)."""

    expander: str
    interface_manifest_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "expander": self.expander,
            "interface_manifest_hash": self.interface_manifest_hash,
        }


@dataclass(frozen=True)
class VerificationContract:
    contract_version: int
    skeleton: Skeleton
    capabilities: tuple[str, ...]
    frozen_files: tuple[FrozenFile, ...]
    fill_files: tuple[FillFile, ...]
    behavioral: Behavioral

    # --- loading ---------------------------------------------------------- #

    @classmethod
    def from_yaml(cls, content: str) -> VerificationContract:
        """Parse a ``verification_contract.yaml`` string. Raises ``ValueError`` on
        YAML-syntax errors or a non-mapping root (the "malformed" class); semantic
        defects are reported by ``lint()``, never raised."""
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:  # noqa: BLE001 — normalize to a single loader-error type
            raise ValueError(f"verification contract is not valid YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("verification contract must be a mapping at the top level")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationContract:
        if not isinstance(data, dict):
            raise ValueError(f"verification contract must be a mapping, got {type(data).__name__}")

        version = data.get("contract_version", 0)

        skel_raw = data.get("skeleton", {})
        if not isinstance(skel_raw, dict):
            raise ValueError("'skeleton' must be a mapping")
        skeleton = Skeleton(
            expander=str(skel_raw.get("expander", "")),
            interface_manifest_hash=str(skel_raw.get("interface_manifest_hash", "")),
        )

        caps_raw = data.get("capabilities", [])
        if not isinstance(caps_raw, list):
            raise ValueError("'capabilities' must be a list")
        capabilities = tuple(str(c) for c in caps_raw)

        frozen_raw = data.get("frozen", [])
        if not isinstance(frozen_raw, list):
            raise ValueError("'frozen' must be a list")
        frozen_files = tuple(_frozen_file_from(entry) for entry in frozen_raw)

        fill_raw = data.get("fill_files", {})
        if not isinstance(fill_raw, dict):
            raise ValueError("'fill_files' must be a mapping of path -> criteria")
        fill_files = tuple(_fill_file_from(path, spec) for path, spec in fill_raw.items())

        behavioral = _behavioral_from(data.get("behavioral", {}))

        return cls(
            contract_version=version if isinstance(version, int) else 0,
            skeleton=skeleton,
            capabilities=capabilities,
            frozen_files=frozen_files,
            fill_files=fill_files,
            behavioral=behavioral,
        )

    # --- serialization / identity ---------------------------------------- #

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "skeleton": self.skeleton.to_dict(),
            "capabilities": list(self.capabilities),
            "frozen": [f.to_dict() for f in self.frozen_files],
            "fill_files": {ff.path: ff.to_dict() for ff in self.fill_files},
            "behavioral": self.behavioral.to_dict(),
        }

    def content_hash(self) -> str:
        """Stable sha256 over the canonical contract content. Recorded in each
        consuming run's resolved config (provenance, P3) and frozen for the yield
        baseline (§6.3). Independent of source key order and whitespace."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # --- iteration -------------------------------------------------------- #

    def all_criteria(self) -> tuple[Criterion, ...]:
        """Every typed criterion across all sections (not probes)."""
        out: list[Criterion] = []
        for ff in self.fill_files:
            out.extend(ff.interface)
            out.extend(ff.implementation)
        out.extend(self.behavioral.build)
        out.extend(self.behavioral.suite.checks)
        return tuple(out)

    def criterion_ids(self) -> tuple[str, ...]:
        """Every stable id in the contract — criteria and probes — in document
        order. Downstream (98.3) resolves ``criteria_refs`` against this."""
        ids = [c.id for c in self.all_criteria()]
        ids.extend(p.id for p in self.behavioral.probes)
        return tuple(ids)

    # --- binding (98.3) --------------------------------------------------- #

    def criterion_index(self) -> dict[str, tuple[Criterion, str]]:
        """Map every typed criterion's stable id to ``(criterion, owning_fill_path)``.

        The owning path is the ``fill_files`` key a file-targeting check applies to
        (empty for behavioral ``build``/``suite`` checks, which are file-less). This
        is the resolution table for plan ``criteria_refs`` — bind validation looks up
        refs here, and dispatch enrichment (98.3 slice D) rebuilds each ref into a
        ``TypedCheck`` stamped with the criterion id, targeting the owning path.

        Probes are excluded: they are not ``TypedCheck``s and run via the probe
        runner (98.4), not the ``criteria_refs`` seam. On a well-linted contract ids
        are unique; if a duplicate slips through, last-writer wins (the linter is the
        gate that prevents it, `lint()._lint_ids`)."""
        index: dict[str, tuple[Criterion, str]] = {}
        for ff in self.fill_files:
            for crit in (*ff.interface, *ff.implementation):
                index[crit.id] = (crit, ff.path)
        for crit in (*self.behavioral.build, *self.behavioral.suite.checks):
            index[crit.id] = (crit, "")
        return index

    def covered_fill_paths(self) -> frozenset[str]:
        """The set of fill-file paths this contract owns the acceptance of. A plan
        task whose ``expected_artifacts`` names one of these must bind that file's
        criteria by ref rather than author its own typed checks (§6.3)."""
        return frozenset(ff.path for ff in self.fill_files)

    def required_ref_ids_for(self, path: str) -> tuple[str, ...]:
        """Every ``interface`` + ``implementation`` criterion id for the fill file at
        ``path``, in document order. A bind-mode plan task producing this file must
        carry all of them — descoping verification is the #439 lesson at the criteria
        level (§6.3). Unknown path ⇒ empty (the file is not contract-covered)."""
        for ff in self.fill_files:
            if ff.path == path:
                return tuple(c.id for c in (*ff.interface, *ff.implementation))
        return ()

    def criteria_index_lines(self) -> list[str]:
        """A human-readable per-covered-file index for the *bind, don't author*
        proposer prompt (§6.3): one line per fill file naming the exact criterion ids
        the proposing task must list in ``criteria_refs``. Files with no per-file typed
        criteria (e.g. JSX views, covered by the behavioral build) are still listed so
        the proposer knows they are contract-owned and must not author their own checks.

        This is a rendering of contract *data* — the ``bind, don't author`` instruction
        prose lives in the managed proposer prompt asset (CLAUDE.md #448), which takes
        these lines as a variable."""
        lines: list[str] = []
        for ff in self.fill_files:
            ids = [c.id for c in (*ff.interface, *ff.implementation)]
            if ids:
                pairs = ", ".join(
                    f"{c.id} ({c.check})" for c in (*ff.interface, *ff.implementation)
                )
                lines.append(f"- {ff.path}: bind {pairs}")
            else:
                lines.append(
                    f"- {ff.path}: contract-owned (no per-file typed criteria); "
                    f"do not author your own for this file"
                )
        return lines

    # --- linting ---------------------------------------------------------- #

    def lint(self) -> list[str]:
        """Return every schema-level defect (§6.2 job 1). Empty list ⇒ the contract
        is well-formed enough to bind; empirical winnability (bare-skeleton +
        reference-fill runs) is phase 98.2's separate, empirical gate."""
        errors: list[str] = []
        self._lint_top_level(errors)
        self._lint_ids(errors)
        self._lint_capabilities(errors)
        self._lint_frozen(errors)
        self._lint_fill_files(errors)
        self._lint_behavioral(errors)
        self._lint_probes(errors)
        return errors

    def _lint_top_level(self, errors: list[str]) -> None:
        if self.contract_version != CONTRACT_VERSION:
            errors.append(
                f"contract_version must be {CONTRACT_VERSION}, got {self.contract_version!r}"
            )
        if not self.skeleton.expander:
            errors.append("skeleton.expander is required")
        # P3/§6.1: the contract must bind to the exact skeleton it verifies.
        if not self.skeleton.interface_manifest_hash:
            errors.append("skeleton.interface_manifest_hash is required (binds the contract)")
        elif not _is_sha256(self.skeleton.interface_manifest_hash):
            errors.append(
                "skeleton.interface_manifest_hash must be a 64-char sha256 hex digest "
                f"(got {self.skeleton.interface_manifest_hash!r})"
            )
        if not self.fill_files:
            errors.append("fill_files is empty — a contract must cover at least one fill file")

    def _lint_ids(self, errors: list[str]) -> None:
        seen: set[str] = set()
        dupes: set[str] = set()
        empty = 0
        for cid in self.criterion_ids():
            if not cid:
                empty += 1
                continue
            if cid in seen:
                dupes.add(cid)
            seen.add(cid)
        if empty:
            errors.append(f"{empty} criterion/probe(s) missing a stable id")
        for cid in sorted(dupes):
            errors.append(
                f"duplicate criterion id {cid!r} — ids must be unique across the contract"
            )

    def _lint_capabilities(self, errors: list[str]) -> None:
        for cap in self.capabilities:
            if cap not in KNOWN_CAPABILITIES:
                errors.append(
                    f"capabilities declares unknown capability {cap!r} "
                    f"(known: {', '.join(sorted(KNOWN_CAPABILITIES))})"
                )
        declared = set(self.capabilities)
        for label, crit in self._labelled_criteria():
            if crit.requires is None:
                continue
            if crit.requires not in KNOWN_CAPABILITIES:
                errors.append(
                    f"{label}: requires unknown capability {crit.requires!r} "
                    f"(known: {', '.join(sorted(KNOWN_CAPABILITIES))})"
                )
            elif crit.requires not in declared:
                errors.append(
                    f"{label}: requires {crit.requires!r} but it is not declared in "
                    f"the top-level capabilities list"
                )

    def _lint_frozen(self, errors: list[str]) -> None:
        for f in self.frozen_files:
            if not _path_is_safe_relative(f.path):
                errors.append(f"frozen: {f.path!r} must be a relative path with no '..' traversal")
            if not _is_sha256(f.sha256):
                errors.append(f"frozen[{f.path}]: sha256 must be a 64-char hex digest")

    def _lint_fill_files(self, errors: list[str]) -> None:
        for ff in self.fill_files:
            if not _path_is_safe_relative(ff.path):
                errors.append(
                    f"fill_files: {ff.path!r} must be a relative path with no '..' traversal"
                )
            for crit in ff.interface:
                self._lint_typed_criterion(
                    errors,
                    f"fill_files[{ff.path}].interface[{crit.id or '?'}]",
                    crit,
                    INTERFACE_CHECK_NAMES,
                    "interface",
                    implied_file=ff.path,
                )
            for crit in ff.implementation:
                self._lint_typed_criterion(
                    errors,
                    f"fill_files[{ff.path}].implementation[{crit.id or '?'}]",
                    crit,
                    IMPLEMENTATION_CHECK_NAMES,
                    "implementation",
                    implied_file=ff.path,
                )

    def _lint_typed_criterion(
        self,
        errors: list[str],
        label: str,
        crit: Criterion,
        allowed_for_class: frozenset[str],
        class_name: str,
        *,
        implied_file: str,
    ) -> None:
        if not crit.check:
            errors.append(f"{label}: missing 'check'")
            return
        if crit.check not in CHECK_SPECS:
            errors.append(
                f"{label}: unknown check {crit.check!r} (known: {', '.join(sorted(CHECK_SPECS))})"
            )
            return
        if crit.check not in allowed_for_class:
            errors.append(
                f"{label}: check {crit.check!r} is not allowed in the {class_name} class "
                f"(allowed: {', '.join(sorted(allowed_for_class))})"
            )
            # keep validating params — the message above is the actionable one

        spec = CHECK_SPECS[crit.check]
        # The target file, when the check needs one, is the fill_files key.
        effective = dict(crit.params)
        if "file" in spec.required_params or "file" in spec.path_params:
            effective.setdefault("file", implied_file)

        missing = spec.required_params - set(effective)
        if missing:
            errors.append(f"{label}: missing required param(s): {', '.join(sorted(missing))}")
        allowed_params = spec.required_params | spec.optional_params
        unknown = set(effective) - allowed_params
        if unknown:
            errors.append(
                f"{label}: unknown param(s): {', '.join(sorted(unknown))} "
                f"(allowed: {', '.join(sorted(allowed_params))})"
            )

        for key, value in effective.items():
            expected = spec.param_types.get(key)
            if expected is not None and not isinstance(value, expected):
                names = (
                    expected.__name__
                    if isinstance(expected, type)
                    else " | ".join(t.__name__ for t in expected)
                )
                errors.append(f"{label}: param {key!r} must be {names}, got {type(value).__name__}")

        self._lint_regex_and_command(errors, label, crit)

    def _lint_regex_and_command(self, errors: list[str], label: str, crit: Criterion) -> None:
        # regexes must compile, and regex_match may only target documents (#464).
        if "pattern" in crit.params:
            pattern = crit.params["pattern"]
            if isinstance(pattern, str):
                try:
                    re.compile(pattern)
                except re.error as exc:
                    errors.append(f"{label}: pattern does not compile: {exc}")
        if crit.check == "regex_match":
            target = crit.params.get("file", "")
            if not regex_target_is_document(target):
                errors.append(
                    f"{label}: regex_match may only target document artifacts "
                    f"(.md/.txt/.rst), not source file {target!r} (#464)"
                )
        # command_exit_zero argv must be safelisted string argv (#422/RC-10a).
        if crit.check == "command_exit_zero":
            argv = crit.params.get("argv")
            if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
                errors.append(f"{label}: command_exit_zero argv must be a list of strings")
            elif not argv_matches_safelist(argv):
                errors.append(
                    f"{label}: command {argv!r} is not in the execution safelist and can "
                    f"never run. Use one of: {'; '.join(command_safelist_names())}"
                )

    def _lint_behavioral(self, errors: list[str]) -> None:
        known = framework_check_ids()
        for crit in (*self.behavioral.build, *self.behavioral.suite.checks):
            if not crit.check:
                errors.append(f"behavioral[{crit.id or '?'}]: missing 'check'")
            elif crit.check not in known:
                errors.append(
                    f"behavioral[{crit.id or '?'}]: unknown framework check {crit.check!r} "
                    f"(known: {', '.join(sorted(known))})"
                )

    def _lint_probes(self, errors: list[str]) -> None:
        for probe in self.behavioral.probes:
            label = f"probe[{probe.id or '?'}]"
            if not probe.subject:
                errors.append(f"{label}: missing 'subject'")
            if "method" not in probe.request or "path" not in probe.request:
                errors.append(f"{label}: request must declare 'method' and 'path'")
            if "status" not in probe.expect:
                errors.append(f"{label}: expect must declare a 'status'")

    def _labelled_criteria(self) -> list[tuple[str, Criterion]]:
        out: list[tuple[str, Criterion]] = []
        for ff in self.fill_files:
            for crit in ff.interface:
                out.append((f"fill_files[{ff.path}].interface[{crit.id or '?'}]", crit))
            for crit in ff.implementation:
                out.append((f"fill_files[{ff.path}].implementation[{crit.id or '?'}]", crit))
        for crit in self.behavioral.build:
            out.append((f"behavioral.build[{crit.id or '?'}]", crit))
        for crit in self.behavioral.suite.checks:
            out.append((f"behavioral.suite[{crit.id or '?'}]", crit))
        return out


# --------------------------------------------------------------------------- #
# Section parsers (module-private; keep from_dict readable)
# --------------------------------------------------------------------------- #


def _frozen_file_from(entry: Any) -> FrozenFile:
    if not isinstance(entry, dict):
        raise ValueError(f"each 'frozen' entry must be a mapping, got {type(entry).__name__}")
    return FrozenFile(path=str(entry.get("path", "")), sha256=str(entry.get("sha256", "")))


def _fill_file_from(path: Any, spec: Any) -> FillFile:
    if not isinstance(spec, dict):
        raise ValueError(f"fill_files[{path!r}] must be a mapping of class -> criteria")
    interface_raw = spec.get("interface", [])
    implementation_raw = spec.get("implementation", [])
    if not isinstance(interface_raw, list) or not isinstance(implementation_raw, list):
        raise ValueError(f"fill_files[{path!r}]: interface/implementation must be lists")
    return FillFile(
        path=str(path),
        interface=tuple(Criterion.from_dict(c) for c in interface_raw),
        implementation=tuple(Criterion.from_dict(c) for c in implementation_raw),
    )


def _behavioral_from(raw: Any) -> Behavioral:
    if not isinstance(raw, dict):
        raise ValueError("'behavioral' must be a mapping")
    build_raw = raw.get("build", [])
    if not isinstance(build_raw, list):
        raise ValueError("behavioral.build must be a list")

    suite_raw = raw.get("suite", {})
    if not isinstance(suite_raw, dict):
        raise ValueError("behavioral.suite must be a mapping (checks + coverage_expectations)")
    checks_raw = suite_raw.get("checks", [])
    coverage_raw = suite_raw.get("coverage_expectations", [])
    if not isinstance(checks_raw, list) or not isinstance(coverage_raw, list):
        raise ValueError("behavioral.suite.checks and coverage_expectations must be lists")

    probes_raw = raw.get("probes", [])
    if not isinstance(probes_raw, list):
        raise ValueError("behavioral.probes must be a list")

    return Behavioral(
        build=tuple(Criterion.from_dict(c) for c in build_raw),
        suite=Suite(
            checks=tuple(Criterion.from_dict(c) for c in checks_raw),
            coverage_expectations=tuple(str(x) for x in coverage_raw),
        ),
        probes=tuple(Probe.from_dict(p) for p in probes_raw),
    )
