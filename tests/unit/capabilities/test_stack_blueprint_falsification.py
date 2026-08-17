"""2c — the falsification pass, as a standing gate.

S3's exit criterion, stated by the plan: *"For each blueprint field, remove or corrupt it and
confirm something breaks in at least one stack. A field whose removal breaks nothing is
decorative — it is describing a fact no consumer reads, and it should be deleted before the
schema is frozen rather than after it has accreted meaning."*

**Why executable, and derived.** Same reasoning as 2a (`test_stack_inventory`). A read-and-
classify pass fails the way reading fails: 1a bounded four items and overclaimed three times.
This enumerates the fields by reflecting over the live declarations, so it cannot skip one —
and a NEW field with no consumer fails here rather than entering the schema unnoticed.

**The outcomes**, and why the distinction is the substance:

- ``RAISES`` / ``CHANGES`` — corrupting the field makes a real offline path throw, or moves
  derived output. Falsified.
- ``ALREADY_EMPTY`` — the field is unset *on this stack*, so emptying it is a no-op. This is
  not evidence of anything, and reporting it as "no effect" would manufacture a decorative
  finding out of a no-op. Each such field must be unset for a **recorded reason** and be
  populated by some other stack, or it falls to the last bucket.
- ``RUNTIME_WITNESS`` — no offline consumer reacts, but a named production reader exists and
  is exercised by its own test below. `check_stack` is the case: four typed-check evaluators
  skip when it is wrong or unset, which SIP-0096 surfaces as unverified rather than verified.
- ``UNEVIDENCED`` — a real reader exists and **no declaration anywhere supplies data**. Not
  decorative in the "nothing reads it" sense, and worse in the sense that matters: it asserts
  per-stack variability that zero stacks demonstrate. Under S5's admission rule read
  subtractively — the same reading the schema draft applies to Tier 3 — it must not be a
  blueprint field.

**This file is also where S5's admission rule is ENFORCED (Stage 2f).** S5 states it as
*"a new blueprint field must be demonstrated on at least two stacks before admission"*, with
the consequence that *"a one-stack need is expressed as a declared optional capability with its
reason"*. That is exactly the classification below, and it is enforced rather than asked for:

- populated on both stacks → falsified on each → admitted;
- populated on **one** stack → ``ALREADY_EMPTY`` on the other → fails until a reason is
  recorded in ``_DECLARED_OPTIONAL``, and ``test_a_declared_optional_is_populated_by_some_stack``
  additionally requires that some stack does populate it;
- populated on **no** stack → rejected. An optional capability nothing populates is not
  optional, it is unevidenced;
- read by nothing → rejected outright.

Recorded here because *what a test enforces stays true; what discipline enforces drifts*
(``test_docs_version_sync``'s own rationale). S5's rule was written only in
``1-6-0-authorship-plan.md``, and a release plan is superseded at the cut — the failure mode
CLAUDE.md names and SIP-0103 §5d paid for. The rule's permanent *statement* still belongs in
the Stack Blueprint SIP at 2g; its permanent *enforcement* is here.

**Four traps this harness had, recorded because each one CHANGED THE ANSWER and the next
author will hit them.** None is hypothetical; every one produced a wrong finding first:

1. *Corrupting an already-empty value.* Emptying `()` to `()` proves nothing. The first run
   reported six decorative candidates, five of which were this.
2. *`name` fields are registry keys.* Patching the stored copy changes no lookup unless the
   observation resolves the key **through the declaration**, which `_REGISTRIES` now does.
3. *Observing the declarations themselves.* The battery serialised each dataclass's own
   fields, so any change trivially "differed" — the pass reported 98 of 104 fields falsified
   and a deliberately decorative probe field passed. **Observe what consumers derive, never
   the declaration.** The negative control at the bottom exists because this got past me.
4. *Attribute-only reader search.* `getattr(cap, "build_support_files", ())` is a read an
   `ast.Attribute` walk cannot see, and that live field was reported decorative because of it.

The honest result after all four: **101 of 107 field-checks falsify, three fields have no
consumer of any kind, and one has a consumer no stack feeds.** The first number was 98 and
was wrong.
"""

from __future__ import annotations

import dataclasses as dc
import json
import pathlib
from contextlib import contextmanager

import pytest

from squadops.capabilities import dev_capabilities, scaffold, scaffold_contract
from squadops.capabilities import verification_scaffold_emission as vse
from squadops.capabilities.handlers import build_profiles, probe_runner
from squadops.sandbox import environment
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_STACKS = ("fullstack_fastapi_react", "nextjs_ts")

#: registry label -> (mapping, key resolved FROM the declaration). Resolving through the
#: declaration rather than the loop variable is what makes a `name` field load-bearing.
_REGISTRIES = {
    "ScaffoldStack": (scaffold._STACKS, lambda s: s.name),
    "DevelopmentCapability": (dev_capabilities.DEV_CAPABILITIES, lambda s: s.dev_capability),
    "EnvironmentContract": (environment._CONTRACTS, lambda s: s.name),
    "BuildProfile": (build_profiles.BUILD_PROFILES, lambda s: s.name),
    "probe profile": (probe_runner._PROFILES, lambda s: s.probe_profile),
    "criteria pack": (scaffold_contract._CRITERIA_PACKS, lambda s: s.criteria_pack),
}

#: Fields with no offline consumer, each carrying the production reader that DOES read it and
#: the test below that exercises it. An entry here is a claim, not an exemption.
_RUNTIME_WITNESS = {
    ("ScaffoldStack", "check_stack"): (
        "acceptance_evaluation.resolve_check_stack -> the typed-check evaluators; "
        "test_check_stack_is_falsified_at_the_acceptance_layer"
    ),
}

#: Fields unset on a stack for a recorded reason. Each MUST be populated by another stack —
#: a field empty everywhere is unevidenced, not optional.
_DECLARED_OPTIONAL = {
    ("ScaffoldStack", "harness_entry_modules"): "Node has no test/app import boundary to forbid",
    ("probe profile", "prepare_argv"): "uvicorn needs no build step before boot",
}

#: Populated by the run itself: fields whose only consumer is a runtime path, with the reads
#: the AST search found. Reported by the summary test so the set is visible rather than
#: implicit — the honest statement of what this pass does and does not exercise.
_RUNTIME_ONLY_OBSERVED: dict[tuple[str, str], list[str]] = {}

#: 2c's product: fields with NO consumer of any kind, found by this pass on 2026-08-17.
#:
#: Recorded rather than deleted here because deletion is a code change with its own review,
#: and the plan assigns it to "before the schema is frozen" — i.e. before 2g. The entries stay
#: pinned so a later reader cannot promote one into the blueprint on the strength of its
#: existing, and `test_the_decorative_fields_are_still_unread` fails if one gains a consumer,
#: which is the signal to remove it from this list rather than leave a stale exemption.
_DECORATIVE_FOUND = {
    ("BuildProfile", "artifact_output_mode"): (
        "declared on all five build profiles, zero reads. The schema draft hoists it into "
        "Tier 3 as core-owned — a default for a fact nothing consults"
    ),
    ("BuildProfile", "validation_rules"): (
        "populated with real content on every profile, zero reads. The schema draft lists it "
        "in Tier 1 as packaging.validation_rules, 'demonstrated'"
    ),
    ("DevelopmentCapability", "expected_extensions"): (
        "populated per stack, zero reads — and TWO docstrings assert it is 'what a dev agent "
        "is given' (scaffold.py:1899, preflight.py:216). Documented as read, read by nothing. "
        "The schema draft lists it in Tier 1 as authored_extensions, 'demonstrated'"
    ),
}

#: A real reader, and no declaration anywhere supplies data. See the module docstring.
_UNEVIDENCED = {
    ("BuildProfile", "default_task_tags"): (
        "builder._resolve_task_tags merges it with experiment_context, which supplies every "
        "tag in practice; empty on all five build profiles"
    ),
}


def _corrupt(value):
    """A same-shaped wrong value, or None when the shape cannot be corrupted generically."""
    if dc.is_dataclass(value) and not isinstance(value, type):
        edits = {
            f.name: "__corrupted__"
            for f in dc.fields(value)
            if isinstance(getattr(value, f.name), str)
        }
        return dc.replace(value, **edits) if edits else None
    if callable(value) and not isinstance(value, type):
        return lambda *a, **k: (_ for _ in ()).throw(AssertionError("corrupted callable"))
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return "__corrupted__"
    if isinstance(value, int):
        return value + 9999
    if isinstance(value, float):
        return value + 9999.0
    if isinstance(value, tuple):
        return ()
    if isinstance(value, frozenset):
        return frozenset()
    if isinstance(value, dict):
        return {}
    return "__corrupted__" if value is None else None


@contextmanager
def _patched(mapping, key, field, value):
    original = mapping[key]
    mapping[key] = dc.replace(original, **{field: value})
    try:
        yield
    finally:
        mapping[key] = original


def _observe(stack_name: str) -> dict[str, str]:
    """Every artifact derivable offline from a stack's declarations."""
    manifest = manifest_for_stack(stack_name)
    stack = scaffold._STACKS[stack_name]
    out = {
        "expand": json.dumps(
            [{"n": f["name"], "c": f["content"]} for f in scaffold.expand(manifest)],
            sort_keys=True,
        ),
        "fill_slots": json.dumps(sorted(scaffold.fill_slot_paths(manifest))),
        "contract": json.dumps(scaffold_contract.emit_contract_dict(manifest), sort_keys=True),
        "frozen_index": json.dumps(sorted(scaffold.frozen_surface_index_lines(manifest))),
        "qa_namespace": json.dumps(sorted(scaffold.qa_test_namespace(manifest))),
        "error_seam_prose": json.dumps(scaffold.error_seam_instructions(manifest)),
        "harness_entry": json.dumps(list(scaffold.harness_entry_modules(stack.name))),
        "pack_name": scaffold_contract._CRITERIA_PACKS[stack.criteria_pack].name,
    }
    # Consumers' OUTPUT, never the declarations themselves. A first version of this battery
    # serialised each declaration's own fields, which made the pass nearly vacuous: any field
    # change trivially "differed", so a deliberately decorative probe field was reported as
    # falsified. Observing the declaration is circular — it proves the field changed, not that
    # anything reads it. The negative control below exists because that got past me once.
    from squadops.capabilities.handlers.cycle.builder import BuilderAssembleHandler

    capability = dev_capabilities.get_capability(stack.dev_capability)
    out["capability_test_matching"] = json.dumps(
        {
            name: dev_capabilities.matches_test_file_patterns(name, capability.name)
            for name in ("a.test.ts", "test_a.py", "a.spec.tsx", "a_test.py", "a.ts", "a.py")
        },
        sort_keys=True,
    )
    profile = build_profiles.get_profile(stack.name)
    out["builder_task_tags"] = json.dumps(
        BuilderAssembleHandler._resolve_task_tags(profile, {"experiment_context": {}}),
        sort_keys=True,
    )
    out["probe_boot_plan"] = json.dumps(
        [str(part) for part in probe_runner.profile_for_stack(stack.name).boot_argv],
    )
    if scaffold.verification_scaffold_for(stack_name):
        emission = vse.emit_verification_scaffold(manifest)
        out["scaffold"] = (
            emission.manifest.scaffold_hash() + emission.manifest.aggregate_spine_hash()
        )
    return out


_SRC_ROOTS = ("src/squadops", "adapters", "scripts")


def _reader_citations(field: str) -> list[str]:
    """Every production read of ``.<field>`` anywhere in the tree.

    AST rather than grep: an attribute access is a read, a string containing the name is not,
    and 2c's whole job is to distinguish "something consumes this" from "the name appears".
    Searched mechanically so a new field's witness cannot be asserted by hand — the citation
    either exists in the tree or the field is decorative.

    **No module is excluded, and an earlier version excluding the declaring one was wrong.**
    The intent was to avoid counting the field's own declaration as a read, but a dataclass
    field is an ``AnnAssign`` and a registry literal passes it as a keyword — neither is an
    ``Attribute`` node, so the exclusion protected against nothing while hiding every consumer
    that lives beside its declaration. The probe runner reads its own profile; excluding
    ``probe_runner.py`` reported four of its live fields as decorative.
    """
    import ast

    citations: list[str] = []
    for root in _SRC_ROOTS:
        for path in pathlib.Path(root).rglob("*.py"):
            rel = str(path)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                # An attribute access...
                if isinstance(node, ast.Attribute) and node.attr == field:
                    citations.append(f"{rel}:{node.lineno}")
                    break
                # ...or a string-keyed getattr, which is equally a read and which an
                # attribute-only search misses. `qa_test.py` reads `build_support_files`
                # exactly this way, and an earlier version of this pass reported that live
                # field as decorative because of it.
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == field
                ):
                    citations.append(f"{rel}:{node.lineno} (getattr)")
                    break
    return citations


def _all_field_checks() -> list[tuple[str, str, str]]:
    """``(registry, stack, field)`` for every declared field. Derived, so it cannot skip."""
    checks = []
    for label, (mapping, resolve) in _REGISTRIES.items():
        for stack_name in _STACKS:
            key = resolve(scaffold._STACKS[stack_name])
            if key in mapping:
                checks += [(label, stack_name, f.name) for f in dc.fields(mapping[key])]
    return checks


def _classify(registry: str, stack_name: str, field: str, baseline: dict) -> str:
    mapping, resolve = _REGISTRIES[registry]
    key = resolve(scaffold._STACKS[stack_name])
    value = getattr(mapping[key], field)
    corrupted = _corrupt(value)
    if corrupted == value:
        return "ALREADY_EMPTY"
    with _patched(mapping, key, field, corrupted):
        for probe_stack in _STACKS:
            try:
                after = _observe(probe_stack)
            except Exception:  # noqa: BLE001 - any raise is a falsification
                return "RAISES"
            if any(after[k] != baseline[probe_stack].get(k) for k in after):
                return "CHANGES"
    return "NO_OFFLINE_EFFECT"


@pytest.fixture(scope="module")
def baseline() -> dict:
    return {s: _observe(s) for s in _STACKS}


@pytest.mark.parametrize(("registry", "stack", "field"), _all_field_checks())
def test_every_declared_field_is_accounted_for(registry, stack, field, baseline):
    """The gate. A field that changes nothing, has no named runtime witness, and is not a
    recorded optional is decorative — and this is where that gets caught, at the moment it
    is added rather than after the schema has frozen around it."""
    outcome = _classify(registry, stack, field, baseline)
    if outcome in ("RAISES", "CHANGES"):
        return
    ref = (registry, field)
    if outcome == "ALREADY_EMPTY":
        assert ref in _DECLARED_OPTIONAL or ref in _UNEVIDENCED, (
            f"{registry}.{field} is unset on {stack} with no recorded reason. Either record "
            f"why it is optional (and confirm another stack populates it), or delete it."
        )
        return

    # No offline consumer reacted. The field is falsifiable only at runtime, which is still a
    # falsification — provided a reader exists. Searched, never asserted: a hand-maintained
    # witness list is a claim the next author inherits without evidence.
    citations = _reader_citations(field)
    if not citations and ref in _DECORATIVE_FOUND:
        return  # already found and recorded by this pass; see _DECORATIVE_FOUND
    assert citations, (
        f"{registry}.{field} survives corruption of both stacks with NO offline consumer and "
        f"NO production read of `.{field}` anywhere in {list(_SRC_ROOTS)}. Per S3's exit "
        f"criterion that is decorative — it describes a fact nothing reads. Delete it before "
        f"the schema freezes, or wire the consumer that justifies it."
    )
    if ref in _RUNTIME_WITNESS:
        return
    # A reader exists but nothing in this file exercises it. Recorded rather than failed: the
    # citation is real evidence, and demanding a bespoke test per field would make this pass
    # unaffordable and therefore unrun. The gap is what _RUNTIME_WITNESS closes over time.
    _RUNTIME_ONLY_OBSERVED.setdefault(ref, citations[:3])


def test_a_declared_optional_is_populated_by_some_stack():
    """An 'optional capability' no stack populates is not optional, it is unevidenced — the
    distinction `default_task_tags` fails and the other two pass."""
    for (registry, field), reason in _DECLARED_OPTIONAL.items():
        mapping, resolve = _REGISTRIES[registry]
        populated = [s for s in _STACKS if getattr(mapping[resolve(scaffold._STACKS[s])], field)]
        assert populated, (
            f"{registry}.{field} is empty on every stack, yet recorded as optional: {reason}"
        )


def test_the_unevidenced_fields_are_still_unevidenced():
    """Pinned so this cannot be quietly resolved by promotion instead of by evidence.

    `default_task_tags` is `{}` on all five build profiles and its reader merges it with
    `experiment_context`, which supplies every tag in practice. If a stack ever populates it,
    this test fails and the field graduates — on evidence, which is the whole point of S5's
    admission rule. Until then it must not enter the blueprint.
    """
    assert all(not p.default_task_tags for p in build_profiles.BUILD_PROFILES.values()), (
        "a build profile now populates default_task_tags — the field is evidenced, so move it "
        "out of _UNEVIDENCED and into the blueprint schema deliberately"
    )


def test_check_stack_is_falsified_at_the_acceptance_layer():
    """`check_stack`'s witness, and the reason this file does not simply trust the schema
    draft's claim that "unset = checks skip".

    Measured, because a first attempt at this used `undefined_names`, which ignores `stack`
    entirely and returns the same verdict for the declared value, a corrupted one and None.
    Four evaluators DO read it — `endpoint_defined`, `field_present`, `function_defined`,
    `harness_boundary` — and picking the wrong one nearly produced a false decorative finding.
    """
    import asyncio
    import pathlib
    import tempfile

    from squadops.cycles.acceptance_checks import get_check
    from squadops.cycles.acceptance_evaluation import resolve_check_stack

    check = get_check("endpoint_defined")
    params = {"file": "routes.py", "methods_paths": ["GET /runs"]}
    with tempfile.TemporaryDirectory() as tmp:
        pathlib.Path(tmp, "routes.py").write_text(
            "from fastapi import APIRouter\nrouter = APIRouter()\n\n"
            "@router.get('/runs')\ndef list_runs():\n    return []\n"
        )
        root = pathlib.Path(tmp)
        declared = resolve_check_stack({"build_profile": "fullstack_fastapi_react"})
        assert declared == "fastapi"

        passes = asyncio.run(check.evaluate(params, root, stack=declared))
        assert passes.status == "passed"

        for wrong in ("__corrupted__", None):
            skipped = asyncio.run(check.evaluate(params, root, stack=wrong))
            assert skipped.status == "skipped", (
                f"stack={wrong!r} must not be credited as verified — SIP-0096 counts a skip "
                f"as unverified, and crediting it would be the false-green class"
            )
            assert skipped.reason == "unsupported_stack_or_syntax"


def test_the_decorative_fields_are_still_unread():
    """The recorded findings cannot become a stale exemption list.

    If one of these gains a consumer, this fails — and the fix is to delete the entry, not to
    keep an exemption for a field that is now load-bearing. An allowlist nobody re-checks is
    how a decorative field survives the freeze it was supposed to be deleted before.
    """
    for (registry, field), why in _DECORATIVE_FOUND.items():
        citations = _reader_citations(field)
        assert not citations, (
            f"{registry}.{field} is now read at {citations[:3]} — it is no longer decorative. "
            f"Remove it from _DECORATIVE_FOUND. Recorded reason was: {why}"
        )


def test_the_pass_reports_what_it_did_not_exercise(baseline):
    """2c's honest coverage statement, and the reason it is a test rather than a comment.

    Fields whose only consumer is a runtime path are falsified by that consumer, not by this
    pass. Saying so out loud is the difference between "every field is falsified" and "every
    field is either falsified here or has a reader I can cite" — and only the second is true.
    """
    for registry, stack, field in _all_field_checks():
        _classify(registry, stack, field, baseline)
    runtime_only = sorted(f"{r}.{f}" for (r, f) in _RUNTIME_ONLY_OBSERVED)
    # Not a threshold — a disclosure. It fails only if the set becomes empty, which would mean
    # the classification silently stopped distinguishing offline from runtime falsification.
    assert runtime_only, (
        "no field classified as runtime-only, which is implausible for a system whose "
        "declarations drive boot, sandboxing and prompts — the classifier has probably "
        "regressed into absorbing everything as CHANGES, which is how this pass was vacuous "
        "on its first run"
    )
