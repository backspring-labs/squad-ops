"""The two deterministic gates an authored manifest passes (#781 M3, #783 M2).

Both are pure predicates over a manifest, so they live together and share one finding
type: :func:`assess_schema` (M2 — is the document well-formed and does it carry its
provenance?) and :func:`assess_winnability` (M3 — can what it describes actually be
built and verified?). The authoring loop runs schema first: a document that has not
declared where its design came from is not worth asking harder questions of.

Can this interface manifest actually be won? (#781, M3)

A manifest that *parses* is not a manifest that can be *satisfied*. It can name a route
the expander cannot place, promise a view with no DOM anchor to query, or imply a
contract holding a check that is dead on arrival — and each of those costs a full
implementation workload to discover.

This module answers the question deterministically, before anything downstream spends
on it. **Closed-surface proofs only** (SIP-0103 §5b Q2): every finding is mechanical
and reproducible. Whether the design actually *satisfies the PRD* is judgment, and it
stays with the ``decisions[].warrant`` discipline and the human review gate.

Pure by construction — manifest text in, findings out. No vault, no cycle, no deploy —
so the gate is provable against adversarial manifests long before an authoring stage
exists to produce one.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Stable finding classes. Typed rather than free text so M6's authoring failure
#: taxonomy can attribute a rejection without parsing prose — the "one vocabulary, not
#: three" intention from the post-1.5 reconciliation, applied before there is anything
#: to reconcile.
PROOF_PARSES = "parses"
PROOF_LINT = "lint"
PROOF_EXPANDS = "expands"
PROOF_CONTRACT_DERIVES = "contract_derives"
PROOF_CHECKS_LIVE = "checks_live"
PROOF_TESTID_COVERAGE = "testid_coverage"
PROOF_STATUS_DECLARED = "status_declared"
#: #838: the manifest declares its own stack, and until VS nothing compared that to the
#: stack the CYCLE was configured for. A manifest for another stack is unwinnable in the
#: most literal sense — the expander builds a different application.
PROOF_STACK_MATCHES_CONFIG = "stack_matches_config"

#: Schema-gate proof classes (M2). ``PROOF_SOURCE_PRD`` was ``PROOF_PROVENANCE`` until #803
#: gave the manifest an actual ``provenance`` block — one word for "where the design came
#: from" and "how the document was authored" is two meanings in one module. It now names the
#: field it checks, like every proof around it.
PROOF_SOURCE_PRD = "source_prd"
PROOF_DECISION_RECORD = "decision_record"


@dataclass(frozen=True)
class WinnabilityFinding:
    """One reason a manifest could not be won, and what to do about it."""

    proof: str
    detail: str


def assess_winnability(
    manifest_content: str, expected_stack: str = ""
) -> tuple[WinnabilityFinding, ...]:
    """Every closed-surface proof this manifest fails, in order.

    All proofs run; findings accumulate. Short-circuiting on the first failure would
    make an author fix one problem per revision and burn ``manifest_max_attempts`` on a
    manifest that had three.

    A parse failure is the one exception — nothing downstream can run without a parsed
    manifest, so it returns alone.

    ``expected_stack`` is the cycle's configured ``build_profile``. Empty skips the check —
    a seeded cycle and the gate's own adversarial fixtures have no cycle config to compare
    against, and inventing a mismatch for them would reject manifests that are correct.
    """
    from squadops.capabilities.scaffold import InterfaceManifest

    try:
        manifest = InterfaceManifest.from_yaml(manifest_content)
    except Exception as exc:  # noqa: BLE001 - untrusted authored output: one rejection
        return (
            WinnabilityFinding(
                PROOF_PARSES,
                f"the manifest is not valid YAML or does not match the interface-manifest "
                f"shape ({exc}). Fix the document structure before the other checks can run.",
            ),
        )

    # #838: a wrong stack returns ALONE, like a parse failure and for the same reason —
    # it invalidates the frame every other proof reasons in. The remaining proofs would run
    # happily against the wrong application and report real-looking findings about testids
    # and statuses for a design that is about to be replaced wholesale. Telling an author to
    # fix a testid in a manifest whose stack is wrong is worse than telling them nothing.
    stack_findings = _stack_findings(manifest, expected_stack)
    if stack_findings:
        return tuple(stack_findings)

    findings: list[WinnabilityFinding] = []
    findings.extend(_lint_findings(manifest))
    findings.extend(_expander_findings(manifest))
    findings.extend(_contract_findings(manifest))
    findings.extend(_testid_findings(manifest))
    findings.extend(_status_findings(manifest))
    return tuple(findings)


def assess_schema(manifest_content: str) -> tuple[WinnabilityFinding, ...]:
    """The M2 schema gate: is this document well-formed and does it cite its origin?

    Distinct from winnability on purpose. This asks whether the manifest is a
    *legible design document* — it parses, it says which PRD it came from, and every
    judgment it made is recorded with a warrant. Whether the design can be BUILT is
    :func:`assess_winnability`, and asking that of a document with no stated provenance
    wastes the harder analysis.

    Citation is at **decision granularity**, not per entry: ``source_prd`` plus
    ``decisions[].warrant``. §5b Correction 3 ruled per-entry citation would bloat
    authoring for little gate value, and the schema has no field for it anyway.
    """
    from squadops.capabilities.scaffold import InterfaceManifest

    try:
        manifest = InterfaceManifest.from_yaml(manifest_content)
    except Exception as exc:  # noqa: BLE001 - untrusted authored output: one rejection
        return (
            WinnabilityFinding(
                PROOF_PARSES,
                f"the manifest is not valid YAML or does not match the interface-manifest "
                f"shape ({exc}). Fix the document structure before anything else can run.",
            ),
        )

    findings: list[WinnabilityFinding] = []
    if not manifest.source_prd.strip():
        findings.append(
            WinnabilityFinding(
                PROOF_SOURCE_PRD,
                "`source_prd` is empty — the manifest does not say which requirements "
                "document it was designed from, so no reviewer can check the design "
                "against its source. Name the PRD this manifest derives from.",
            )
        )
    findings.extend(_decision_findings(manifest))
    return tuple(findings)


def _decision_findings(manifest) -> list[WinnabilityFinding]:
    """Every recorded judgment must be attributable, or answerable.

    A resolved decision needs its PRD ``warrant`` — that is the whole point of recording
    it, and a choice with no citation is indistinguishable from an invention. An
    unresolved one needs its ``question``, or it defers something without saying what,
    which is worse than defaulting silently: it looks like diligence.
    """
    findings: list[WinnabilityFinding] = []
    for index, decision in enumerate(manifest.decisions):
        label = f"`{decision.id}`" if decision.id else f"entry {index}"
        if not decision.id.strip():
            findings.append(
                WinnabilityFinding(
                    PROOF_DECISION_RECORD,
                    f"decision {label} has no `id`, so it cannot be referenced in review "
                    f"or tracked across revisions.",
                )
            )
        if decision.unresolved:
            if not decision.question.strip():
                findings.append(
                    WinnabilityFinding(
                        PROOF_DECISION_RECORD,
                        f"decision {label} is marked `unresolved` but states no "
                        f"`question` — it defers a design choice without saying which "
                        f"one, which reads as diligence while communicating nothing.",
                    )
                )
        else:
            if not decision.choice.strip():
                findings.append(
                    WinnabilityFinding(
                        PROOF_DECISION_RECORD,
                        f"decision {label} records no `choice`. Either state the choice "
                        f"made, or mark it `unresolved: true` with the question.",
                    )
                )
            if not decision.warrant.strip():
                findings.append(
                    WinnabilityFinding(
                        PROOF_DECISION_RECORD,
                        f"decision {label} has no `warrant` — a choice with no citation "
                        f"back to the PRD is indistinguishable from an invention. Cite "
                        f"the section it follows from.",
                    )
                )
    return findings


def _lint_findings(manifest) -> list[WinnabilityFinding]:
    """The SIP-0099 net: parses-but-unexpandable classes the linter already names."""
    return [WinnabilityFinding(PROOF_LINT, e) for e in manifest.lint()]


def _expander_findings(manifest) -> list[WinnabilityFinding]:
    """The skeleton this manifest implies must be expressible, with slots to fill.

    A manifest that expands to zero fill slots describes an application nobody can be
    asked to build: every file would be frozen, so the squad has nothing to write and
    the cycle would 'succeed' having produced nothing (the pf-26 wrong-root class, one
    level up from where it was found).
    """
    from squadops.capabilities.scaffold import expand, fill_slot_paths

    try:
        expand(manifest)
    except Exception as exc:  # noqa: BLE001 - expander refusal is a finding, not a crash
        return [
            WinnabilityFinding(
                PROOF_EXPANDS,
                f"the expander cannot build a skeleton from this manifest ({exc}). Check "
                f"that routes and endpoints use paths the stack's scaffold roots allow.",
            )
        ]

    if not fill_slot_paths(manifest):
        return [
            WinnabilityFinding(
                PROOF_EXPANDS,
                "this manifest expands to a skeleton with no fill slots — every file "
                "would be frozen, leaving the squad nothing to implement. Declare at "
                "least one endpoint or route that requires authored code.",
            )
        ]
    return []


def _contract_findings(manifest) -> list[WinnabilityFinding]:
    """The derived contract must exist, be structurally valid, and be satisfiable.

    Three distinct failures: derivation refusing outright, derivation producing a contract
    that fails its own linter, and derivation producing a check that can never execute. The
    third is the #671 class one level up — a check that skips at every evaluation forever is
    dead weight the plan still has to carry.

    **The linter call is #849, and its absence is the more interesting half of that bug.**
    ``VerificationContract.lint()`` has existed throughout, and ``_lint_ids`` detects the
    duplicate-id defect precisely — but repo-wide its only callers were
    ``scripts/dev/contract_gate.py`` and unit tests. Both run against the *reference FastAPI
    manifest*, whose criterion ids cannot collide, so the guard was exercised only by the one
    input incapable of failing it and was absent from every path that derives a contract at
    cycle time. Stack #2's contract reached a live run malformed.

    Linting here rather than at the storage seam is deliberate: this is the gate that already
    answers "is this manifest winnable", a malformed contract is exactly a way for it not to
    be, and a rejection here re-rolls framing for free (#522) instead of failing mid-run.
    """
    from squadops.capabilities.scaffold_contract import emit_contract_dict
    from squadops.cycles.acceptance_check_spec import CHECK_SPECS, is_check_applicable
    from squadops.cycles.verification_contract import VerificationContract

    try:
        contract = emit_contract_dict(manifest)
    except Exception as exc:  # noqa: BLE001 - derivation refusal is a finding
        return [
            WinnabilityFinding(
                PROOF_CONTRACT_DERIVES,
                f"no verification contract could be derived from this manifest ({exc}), "
                f"so nothing downstream could state what 'done' means.",
            )
        ]

    # Structural validity, before anything reads the contract's contents. A contract whose
    # own linter rejects it is not a contract the rest of this function can reason about —
    # duplicate ids in particular make `criterion_index()` silently lossy, so the
    # per-check findings below would be computed over criteria no ref can ever resolve to.
    try:
        lint_errors = VerificationContract.from_dict(contract).lint()
    except Exception as exc:  # noqa: BLE001 - a contract that will not even load is a finding
        return [
            WinnabilityFinding(
                PROOF_CONTRACT_DERIVES,
                f"the contract derived from this manifest could not be loaded ({exc}).",
            )
        ]
    if lint_errors:
        return [
            WinnabilityFinding(
                PROOF_CONTRACT_DERIVES,
                f"the contract derived from this manifest is structurally invalid: "
                f"{'; '.join(lint_errors)}. Downstream binding resolves criteria by id and "
                f"would silently drop what it cannot address, so the plan would read as "
                f"fully covered while part of the surface went unverified.",
            )
        ]

    findings: list[WinnabilityFinding] = []
    for slot_path, sections in (contract.get("fill_files") or {}).items():
        for section in ("interface", "implementation"):
            for entry in sections.get(section) or []:
                name = entry.get("check")
                if name not in CHECK_SPECS:
                    findings.append(
                        WinnabilityFinding(
                            PROOF_CHECKS_LIVE,
                            f"the contract this manifest implies uses check `{name}` on "
                            f"`{slot_path}`, which is not a registered check.",
                        )
                    )
                elif not is_check_applicable(name, str(entry.get("file") or slot_path)):
                    findings.append(
                        WinnabilityFinding(
                            PROOF_CHECKS_LIVE,
                            f"check `{name}` can never evaluate `{slot_path}` — it would "
                            f"skip at every evaluation, so the slot would ship unverified "
                            f"while appearing covered.",
                        )
                    )
    return findings


def _stack_findings(manifest, expected_stack: str) -> list[WinnabilityFinding]:
    """The manifest must be for the stack this cycle is building (#838).

    Found by VS: `cyc_afa934886acd` was configured `build_profile=nextjs_ts`, the manifest
    declared `fullstack_fastapi_react`, and **every component behaved correctly while building
    the wrong application for 75 minutes**. `lint()` accepts any *registered* stack — is it
    known, never is it the one asked for — so nothing downstream had a reason to object.

    The author is told the target (the authoring template renders it), but it lost to a
    technical design that named the other stack eight times; the design stage is not told the
    stack at all. That plumbing is a separate fix. This proof is the deterministic backstop
    that holds regardless of what any model writes, and it turns a 75-minute discovery into a
    seconds-long one.
    """
    declared = str(getattr(manifest, "stack", "") or "")
    if not expected_stack or declared == expected_stack:
        return []
    return [
        WinnabilityFinding(
            PROOF_STACK_MATCHES_CONFIG,
            f"this manifest declares `stack: {declared}` but the cycle is configured to build "
            f"`{expected_stack}`. The expander would produce a different application than the "
            f"one requested — every file, every fill slot, and every derived check would be "
            f"for the wrong stack. Declare `stack: {expected_stack}`.",
        )
    ]


def _testid_findings(manifest) -> list[WinnabilityFinding]:
    """Every route needs at least one DOM anchor, or its view cannot be tested.

    A view with no declared testid gives qa nothing stable to query, so any test
    written against it is guessing at markup the dev was free to change.
    """
    missing = [r.path for r in manifest.frontend.routes if not r.testids]
    if not missing:
        return []
    return [
        WinnabilityFinding(
            PROOF_TESTID_COVERAGE,
            f"route(s) {', '.join(f'`{p}`' for p in missing)} declare no `testids`, so "
            f"qa has no stable anchor to query and any test written against them guesses "
            f"at markup. Declare at least one testid per route.",
        )
    ]


def _status_findings(manifest) -> list[WinnabilityFinding]:
    """A collection POST must declare its success status, or the contract is unwinnable.

    Measured, not assumed (#772). The contract deriver expects ``success_status or 201``
    for a collection POST, while the scaffold omits ``status_code=`` when it is
    undeclared — so FastAPI returns 200 and the probe asserts 201 against a correctly
    implemented app. The field's own docstring records this costing a roll at pf-39:
    green depended on the dev agent volunteering ``status_code=201``, "and that single
    token was the whole difference."

    Deliberately narrow. Child-action POSTs default to 200 on *both* sides and agree;
    GETs derive no status probe at all. Requiring the field everywhere would reject the
    reference manifest — which declares it on 1 of 5 endpoints — and a rule that rejects
    the artifact the 1.4 evidence was measured against is the wrong rule.
    """
    missing = [
        ep.path
        for ep in manifest.api.endpoints
        if ep.method == "POST" and "{" not in ep.path and ep.success_status is None
    ]
    if not missing:
        return []
    return [
        WinnabilityFinding(
            PROOF_STATUS_DECLARED,
            f"endpoint(s) POST {', '.join(f'`{p}`' for p in missing)} do not declare "
            f"`success_status`. The derived contract would assert 201 while the scaffold "
            f"emits a route returning 200, so the probe fails against a correct "
            f"implementation. Declare the status the endpoint returns on success.",
        )
    ]
