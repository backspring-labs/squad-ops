#!/usr/bin/env python3
"""Verification-set driver — ONE roll per invocation, facts only.

Promoted from the session scratchpad that drove the 1.6.3 and 1.6.4 sets (sixteen
counted rolls and three shakeouts), with the two defects those sets recorded against it
fixed and its assumptions moved out of the code:

* **No fixed parameters in the code.** Project, squad, request profile, overrides, the
  frozen deploy's identity, the gate constant and the launch notes all come from a
  set-config YAML (``--set``) — the pre-registration's §1 table as data, committed
  beside the pre-registration it belongs to. The scratchpad copies carried them as
  constants and were hand-edited per set.
* **The stack is a fact of the cycle, not of the driver.** It is derived from the
  request profile's defaults and the overrides, and the P0 static checks dispatch on
  it. A stack with no registered P0 check is refused loudly, never silently passed
  (the #818 rule). The scratchpad opened ``lib/models.ts`` unconditionally.
* **The log window is UTC-explicit.** ``docker logs --since`` read the wrong window
  because the timestamp carried no zone (1.6.4 record §4, "instrument defect").
* **Every readout is read by its REASON, never by a count (#1276, 1.7.1 record §7).**
  A prediction reads "exercised" or "falsified" off rows whose reason is not the one it
  names otherwise: React roll 5's "1 kind-gate rejection" was ``assertion_kinds_match``
  failing with ``file_not_found``, and Next.js roll 1's "unverifiable, toolchain absent"
  was an absent *file*. Three of the 1.7.1 readouts were misread this way. So a readout
  is a ``{reason: count}`` map, non-execution is reported beside failure (#1261 arrived as
  skipped rows), and an emission fact is read from the emission — the producing agent's
  own ``emission shape:`` line — not from a downstream token.

Deliberately not a loop over a set: §5.1's *reset* rule requires someone to NOTICE a new
harness-attributable failure, so everything mechanical is automated and the scoring
decision — counted / void / reset — is left at the roll boundary, where a reader is. It
does not judge: it collects what happened and renders it; the pre-registration says
what those facts mean.

Usage:
    .venv/bin/python scripts/dev/verification_set_driver.py preflight --set <yaml>
    .venv/bin/python scripts/dev/verification_set_driver.py shakeout  --set <yaml> [--dry-run]
    .venv/bin/python scripts/dev/verification_set_driver.py roll      --set <yaml> --roll N [--dry-run]

``shakeout`` is NON-COUNTING by declaration: it records the deploy's identity instead of
asserting it (first cycle on new images — nothing to hold to yet). ``roll`` asserts the
frozen image ids, pins HEAD on roll 1 and holds it, and asserts the config hash.

The procedure around this script — the shakeout loop and its exit rule, what a diagnostic
must be, how a launch survives the session, how a dead driver is re-attached — is
``docs/plans/verification-sets/README.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
#: Where every set config lives, and where a config's ``compare_with`` names its pair.
SET_CONFIG_DIR = REPO / "docs" / "plans" / "verification-sets"
SQUADOPS = str(REPO / ".venv" / "bin" / "squadops")
PYTHON = str(REPO / ".venv" / "bin" / "python")

#: docker-compose service names (fixed by docker-compose.yml; CLAUDE.md forbids renaming).
AGENT_SERVICES = ("max", "neo", "nat", "bob", "eve", "data")
DEPLOY_SERVICES = ("runtime-api", *AGENT_SERVICES)
#: The Solo arm's one container (SIP-0108 §10i, the 1.8.1 window). Not a deploy service: a
#: squad deploy has no `han`, and a set that does not name it is not asked about it. A set
#: names it by pinning its image id or probing it, and only then is it read and required up.
SOLO_SERVICES = ("han",)
KNOWN_SERVICES = (*DEPLOY_SERVICES, *SOLO_SERVICES)
POSTGRES_CONTAINER = "squadops-postgres"
RUNTIME_API_CONTAINER = "squadops-runtime-api"

#: The ``execution_overrides`` key a fault-injected cycle declares (#1251). Kept as a
#: literal here rather than imported: the driver runs from its own checkout and must be able
#: to refuse a counting roll even against a deploy whose framework predates the module.
FAULT_DECLARATION_KEY = "fault_injection"


# ---------------------------------------------------------------------------
# The evidence vocabulary — three states for every registered record field (#1445)
# ---------------------------------------------------------------------------
#
# A record field used to be a value or an absence, and the 1.7.4 record §9 says why that is
# not enough: a readout that cannot tell "did not happen" from "could not be asked" is not
# evidence. Three findings on that line were the same defect in different clothes — a probe
# that could not run recorded like one that answered (#1425), a field labelled in units it
# did not count (#1431), and a handoff readout that read empty on every roll because its
# producer is structurally silent on a clean roll. So every registered field carries one of:
#
#   observed(value)    the condition was asked and answered;
#   asked_none         the condition was asked and was absent or zero;
#   unaskable(reason)  the producer could not ask it on this roll, with the structural reason.
#
# ``EVIDENCE_FIELDS`` is the schema property the pre-registration cites: per field, the
# conditions under which its producer is silent, each mapped to its reason. ``render``
# prints the three states differently and never folds ``unaskable`` into a zero or a count.

#: The three states, as the record spells them.
OBSERVED = "observed"
ASKED_NONE = "asked_none"
UNASKABLE = "unaskable"
EVIDENCE_STATES = (OBSERVED, ASKED_NONE, UNASKABLE)


@dataclass(frozen=True)
class Evidence:
    """One record field in the three-state vocabulary.

    ``declared`` is False when the state was INFERRED off a bare pre-#1445 value (a stored
    1.7.4 record, or a test fixture): a non-empty bare value was necessarily asked and
    answered, but an empty one cannot say whether it was asked — ``render`` names the
    inference rather than letting it read as a declaration.
    """

    state: str
    value: Any = None
    reason: str | None = None
    declared: bool = True

    @classmethod
    def observed(cls, value: Any) -> Evidence:
        return cls(OBSERVED, value=value)

    @classmethod
    def asked_none(cls, value: Any = None) -> Evidence:
        """``value`` is the field's own empty shape (``[]``, ``{}``, ``0``) so a consumer
        that needs a typed empty gets one."""
        return cls(ASKED_NONE, value=value)

    @classmethod
    def unaskable(cls, reason: str) -> Evidence:
        return cls(UNASKABLE, reason=reason)

    @classmethod
    def of(cls, value: Any, unaskable_reason: str | None = None) -> Evidence:
        """The state a producer's output is in: ``unaskable`` when a structural condition
        fired, else ``observed`` / ``asked_none`` by whether the value answers anything."""
        if unaskable_reason:
            return cls.unaskable(unaskable_reason)
        return cls.asked_none(value) if is_none_answer(value) else cls.observed(value)

    def record(self) -> dict:
        """The fixed dict shape the JSON record carries."""
        if self.state == UNASKABLE:
            return {"state": UNASKABLE, "reason": self.reason}
        return {"state": self.state, "value": self.value}

    @classmethod
    def read(cls, obj: Any) -> Evidence:
        """A record field back into the vocabulary — legacy-tolerant (see ``declared``)."""
        if (
            isinstance(obj, dict)
            and obj.get("state") in EVIDENCE_STATES
            and set(obj) <= {"state", "value", "reason"}
        ):
            return cls(obj["state"], value=obj.get("value"), reason=obj.get("reason"))
        return cls(
            ASKED_NONE if is_none_answer(obj) else OBSERVED,
            value=obj,
            declared=False,
        )

    def value_or(self, default: Any) -> Any:
        """The answer, or ``default`` when there is none to read (unaskable, or a legacy
        field that was missing)."""
        if self.state == UNASKABLE or self.value is None:
            return default
        return self.value


def is_none_answer(value: Any) -> bool:
    """Whether a produced value answers nothing: empty, zero, or a mapping whose every
    value answers nothing (``{"failed": {}, "skipped": {}}``, ``{"overruns": 0, ...}``)."""
    if value is None or value is False:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    if isinstance(value, (str, list, tuple, set)):
        return len(value) == 0
    if isinstance(value, dict):
        return all(is_none_answer(v) for v in value.values())
    return False


#: Every structural reason a producer can be silent, keyed by the condition name a field
#: registers. A condition may carry a ``:<detail>`` suffix (``check_never_evaluated:foo``);
#: the reason is looked up on the prefix and formatted with the detail.
UNASKABLE_REASONS: dict[str, str] = {
    "no_implementation_run": "no implementation run — nothing was built to read",
    "runtime_window_empty": (
        "the runtime-api log window read no lines at all — an instrument window defect "
        "(1.6.4 record §4), not a quiet loop"
    ),
    "no_correction_round": (
        "no correction round — the line is emitted only on the patch path, so a clean roll "
        "cannot produce it"
    ),
    "no_emission_shape_lines": (
        "the agent log windows carried no `emission shape:` line — the fact is read where the "
        "emission happens (#1276) and the window read none"
    ),
    "no_emission_retry_aimed": (
        "no emission retry was aimed in the window (#1372) — the appendix question presupposes "
        "a retry"
    ),
    "no_correction_decision_stored": (
        "no correction_decision.md stored — the claim is read from the decision itself (#968)"
    ),
    "no_fill_merge_artifact": "no fill_merge_evidence.json stored for the run (#999)",
    "no_test_report_stored": (
        "no test_report.md stored for the run — which suites the runner collected is read from "
        "the report the qa handler writes (#1540)"
    ),
    "no_qa_scaffold_suite": (
        "no qa-authored suite stored under __tests__/scaffold/ — the fill layer's rejections "
        "are read from the suite text"
    ),
    "no_typed_check_evaluation_stored": (
        "no typed_check_evaluation_*.json stored for the run (#114)"
    ),
    "check_never_evaluated": (
        "no row of `{detail}` was evaluated on the run — a stack- or content-conditional check "
        "that had nothing to look at"
    ),
    "filtered_at_typed_check_seam": (
        "filtered at the typed-check seam — the framework's required_files row is not an "
        "`acceptance:` row and never reaches the artifact "
        "(handlers/cycle/validation.py:250–254, #114)"
    ),
    "logged_in_the_agent_container": (
        "the line is logged in the qa agent's container (handlers/cycle/qa_test.py:1546), "
        "never in the runtime-api window this field reads — the stored fact is "
        "loop_texture.fill_merge_evidence[].self_eval_fills (#1445 finding)"
    ),
    "cycle_predates_code_lineage": (
        "the cycle record carries no framework version — it was created before #80 or on a "
        "deploy without migration 1040, so neither the version nor the commit was stamped"
    ),
    "no_attempt_stamp": (
        "the banked artifacts carry no attempt marker (a pre-#1436 record), so two failed "
        "attempts of one task cannot be told from one attempt that banked two files — the "
        "emission count is not derivable and the ARTIFACT count is reported instead (#1436)"
    ),
    "probe_could_not_run": (
        "the probe could not run ({detail}) — an unasked question, not an answer (#1425)"
    ),
    "no_repair_revision_form_line": (
        "no `repair_revision_form` line in the agents' windows — a repair handler logs one per "
        "repair (SIP-0107 §46a), so either no repair was dispatched or the deployed image "
        "predates the instrument"
    ),
}

#: The conditions common to every readout parsed off the runtime-api window's patch path.
_PATCH_PATH = ("runtime_window_empty", "no_correction_round")
_AGENT_WINDOW = ("no_emission_shape_lines",)
_STORED_EVALUATIONS = ("no_implementation_run", "no_typed_check_evaluation_stored")

#: THE REGISTRY: record field (dotted path) → the conditions under which its producer is
#: structurally silent, in the order they are tested. A field with no conditions is always
#: askable and reads ``observed`` or ``asked_none``. ``loaded_checks.*`` covers every probe
#: the set config declares. A field in the record's evidence groups that is not registered
#: here fails the wiring test — the registry is the schema, not a summary of it.
EVIDENCE_FIELDS: dict[str, tuple[str, ...]] = {
    # collect(): stored artifacts of the implementation run
    "correction_rounds": ("no_implementation_run",),
    "failed_emission_artifacts_banked": ("no_implementation_run",),
    "failed_emissions_banked": ("no_implementation_run", "no_attempt_stamp"),
    # loop_texture: the runtime-api window, patch path
    "loop_texture.narrowed_targets": _PATCH_PATH,
    "loop_texture.language_fallbacks": _PATCH_PATH,
    "loop_texture.fill_targets": _PATCH_PATH,
    "loop_texture.refused_patches": _PATCH_PATH,
    "loop_texture.patch_verifications": _PATCH_PATH,
    "loop_texture.applied_patches": _PATCH_PATH,
    "loop_texture.retests": _PATCH_PATH,
    "loop_texture.plan_defect_terminations": _PATCH_PATH,
    "loop_texture.plan_defect_after_zero_applied": _PATCH_PATH,
    "loop_texture.refused_rounds_not_counted": _PATCH_PATH,
    "loop_texture.required_files_declared": _PATCH_PATH,
    "loop_texture.framework_rows_rederived": _PATCH_PATH,
    "loop_texture.candidate_identities": _PATCH_PATH,
    "loop_texture.analyzer_claims_dropped": _PATCH_PATH,
    "loop_texture.analyzer_claims_refuted": _PATCH_PATH,
    "loop_texture.unjoinable_refutations": _PATCH_PATH,
    "loop_texture.refunded_rounds": _PATCH_PATH,
    "loop_texture.evidence_superseded": _PATCH_PATH,
    "loop_texture.qa_owned_routed": _PATCH_PATH,
    "loop_texture.own_artifact_locus": _PATCH_PATH,
    "loop_texture.absent_anchor_routed": _PATCH_PATH,
    "loop_texture.repair_brief_case_counts": _PATCH_PATH,
    "loop_texture.decided_by_agent": _PATCH_PATH,
    "loop_texture.unverifiable_by_reason": _PATCH_PATH,
    "loop_texture.no_execution_by_skip_reason": _PATCH_PATH,
    "loop_texture.no_execution_on_passed_verifications": _PATCH_PATH,
    # loop_texture: the runtime-api window, emission path (any roll)
    "loop_texture.emission_retries": ("runtime_window_empty",),
    # A producer that has never been able to answer: the qa handler logs this line in its
    # own container and the field reads the runtime-api's window. Found by this migration.
    "loop_texture.self_eval_fill_merges": ("logged_in_the_agent_container",),
    # loop_texture: the agents' windows
    "loop_texture.emissions_logged": (),
    "loop_texture.contentless_emissions": _AGENT_WINDOW,
    "loop_texture.contentless_by_handler": _AGENT_WINDOW,
    "loop_texture.empty_repair_emissions": _AGENT_WINDOW,
    "loop_texture.emission_tokens_by_handler": _AGENT_WINDOW,
    "loop_texture.placeholder_strips": _AGENT_WINDOW,
    "loop_texture.faults_applied": _AGENT_WINDOW,
    "loop_texture.retried_with_fact": (*_AGENT_WINDOW, "no_emission_retry_aimed"),
    "loop_texture.retried_blind": (*_AGENT_WINDOW, "no_emission_retry_aimed"),
    "loop_texture.repair_revision_forms": (
        *_AGENT_WINDOW,
        "no_correction_round",
        "no_repair_revision_form_line",
    ),
    # loop_texture: the Prefect server's window (its filter keeps only overrun lines, so an
    # empty window is a quiet one)
    "loop_texture.prefect_loop_overruns": (),
    # loop_texture: the artifact vault
    "loop_texture.decision_inherited_claims": (
        "no_implementation_run",
        "no_correction_decision_stored",
    ),
    "loop_texture.fill_rejections": ("no_implementation_run", "no_qa_scaffold_suite"),
    "loop_texture.fill_merge_evidence": ("no_implementation_run", "no_fill_merge_artifact"),
    "loop_texture.uncollected_suites": ("no_implementation_run", "no_test_report_stored"),
    "loop_texture.stored_under_placeholder": ("no_implementation_run",),
    # typed_checks: the stored evaluation artifacts
    "typed_checks.by_check": _STORED_EVALUATIONS,
    "typed_checks.checks_by_environment": _STORED_EVALUATIONS,
    "typed_checks.stale_evaluations": _STORED_EVALUATIONS,
    "typed_checks.assertion_kinds_match_rows": (
        *_STORED_EVALUATIONS,
        "check_never_evaluated:assertion_kinds_match",
    ),
    "typed_checks.additive_containment_rows": (
        *_STORED_EVALUATIONS,
        "check_never_evaluated:additive_containment",
    ),
    "typed_checks.dom_anchor_queries_rows": (
        *_STORED_EVALUATIONS,
        "check_never_evaluated:dom_anchor_queries",
    ),
    "typed_checks.container_packaging_rows": (
        *_STORED_EVALUATIONS,
        "check_never_evaluated:container_packaging",
    ),
    "typed_checks.undefined_names_rows": (
        *_STORED_EVALUATIONS,
        "check_never_evaluated:undefined_names",
    ),
    # H1's first source: the framework row in the typed-check artifact, which the seam
    # filters out by design — on every roll, not only clean ones.
    "typed_checks.required_files_rows": ("no_implementation_run", "filtered_at_typed_check_seam"),
    # deploy identity: one entry per probe the set config declares
    "loaded_checks.*": ("probe_could_not_run",),
    # #80: the code and configuration the cycle record says created the cycle — observed on
    # the record, beside the set config's typed `frozen_deploy_commit`. An empty commit on a
    # stamped record is an answer: the image recorded none.
    "lineage.framework_version": ("cycle_predates_code_lineage",),
    "lineage.framework_git_sha": ("cycle_predates_code_lineage",),
    "lineage.request_profile": (),
}

#: The record keys whose members are evidence fields — the wiring test asserts every
#: member of these is registered and every registered field of these is produced.
EVIDENCE_GROUPS = ("loop_texture", "typed_checks", "loaded_checks", "lineage")
#: Record metadata that lives beside evidence fields without being one.
_NOT_EVIDENCE = {"loop_texture.log_window"}


def unaskable_reason(condition: str) -> str:
    name, _, detail = condition.partition(":")
    return UNASKABLE_REASONS[name].format(detail=detail)


def registered_conditions(path: str) -> tuple[str, ...]:
    """The conditions registered for ``path``, honouring the ``group.*`` wildcard."""
    if path in EVIDENCE_FIELDS:
        return EVIDENCE_FIELDS[path]
    group, _, _ = path.rpartition(".")
    return EVIDENCE_FIELDS.get(f"{group}.*", ())


def evidence_for(path: str, value: Any, context: Mapping[str, Any]) -> Evidence:
    """The state of one registered field from its produced value and the roll's context.

    ``context`` maps a condition name to whether it holds; a condition the context does
    not carry (``None``) is one the caller could not derive — the field then reads
    ``observed``/``asked_none`` off its value with ``declared=False``, so a re-render of a
    stored record says which states it inferred rather than declaring them.
    """
    underivable = False
    for condition in registered_conditions(path):
        holds = context.get(condition)
        if holds:
            return Evidence.unaskable(unaskable_reason(condition))
        if holds is None:
            underivable = True
    ev = Evidence.of(value)
    return Evidence(ev.state, value=ev.value, declared=not underivable)


class UnregisteredEvidenceField(KeyError):
    """A collector emitted a field the registry does not describe."""


def with_states(group: str, fields: dict, context: Mapping[str, Any]) -> dict:
    """Every registered field of ``group`` in ``fields`` rewritten into the record shape;
    metadata (``_NOT_EVIDENCE``) passes through untouched.

    An UNREGISTERED field is refused, not defaulted: ``EVIDENCE_FIELDS`` is the schema, and
    a field that quietly reads "always askable" is the #1445 defect wearing the fix's
    clothes — the reader would take its empty value for an answer. Adding a readout means
    stating when its producer is silent, in the same PR.
    """
    out: dict = {}
    for key, value in fields.items():
        path = f"{group}.{key}"
        if path in _NOT_EVIDENCE:
            out[key] = value
            continue
        if path not in EVIDENCE_FIELDS and f"{group}.*" not in EVIDENCE_FIELDS:
            raise UnregisteredEvidenceField(
                f"{path} is not in EVIDENCE_FIELDS — register the conditions under which "
                "its producer is silent (or add it to _NOT_EVIDENCE if it is metadata)"
            )
        out[key] = evidence_for(path, value, context).record()
    return out


def evidence_at(rec: Mapping[str, Any], path: str) -> Evidence | None:
    """The field at a dotted path, in the vocabulary; ``None`` when the record lacks it."""
    node: Any = rec
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return Evidence.read(node)


def value_at(rec: Mapping[str, Any], path: str, default: Any = None) -> Any:
    """The answer at a dotted path, or ``default`` when there is none to read."""
    ev = evidence_at(rec, path)
    return default if ev is None else ev.value_or(default)


def registry_table() -> str:
    """``EVIDENCE_FIELDS`` as the markdown table a pre-registration pastes."""
    lines = [
        "| field | unaskable when | reads |",
        "|---|---|---|",
    ]
    for path, conditions in EVIDENCE_FIELDS.items():
        if not conditions:
            lines.append(f"| `{path}` | never — always askable | observed / asked_none |")
            continue
        for condition in conditions:
            lines.append(f"| `{path}` | `{condition}` | {unaskable_reason(condition)} |")
    return "\n".join(lines)


def declared_fault_names(overrides: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The faults a set config declares — the same normalisation the framework applies.

    Duplicated rather than imported for the reason above: the driver must be able to refuse
    a counting roll against a deploy whose framework predates the module. The two are held
    to each other by ``test_the_drivers_fault_normaliser_agrees_with_the_frameworks``, so
    the duplication cannot drift.

    Before this existed, ``preflight`` and the record renderer each iterated the raw override
    value. A single fault arrives from ``--set`` as a *string*, so iterating it yielded its
    characters and the diagnostic's own record named the fault as `_, a, b, e, …` (#1298).
    """
    declared = (overrides or {}).get(FAULT_DECLARATION_KEY)
    if not declared:
        return ()
    if isinstance(declared, str):
        declared = [part for part in (p.strip() for p in declared.split(",")) if part]
    return tuple(str(name) for name in declared)


POLL_S = 30
MAX_WAIT_S = 4 * 60 * 60


# ---------------------------------------------------------------------------
# Set config — the pre-registration's §1 as data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadedCheck:
    """One "loaded, not built" probe: a named question asked inside one container.

    ``name`` says what the probe ASKS and is what the recorded identity keys on; ``service``
    says where to ask it. A YAML entry whose value is a plain string keeps the older shape,
    where the name is itself the service — every set through 1.7.3 is written that way and
    records byte-identical keys under this class.
    """

    name: str
    service: str
    source: str


@dataclass(frozen=True)
class SetConfig:
    name: str
    project: str
    squad_profile: str
    request_profile: str
    gate_name: str
    #: Copied verbatim onto every gate approval — NO substitution of any kind (§6).
    gate_notes: str
    #: The only formatting the driver does: ``{roll}`` and ``{n}``.
    launch_notes: str
    shakeout_notes: str
    n_rolls: int
    overrides: dict[str, str] = field(default_factory=dict)
    #: Empty = record, do not assert (a shakeout on a fresh deploy).
    expected_config_hash_prefix: str = ""
    #: The squad-profile snapshot the set is frozen on. A per-agent override (1.6.5 E:
    #: eve's completion budget) moves THIS identity and leaves resolved_config_hash — the
    #: request-profile side — untouched; a set that asserted only the latter would accept
    #: a roll on a different squad configuration.
    expected_squad_snapshot_prefix: str = ""
    frozen_deploy_commit: str = ""
    frozen_image_ids: dict[str, str] = field(default_factory=dict)
    #: ``{service: python_source}`` — "loaded, not built": run inside the container and
    #: recorded with the deploy identity (the pre-registration's own list, as data).
    loaded_checks: tuple[LoadedCheck, ...] = ()
    records_dir: str = ""
    pre_registration: str = ""
    #: The comparison arm this set is (SIP-0108 §4.4, §10h): the name a pre-registration's
    #: comparison section pairs by. Empty means the set is not part of a comparison — every
    #: set before 1.8.1 is one arm by construction, and saying so is not the same as
    #: declaring one.
    #:
    #: The arm's IDENTITY is squad profile × request profile × model, which this config
    #: already carries in ``squad_profile`` and ``request_profile``; the declaration names
    #: it so two configs can be compared and so a record says which arm produced it.
    arm: str = ""
    #: The set config of the arm this one is compared against, by file name in the same
    #: directory. Present on exactly one side of a pair: the comparison gate runs from
    #: whichever config names the other, so the check has two configs to read.
    compare_with: str = ""
    #: The comparison window's REGISTERED sample and attempt budget (plan §4.3: six valid pairs
    #: of at most eight attempted), declared on both arm configs and required to agree. Data,
    #: never a CLI flag: a value the operator could change at launch or on resume is a value
    #: that could change after results exist.
    window_pairs: int = 0
    window_max_attempts: int = 0
    #: This config's own file name, so a counterpart named in ``compare_with`` can be checked
    #: against the config actually supplied rather than against "any file that exists" — and
    #: its resolved path, so a supplied file that merely SHARES the canonical basename is
    #: refused rather than admitted while the gate reloads the canonical one (#1645 review).
    source: str = ""
    source_path: str = ""

    @property
    def records_path(self) -> Path:
        # var/ is gitignored and user-writable; data/ is the docker volume, owned by root —
        # the first launch died on mkdir there before it created anything.
        return (
            Path(self.records_dir)
            if self.records_dir
            else REPO / "var" / "verification_sets" / self.name
        )

    @property
    def head_pin(self) -> Path:
        return self.records_path / ".head_pin"


_REQUIRED = (
    "name",
    "project",
    "squad_profile",
    "request_profile",
    "gate_name",
    "gate_notes",
    "launch_notes",
    "shakeout_notes",
    "n_rolls",
)


def load_set_config(path: Path) -> SetConfig:
    raw = yaml.safe_load(path.read_text()) or {}
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        raise SystemExit(f"{path}: set config is missing {', '.join(missing)}")
    # A list stays a readable list in the YAML and is carried as the comma form the CLI's
    # `--set` can express (#1298); `str(["a"])` produced `"['a']"`, which the framework's
    # guard then refused at cycle create.
    overrides = {
        str(k): (",".join(str(i) for i in v) if isinstance(v, list | tuple) else str(v))
        for k, v in (raw.get("overrides") or {}).items()
    }
    image_ids = {str(k): str(v) for k, v in (raw.get("frozen_image_ids") or {}).items()}
    unknown = sorted(set(image_ids) - set(KNOWN_SERVICES))
    if unknown:
        raise SystemExit(f"{path}: frozen_image_ids names unknown services {unknown}")
    checks: list[LoadedCheck] = []
    for key, value in (raw.get("loaded_checks") or {}).items():
        name = str(key)
        if isinstance(value, dict):
            absent = [k for k in ("service", "source") if k not in value]
            if absent:
                raise SystemExit(f"{path}: loaded_checks[{name}] is missing {', '.join(absent)}")
            checks.append(LoadedCheck(name, str(value["service"]), str(value["source"])))
        else:
            checks.append(LoadedCheck(name, name, str(value)))
    unknown_services = sorted({c.service for c in checks} - set(KNOWN_SERVICES))
    if unknown_services:
        raise SystemExit(
            f"{path}: loaded_checks names unknown services {unknown_services} — a probe whose "
            "container does not exist can only ever record an error, and in the deploy identity "
            "that reads exactly like a probe that ran and reported"
        )
    return SetConfig(
        name=str(raw["name"]),
        project=str(raw["project"]),
        squad_profile=str(raw["squad_profile"]),
        request_profile=str(raw["request_profile"]),
        gate_name=str(raw["gate_name"]),
        gate_notes=str(raw["gate_notes"]).strip(),
        launch_notes=str(raw["launch_notes"]).strip(),
        shakeout_notes=str(raw["shakeout_notes"]).strip(),
        n_rolls=int(raw["n_rolls"]),
        overrides=overrides,
        expected_config_hash_prefix=str(raw.get("expected_config_hash_prefix") or ""),
        expected_squad_snapshot_prefix=str(raw.get("expected_squad_snapshot_prefix") or ""),
        frozen_deploy_commit=str(raw.get("frozen_deploy_commit") or ""),
        frozen_image_ids=image_ids,
        loaded_checks=tuple(checks),
        records_dir=str(raw.get("records_dir") or ""),
        pre_registration=str(raw.get("pre_registration") or ""),
        arm=str(raw.get("arm") or ""),
        compare_with=str(raw.get("compare_with") or ""),
        window_pairs=int(raw.get("window_pairs") or 0),
        window_max_attempts=int(raw.get("window_max_attempts") or 0),
        source=path.name,
        source_path=str(path.resolve()),
    )


def render_launch_notes(template: str, roll: int, n: int) -> str:
    """``{roll}`` and ``{n}`` only — never ``str.format`` on text that may carry braces."""
    return template.replace("{roll}", str(roll)).replace("{n}", str(n))


# ---------------------------------------------------------------------------
# The stack is the cycle's fact
# ---------------------------------------------------------------------------


def derive_stack(profile_defaults: Mapping[str, Any], overrides: Mapping[str, str]) -> str:
    """``build_profile`` from the overrides, else the request profile's defaults.

    Refuses rather than guesses: a driver that assumed a stack opened ``lib/models.ts``
    on every cycle, which is exactly wrong for stack #1.
    """
    stack = overrides.get("build_profile") or profile_defaults.get("build_profile")
    if not stack:
        raise SystemExit(
            "cannot derive the stack: no build_profile in overrides or profile defaults"
        )
    return str(stack)


def stack_for(cfg: SetConfig) -> str:
    from squadops.contracts.cycle_request_profiles import load_profile

    return derive_stack(load_profile(cfg.request_profile).defaults, cfg.overrides)


# ---------------------------------------------------------------------------
# Shell / evidence helpers
# ---------------------------------------------------------------------------


def sh(cmd: str, check: bool = True) -> str:
    proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"FAILED: {cmd}\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def docker_logs(container: str, since: str, until: str | None = None) -> list[str]:
    """One container's log window, BOTH streams (#1276).

    ``docker logs`` replays the container's stdout and stderr on the reader's own stdout
    and stderr respectively, and ``sh`` returns stdout alone. The runtime-api's logging
    lands on stdout, so every readout built from it happened to work; the agents' lands on
    stderr, so the emission facts — logged where the emission happens — were unreadable to
    an instrument that only ever looked at one stream. Which stream a container happens to
    use is not a fact any readout should depend on.
    """
    # 1.7.4: bounded at both ends. A window with no end reads every later cycle's lines
    # into a record re-rendered after them — the deploy A re-render of the contentless-builder
    # diagnostic carried the analyzer diagnostic's qa retries as its own (#1372's field).
    bound = f" --until {until}" if until else ""
    proc = subprocess.run(
        shlex.split(f"docker logs --since {since}{bound} {container}"),
        capture_output=True,
        text=True,
    )
    return (proc.stdout + proc.stderr).splitlines()


def psql(query: str) -> str:
    return sh(
        f"docker exec {POSTGRES_CONTAINER} psql -U squadops -d squadops -tAc " + shlex.quote(query)
    )


def log(msg: str) -> None:
    print(f"[{datetime.now(UTC).strftime('%H:%M:%S')}Z] {msg}", flush=True)


def cycle_log_until(cycle_id: str, grace_seconds: int = 60) -> str | None:
    """The end of a cycle's log window: its last run's ``finished_at`` plus a grace for the
    lines the executor writes at the very end — or None while a run is still open, in
    which case the window has no end and the record says so."""
    raw = psql(
        "select to_char(max(finished_at) at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'), "
        f"count(*) filter (where finished_at is null) from cycle_runs where cycle_id='{cycle_id}';"
    )
    if not raw or "|" not in raw:
        return None
    finished, open_runs = raw.split("|", 1)
    if not finished.strip() or open_runs.strip() != "0":
        return None
    moment = datetime.strptime(finished.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return log_since(moment + timedelta(seconds=grace_seconds))


def log_since(moment: datetime) -> str:
    """RFC 3339 with an explicit zone — what ``docker logs --since`` needs.

    The scratchpad driver passed ``%Y-%m-%dT%H:%M:%S`` with no zone; docker read it in
    the daemon's local time and the P4/P5 windows came back empty (1.6.4 record §4).
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def login() -> None:
    """Refresh the token immediately before any state-changing call — it expires in minutes,
    and gate approvals land hours after launch. Do NOT pass --keycloak-url (the override
    logs in at Keycloak and then 401s on every API call; silent at login)."""
    user = os.environ.get("SQUADOPS_DRIVER_USER", "squadops-admin")
    password = os.environ.get("SQUADOPS_DRIVER_PASSWORD", "admin123")
    sh(f"{SQUADOPS} login -u {shlex.quote(user)} -p {shlex.quote(password)}")


def image_id(service: str) -> str:
    return sh(f"docker inspect --format={{{{.Image}}}} squadops-{service}", check=False)[7:19]


def named_services(cfg: SetConfig) -> tuple[str, ...]:
    """The services this set's identity is read from: the deploy's, plus any solo service the
    config names by pinning its image or probing it (the 1.8.1 window's `han`)."""
    extra = {c.service for c in cfg.loaded_checks} | set(cfg.frozen_image_ids)
    return (*DEPLOY_SERVICES, *(s for s in SOLO_SERVICES if s in extra))


def set_agent_services(cfg: SetConfig) -> tuple[str, ...]:
    """The agent containers this set's work can run in: its named services minus the API."""
    return tuple(s for s in named_services(cfg) if s != "runtime-api")


def deploy_identity(cfg: SetConfig) -> dict[str, str]:
    ids = {s: image_id(s) for s in named_services(cfg)}
    ids["head"] = sh(f"git -C {REPO} rev-parse --short HEAD")
    for check in cfg.loaded_checks:
        # A failed check must say WHY: an ImportError here is the "rebuild exited 0 with
        # stale images" signal, and an empty string reads as "nothing to report". Preflight
        # is what makes anyone act on it — see its unrunnable-probe guard.
        proc = subprocess.run(
            ["docker", "exec", f"squadops-{check.service}", "python", "-c", check.source],
            capture_output=True,
            text=True,
        )
        err = (proc.stderr or "").strip().splitlines()
        ids[f"{check.name}:loaded"] = (
            proc.stdout.strip()
            if proc.returncode == 0
            else (f"ERROR: {err[-1] if err else f'exit {proc.returncode}'}")
        )
    return ids


# ---------------------------------------------------------------------------
# Preflight — §2.6 and the freeze, at EVERY launch
# ---------------------------------------------------------------------------


def loaded_check_evidence(identity: Mapping[str, str]) -> dict[str, dict]:
    """The deploy identity's probes in the vocabulary, keyed by probe name (#1425, #1445).

    In the raw identity an errored probe and an answered one are indistinguishable — both
    are a string beside the service. Here a probe that could not run is ``unaskable`` with
    the error as its reason, an empty answer with exit 0 is ``asked_none``, and anything
    else is ``observed``.
    """
    out: dict[str, dict] = {}
    for key, answer in sorted(identity.items()):
        if not key.endswith(":loaded"):
            continue
        name = key.removesuffix(":loaded")
        if answer.startswith("ERROR:"):
            reason = unaskable_reason(
                f"probe_could_not_run:{answer.removeprefix('ERROR:').strip()}"
            )
            out[name] = Evidence.unaskable(reason).record()
        else:
            out[name] = Evidence.of(answer).record()
    return out


def loaded_check_problems(identity: dict[str, str]) -> list[str]:
    """Preflight problems for the probes in a deploy identity that could not RUN — the
    ``unaskable`` probes of ``loaded_check_evidence``."""
    unrun = sorted(
        name
        for name, ev in loaded_check_evidence(identity).items()
        if Evidence.read(ev).state == UNASKABLE
    )
    if not unrun:
        return []
    detail = "; ".join(f"{k}:loaded -> {identity[f'{k}:loaded']}" for k in unrun)
    return [
        f"§7 LOADED CHECK DID NOT RUN ({len(unrun)}): {detail} — the surface it asks about "
        "is unverified on this deploy"
    ]


def framework_drift_problems(cfg: SetConfig) -> list[str]:
    """Problems when the DEPLOY's framework code and the INSTRUMENT's have diverged.

    The driver does not only report: it imports `squadops` modules to compute P0 and B1,
    reconstructing what the framework should have produced and comparing. Those imports
    resolve against the driver's own tree, never the deployed images — so a framework
    change landing on main after the deploy would have the instrument judge a roll against
    logic the system never ran, and nothing in the record would look wrong.

    `frozen_deploy_commit` exists to make that checkable instead of assumed; before this it
    was typed and never read. Docs and driver changes are free, which is what lets an
    instrument fix land mid-set without a rebuild — `src/` and `adapters/` are not.
    """
    if not cfg.frozen_deploy_commit:
        return [
            "counting roll with no frozen_deploy_commit — the framework-drift check cannot "
            "run, and the driver imports squadops modules to judge P0 and B1"
        ]
    # An unresolvable ref must not read as "no drift": `sh(check=False)` returns empty
    # stdout on failure, which is exactly the shape of a clean diff.
    if not sh(
        f"git -C {REPO} rev-parse --verify --quiet {cfg.frozen_deploy_commit}^{{commit}}",
        check=False,
    ):
        return [
            f"frozen_deploy_commit {cfg.frozen_deploy_commit} does not resolve in the driver's "
            "tree — the framework-drift check could not run, which is not the same as passing"
        ]
    changed = sh(
        f"git -C {REPO} diff --name-only {cfg.frozen_deploy_commit}..HEAD -- src/ adapters/"
    ).splitlines()
    if not changed:
        return []
    shown = ", ".join(changed[:5]) + (f" (+{len(changed) - 5} more)" if len(changed) > 5 else "")
    return [
        f"§7 FRAMEWORK DRIFT: {len(changed)} file(s) under src/ or adapters/ differ between the "
        f"frozen deploy {cfg.frozen_deploy_commit} and the driver at HEAD — {shown}. The driver "
        "imports these to judge P0 and B1; the images do not have them."
    ]


def preflight(cfg: SetConfig, *, counting: bool, identity: dict[str, str]) -> list[str]:
    problems: list[str] = []
    # #1425: three 1.7.4 probes named containers that do not exist and recorded "No such
    # container" through a whole checkpoint pair that was then read as clean. "Loaded, not
    # built" is the only evidence that the deploy carries the code the set claims, so an
    # error here stops the launch rather than riding into the record for someone to notice.
    problems.extend(loaded_check_problems(identity))
    leases = psql("select count(*) from focus_leases where released_at is null;")
    if leases != "0":
        problems.append(f"§2.6: {leases} unreleased focus leases (must be 0) — #529 deadlock risk")
    running = psql("select count(*) from cycle_runs where status='running';")
    if running != "0":
        problems.append(f"§2.6: {running} runs already in flight (the GPU is not shareable)")
    dirty = sh(f"git -C {REPO} status --porcelain")
    if dirty:
        problems.append(f"§7: working tree is dirty ({len(dirty.splitlines())} files)")
    # #1251: a declared emission fault makes the cycle a DIAGNOSTIC. It runs the roll's own
    # path with a deliberate defect in it, which is exactly what makes it useful and exactly
    # what makes its red meaningless as a verdict. Refused for a counting roll, reported for
    # a shakeout, and never silent: an injected red in a counted record would read as the
    # squad failing.
    faults = sorted(declared_fault_names(cfg.overrides))
    if faults and counting:
        problems.append(
            f"§4: the set config declares fault injection ({', '.join(faults)}) — a cycle "
            "with a deliberate fault is a diagnostic and cannot be counted. Run it as a "
            "shakeout, and name the fault beside every readout it produces."
        )
    elif faults:
        log(f"DIAGNOSTIC: this cycle injects fault(s) {', '.join(faults)} — non-counting")
    if not counting:
        return problems
    if not cfg.frozen_image_ids:
        problems.append(
            "counting roll with no frozen_image_ids in the set config — pre-register the deploy first"
        )
    problems.extend(squad_snapshot_problems(cfg))
    problems.extend(framework_drift_problems(cfg))
    # SIP-0108 §4.4: the arms are compared BEFORE either is observed. A substrate that
    # drifted after the first roll cannot be undone, so this refuses the launch.
    problems.extend(comparison_problems(cfg))
    for service, expected in cfg.frozen_image_ids.items():
        actual = image_id(service)
        if actual != expected:
            problems.append(
                f"§7 DEPLOY CHANGED: squadops-{service} is image {actual or '?'}, the set is "
                f"frozen on {expected}. A rebuild mid-set voids comparability."
            )
    head = sh(f"git -C {REPO} rev-parse --short HEAD")
    if cfg.head_pin.exists():
        pinned = cfg.head_pin.read_text().strip()
        if head != pinned:
            problems.append(
                f"§7 MERGE DURING THE SET: HEAD is {head}, pinned at {pinned} when roll 1 launched. "
                "Abort and re-register rather than continuing."
            )
    else:
        log(f"pinning HEAD at {head} — §7 binds from here")
    return problems


def _role_by_task_type() -> dict[str, str]:
    """Every dispatched task type and the role that runs it, from the framework's own tables.

    The union of the step tables, the correction steps and the repair steps — never a guess
    from a task type's namespace. A type no table names has no role here and is reported as
    such, which is what makes a missing effective cap a NAMED mismatch rather than a gap.
    """
    from squadops.cycles import task_plan as tp

    pairs: dict[str, str] = {}
    for name in dir(tp):
        if name.endswith("TASK_STEPS"):
            for task_type, role in getattr(tp, name):
                pairs[str(task_type)] = role
    for task_type, role in tp.CORRECTION_STEP_TASKS.values():
        pairs[str(task_type)] = role
    for steps in tp._REPAIR_STEPS_BY_FAILED_TASK_TYPE.values():
        for task_type, role in steps:
            pairs[str(task_type)] = role
    return pairs


#: What a task type's effective cap reads when the deploy declares no override for the role
#: that runs it. A NAMED value, present in both arms' maps, so "no override" on one side and
#: 12288 on the other is a mismatch the comparison can see rather than a key one map lacks.
CAP_DEFAULT = "default"
#: …and when no table names a role for the type at all.
CAP_NO_ROLE = "no_role_declared"


def effective_caps_by_task_type(profile: dict) -> dict[str, object]:
    """Each dispatched task type's effective completion cap under *profile* (#1619).

    Per-call caps are AGENT-level overrides, not task-type scoped (SIP-0108 §4.4), so the
    effective cap for a task type is the cap of whichever agent serves the role that runs it.
    A one-agent arm therefore has one cap for every type, and the squad has one per member —
    which is why #1619's resolution 1 flattens `full-38`'s members to a single value.

    Every type with a declared reasoning level appears in the map, with ``CAP_DEFAULT`` or
    ``CAP_NO_ROLE`` where there is nothing to read. An omitted key cannot be compared.
    """
    from squadops.capabilities.reasoning_policy import REASONING_BY_TASK_TYPE

    cap_by_role: dict[str, object] = {}
    for agent in profile.get("agents", []):
        if not agent.get("enabled", True):
            continue
        cap = (agent.get("config_overrides") or {}).get("max_completion_tokens", CAP_DEFAULT)
        for role in agent.get("serves_roles") or [agent.get("role")]:
            cap_by_role[str(role)] = cap
    roles = _role_by_task_type()
    out: dict[str, object] = {}
    for task_type in sorted(str(t) for t in REASONING_BY_TASK_TYPE):
        role = roles.get(task_type)
        out[task_type] = CAP_NO_ROLE if role is None else cap_by_role.get(role, CAP_DEFAULT)
    return out


#: The grant family each producer namespace draws, as ``scaffold_enforcement`` selects it.
#: Read from the same rule rather than copied: a namespace that gains a grant there and not
#: here would make the arms read equal on an authority that had changed.
def effective_task_authority() -> dict[str, str]:
    """Each dispatched task type's write-grant family, derived from the task alone.

    A task type outside the three producer namespaces authors under no scaffold grant, which
    is a NAMED value (``none``) and not an absent key — two maps cannot disagree about a key
    neither has.
    """
    import inspect

    from squadops.capabilities.reasoning_policy import REASONING_BY_TASK_TYPE
    from squadops.cycles import scaffold_enforcement

    source = inspect.getsource(scaffold_enforcement)
    families = dict(re.findall(r'"(\w+)": (WriteGrant\.\w+)', source))
    return {
        str(t): families.get(str(t).partition(".")[0], "none")
        for t in sorted(str(x) for x in REASONING_BY_TASK_TYPE)
    }


def arm_substrate(cfg: SetConfig) -> dict:
    """What a comparison arm holds equal, read from the deploy rather than declared.

    SIP-0108 §4.4: the arms differ ONLY by the reasoning organization. Everything else is
    held equal, and "the comparison refuses to run if either arm's effective grants for a task
    type differ" — so the equality is checked, not asserted in prose.

    Read through the API and the framework's own declarations, not from this tree's config
    files: the arms run on a deploy, and a comparison that compared two YAML files would pass
    while the deploy served something else.
    """
    from squadops.capabilities.reasoning_policy import REASONING_BY_TASK_TYPE

    login()
    served = json.loads(
        sh(f"{SQUADOPS} --format json squad-profiles show {shlex.quote(cfg.squad_profile)}")
    )
    request = json.loads(
        sh(f"{SQUADOPS} --format json request-profiles show {shlex.quote(cfg.request_profile)}")
    )
    defaults = request.get("defaults") or {}
    return {
        "model": sorted({str(a.get("model")) for a in served.get("agents", [])}),
        # §4.4: "Authority stays task-scoped. A producer's write grant is derived from the
        # task it performs, never from the agent." The enforcement selects the grant from the
        # task type's own namespace and reads nothing from the profile, so a one-agent arm
        # widens no grant — which is a claim the record should CARRY rather than restate. Read
        # through the same rule the enforcement uses.
        "task_authority": effective_task_authority(),
        # Per-task-type reasoning is declared by the framework, so it is equal by
        # construction — recorded so a record can show that rather than assume it.
        "reasoning_by_task_type": {
            str(k): str(v)
            for k, v in sorted(REASONING_BY_TASK_TYPE.items(), key=lambda kv: str(kv[0]))
        },
        # #1619: the EFFECTIVE cap per task type, with a named value where there is no
        # override — never an absent key, which two maps cannot disagree about.
        "effective_caps_by_task_type": effective_caps_by_task_type(served),
        # The execution envelope §4.4 holds equal: the run budget and the loop's own budgets.
        "execution_envelope": {
            key: defaults.get(key)
            for key in (
                "time_budget_seconds",
                "max_correction_attempts",
                "max_self_eval_passes",
                "max_task_retries",
                "max_task_seconds",
                "required_checks",
            )
        },
        "request_profile": cfg.request_profile,
    }


def runtime_topology(services: Sequence[str] = DEPLOY_SERVICES) -> dict:
    """Which agent containers are up, as a substrate fact (plan §4.3).

    "All relevant containers remain running for both arms; only the designated arm receives
    work." A comparison where one arm ran with six agent processes resident and the other with
    one is a comparison of two memory envelopes on a single-GPU box, whatever the record says
    about the organization. ``services`` is every service either arm names, so a window whose
    solo arm names `han` requires all eight up, not seven.
    """
    return {
        service: (image_id(service) != "")
        for service in sorted(s for s in services if s not in ("runtime-api",))
    }


def run_state_isolation_problems(cfg: SetConfig) -> list[str]:
    """Nothing is in flight and no lease is held before an arm's roll launches (plan §4.3).

    Run-state isolation is what lets the record show that an arm could not learn anything from
    the arm that ran before it. A cycle already running, or a focus lease still held, means the
    previous roll's state is live while this one starts.
    """
    problems: list[str] = []
    running = psql("select count(*) from cycle_runs where status='running';")
    if running != "0":
        problems.append(
            f"§4.3 run-state isolation: {running} run(s) already in flight — an arm must start "
            "from a quiet box, or the pair is not a matched trial"
        )
    leases = psql("select count(*) from focus_leases where released_at is null;")
    if leases != "0":
        problems.append(
            f"§4.3 run-state isolation: {leases} unreleased focus lease(s) — the previous "
            "roll's state is still live"
        )
    return problems


def arm_substrate_problems(one: SetConfig, other: SetConfig) -> list[str]:
    """Refuse a comparison whose arms differ by anything but the reasoning organization.

    Each difference is named with both readings: a comparison that fails closed with "the
    substrate differs" tells the reader nothing about which half to fix. Every key §4.4 and
    plan §4.3 hold equal is compared, and a per-task-type map is diffed key by key so the
    message names the types rather than two dictionaries.
    """
    problems: list[str] = []
    a, b = arm_substrate(one), arm_substrate(other)
    if one.arm and one.arm == other.arm:
        problems.append(
            f"§4.4: both configs declare the arm {one.arm!r} — a comparison needs two arms"
        )
    per_type = (
        ("effective_caps_by_task_type", "effective per-task-type completion cap"),
        ("reasoning_by_task_type", "per-task-type reasoning level"),
        ("task_authority", "effective task authority (write grants)"),
    )
    for key, label in per_type:
        differing = sorted(t for t in set(a[key]) | set(b[key]) if a[key].get(t) != b[key].get(t))
        if differing:
            shown = ", ".join(
                f"{t}: {one.arm or one.name}={a[key].get(t)!r} vs "
                f"{other.arm or other.name}={b[key].get(t)!r}"
                for t in differing[:4]
            )
            more = f" (+{len(differing) - 4} more)" if len(differing) > 4 else ""
            problems.append(f"§4.4 SUBSTRATE DIFFERS on {label} — {shown}{more}")
    for key, label in (
        ("model", "model and serving"),
        ("execution_envelope", "execution envelope"),
    ):
        if a[key] != b[key]:
            problems.append(
                f"§4.4 SUBSTRATE DIFFERS on {label}: {one.arm or one.name} reads {a[key]}, "
                f"{other.arm or other.name} reads {b[key]}. The arms may differ only by the "
                "reasoning organization; anything else makes the comparison unreadable."
            )
    return problems


def comparison_problems(cfg: SetConfig) -> list[str]:
    """The comparison gate, run BEFORE either arm is observed (SIP-0108 §4.4, plan §4.3).

    A set that names a counterpart is one arm of a pair, and a pair may differ only by the
    reasoning organization. Everything else §4.4 and §4.3 hold equal is read from the deploy
    here — effective task authority, per-task-type caps and reasoning levels, the execution
    envelope, run-state isolation and runtime topology — and any difference refuses the launch.
    A comparison whose substrate drifted is not a comparison, and after the first roll is
    observed there is nothing to do about it.
    """
    if not cfg.compare_with:
        return []
    # Beside this config, which is where every set config lives.
    other_path = SET_CONFIG_DIR / cfg.compare_with
    if not other_path.exists():
        return [
            f"§4.4: compare_with names {cfg.compare_with}, which is not a set config in "
            f"{other_path.parent}"
        ]
    return pair_comparison_problems(cfg, load_set_config(other_path))


def pair_comparison_problems(cfg: SetConfig, other: SetConfig) -> list[str]:
    """The comparison gate over two LOADED configs — the objects the caller holds, never a
    counterpart re-read from disk by name. ``cmd_window`` calls this with the two supplied
    configs before pair 1's first roll, so changing any evaluated field of either supplied
    config changes what the gate sees; the per-launch gate loads its counterpart and delegates
    here (the #1645 review's acceptance condition)."""
    problems = arm_substrate_problems(cfg, other)
    problems.extend(run_state_isolation_problems(cfg))
    topology = runtime_topology(sorted(set(named_services(cfg)) | set(named_services(other))))
    absent = sorted(svc for svc, up in topology.items() if not up)
    if absent:
        problems.append(
            f"§4.3 runtime topology: agent container(s) {absent} are not up. All relevant "
            "containers stay running for BOTH arms and only the designated arm receives work — "
            "an arm measured against a different memory envelope on a single-GPU box is a "
            "comparison of envelopes, not of organizations."
        )
    return problems


#: The arm name whose rolls must prove the §10i absences. One constant, so the gate and a
#: set config cannot disagree about which arm is the solo one.
SOLO_ARM = "solo"

#: What a Solo roll must NOT have produced (SIP-0108 §10i item 6): "Han never saw it" as a
#: fact the record proves, rather than a property of a profile nobody re-read.
_SOLO_FORBIDDEN_ARTIFACTS = (
    "failure_analysis.md",
    "correction_decision.md",
)


def solo_absence_problems(cfg: SetConfig, cycle_id: str, run_id: str) -> list[str]:
    """The per-roll preflight for a solo arm — the three absences, read from the vault.

    §10i item 6. A framing document, a failure analysis or a correction decision stored for a
    Solo run means the arm did not run without them, whatever the profile declared. The record
    proves the absence rather than inheriting it from a config.
    """
    problems: list[str] = []
    for art in artifact_dirs(cfg, cycle_id, run_id):
        m = _metadata(art)
        if not m:
            continue
        filename = str(m.get("filename") or "")
        if filename in _SOLO_FORBIDDEN_ARTIFACTS:
            problems.append(
                f"§10i: solo arm stored {filename} ({art.name}) — the arm is defined by running "
                "correction without the analyzer and the lead, so this roll did not run the arm"
            )
        if str((m.get("metadata") or {}).get("producing_task_type", "")).startswith("governance."):
            problems.append(
                f"§10i: solo arm stored a governance artifact ({filename}, {art.name}) — "
                "framing roles are the squad arm's, not this one's"
            )
    return problems


def live_squad_snapshot(profile_id: str) -> str:
    """The squad snapshot a cycle created now would carry, read from the runtime API.

    The same hash the runtime stamps on a cycle (``compute_profile_snapshot_hash`` over the
    profile it resolves), computed from the profile the API serves, so it reads Postgres or the
    YAML file, whichever the deploy runs.
    """
    from squadops.cycles.lifecycle import compute_profile_snapshot_hash
    from squadops.cycles.models import AgentProfileEntry, SquadProfile

    login()
    data = json.loads(sh(f"{SQUADOPS} --format json squad-profiles show {shlex.quote(profile_id)}"))
    profile = SquadProfile(
        profile_id=data["profile_id"],
        name=data.get("name", ""),
        description=data.get("description", ""),
        version=int(data["version"]),
        agents=tuple(
            AgentProfileEntry(
                agent_id=a["agent_id"],
                role=a["role"],
                model=a["model"],
                enabled=bool(a["enabled"]),
                config_overrides=dict(a.get("config_overrides") or {}),
                # The declared role → agent map is part of the snapshot identity since
                # 1.8.1 (SIP-0108 §10i item 1). Omitting it here would hash an empty map
                # against the runtime's real one, and every counting roll would refuse to
                # launch reading "SQUAD PROFILE CHANGED" on a profile nobody touched.
                serves_roles=tuple(a.get("serves_roles") or ()),
            )
            for a in data["agents"]
        ),
        created_at=datetime.now(UTC),
    )
    return compute_profile_snapshot_hash(profile)


def squad_snapshot_problems(cfg: SetConfig) -> list[str]:
    """A counting roll refuses to launch on a squad profile the set is not frozen on (#1568).

    The frozen image ids made the squad immutable while profiles lived in the image's YAML.
    Since #1568 the deploy reads them from Postgres, where the API can edit one mid-set with
    no rebuild. So a counting set pins the snapshot, and the live profile is compared
    **before** the roll launches. The post-run comparison in ``_run_cycle`` only stopped the
    set after a roll had spent its budget on the wrong squad.
    """
    prefix = cfg.expected_squad_snapshot_prefix
    if not prefix:
        return [
            "counting roll with no expected_squad_snapshot_prefix in the set config — squad "
            "profiles are editable data (#1568); pin the snapshot the set is frozen on"
        ]
    try:
        live = live_squad_snapshot(cfg.squad_profile)
    except (SystemExit, ValueError, KeyError) as exc:
        return [f"§7 could not read the live snapshot of {cfg.squad_profile}: {exc}"]
    if identity_mismatch(prefix, live):
        return [
            f"§7 SQUAD PROFILE CHANGED: {cfg.squad_profile} snapshots to {live[:16]}, the set is "
            f"frozen on {prefix}. An edit to the profile mid-set voids comparability."
        ]
    return []


# ---------------------------------------------------------------------------
# Launch and drive
# ---------------------------------------------------------------------------


def launch(cfg: SetConfig, notes: str) -> tuple[str, str, str]:
    login()
    sets = " ".join(f"--set {k}={v}" for k, v in cfg.overrides.items())
    out = sh(
        f"{SQUADOPS} cycles create {cfg.project} --squad-profile {cfg.squad_profile} "
        f"--request-profile {cfg.request_profile} {sets} --notes {shlex.quote(notes)}"
    )
    cyc = re.search(r"(cyc_[0-9a-f]+)", out)
    run = re.search(r"(run_[0-9a-f]+)", out)
    chash = re.search(r"hash:\s*([0-9a-f]+)", out)
    if not (cyc and run):
        raise SystemExit(f"could not parse create output:\n{out}")
    return cyc.group(1), run.group(1), (chash.group(1) if chash else "")


def gate_pending(cycle_id: str) -> str | None:
    """The framing run awaiting a decision, if any. Keys on the WAITING state."""
    got = psql(
        f"select r.run_id from cycle_runs r where r.cycle_id='{cycle_id}' and r.workload_type='framing' "
        "and r.status='completed' and not exists "
        "(select 1 from cycle_gate_decisions g where g.run_id=r.run_id);"
    )
    return got or None


def terminal_impl(cycle_id: str) -> str | None:
    status = psql(
        f"select status from cycle_runs where cycle_id='{cycle_id}' and workload_type='implementation' "
        "order by run_number desc limit 1;"
    )
    active = psql(
        f"select count(*) from cycle_runs where cycle_id='{cycle_id}' and status='running';"
    )
    return status if status and status != "running" and active == "0" else None


def ended_without_implementation(cycle_id: str) -> str | None:
    """``"<status>: <reason>"`` once the cycle has stopped without ever creating an
    implementation run, else None.

    **Why this exists (#1168).** ``terminal_impl`` only ever reports on an implementation
    run. A cycle whose framing fails never creates one, so it returned None on every poll
    and ``drive`` span for the full four-hour ``MAX_WAIT_S`` — no record written, the
    watcher never woken, and the next set's preflight blocked behind a process that would
    not exit. Measured on the 1.7.0 Atlas shakeout ``cyc_6e068cdd7de0`` (2026-08-28,
    framing failed at ``governance.prepare_plan_authoring_brief``); killed by hand.

    Named for the condition rather than for ``framing_failed`` as #1168 sketched it,
    because a framing that is *cancelled* reaches this state too and did so 32 times in
    the run table — calling that a failure would put a wrong word in a banked record.

    The three clauses are ordered cheapest-first and each is load-bearing: an
    implementation run existing at all means ``terminal_impl`` owns the answer; anything
    running or queued means the cycle may still create one; and only then is a run that
    ended ``failed``/``cancelled`` the reason it never will. A framing sitting
    ``completed`` at an open gate matches none of them, so the gate loop keeps its turn.
    """
    if (
        psql(
            f"select count(*) from cycle_runs where cycle_id='{cycle_id}' "
            "and workload_type='implementation';"
        )
        != "0"
    ):
        return None
    if (
        psql(
            f"select count(*) from cycle_runs where cycle_id='{cycle_id}' "
            "and status in ('running','queued');"
        )
        != "0"
    ):
        return None
    return (
        psql(
            "select status||': '||coalesce(nullif(failure_reason,''),'no failure_reason recorded') "
            f"from cycle_runs where cycle_id='{cycle_id}' and status in ('failed','cancelled') "
            "order by run_number desc limit 1;"
        )
        or None
    )


def drive(cfg: SetConfig, cycle_id: str) -> str | None:
    """Approve the gate (§6 constant, verbatim) when it opens; return once the cycle can
    produce nothing further. Returns the reason when it ended with no implementation run
    (#1168), None on the ordinary path."""
    started = time.time()
    approved: set[str] = set()
    while time.time() - started < MAX_WAIT_S:
        pending = gate_pending(cycle_id)
        if pending and pending not in approved:
            log(f"gate open on {pending} — applying the §6 constant")
            login()
            sh(
                f"{SQUADOPS} runs gate {cfg.project} {cycle_id} {pending} {cfg.gate_name} "
                f"--approve --as-agent --notes {shlex.quote(cfg.gate_notes)}"
            )
            approved.add(pending)
            continue
        done = terminal_impl(cycle_id)
        if done:
            log(f"implementation run terminal: {done}")
            return None
        red = ended_without_implementation(cycle_id)
        if red:
            log(f"cycle ended with no implementation run — {red}")
            return red
        time.sleep(POLL_S)
    raise SystemExit(f"driver timed out after {MAX_WAIT_S}s on {cycle_id}")


# ---------------------------------------------------------------------------
# Collect — the per-roll record
# ---------------------------------------------------------------------------


def artifact_dirs(cfg: SetConfig, cycle_id: str, run_id: str) -> list[Path]:
    root = REPO / "data" / "artifacts" / cfg.project / cycle_id / run_id
    return sorted(root.glob("art_*")) if root.exists() else []


def _metadata(art: Path) -> dict | None:
    meta = art / "metadata.json"
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text())
    except (OSError, ValueError):
        return None


def artifact_text(
    cfg: SetConfig,
    cycle_id: str,
    run_id: str,
    filename: str,
    producing_task_type: str | None = None,
) -> str | None:
    for art in artifact_dirs(cfg, cycle_id, run_id):
        m = _metadata(art)
        if not m or m.get("filename") != filename:
            continue
        if (
            producing_task_type
            and (m.get("metadata") or {}).get("producing_task_type") != producing_task_type
        ):
            continue
        try:
            return (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            return None
    return None


def parse_run_rows(text: str) -> list[dict]:
    runs = []
    for r in text.splitlines():
        num, wtype, status, reason, run_id, secs = (r.split("|") + [""] * 6)[:6]
        if not num:
            continue
        runs.append(
            {
                "run_number": int(num),
                "workload": wtype,
                "status": status,
                "failure_reason": reason,
                "run_id": run_id,
                "seconds": int(secs or 0),
            }
        )
    return runs


#: The task types whose stored artifacts are the qa suites B1 reads (strings at the
#: boundary, #559 — these are the values ``producing_task_type`` carries in the vault).
_QA_SUITE_TASKS = ("qa.test", "qa.test_repair")


def _is_suite_name(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    return (
        base.endswith((".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".spec.ts", ".spec.tsx"))
        or (base.startswith("test_") and base.endswith(".py"))
        or base.endswith("_test.py")
    )


def _stored_qa_suites(cfg: SetConfig, cycle_id: str, run_id: str) -> list[tuple[str, str]]:
    """Every stored version of every qa-authored suite in the run — the denominator B1
    reports, so a held B1 says how many suites it held over."""
    out: list[tuple[str, str]] = []
    for art in artifact_dirs(cfg, cycle_id, run_id):
        m = _metadata(art)
        if not m:
            continue
        if (m.get("metadata") or {}).get("producing_task_type") not in _QA_SUITE_TASKS:
            continue
        name = str(m.get("filename") or "")
        if not _is_suite_name(name):
            continue
        try:
            out.append((name, (REPO / m["vault_uri"]).read_text()))
        except (OSError, KeyError):
            continue
    return out


def _table_forms(entity: str) -> list[tuple[str, re.Pattern[str]]]:
    """The forms a suite uses to name an entity's store table, per stack: the React
    scaffold's ``backend/store.py`` exposes ``<snake>_store`` per root entity, the Next.js
    scaffold's ``lib/store.ts`` exposes ``TABLES.<Entity>`` (also ``TABLES['Entity']``).
    ``_snake`` is the store's own naming rule, imported so the two cannot drift."""
    from squadops.capabilities.stack_fastapi_react import _snake

    escaped = re.escape(entity)
    return [
        (
            f"TABLES.{entity}",
            re.compile(rf"\bTABLES\s*(?:\.\s*{escaped}\b|\[\s*['\"]{escaped}['\"]\s*\])"),
        ),
        (f"{_snake(entity)}_store", re.compile(rf"\b{re.escape(_snake(entity))}_store\b")),
    ]


def non_root_fixture_tables(manifest_text: str | None, suites: list[tuple[str, str]]) -> dict:
    """B1 as a field (1.7.4 plan §3.1; #1087/#1112) — pure, so the read is testable.

    B1: no stored qa suite names a fixture table for a non-root entity. The manifest says
    which entities a correct application persists as rows of their own
    (``root_persisted_entities`` — the rule the store was generated by, imported rather
    than restated); every declared entity that is not one of those is a shape, and a suite
    that inserts into or asserts on its table (1.6.3: ``expect(all(TABLES.Participant))``)
    is asserting on a table no correct implementation touches. ``mentions`` empty means B1
    held over ``suites_read`` suites; a missing manifest is a refusal, not a hold.
    """
    if not manifest_text:
        return {
            "suites_read": len(suites),
            "root_entities": None,
            "non_root_entities": None,
            "mentions": None,
            "refused": "no interface_manifest.yaml stored for the run",
        }
    from squadops.capabilities.scaffold import InterfaceManifest, root_persisted_entities

    manifest = InterfaceManifest.from_yaml(manifest_text)
    declared = [e.name for e in (getattr(manifest, "entities", ()) or ())]
    roots = list(root_persisted_entities(manifest))
    non_root = [e for e in declared if e not in roots]
    mentions: list[dict] = []
    for name, text in suites:
        for entity in non_root:
            for form, pattern in _table_forms(entity):
                if pattern.search(text):
                    mentions.append({"suite": name, "entity": entity, "form": form})
    return {
        "suites_read": len(suites),
        "root_entities": roots,
        "non_root_entities": non_root,
        "mentions": mentions,
    }


def completed_framing_run(cycle_id: str) -> str | None:
    """The framing run that was APPROVED — never `head -1` (a rejected framing's contract
    once produced a spurious audit FAIL against endpoints the deliverable never had)."""
    return (
        psql(
            "select g.run_id from cycle_gate_decisions g join cycle_runs r on r.run_id=g.run_id "
            f"where r.cycle_id='{cycle_id}' and g.decision='approved' order by g.decided_at desc limit 1;"
        )
        or None
    )


def _criteria_unverified(summary: dict) -> list[str]:
    """The contract criteria the run did not verify, by name.

    The framework derives this on its own summary (`criteria_unverified`, #945); the
    driver reads the stored JSON, so it derives the same subtraction here rather than
    reporting a count a reader cannot resolve to names.
    """
    verified = set(summary.get("criteria_verified") or [])
    return [c for c in (summary.get("criteria_total") or []) if c not in verified]


def emissions_from_stamps(banked: list[dict]) -> int | None:
    """The EMISSION count behind #971's banked artifacts, or ``None`` when not derivable.

    #1436: a failed emission's artifacts carry ``attempt`` since 1.7.5, so emissions are
    ``(task_id, attempt)`` groups. Any artifact without the stamp (every record through
    1.7.4) makes the count underivable — ``None``, which the registry turns into
    ``unaskable`` rather than a number. Never inferred from timestamps: round 2 of the
    1.7.4 line banked three artifacts 42 ms apart that were ONE emission and two 6.3 s
    apart that were TWO attempts, and no clustering rule separates those on a slow write.
    """
    if any("attempt" not in m for m in banked):
        return None
    return len({(m.get("task_id"), int(m["attempt"])) for m in banked})


def collect(cfg: SetConfig, cycle_id: str) -> dict:
    runs = parse_run_rows(
        psql(
            "select run_number||'|'||workload_type||'|'||status||'|'||coalesce(failure_reason,'')||'|'"
            "||run_id||'|'||extract(epoch from (finished_at-started_at))::int "
            f"from cycle_runs where cycle_id='{cycle_id}' order by run_number;"
        )
    )
    impl = next((r for r in reversed(runs) if r["workload"] == "implementation"), None)
    framings = [r for r in runs if r["workload"] == "framing"]
    gates = psql(
        "select g.gate_name||'|'||g.decision||'|'||g.decided_by from cycle_gate_decisions g "
        f"join cycle_runs r on r.run_id=g.run_id where r.cycle_id='{cycle_id}' order by g.decided_at;"
    ).splitlines()
    summary: dict = {}
    corrections = 0
    # #1431 was a LABEL defect and is fixed as one: this counts the artifacts #971 banks,
    # and the readout now says so. Grouping them into an emission count was tried and
    # reverted (#1436) — `task_id` is the only key the banked metadata carries, and two
    # failed ATTEMPTS of one task share it. Round 2's Next.js half is the counter-example:
    # two attempts 6.3 s apart, each banking one `build_warnings.md`, collapsed to 1, while
    # the React half's three artifacts 42 ms apart were correctly one. Clustering on
    # timestamps would separate today's data and fail silently on a slow emission. The
    # emission count is not derivable from what is stored; stamping the attempt at the
    # banking seam is #1436.
    failed_emission_artifacts = 0
    banked_metadata: list[dict] = []
    if impl:
        raw = psql(
            "select summary from run_verification_summaries where run_id='{}';".format(
                impl["run_id"]
            )
        )
        try:
            summary = json.loads(raw) if raw else {}
        except ValueError:
            summary = {}
        for art in artifact_dirs(cfg, cycle_id, impl["run_id"]):
            m = _metadata(art)
            if not m:
                continue
            if m.get("filename") == "correction_decision.md":
                corrections += 1
            if (m.get("metadata") or {}).get("emission_status") == "failed":
                failed_emission_artifacts += 1
                banked_metadata.append(m.get("metadata") or {})
    snapshot = psql(
        f"select coalesce(squad_profile_snapshot_ref,'') from cycle_registry where cycle_id='{cycle_id}';"
    )
    lineage = cycle_lineage(
        psql(
            "select coalesce(to_jsonb(c)->>'framework_version','')||'|'||"
            "coalesce(to_jsonb(c)->>'framework_git_sha','')||'|'||"
            "coalesce(to_jsonb(c)->>'request_profile','') "
            f"from cycle_registry c where c.cycle_id='{cycle_id}';"
        )
    )
    emissions = emissions_from_stamps(banked_metadata)
    context = {
        "no_implementation_run": impl is None,
        # #1436: without the attempt stamp two failed ATTEMPTS of one task are
        # indistinguishable from one attempt that banked two files, so the emission count
        # is not derivable — unaskable, never an inferred number.
        "no_attempt_stamp": emissions is None,
    }
    return {
        "cycle_id": cycle_id,
        "squad_profile_snapshot_ref": snapshot,
        "lineage": lineage,
        # SIP-0108 §4.1: the projection over the durable record, rendered rather than left
        # recomputable (the 1.8.0 evidence gate's gap, §10c.6).
        "cycle_assessment": cycle_assessment(cfg, cycle_id),
        "runs": runs,
        "gate_decisions": [
            dict(zip(("gate", "decision", "decided_by"), g.split("|"), strict=False)) for g in gates
        ],
        "framing_runs": len(framings),
        "framing_rerolls": max(0, len(framings) - 1),
        # #1445: all three are read from the implementation run's stored artifacts, so
        # without one they are unaskable — a record that read "0 correction rounds" for a
        # cycle that never built anything was reporting an absence as a fact.
        "correction_rounds": evidence_for("correction_rounds", corrections, context).record(),
        "failed_emission_artifacts_banked": evidence_for(
            "failed_emission_artifacts_banked", failed_emission_artifacts, context
        ).record(),
        # #1436: artifacts and emissions are separate numbers, both true. The emission count
        # is unaskable on every record whose banked artifacts predate the attempt stamp.
        "failed_emissions_banked": evidence_for(
            "failed_emissions_banked", emissions, context
        ).record(),
        "verdict": summary.get("verdict"),
        "failed_checks": summary.get("failed", []),
        "criteria_total": len(summary.get("criteria_total", []) or []),
        "criteria_verified": len(summary.get("criteria_verified", []) or []),
        "criteria_unevidenced": summary.get("criteria_unevidenced", []) or [],
        # Named, never left to a subtraction the reader has to do (#945/#1021, applied
        # to the record). The React checkpoint on deploy B rendered "21 / 24" beside an
        # empty unevidenced list: the three `vc-view-compiles-*` criteria had produced
        # evidence and were not credited, and the record could not say which three or
        # why. `unverified` is the shortfall; `adverse` is the half that produced a row.
        "criteria_unverified": _criteria_unverified(summary),
        "criteria_adverse": [
            c
            for c in _criteria_unverified(summary)
            if c not in set(summary.get("criteria_unevidenced") or [])
        ],
        "wall_clock_seconds": sum(r["seconds"] for r in runs),
        "impl_run_id": impl["run_id"] if impl else None,
    }


def cycle_assessment(cfg: SetConfig, cycle_id: str) -> dict:
    """The cycle's ``CycleAssessment``, read through the product's own reader (SIP-0108 §4.1).

    The 1.8.0 evidence gate asked that every counted record CARRY an assessment. It was met by
    recomputing the projection by hand over the nine counted cycles, because the durable stores
    carried its inputs and nothing printed it (1.8.0 pre-registration §10c.6). The record now
    carries it.

    Read through ``squadops cycles assess`` rather than by importing the projection: the driver
    reads a deployed container's answer, not this tree's module, exactly as
    ``live_squad_snapshot`` does. A driver newer than its deploy therefore reads the assessment
    as unaskable rather than computing one the deploy never produced.
    """
    reason = (
        "the deploy served no assessment for this cycle — a runtime API older than the "
        "`cycles assess` route, a CLI that has no such command, or a cycle it cannot read"
    )
    try:
        # #1654: read at the END of a roll, an hour after launch; the token lives minutes.
        # Without a fresh login the CLI fails and the record blamed the deploy.
        login()
        raw = sh(
            f"{SQUADOPS} --format json cycles assess "
            f"{shlex.quote(cfg.project)} {shlex.quote(cycle_id)}",
            check=False,
        )
        data = json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError, SystemExit) as exc:
        # A driver older or newer than its deploy reads the assessment as UNASKABLE rather
        # than computing one the deploy never produced, or failing the whole record over a
        # reading that is texture (#1445).
        return {"state": "unaskable", "reason": f"{reason} ({type(exc).__name__})"}
    if not isinstance(data, dict) or "cycle_id" not in data:
        return {"state": "unaskable", "reason": reason}
    indicators = {
        dimension: data.get(dimension) or []
        for dimension in ("outcome", "quality", "coordination", "efficiency")
    }
    states: dict[str, int] = {}
    for group in indicators.values():
        for ind in group:
            states[ind.get("state", "?")] = states.get(ind.get("state", "?"), 0) + 1
    return {
        "state": "observed",
        "attribution": (data.get("attribution") or {}).get("primary"),
        "attribution_state": (data.get("attribution") or {}).get("state"),
        "assessment_version": data.get("assessment_version"),
        "attribution_registry_version": data.get("attribution_registry_version"),
        "evidence_identity": data.get("evidence_identity"),
        "assessed_by": data.get("assessor_framework_version"),
        "assessed_at_sha": data.get("assessor_git_sha"),
        # The three-state tally is the reading the gate is about: an assessment whose
        # indicators are mostly unaskable is not an assessed cycle, and a count says so
        # without the reader opening every indicator.
        "indicator_states": states,
        "indicators": indicators,
    }


def cycle_lineage(raw: str) -> dict:
    """The ``lineage`` group from the cycle row's ``version|commit|profile`` (#80).

    Read through ``to_jsonb`` by ``collect`` so a deploy from before migration 1040 answers
    with empty strings instead of failing the query: a driver newer than the deploy it reads
    must still write the record, and say the lineage is unaskable there.
    """
    version, commit, profile = ([*raw.split("|"), "", "", ""])[:3]
    return with_states(
        "lineage",
        {
            "framework_version": version.strip(),
            "framework_git_sha": commit.strip(),
            "request_profile": profile.strip(),
        },
        {"cycle_predates_code_lineage": not version.strip()},
    )


def boot_audit(cfg: SetConfig, cycle_id: str, impl_run: str) -> dict:
    framing = completed_framing_run(cycle_id)
    if not framing:
        return {"ran": False, "reason": "no approved framing run — no contract to audit against"}
    contract = None
    for art in artifact_dirs(cfg, cycle_id, framing):
        m = _metadata(art)
        if m and m.get("filename") == "verification_contract.yaml":
            contract = art / "verification_contract.yaml"
            break
    if contract is None:
        return {"ran": False, "reason": f"no verification_contract.yaml under framing {framing}"}
    log(f"boot audit against the APPROVED framing's contract ({framing})")
    proc = subprocess.run(
        [
            PYTHON,
            "scripts/dev/audit_delivered_app.py",
            cycle_id,
            impl_run,
            "--contract",
            str(contract),
            "--project",
            cfg.project,
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    return audit_outcome(proc.returncode, proc.stdout or proc.stderr, framing)


def audit_outcome(returncode: int, output: str, framing: str) -> dict:
    """The boot audit as the record keeps it — pure. ``detail`` is the verdict line;
    ``failures`` is every FAIL line the audit printed, each carrying the response it
    judged (#1324), so a rejected roll can be root-caused after the app is gone."""
    tail = (output or "").strip().splitlines()
    return {
        "ran": True,
        "passed": returncode == 0,
        "exit_code": returncode,
        "contract_from": framing,
        "detail": tail[-1] if tail else "",
        "failures": [line for line in tail if line.startswith("FAIL")],
    }


# ---------------------------------------------------------------------------
# P0 — the seeded frozen tree against the manifest, per stack, no model in the loop
# ---------------------------------------------------------------------------

Reader = Callable[[str], str | None]


def _p0_nextjs_ts(manifest: Any, seeded: Reader) -> dict:
    from squadops.capabilities.scaffold import root_persisted_entities
    from squadops.capabilities.stack_nextjs_ts import _ts_type

    models = seeded("lib/models.ts") or ""
    store = seeded("lib/store.ts") or ""
    harness = seeded("__tests__/harness.test.ts") or ""
    declared = frozenset(
        [e.name for e in manifest.entities] + [s.name for s in manifest.api.request_shapes]
    )
    expected, mismatches = [], []
    for entity in manifest.entities:
        for f in entity.fields:
            if f.type.strip().lower().startswith("list["):
                want = f"{f.name}{'' if f.required else '?'}: {_ts_type(f.type, declared)}"
                expected.append(want)
                if want not in models:
                    mismatches.append(want)
    roots = list(root_persisted_entities(manifest))
    tables = re.findall(r"^\s+(\w+): '", store, re.M)
    harness_table = (re.findall(r"TABLES\.(\w+)", harness) or [None])[0]
    return {
        "stack": "nextjs_ts",
        "asserted": True,
        "models_expected_collection_lines": expected,
        "models_mismatches": mismatches,
        "p0_models_entity_typed": not mismatches,
        "store_tables": tables,
        "root_persisted_entities": roots,
        "p0_store_root_only": tables == roots,
        "harness_table": harness_table,
        "p0_harness_root": harness_table in roots,
        "passed": not mismatches and tables == roots and harness_table in roots,
    }


def _p0_fullstack_fastapi_react(manifest: Any, seeded: Reader) -> dict:
    """Stack #1's seeded tree against its manifest.

    Asserted: every collection field in ``backend/models.py`` carries the manifest's
    element type (``_py_type`` passes entity names through — the #1096 class cannot
    recur here, and this is where that stays true). Recorded, NOT asserted: any store
    beyond the roots. Since #1087's stack #1 half the expander emits the roots only, so on a
    current deploy ``stores_beyond_roots`` reads ``[]``; on one built before it, the
    per-entity dicts — texture either way, never a verdict.
    """
    from squadops.capabilities.scaffold import root_persisted_entities
    from squadops.capabilities.stack_fastapi_react import _py_type

    models = seeded("backend/models.py") or ""
    store = seeded("backend/store.py") or ""
    expected, mismatches = [], []
    nullable_expected, nullable_mismatches = [], []
    for entity in manifest.entities:
        for f in entity.fields:
            if f.type.strip().lower().startswith("list["):
                want = f"{f.name}: {_py_type(f.type)}"
                expected.append(want)
                if want not in models:
                    mismatches.append(want)
            elif ((not f.required) or (f.has_default and f.default is None)) and not (
                f.has_default and f.default is not None
            ):
                # #1125 (1.6.6 A, prediction R1): an optional field — declared
                # ``required: false`` or ``default: null`` — freezes nullable. The
                # ``str = None`` form pydantic rejects sat under five of six 1.6.5 rolls.
                #
                # A declared NON-NULL default is the exception, and it is the rule's
                # boundary rather than a weakening of it: ``{required: false, default: 0}``
                # renders ``int = 0``, which is what the manifest asked for, and demanding
                # ``int | None = None`` would discard the default. #1125 was about an
                # optional field with NO default; no manifest had produced the other shape
                # until the 1.7.2 shakeout on `e2dff444` (`cyc_9a1acc7623b4`), where
                # ``participant_count: {type: int, required: false, default: 0}`` FALSIFIED
                # P0 against a scaffold that was right. P0 is a carried prediction, so on a
                # counted roll that false positive would have stopped the set.
                want = f"{f.name}: {_py_type(f.type)} | None = None"
                nullable_expected.append(want)
                if want not in models:
                    nullable_mismatches.append(want)
    roots = list(root_persisted_entities(manifest))
    stores = re.findall(r"^(\w+)_store:", store, re.M)
    return {
        "stack": "fullstack_fastapi_react",
        "asserted": True,
        "models_expected_collection_lines": expected,
        "models_mismatches": mismatches,
        "p0_models_entity_typed": not mismatches,
        "models_nullable_expected_lines": nullable_expected,
        "models_nullable_mismatches": nullable_mismatches,
        "p0_optional_fields_nullable": not nullable_mismatches,
        "store_names": stores,
        "root_persisted_entities": roots,
        "stores_beyond_roots": sorted(set(stores) - {_snake(r) for r in roots}),
        "passed": not mismatches and not nullable_mismatches,
    }


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


_P0_CHECKS: dict[str, Callable[[Any, Reader], dict]] = {
    "nextjs_ts": _p0_nextjs_ts,
    "fullstack_fastapi_react": _p0_fullstack_fastapi_react,
}


def p0_checks(stack: str, manifest: Any, seeded: Reader) -> dict:
    """Dispatch the seeded-tree check on the cycle's stack; refuse an unregistered one."""
    check = _P0_CHECKS.get(stack)
    if check is None:
        return {
            "stack": stack,
            "asserted": False,
            "passed": False,
            "refused": f"no P0 check registered for stack {stack!r} — register one, do not skip",
        }
    if manifest is None:
        return {
            "stack": stack,
            "asserted": False,
            "passed": False,
            "refused": "no interface_manifest.yaml found under the framing or implementation run",
        }
    return check(manifest, seeded)


def static_checks(
    cfg: SetConfig, stack: str, cycle_id: str, impl_run: str | None, framing_run: str | None
) -> dict:
    from squadops.capabilities.scaffold import InterfaceManifest

    out: dict = {}
    manifest = None
    manifest_text: str | None = None
    for run in (impl_run, framing_run):
        text = artifact_text(cfg, cycle_id, run, "interface_manifest.yaml") if run else None
        if text:
            manifest = InterfaceManifest.from_yaml(text)
            manifest_text = text
            break
    if impl_run:
        # B1 (1.7.4 plan §3.1): a field, read from the stored suites against the stored
        # manifest — the 1.7.3 record read it by hand (a grep over 43 suites).
        out["non_root_fixture_tables"] = non_root_fixture_tables(
            manifest_text, _stored_qa_suites(cfg, cycle_id, impl_run)
        )
    if impl_run:
        out["p0"] = p0_checks(
            stack,
            manifest,
            lambda name: artifact_text(
                cfg, cycle_id, impl_run, name, producing_task_type="scaffold.expand"
            ),
        )
    if framing_run:
        contract = artifact_text(cfg, cycle_id, framing_run, "verification_contract.yaml")
        out["contract_json_has_probes"] = contract.count("json_has:") if contract else None
        # 1.6.6 R5 (#1128): no POST probe on an endpoint that declares a request body ships {}.
        out["empty_body_probes"] = (
            empty_body_probes(manifest, contract) if contract and manifest is not None else None
        )
    if impl_run:
        # 1.6.6 R2 (#1127): no stored report fails "Found multiple elements".
        out["multiple_elements_reports"] = _report_scan(
            cfg, cycle_id, impl_run, "Found multiple elements"
        )
    return out


def empty_body_probes(manifest: Any, contract_text: str) -> list[str]:
    """Ids of POST probes that carry ``json: {}`` on an endpoint whose manifest declares a
    ``request:`` — the shape that made 1.6.5 FastAPI+React roll 3 unsatisfiable (#1128)."""
    paths_with_request = {ep.path for ep in manifest.api.endpoints if ep.request}
    try:
        contract = yaml.safe_load(contract_text) or {}
    except yaml.YAMLError:
        return ["<contract unparseable>"]
    probes = ((contract.get("behavioral") or {}).get("probes")) or []
    return [
        str(p.get("id"))
        for p in probes
        if isinstance(p, dict)
        and (p.get("request") or {}).get("method") == "POST"
        and (p.get("request") or {}).get("path") in paths_with_request
        and (p.get("request") or {}).get("json") == {}
    ]


def _report_scan(cfg: SetConfig, cycle_id: str, impl_run: str, needle: str) -> list[str]:
    """Task ids whose stored ``test_report.md`` contains ``needle`` (per-round evidence, #1127)."""
    hits: list[str] = []
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        m = _metadata(art)
        if not m or str(m.get("filename", "")) != "test_report.md":
            continue
        try:
            text = (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            continue
        if needle in text:
            hits.append(str((m.get("metadata") or {}).get("task_id") or art.name))
    return sorted(hits)


def ledger_checks(rec: dict) -> dict:
    """#1021 at N=1: a green roll credits every criterion."""
    unevidenced = rec.get("criteria_unevidenced") or []
    return {
        "criteria": f"{rec.get('criteria_verified')}/{rec.get('criteria_total')}",
        "compile_criteria_unevidenced": [
            c for c in unevidenced if str(c).startswith("vc-compiles")
        ],
        "p_coverage_full": rec.get("verdict") != "accepted"
        or (rec.get("criteria_verified") == rec.get("criteria_total")),
    }


def runtime_log_window(since: str, until: str | None = None) -> list[str]:
    return _runtime_lines_of_interest(docker_logs(RUNTIME_API_CONTAINER, since, until))


def _runtime_lines_of_interest(lines: list[str]) -> list[str]:
    keys = (
        "correction_repair_target",
        "correction_repair_locus",
        "repair emitted no content",
        "correction_terminated",
        "self_eval fills",
        "fill merge",
        "patch_verification task=",
        "patch_retest task=",
        "Dispatched task task-",
        "plan_defect terminal",
        "evidence superseded",
        # 1.7.1 (plan §4): R2/R4's routing tokens ride correction_repair_locus lines; the
        # qa repair's case count (R4) and rule B's agent-decided verifications (R7) do not.
        "correction_repair_brief",
        "decided_by_agent=",
        # #1631: #968's prose refutation is logged on its OWN line by
        # `adapters.cycles.correction_runner`, carrying no other key — so without it here the
        # line never reaches `analyzer_claims_refuted` and A1 reads NO on a mechanism that
        # fired. #1616 added the reader and the decision_task join and did not add this, and
        # its replay fed `docker logs` straight to the reader, bypassing this filter: it
        # proved the function and said nothing about the wiring. Two shakeout runs were spent
        # on a reading that could not have come back YES.
        "analyzer_claim_refuted",
        # 1.7.4 (#1372, R1): the executor's aimed emission retry, with the signature and
        # token facts the appendix is built from (#1110).
        "Retryable failure for",
        # 1.7.4 (#1374, F1): the accepted-patch path re-deriving a framework row on the
        # patched set (#1318/#1364 today; every contract row after #1374).
        "re-derived required_files",
        # SIP-0107 §20: the accepted-patch path's candidate identity, verified and persisted.
        "patch_candidate_identity task=",
    )
    return [line for line in lines if any(k in line for k in keys)]


#: The lines the driver keeps from the producing agents' windows. ``emission shape:`` is
#: every emission's shape (#1276); ``fence path placeholder:`` is the extractor saying it
#: repaired a ``path/``-prefixed fence (#1272) — the only place the model's own behaviour
#: behind L8 is observable, since the stored name is post-repair (#1311).
_AGENT_LINE_KEYS = (
    "emission shape:",
    "fence path placeholder:",
    # 1.7.4 (#1372, R1): the handler's own trace that the aimed retry's appendix rendered
    # ("appended for") or did not ("NOT appended for") — logged where the prompt is built.
    "emission retry feedback",
    # SIP-0107 §46a: one per repair — the edit form it was offered, the form its response took.
    "repair_revision_form ",
    # #1588: the fault hook's own trace — APPLIED to which attempt, or declared and out of
    # scope. A seam reading that does not know whether its fault applied credited L4 on a
    # refund the dev's prose answer earned, in a cycle where no qa repair ever ran.
    "fault_injection: ",
)


def _agent_lines_of_interest(lines: list[str]) -> list[str]:
    return [line for line in lines if any(key in line for key in _AGENT_LINE_KEYS)]


PREFECT_SERVER_CONTAINER = "squadops-prefect-server"
_LOOP_OVERRUN = re.compile(
    r"prefect\.server\.services\.(?P<service>\w+) - (?:\w+) took (?P<seconds>[\d.]+) seconds to run, "
    r"which is longer than its loop interval of (?P<interval>[\d.]+) seconds"
)


def prefect_loop_overruns(lines: list[str]) -> dict:
    """#330 (1.7.4 plan §3.3, read live): the Prefect server's loop services that took
    longer than their interval during the window — per service, the count and the worst
    overrun in seconds. Pure; the window comes from ``prefect_log_window``."""
    by_service: dict[str, dict] = {}
    for line in lines:
        m = _LOOP_OVERRUN.search(line)
        if not m:
            continue
        row = by_service.setdefault(m.group("service"), {"count": 0, "worst_seconds": 0.0})
        row["count"] += 1
        row["worst_seconds"] = max(row["worst_seconds"], float(m.group("seconds")))
    return {
        "overruns": sum(r["count"] for r in by_service.values()),
        "by_service": dict(sorted(by_service.items())),
    }


def prefect_log_window(since: str, until: str | None = None) -> list[str]:
    return [
        line
        for line in docker_logs(PREFECT_SERVER_CONTAINER, since, until)
        if "loop interval" in line
    ]


def agent_log_window(
    since: str, until: str | None = None, services: Sequence[str] = AGENT_SERVICES
) -> list[str]:
    """The producing agents' emission lines (#1276, #1311).

    The loop's emission facts are logged where the emission happens — in the role's own
    container — and the driver had only ever read the runtime-api's window. So
    ``empty_repair_emissions`` keyed on a runtime-api token ("repair emitted no content")
    that the 1.7.1 prose-only repairs never produced, and the contentless first attempts
    that shaped five of seven counted rolls appeared in no readout at all.

    ``services`` is the set's agent containers (``set_agent_services``). A solo arm's
    work runs in ``han`` alone, so a window over the squad's six containers read every
    emission fact of a Solo roll as unaskable, the per-roll completion tokens the window
    reports included (#1651).
    """
    lines: list[str] = []
    for service in services:
        lines += _agent_lines_of_interest(docker_logs(f"squadops-{service}", since, until))
    return lines


#: The literal segment the fence example once carried and the extractor strips; the same
#: string as ``fenced_parser._PLACEHOLDER_PREFIX``, held here rather than imported because
#: the driver reads the deployed container's log, not this tree's module — the test guards
#: the two against drifting apart.
_PLACEHOLDER_PREFIX = "path/"
#: The analyzer fault's marker (``fault_injection.INJECTED_CLAIM_MARKER``), held here for
#: the same reason as the placeholder prefix: the driver reads a deployed container's
#: artifacts, not this tree's module. The test guards the two against drifting apart.
_INJECTED_CLAIM_MARKER = "__squadops_injected_fault__"


#: The injected claim's substance, as the decision may repeat it without the marker: the
#: analyzer diagnostic on deploy A (cyc_1063c4dca548) produced a decision that named "an
#: injected backend fault" and "the missing router registration" and put `backend` in
#: `affected_task_types` — the refuted claim absorbed in full — while carrying no marker
#: string. A readout keyed on the marker alone read it as not inherited (the 1.7.2 §7
#: failure: a readout that cannot see its own miss).
# "injected" alone is not the claim's: the own-frame chain diagnostic's decision (no analyzer
# fault declared) said "injected" of the fault call it could see in the suite. The echoes are
# the claim's own phrases.
_INJECTED_CLAIM_ECHOES = (
    "injected backend fault",
    "registers its router",
    "router registration",
    "runs endpoints return 404",
)


def _foreign_task_types(values) -> list[str]:
    """Entries of a decision's ``affected_task_types`` that name no task type — a
    ``backend`` or a file path where a ``qa.test`` belongs is the analyzer's claim leaking
    into the decision's own structured field."""
    out = []
    for v in values or []:
        text = str(v).strip()
        if "." not in text or " " in text or "/" in text:
            out.append(text)
    return out


_CLAIM_REFUTED = re.compile(
    r"analyzer_claim_refuted task=(?P<task>\S+)(?: decision_task=(?P<decision>\S+))? "
    r"paths=(?P<paths>[^—]+)"
)


def analyzer_claims_refuted(lines) -> list[dict]:
    """#968's PROSE half: the claims the framework refuted against the workspace.

    The structured half (``analyzer_claims_dropped``) reads a file DROPPED from a repair
    target, which never runs on an own-artifact route because ``_locus_and_repair_target``
    returns before ``_resolve_repair_target``. On the deploy-F false-claim diagnostic the
    refutation fired and that reader saw ``[]`` (#1600) — the mechanism A1 exists to exercise,
    invisible to the readout watching for it.
    """
    out: list[dict] = []
    for line in lines:
        m = _CLAIM_REFUTED.search(line)
        if not m:
            continue
        out.append(
            {
                "task": m.group("task"),
                # The round's own decision step — the id its stored artifact carries, and the
                # only key that joins a refutation to the decision it was told to. A deploy
                # that predates the field reads "" and cannot be joined, which is a third
                # state, not a licence to match every decision of the run.
                "decision_task": m.group("decision") or "",
                "paths": [p.strip() for p in m.group("paths").split(",") if p.strip()],
            }
        )
    return out


def refuted_paths_by_decision(refutations) -> dict[str, tuple[str, ...]]:
    """Refuted paths keyed by the decision step they were told to (#1600's review).

    Flattening every refutation's paths into one set and handing it to every stored decision
    lets a refutation in round 0 excuse the same path QUOTED in round 1 — A1 false-greens
    across rounds instead of across prose styles. The join is per decision, or it is not made.
    """
    by_decision: dict[str, list[str]] = {}
    for entry in refutations or []:
        key = str(entry.get("decision_task") or "")
        if not key:
            continue
        by_decision.setdefault(key, []).extend(entry.get("paths") or [])
    return {k: tuple(dict.fromkeys(v)) for k, v in by_decision.items()}


def unjoinable_refutations(refutations) -> list[dict]:
    """Refutations a deploy emitted without naming their decision step.

    They cannot be correlated, and the reading says so rather than matching them to everything.
    """
    return [e for e in (refutations or []) if not e.get("decision_task")]


def _decision_reading(text: str, refuted_paths: tuple[str, ...] = ()) -> dict:
    """What a stored correction decision carries of the injected claim — pure.

    ``inherited`` was ``marker in text``, which counts a decision that QUOTES the injected
    path in order to refute it (#1600): deploy F's lead wrote "the primary causal claim (an
    unregistered router in `backend/__squadops_injected_fault__.py`) is refuted by the
    workspace", the invariant held exactly as #968 intends, and the record said the opposite.
    On deploy E the same diagnostic read ``inherited: false`` only because that lead
    paraphrased instead of quoting — the reading turned on prose style.

    The join is on content, not prose: a path the framework refuted, repeated by the
    decision, is ``refuted_verbatim`` — a third state reported beside ``inherited`` and never
    counted as it. Carrying the marker where NO refutation covered it is inheritance still.
    """
    lowered = text.lower()
    try:
        doc = json.loads(text)
    except ValueError:
        doc = {}
    quoted = [p for p in refuted_paths if p and p in text]
    return {
        "inherited": _INJECTED_CLAIM_MARKER in text and not quoted,
        "refuted_verbatim": quoted,
        "echoes": [e for e in _INJECTED_CLAIM_ECHOES if e in lowered],
        "foreign_affected_task_types": _foreign_task_types(
            doc.get("affected_task_types") if isinstance(doc, dict) else None
        ),
    }


def _decision_inherited_claims(
    cfg: SetConfig,
    cycle_id: str,
    run_id: str,
    refuted_by_decision: dict[str, tuple[str, ...]] | None = None,
) -> list[dict]:
    """Each stored correction decision of the run and what it carries of the analyzer
    fault's claim (A1, #968): the marker verbatim (``inherited``), the claim's substance
    without it (``echoes``), and non-task-type entries in ``affected_task_types``."""
    out: list[dict] = []
    for art in artifact_dirs(cfg, cycle_id, run_id):
        m = _metadata(art)
        if not m or m.get("filename") != "correction_decision.md":
            continue
        try:
            text = (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            continue
        # Each decision is joined ONLY to the refutation told to its own step. The
        # artifact's metadata carries that task id; a decision the map does not name was
        # refuted nothing, whatever another round's refutation said.
        task_id = str((m.get("metadata") or {}).get("task_id") or "")
        own = (refuted_by_decision or {}).get(task_id, ())
        out.append(
            {
                "artifact": art.name,
                "decision_task": task_id,
                **_decision_reading(text, own),
            }
        )
    return out


_PLACEHOLDER_STRIP = re.compile(
    r"fence path placeholder: '(?P<emitted>[^']+)' emitted under .*?; "
    r"stripped to '(?P<stripped>[^']+)'"
)


def placeholder_strips(lines: list[str]) -> list[dict]:
    """Every fence the extractor repaired out from under ``path/`` (#1311) — pure.

    L8 was read from stored artifact names, which are what the extractor *left*, so a
    model that emitted under the placeholder on every roll read as "held" as long as the
    repair worked. This is the model's behaviour; ``stored_under_placeholder`` is the
    extractor's. The two halves of #1272 fail independently and are read apart.
    """
    return [
        {"emitted": m.group("emitted"), "stripped_to": m.group("stripped")}
        for m in (_PLACEHOLDER_STRIP.search(line) for line in lines)
        if m
    ]


_FAULT_APPLIED = re.compile(
    r"fault_injection: APPLIED (?P<fault>\w+) to task=(?P<task>\S+) handler=(?P<handler>\S+) "
    r"chars (?P<before>\d+) -> (?P<after>\d+) scope=(?P<scope>\w+)"
)
_FAULT_OUT_OF_SCOPE = re.compile(
    r"fault_injection: (?P<fault>\w+) declared for (?P<task>\S+) but this attempt is outside "
    r"its scope \((?P<scope>\w+)\)"
)


def faults_applied(lines: list[str]) -> dict[str, dict[str, list[dict]]]:
    """Per declared fault, the attempts it was APPLIED to and the attempts it was declared
    for but out of scope — read from the fault hook's own lines in the agents' logs (#1588).

    A seam reading is a claim about what the fault's application caused. Without this fact
    the own-frame diagnostic's record credited L4 on a refund that the dev's prose refusal
    had earned, in a cycle where the qa repair the fault targets never ran; the fault was
    never applied and the seam was never exercised. Pure; ``seam_readouts`` reads it.
    """
    out: dict[str, dict[str, list[dict]]] = {}
    for line in lines:
        if (m := _FAULT_APPLIED.search(line)) is not None:
            out.setdefault(m.group("fault"), {"applied": [], "out_of_scope": []})["applied"].append(
                {
                    "task": m.group("task"),
                    "handler": m.group("handler"),
                    "chars_before": int(m.group("before")),
                    "chars_after": int(m.group("after")),
                    "scope": m.group("scope"),
                }
            )
        elif (m := _FAULT_OUT_OF_SCOPE.search(line)) is not None:
            out.setdefault(m.group("fault"), {"applied": [], "out_of_scope": []})[
                "out_of_scope"
            ].append({"task": m.group("task"), "scope": m.group("scope")})
    return out


def stored_under_placeholder(names) -> list[str]:
    """Stored artifact names that still carry the placeholder — the extractor half of L8."""
    return sorted(name for name in names if str(name).startswith(_PLACEHOLDER_PREFIX))


def _stored_artifact_names(cfg: SetConfig, cycle_id: str, run_id: str) -> list[str]:
    names = []
    for art in artifact_dirs(cfg, cycle_id, run_id):
        m = _metadata(art)
        if m and m.get("filename"):
            names.append(str(m["filename"]))
    return names


#: The runtime-api lines that show the correction path was entered, whatever the stored
#: decision count says — a refunded round, for one, is re-taken rather than spent.
_CORRECTION_MARKERS = (
    "correction_repair",
    "correction attempt",
    "correction_terminated",
    "patch_verification task=",
    "patch_retest task=",
)


def correction_entered(logs: Sequence[str], correction_rounds: int | None) -> bool:
    """Whether this roll took the patch path at all — the condition every patch-path
    readout is unaskable without (#1445)."""
    if (correction_rounds or 0) >= 1:
        return True
    return any(marker in line for line in logs for marker in _CORRECTION_MARKERS)


def loop_texture(
    cfg: SetConfig,
    cycle_id: str,
    impl_run: str | None,
    since: str,
    until: str | None = None,
    *,
    correction_rounds: int | None = None,
) -> dict:
    raw = docker_logs(RUNTIME_API_CONTAINER, since, until)
    logs = _runtime_lines_of_interest(raw)
    out = texture_from_logs(logs)
    agent_lines = agent_log_window(since, until, set_agent_services(cfg))
    out.update(texture_from_emission_shapes(agent_lines))
    out.update(texture_from_retry_feedback(agent_lines))
    out["repair_revision_forms"] = repair_revision_forms(agent_lines)
    # #330: the Prefect server's loop-service overruns in this cycle's window.
    out["prefect_loop_overruns"] = prefect_loop_overruns(prefect_log_window(since, until))
    out["log_window"] = {"since": since, "until": until}
    # 1.7.4 (#968, A1): whether a stored correction decision carries the analyzer fault's
    # marker — read from the decision itself, the artifact the repair brief is built from.
    refutations = out.get("analyzer_claims_refuted", [])
    out["unjoinable_refutations"] = unjoinable_refutations(refutations)
    out["decision_inherited_claims"] = (
        _decision_inherited_claims(cfg, cycle_id, impl_run, refuted_paths_by_decision(refutations))
        if impl_run
        else []
    )
    rejections = _fill_rejections(cfg, cycle_id, impl_run) if impl_run else None
    out["fill_rejections"] = rejections or []
    # #999: the qa task's fill-merge evidence, persisted as an artifact and read from it.
    out["fill_merge_evidence"] = fill_merge_evidence(cfg, cycle_id, impl_run) if impl_run else []
    # #1540: suites the runner never collected — non-execution with no row anywhere else.
    uncollected = uncollected_suites(cfg, cycle_id, impl_run) if impl_run else None
    out["uncollected_suites"] = uncollected or []
    # #1311: L8 as two claims. L8a — the model emitted under the placeholder and the
    # extractor repaired it (read from the agent's log, the only place it is visible).
    # L8b — a stored name still carries it (read from the tree, the old readout).
    out["placeholder_strips"] = placeholder_strips(agent_lines)
    # #1588: which attempts each declared fault actually bit, from the hook's own lines.
    out["faults_applied"] = faults_applied(agent_lines)
    out["stored_under_placeholder"] = (
        stored_under_placeholder(_stored_artifact_names(cfg, cycle_id, impl_run))
        if impl_run
        else []
    )
    # #1445: every field into the vocabulary, off the conditions this roll can state.
    context = {
        "no_implementation_run": impl_run is None,
        "runtime_window_empty": len(raw) == 0,
        "no_correction_round": not correction_entered(logs, correction_rounds),
        "no_emission_shape_lines": out["emissions_logged"] == 0,
        "no_emission_retry_aimed": len(out["emission_retries"]) == 0,
        "no_repair_revision_form_line": len(out["repair_revision_forms"]) == 0,
        "no_correction_decision_stored": (correction_rounds or 0) == 0,
        "no_fill_merge_artifact": len(out["fill_merge_evidence"]) == 0,
        "no_test_report_stored": uncollected is None,
        "no_qa_scaffold_suite": rejections is None,
        "logged_in_the_agent_container": True,
    }
    return with_states("loop_texture", out, context)


#: What each fault's diagnostic must show to have REACHED the seam its prediction names —
#: read from the record, never from "the fault fired" (#1310, #1300). A fault can bite and
#: exercise a neighbouring seam: the absent-suite fault under first-attempt scope fired,
#: the emission retry recovered, and correction was never entered — and the record would
#: have read as L2 exercised. Keyed by the fault name (the declaration is the boundary
#: between the framework and this instrument; the test holds the two lists together).
#: Each entry: the seam, the record fields the readout reads (so ``seam_readouts`` can say
#: which of them were unaskable on the roll — a NO decided over an unaskable field is not a
#: NO, #1445), and the reading.
def _a1_reading(rec: Mapping[str, Any]) -> tuple[bool | None, dict]:
    """A1, with the correlation the reading depends on stated rather than assumed.

    ``reached`` is None — UNASKABLE — when a refutation fired that the deploy did not name a
    decision step for. Such a refutation cannot be joined to the decision it was told to, and
    matching it against every decision of the run is what lets a round-0 refutation excuse a
    path quoted in round 1 (#1600's review). A reading that cannot correlate says so.
    """
    decisions = value_at(rec, "loop_texture.decision_inherited_claims", [])
    refutations = value_at(rec, "loop_texture.analyzer_claims_refuted", [])
    unjoinable = value_at(rec, "loop_texture.unjoinable_refutations", [])
    evidence = {
        "decisions": decisions,
        "refuted_by_workspace_check": refutations,
        "unjoinable_refutations": unjoinable,
        "dropped_from_repair_target": value_at(rec, "loop_texture.analyzer_claims_dropped", []),
    }
    if unjoinable:
        evidence["unaskable_reason"] = (
            "the deploy emitted a refutation without naming its decision step, so it cannot be "
            "correlated to the decision it was told to; a run-wide match would let one round's "
            "refutation excuse another round's quote"
        )
        return None, evidence
    reached = (
        len(decisions) >= 1
        # The refutation is the mechanism this diagnostic exists to exercise: without it
        # firing, a clean decision proves only that the fault never reached the lead.
        and len(refutations) >= 1
        # The marker or the claim's substance decides; ``foreign_affected_task_types``
        # stays in the reading as D1's texture — the contentless-builder diagnostic's
        # decision (no analyzer fault) already carried `builder`, `assembler`, `data`,
        # `qa_handoff` there, so the field is the lead's habit, not the claim's leak.
        and not any(d.get("inherited") or d.get("echoes") for d in decisions)
    )
    return reached, evidence


_FAULTED_TASK_TYPE = re.compile(r"-(?P<ttype>[a-z_]+\.[a-z_]+)$")

#: The AFFIRMATIVE own-artifact locus, em dash included. #1054's branch logs
#: ``own_artifact DISPUTED —``, sets the locus to UNKNOWN and falls through to the DEV
#: CHAIN — the opposite of this seam's question. A prefix match on
#: ``correction_repair_locus: own_artifact`` swallows it and reads L7 YES on a routing that
#: was explicitly refused, which is the #1130/#1270 defect reading as a pass.
_AFFIRMATIVE_OWN_ARTIFACT = "correction_repair_locus: own_artifact \u2014 "


def _qa_own_frame_routed_reading(rec: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """L7: the own-frame failure routed to the qa repair — read from WHERE the repair went,
    not from which branch logged it.

    Every `correction_repair_locus: own_artifact` branch means the failing task repairs its
    own artifact, which IS the routing this seam asks about; there is no competing
    `locus=dev_chain` line, so the #1130/#1270 defect this seam exists to catch shows up as
    the ABSENCE of an own_artifact locus for the faulted task's type, and still reads NO.

    Joined on the faulted task's type (`task-run_x-mNNN-qa.test` -> `qa.test`) rather than
    accepting any locus in the run, so a round that routed some other task's failure cannot
    excuse this one — the #1616 lesson about a flattened join.
    """
    # Filtered here as well as in the collector: the seam's guarantee belongs to the
    # reading, so a field filled by an older collector — or by a hand-built record — cannot
    # make a DISPUTED line, which routes to the dev chain, read as an own-artifact route.
    loci = [
        line
        for line in (value_at(rec, "loop_texture.own_artifact_locus", []) or [])
        if _AFFIRMATIVE_OWN_ARTIFACT in line
    ]
    types = {
        m.group("ttype")
        for a in (_applied_attempts(rec, "qa_suite_own_frame_failure") or [])
        if (m := _FAULTED_TASK_TYPE.search(str(a.get("task") or ""))) is not None
    }
    if types:
        # Token-aware: a bare ``in`` makes ``qa.test`` match ``qa.test_repair``, so the
        # repair task's own locus would answer for the task that failed.
        patterns = [re.compile(rf"(?<![\w.]){re.escape(ttype)}(?![\w.])") for ttype in types]
        loci = [line for line in loci if any(pat.search(line) for pat in patterns)]
    return bool(loci), loci


SEAM_READOUTS: dict[str, tuple[str, tuple[str, ...], Callable[[dict], tuple[bool, Any]]]] = {
    "qa_suite_absent": (
        "L2: the qa task entered correction and its repair was retested",
        ("correction_rounds", "loop_texture.retests", "loop_texture.faults_applied"),
        lambda rec: _qa_suite_absent_reading(rec),
    ),
    "qa_suite_at_path_prefix": (
        "L8b: the extractor repaired a fence emitted under the placeholder",
        ("loop_texture.placeholder_strips",),
        lambda rec: (
            len(value_at(rec, "loop_texture.placeholder_strips", [])) >= 1,
            value_at(rec, "loop_texture.placeholder_strips", []),
        ),
    ),
    "qa_suite_own_frame_failure": (
        "L7: the own-frame failure routed to the qa repair",
        ("loop_texture.own_artifact_locus", "loop_texture.qa_owned_routed"),
        _qa_own_frame_routed_reading,
    ),
    "repair_prose_only": (
        "L4: the prose-only repair was refunded rather than verified",
        ("loop_texture.refunded_rounds", "loop_texture.faults_applied"),
        lambda rec: _repair_prose_only_reading(rec),
    ),
    # #1506: the contentless-builder sequence is two seams read on their own evidence. Since
    # #1372 the builder retries a contentless emission with its fact, so one first-attempt
    # fault reaches R1 and can never reach F1 — the retry recovers attempt 2 before the task
    # fails into correction. The 1.7.5 compound readout (correction entered AND a builder
    # patch verified) read NO on a deploy where R1 had held, for a reason the readout could
    # not say.
    #
    # R1 (first-attempt fault). YES = the executor aimed a retry at the builder, the builder's
    # handler rendered the emission-shape fact into it, and the retry's emission was accepted:
    # no second builder retry and no builder repair on the patch path. A blind retry, a retry
    # that failed again, or a builder that ended in correction is the seam reached and R1 not
    # holding, and the evidence names which.
    "builder_emission_contentless": (
        "R1: the contentless builder attempt was retried with its emission-shape fact, and "
        "the retry's emission was accepted",
        (
            "loop_texture.emission_retries",
            "loop_texture.retried_with_fact",
            "loop_texture.retried_blind",
        ),
        lambda rec: _builder_retry_reading(rec),
    ),
    # F1 (all-emission-attempts fault). YES = the builder entered correction and the accepted
    # patch path re-derived its framework rows from the patched set — the line
    # `PatchAcceptance` logs (#1374). A refused builder repair derives no rows and is not the
    # seam reached; the evidence carries the rows and the retries it took to get there.
    "builder_emission_contentless_all_attempts": (
        "F1: the builder, contentless through its emission retries, entered correction and "
        "its accepted patch's framework rows were re-derived from the patched set",
        (
            "correction_rounds",
            "loop_texture.patch_verifications",
            "loop_texture.framework_rows_rederived",
            "typed_checks.required_files_rows",
            "loop_texture.emission_retries",
        ),
        lambda rec: (
            (value_at(rec, "correction_rounds", 0) or 0) >= 1
            and bool(_builder_lines(value_at(rec, "loop_texture.framework_rows_rederived", []))),
            {
                "correction_rounds": value_at(rec, "correction_rounds", 0),
                "builder_patch_verifications": _builder_lines(
                    value_at(rec, "loop_texture.patch_verifications", [])
                ),
                "framework_rows_rederived": value_at(
                    rec, "loop_texture.framework_rows_rederived", []
                ),
                "required_files_rows": _required_files_rows(rec),
                "builder_emission_retries": _builder_lines(
                    value_at(rec, "loop_texture.emission_retries", [])
                ),
            },
        ),
    ),
    # 1.8.0 plan §4.1: the dev lane. YES = correction was entered, the development repair's
    # target was narrowed to the probe-owned slot that serves the join route (the line
    # `correction_repair_target` logs, #1015), and a patch was applied on the patch path. The
    # patch lines do not name the repairing role, so the narrowed target is what ties the
    # applied patch to the dev lane; a refused patch, or a repair aimed anywhere else, is the
    # seam not reached and the evidence says which.
    "dev_join_response_omits_declared_fields": (
        "the dev lane: the join probe failure was repaired by a development repair narrowed to "
        "the probe-owned join slot, and the patch was applied",
        (
            "correction_rounds",
            "loop_texture.narrowed_targets",
            "loop_texture.patch_verifications",
            "loop_texture.applied_patches",
            "loop_texture.refused_patches",
        ),
        lambda rec: _dev_join_repair_reading(rec),
    ),
    # 1.7.4 plan §3.1: A1. YES = a decision was stored for the faulted round and none
    # carries the refuted claim; a decision that inherited it is the seam reached and the
    # invariant false, which the evidence names by artifact (pre-#968 that is the expected
    # reading — the diagnostic proves the fault reaches the decision).
    "analyzer_false_source_claim": (
        "A1: the framework refuted the claim against the workspace, a decision was reached, "
        "and none of them inherited it — quoting a refuted path to reject it is not "
        "inheritance (#1600)",
        (
            "loop_texture.decision_inherited_claims",
            "loop_texture.analyzer_claims_refuted",
            "loop_texture.analyzer_claims_dropped",
        ),
        _a1_reading,
    ),
}


def _applied_attempts(rec: Mapping[str, Any], fault: str) -> list[dict] | None:
    """The attempts ``fault`` was APPLIED to, per the fault hook's own lines — or ``None``
    when the record predates the field (#1588) and cannot say."""
    texture = rec.get("loop_texture") if isinstance(rec, Mapping) else None
    if not isinstance(texture, Mapping) or "faults_applied" not in texture:
        return None
    by_fault = value_at(rec, "loop_texture.faults_applied", {}) or {}
    return list((by_fault.get(fault) or {}).get("applied") or [])


def _out_of_scope_attempts(rec: Mapping[str, Any], fault: str) -> list[dict]:
    by_fault = value_at(rec, "loop_texture.faults_applied", {}) or {}
    return list((by_fault.get(fault) or {}).get("out_of_scope") or [])


def _lines_naming_applied_tasks(lines: list[str], rec: Mapping[str, Any], fault: str) -> list[str]:
    """The lines about a task the fault was applied to. When the record cannot say which
    (it predates the field, or the fault never applied) every line is kept — the applied
    requirement in ``seam_readouts`` decides the reading in that case, not this join."""
    ids = [a["task"] for a in (_applied_attempts(rec, fault) or []) if a.get("task")]
    if not ids:
        return list(lines)
    return [line for line in lines if any(task in line for task in ids)]


_REPAIR_ROUND = re.compile(r"^repair-run_[0-9a-f]+-(?P<round>\d+)-")
_REFUND_ATTEMPT = re.compile(r"correction attempt (?P<attempt>\d+) refunded")


def _qa_suite_absent_reading(rec: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    """L2: a retest of the faulted qa task after correction — not of some other task (#1588)."""
    rounds = value_at(rec, "correction_rounds", 0) or 0
    retests = [r for r in value_at(rec, "loop_texture.retests", []) or [] if "qa.test" in r]
    of_faulted = _lines_naming_applied_tasks(retests, rec, "qa_suite_absent")
    return rounds >= 1 and bool(of_faulted), {
        "correction_rounds": rounds,
        "retests": value_at(rec, "loop_texture.retests", []),
        "retests_of_the_faulted_task": of_faulted,
    }


def _repair_prose_only_reading(rec: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """L4: the refund of the ROUND whose repair the fault stripped — the repair task id
    carries the round (``repair-run_x-00-…``) and the refund line the attempt (#1588). The
    own-frame diagnostic's run 1 carried a refund of the dev's prose answer in a cycle where
    the fault's target never ran; read without the join, that was L4 reached."""
    refunds = list(value_at(rec, "loop_texture.refunded_rounds", []) or [])
    rounds = {
        int(m.group("round"))
        for a in (_applied_attempts(rec, "repair_prose_only") or [])
        if (m := _REPAIR_ROUND.match(str(a.get("task") or ""))) is not None
    }
    if rounds:
        refunds = [
            r
            for r in refunds
            if (m := _REFUND_ATTEMPT.search(r)) is not None and int(m.group("attempt")) in rounds
        ]
    return bool(refunds), refunds


def seam_readouts(faults, rec: dict) -> dict[str, dict]:
    """Per declared fault: the seam it names, whether the record shows it reached, and the
    evidence read. A fault with no readout is named as such rather than skipped — a
    diagnostic nothing can read proves nothing (#1300).

    #1588: a seam is read only when its fault APPLIED. A fault declared for a task that never
    ran, or whose every attempt fell outside the fault's scope, exercised nothing — the
    reading is neither YES nor NO, and ``reached`` is ``None`` with the reason beside it, the
    three-state rule the texture fields follow (#1445). A record that predates the field
    keeps its reading, with the absence named.
    """
    out: dict[str, dict] = {}
    for name in faults:
        entry = SEAM_READOUTS.get(name)
        if entry is None:
            out[name] = {"seam": None, "reached": None, "evidence": "no readout for this fault"}
            continue
        seam, reads, read = entry
        reached, evidence = read(rec)
        # #1445: a field the reading could not ask is named beside the answer, so a NO
        # decided over an unaskable field is never read as the seam not reached.
        unaskable = {
            path: ev.reason
            for path in reads
            if (ev := evidence_at(rec, path)) is not None and ev.state == UNASKABLE
        }
        applied = _applied_attempts(rec, name)
        # A reading that answered None answered UNASKABLE, and it stays that way: coercing it
        # to False would report "the seam was not reached" for a question the record could
        # not be asked (#1445). Only a reading that answered a boolean is a YES or a NO.
        state: bool | None = None if reached is None else bool(reached)
        if applied is None:
            unaskable["loop_texture.faults_applied"] = (
                "not recorded — the record predates the applied fact (#1588); the reading "
                "stands on the seam's evidence alone"
            )
        elif not applied:
            out_of_scope = _out_of_scope_attempts(rec, name)
            unaskable["loop_texture.faults_applied"] = (
                "the fault never applied — "
                + (
                    "declared for "
                    + ", ".join(sorted({str(a.get("task")) for a in out_of_scope}))
                    + " but every attempt was outside its scope"
                    if out_of_scope
                    else "no attempt of its target task ran"
                )
                + "; the seam was not exercised, so this is neither YES nor NO (#1588)"
            )
            state = None
        out[name] = {
            "seam": seam,
            "reached": state,
            "evidence": evidence,
            "unaskable": unaskable,
            "applied": applied or [],
        }
    return out


def _seam_state(reading: Mapping[str, Any]) -> str:
    if not reading.get("seam"):
        return "NO READOUT"
    if reading.get("reached") is None:
        return "UNASKABLE"
    return "YES" if reading.get("reached") else "NO"


def _applied_words(reading: Mapping[str, Any]) -> str:
    applied = reading.get("applied") or []
    if not applied:
        return ""
    return " — fault applied to " + ", ".join(
        f"`{a.get('task')}` ({a.get('chars_before')}→{a.get('chars_after')} chars)" for a in applied
    )


#: The builder's two names in the logs: its task id suffix on the executor's lines, its
#: handler name on the agent's. Read from the code that writes them (TaskType.BUILDER_ASSEMBLE,
#: `BuilderAssembleHandler._handler_name`), never from a stack.
_BUILDER_TASK = "builder.assemble"
_BUILDER_HANDLER = "builder_assemble_handler"
_RETRY_ATTEMPT = re.compile(r"\(attempt (\d+)\)")


def _builder_lines(lines: Any) -> list[str]:
    """The lines about the builder's task, by its task id suffix."""
    return [line for line in (lines or []) if _BUILDER_TASK in line]


#: The slots that serve the join route on each stack: stack #1's single routes file, stack #2's
#: per-path route file.
_JOIN_SLOTS = ("backend/routes.py", "/join/route.ts")


def _dev_join_repair_reading(rec: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    """The dev lane (1.8.0 plan §4.1): a repair narrowed to the join slot, and a patch applied."""
    narrowed = [
        line
        for line in value_at(rec, "loop_texture.narrowed_targets", []) or []
        if any(slot in line for slot in _JOIN_SLOTS)
    ]
    applied = value_at(rec, "loop_texture.applied_patches", 0) or 0
    rounds = value_at(rec, "correction_rounds", 0) or 0
    return rounds >= 1 and bool(narrowed) and applied >= 1, {
        "correction_rounds": rounds,
        "narrowed_to_join_slot": narrowed,
        "applied_patches": applied,
        "refused_patches": value_at(rec, "loop_texture.refused_patches", []),
    }


def _builder_retry_reading(rec: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    """R1 (#1372, #1506): the builder's aimed retry carried its fact and its emission held."""
    retries = _builder_lines(value_at(rec, "loop_texture.emission_retries", []))
    attempts = sorted(
        int(m.group(1)) for line in retries if (m := _RETRY_ATTEMPT.search(line)) is not None
    )
    with_fact = [
        line
        for line in value_at(rec, "loop_texture.retried_with_fact", []) or []
        if _BUILDER_HANDLER in line
    ]
    blind = [
        line
        for line in value_at(rec, "loop_texture.retried_blind", []) or []
        if _BUILDER_HANDLER in line
    ]
    repaired = _builder_lines(value_at(rec, "loop_texture.patch_verifications", []))
    reached = bool(retries) and bool(with_fact) and attempts == [1] and not blind and not repaired
    return reached, {
        "builder_emission_retries": retries,
        "retry_attempts": attempts,
        "retried_with_fact": with_fact,
        "retried_blind": blind,
        "builder_patch_verifications": repaired,
    }


def _required_files_rows(rec: Mapping[str, Any]) -> Any:
    """H1's first source. The registered field when the record carries it; a pre-#1445
    record only has ``by_check``, where the row is absent by the seam's design."""
    if evidence_at(rec, "typed_checks.required_files_rows") is not None:
        return value_at(rec, "typed_checks.required_files_rows", {})
    return (value_at(rec, "typed_checks.by_check", {}) or {}).get("required_files", {})


def _fact(line: str, marker: str) -> str:
    """The log line from ``marker`` to its end — the fact, with the timestamp and logger
    prefix dropped and no width cap (#1330).

    ``line[-200:]`` recorded the 1.7.2 Next.js roll 2 refusals as ``'tion task=…'`` and
    ``'pe=qa.test …'`` — the second with its task id gone — because a qa refusal's fact is
    longer than 200 characters. A window of a line is not the line.
    """
    at = line.find(marker)
    return line[at:].rstrip() if at >= 0 else line.strip()


def _field(line: str, key: str) -> str | None:
    """``key=value`` off a space-separated log line — the shape executor readouts use."""
    match = re.search(rf"\b{re.escape(key)}=(\S*)", line)
    return match.group(1) if match else None


def _count_by(values) -> dict[str, int]:
    """``{value: count}``, most frequent first — the shape #1276 requires of every readout.

    An integer says a prediction fired; it never says on what. Three 1.7.1 readouts were
    misread because the reason was thrown away at exactly this line (record §4.6).
    """
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def _sum_pairs(entries) -> dict[str, int]:
    """``reason:count`` entries summed by reason — the ``skips=`` field's own shape.

    Counting the entries instead of their counts would report "1 missing_tooling" for a
    verification where three rows skipped, which is the class of misreading #1276 is about.
    """
    counts: dict[str, int] = {}
    for entry in entries:
        reason, _, count = entry.partition(":")
        try:
            counts[reason] = counts.get(reason, 0) + (int(count) if count else 1)
        except ValueError:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


#: The agent-side emission-shape line (``handlers/emission_log.py``). ``reasoning_tokens``
#: and ``reasoning_chars`` are alternatives — Ollama reports no thinking count, so the
#: production arm renders the text's length instead (#1195).
_EMISSION_SHAPE = re.compile(
    r"(?P<handler>\S+) emission shape: chars=(?P<chars>\d+) "
    r"completion_tokens=(?P<tokens>\S+)"
    r"(?: reasoning_tokens=(?P<reasoning_tokens>\S+))?"
    r"(?: reasoning_chars=(?P<reasoning_chars>\d+))?"
    r" fences=(?P<fences>\{[^}]*\})"
)

#: An emission is CONTENTLESS when it addresses no file and is shorter than a sentence or
#: two of intent (1.7.2 plan §4, prediction L1). The 1.7.1 sample ran 0–265 chars.
CONTENTLESS_CHARS = 400


def emission_shapes(lines: list[str]) -> list[dict]:
    """Every agent emission's shape, parsed — pure, so the parse is testable."""
    shapes = []
    for line in lines:
        match = _EMISSION_SHAPE.search(line)
        if not match:
            continue
        fences = {
            key: int(value) for key, value in re.findall(r"'(\w+)': (\d+)", match.group("fences"))
        }
        shapes.append(
            {
                "handler": match.group("handler"),
                "chars": int(match.group("chars")),
                "completion_tokens": match.group("tokens"),
                "reasoning_tokens": match.group("reasoning_tokens"),
                "reasoning_chars": match.group("reasoning_chars"),
                "fences": fences,
                "fences_total": sum(fences.values()),
            }
        )
    return shapes


def texture_from_emission_shapes(lines: list[str]) -> dict:
    """The emission readouts, read from the emission itself (#1276, #1268).

    ``contentless_emissions`` is prediction L1's instrument and carries each emission's
    own ``chars``/``completion_tokens``, so a record says what the model actually returned
    rather than that something was missing downstream. ``empty_repair_emissions`` is the
    repair-handler subset of the same fact — it used to key on a runtime-api log token
    that both 1.7.1 prose-only repairs failed to produce.
    """
    shapes = emission_shapes(lines)
    contentless = [
        shape
        for shape in shapes
        if shape["fences_total"] == 0 and shape["chars"] < CONTENTLESS_CHARS
    ]
    return {
        "emissions_logged": len(shapes),
        "contentless_emissions": contentless,
        "contentless_by_handler": _count_by(shape["handler"] for shape in contentless),
        "empty_repair_emissions": [shape for shape in contentless if "repair" in shape["handler"]],
        # #1285 (1.7.2 record §8): "qa primary tokens" was declared as texture and no roll
        # record carried it — the driver parsed each emission's tokens and kept only the
        # contentless ones. Every emission's tokens by handler, so the qa authoring pair's
        # completion and reasoning spend is readable from the record, by mode.
        "emission_tokens_by_handler": emission_tokens_by_handler(shapes),
    }


_RETRY_APPENDED = "emission retry feedback appended for"
_RETRY_NOT_APPENDED = "emission retry feedback NOT appended for"


def texture_from_retry_feedback(agent_lines: list[str]) -> dict:
    """R1's field (1.7.4 plan §3.1; #1372) — read from the handler's own trace, pure.

    An aimed emission retry carries the prior attempt's emission-shape fact only if the
    handler rendered the feedback appendix; ``cycle/base.py`` logs the positive trace
    ("appended for … signature=… expected_files=N") and the negative one ("NOT appended …
    re-rolls blind"). Before #1372 only the develop handler renders it, so a qa or builder
    retry leaves neither line: the field exists before the fix so the pre-registration has
    a producer to check, and the record reads a retry with no line as blind by subtraction
    from ``emission_retries``.
    """
    return {
        "retried_with_fact": [
            _fact(line, _RETRY_APPENDED) for line in agent_lines if _RETRY_APPENDED in line
        ],
        "retried_blind": [
            _fact(line, _RETRY_NOT_APPENDED) for line in agent_lines if _RETRY_NOT_APPENDED in line
        ],
    }


_REVISION_FORM_MARKER = "repair_revision_form "


def repair_revision_forms(agent_lines: list[str]) -> list[dict]:
    """Every repair's revision form (SIP-0107 §46a, §39.8), parsed from the handler's own line —
    pure.

    One line per repair, logged in the repairing role's container: what the edit form offered
    (each file, with the entities listed for it), the form the response took (``edits``,
    ``whole_file``, ``edits_and_whole_file``, ``fill``, ``new_files_only`` or ``none``), and the
    transaction's result. ``whole_file_offered`` is §46a's unauthorized whole-file fallback,
    counted per cell before the flip. A line that does not parse is kept as ``unparsed`` rather
    than dropped, so a changed format cannot read as fewer repairs.
    """
    forms = []
    for line in agent_lines:
        _, marker, payload = line.partition(_REVISION_FORM_MARKER)
        if not marker:
            continue
        try:
            forms.append(json.loads(payload))
        except ValueError:
            forms.append({"unparsed": line.strip()})
    return forms


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def emission_tokens_by_handler(shapes: list[dict]) -> dict[str, dict]:
    """Per handler: emissions, and the summed completion / reasoning tokens and reasoning
    chars where the shape line carried them — pure. A token field the adapter did not
    report (``None``) is counted as absent, not as zero, so a record can tell "no spend"
    from "unreported" (the #1285 shape: a declared field with no producer)."""
    out: dict[str, dict] = {}
    for shape in shapes:
        row = out.setdefault(
            shape["handler"],
            {
                "emissions": 0,
                "completion_tokens": 0,
                "reasoning_tokens": 0,
                "reasoning_chars": 0,
                "unreported_completion": 0,
                "unreported_reasoning": 0,
            },
        )
        row["emissions"] += 1
        for field_name, key in (
            ("completion_tokens", "completion_tokens"),
            ("reasoning_tokens", "reasoning_tokens"),
            ("reasoning_chars", "reasoning_chars"),
        ):
            value = _int_or_none(shape.get(key))
            if value is None:
                if field_name != "reasoning_chars":
                    row["unreported_" + field_name.split("_")[0]] += 1
                continue
            row[field_name] += value
    return dict(sorted(out.items()))


def texture_from_logs(logs: list[str]) -> dict:
    """The loop's readouts from the runtime-api log window — pure, so the parse is testable.

    1.6.6 (plan §2.3): ``refused_patches`` (patch verification refused the repair — never
    applied), ``applied_patches`` (a retest ran, or verification passed), and
    ``plan_defect_after_zero_applied`` — prediction R4's falsifier, readable from the
    record instead of the executor log. ``refused_rounds_not_counted`` is D's own line;
    ``evidence_superseded`` is F's (#1111).
    """
    # A patch is APPLIED when verification passed or a retest ran on it; it is REFUSED when
    # verification failed, or came back unverifiable and the executor re-dispatched the task
    # instead of retesting (a dev task with no executable typed checks — the Next.js 1.6.6
    # shakeout's shape, which the first reading of this readout missed). Read sequentially
    # per task so an unverifiable-then-retest pair counts once, as applied.
    refused: list[str] = []
    verifications: list[str] = []
    applied = 0
    pending: dict[str, str] = {}  # task -> the unverifiable line awaiting its fate
    for line in logs:
        if "patch_verification task=" in line:
            verifications.append(_fact(line, "patch_verification task="))
            task = line.split("patch_verification task=", 1)[1].split()[0]
            if "status=passed" in line:
                applied += 1
            elif "status=failed" in line:
                refused.append(_fact(line, "patch_verification task="))
            elif "status=unverifiable" in line:
                pending[task] = _fact(line, "patch_verification task=")
        elif "patch_retest task=" in line:
            task = line.split("patch_retest task=", 1)[1].split()[0]
            pending.pop(task, None)
            applied += 1
        elif "Dispatched task " in line:
            task = line.split("Dispatched task ", 1)[1].split()[0]
            if task in pending:
                refused.append(pending.pop(task))
    refused.extend(pending.values())
    terminations = [
        _fact(line, "correction_terminated_plan_defect")
        for line in logs
        if "correction_terminated_plan_defect" in line
    ]
    return {
        "narrowed_targets": [
            _fact(line, "correction_repair_target:")
            for line in logs
            if "narrowed to the slot" in line
        ],
        "language_fallbacks": sum("falling back to same-language" in line for line in logs),
        "fill_targets": [
            _fact(line, "correction_repair_locus:") for line in logs if "re-fills slot" in line
        ],
        "self_eval_fill_merges": [
            _fact(line, "self_eval fills") for line in logs if "self_eval fills" in line
        ],
        "refused_patches": refused,
        # 1.7.4: every verification as a fact, so a readout can find the one for a named
        # task (the contentless-builder diagnostic asks whether the BUILDER's repair was
        # verified, which the aggregate above cannot say).
        "patch_verifications": verifications,
        "applied_patches": applied,
        # #1310: the retests themselves, so a diagnostic can say WHICH task's repair was
        # retested (L2 is "the repair that supplied the suite is retested" — for a qa task).
        "retests": [
            _fact(line, "patch_retest task=") for line in logs if "patch_retest task=" in line
        ],
        "plan_defect_terminations": terminations,
        "plan_defect_after_zero_applied": bool(terminations) and applied == 0,
        "refused_rounds_not_counted": [
            _fact(line, "plan_defect terminal")
            for line in logs
            if "not counted as a repeat (#1129)" in line
        ],
        # 1.7.4 (#1372): every emission retry the executor aimed, as a fact. Read beside
        # ``retried_with_fact`` / ``retried_blind`` (the agents' side of the same seam): a
        # retry aimed here with no "appended" line in any agent window is a retry that
        # re-rolled blind — a handler that never renders the appendix leaves no trace of
        # its own, which is the #1372 shape (qa and the builder today; develop renders it).
        "emission_retries": [
            _fact(line, "Retryable failure for") for line in logs if "Retryable failure for" in line
        ],
        # 1.7.4 (#968, A1): the structured half of an analyzer claim refuted by the
        # workspace (`_verified_implicated_files`) — the control beside the prose half,
        # which nothing checks yet and which the decision reads.
        # 1.7.4 (#1374, F1): the framework rows the accepted-patch path re-derived on the
        # patched set — the corrected result's own row, read from the executor's line
        # ("patch task=… re-derived required_files on the patched set: passed=… missing=…").
        # The contentless-builder diagnostic showed `typed_checks.by_check` carries no such
        # row: the re-derivation is composed into the result, not stored as an evaluation
        # artifact, so this line is the only place the fact is visible from outside.
        # H1 (1.7.4) reads "no counted roll is rejected or blocked on the handoff", and
        # its own blind spot is that a NEW required file the profile derives fails
        # identically under a different name. So the readout is every required file the
        # roll's own evidence names, never the one the bar is about (#1312 added
        # `required=` to the row and to this line).
        "required_files_declared": sorted(
            {
                name
                for line in logs
                if "re-derived required_files" in line
                for name in (_field(line, "required") or "").split(",")
                if name and name != "-"
            }
        ),
        "framework_rows_rederived": [
            _fact(line, "patch task=") for line in logs if "re-derived required_files" in line
        ],
        # SIP-0107 §20 / §39.4: every accepted patch names the candidate it verified and the set
        # it stored; a mismatch fails the run, so a disagreeing entry is the failure's own line.
        "candidate_identities": [
            {
                "task": _field(line, "task"),
                "verified": _field(line, "verified_revision_id"),
                "persisted": _field(line, "persisted_revision_id"),
                "agree": "MISMATCH" not in line
                and _field(line, "verified_revision_id") == _field(line, "persisted_revision_id"),
            }
            for line in logs
            if "patch_candidate_identity task=" in line
        ],
        "analyzer_claims_dropped": [
            _fact(line, "correction_repair_target:")
            for line in logs
            if "dropped, not aimed at (#968)" in line
        ],
        # #1600: #968's PROSE half, which is the one an own-artifact route actually reaches.
        "analyzer_claims_refuted": analyzer_claims_refuted(logs),
        # L4 (#1273): the executor REFUNDS a round whose repair emitted no content — the
        # round is re-taken rather than spent (#1053/#998). This is the seam L4 names, and it
        # is a different mechanism from the #1129 exclusion above (a refused patch's
        # signature not counted as a repeat): the 1.7.3 chain diagnostic on the pinned deploy
        # refunded round 0 exactly as predicted and the readout, wired to the wrong field,
        # read L4 as not reached.
        "refunded_rounds": [
            _fact(line, "correction attempt")
            for line in logs
            if "refunded: the repair emitted no content" in line
        ],
        "evidence_superseded": [
            _fact(line, "patch_retest task=") for line in logs if "evidence superseded" in line
        ],
        # 1.7.1 (plan §4). R2: a qa-owned own-frame failure routed to the qa repair
        # (#1130). R4: the qa repair brief's case count (#1123) and an undeclared-anchor
        # routing. R7: patch verifications decided by the producing agent's own executed
        # rows (#1229, rule B) versus those that came back unverifiable because nothing
        # executed where verification ran.
        "qa_owned_routed": [
            _fact(line, "correction_repair_locus:") for line in logs if "qa_owned_routed" in line
        ],
        # Every own_artifact locus, whichever branch decided it. L7 asks whether an own-frame
        # failure reached the qa repair; `qa_owned_routed` is ONE of five branches that route
        # it there (#1130, #1581's unanimity, #970's re-fill, the absent-anchor rule, #1054's
        # dispute), and reading only that literal marker made a routing that worked read as a
        # routing that did not. Deploy A's `cyc_464625db7c2b` routed through unanimity and L7
        # read NO on a held invariant. Same family as #1616 — read the mechanism, not a token.
        "own_artifact_locus": [
            _fact(line, "correction_repair_locus:")
            for line in logs
            if _AFFIRMATIVE_OWN_ARTIFACT in line
        ],
        "absent_anchor_routed": [
            _fact(line, "correction_repair_locus:")
            for line in logs
            if "absent_anchor_routed" in line
        ],
        # #1276: the count alone cannot be read — a zero-case brief is correct when the
        # failed result carried no behavioural evidence and is the #1273 defect when it
        # did. Each record carries the count, the result the evidence was built from, and
        # whether that result had a ``tests_pass`` row at all.
        "repair_brief_case_counts": [
            {
                "cases": int(m.group("cases")),
                "from": m.group("source") or "?",
                "tests_pass_rows": int(m.group("rows")) if m.group("rows") else None,
            }
            for m in (
                re.search(
                    r"carries (?P<cases>\d+) failing case\(s\) for .*?"
                    r"(?: from=(?P<source>\S+) tests_pass_rows=(?P<rows>\d+))?$",
                    line.rstrip(),
                )
                for line in logs
                if "correction_repair_brief:" in line
            )
            if m
        ],
        "decided_by_agent": sum(
            int(m.group(1))
            for m in (re.search(r"decided_by_agent=(\d+)", line) for line in logs)
            if m
        ),
        # #1276: "unverifiable" is a verdict, not a reason. The 1.7.1 R7 readout counted
        # every ``no_executed_blocking_checks`` as an absent toolchain; Next.js roll 1's
        # came from an absent file (a prose-only repair). Both facts are on the line —
        # the verdict's own ``reason=`` and, since this issue, the rows' ``skips=``.
        "unverifiable_by_reason": _count_by(
            _field(line, "reason") or "unstated"
            for line in logs
            if "patch_verification task=" in line and "status=unverifiable" in line
        ),
        # The whole fact, not the unverifiable half. This counted skips only on
        # verifications that came back `unverifiable`, and read 0 for the React
        # checkpoint on deploy B — whose qa repair PASSED verification while three
        # `frontend_compiles` rows never ran (`skips=missing_tooling:3`), demoting
        # three already-passed view criteria. A skip on a passing verification is the
        # one this readout exists to surface (#1261, CLAUDE.md: count non-execution
        # beside failure).
        "no_execution_by_skip_reason": _sum_pairs(
            entry
            for line in logs
            if "patch_verification task=" in line
            for entry in (_field(line, "skips") or "").split(",")
            if entry and entry != "-"
        ),
        "no_execution_on_passed_verifications": _sum_pairs(
            entry
            for line in logs
            if "patch_verification task=" in line and "status=passed" in line
            for entry in (_field(line, "skips") or "").split(",")
            if entry and entry != "-"
        ),
    }


#: The typed checks the predictions read per roll, by check name. Read from every stored
#: ``typed_check_evaluation_*.json`` of the implementation run, so the readout is the
#: stored state, never a log.
#:
#: **Named for the check, not for a verdict (#1276).** These were ``kind_gate_rejections``
#: and friends, and reported an integer: React roll 5's "1 kind-gate rejection" was
#: ``assertion_kinds_match`` failing with ``file_not_found`` — the gate never rejected
#: anything. A row's reason is the readout; the count is what the reason is counted by.
_PREDICTION_CHECKS = {
    "assertion_kinds_match_rows": "assertion_kinds_match",
    "additive_containment_rows": "additive_containment",
    "dom_anchor_queries_rows": "dom_anchor_queries",
    "container_packaging_rows": "container_packaging",
    "undefined_names_rows": "undefined_names",
}

#: The row statuses a readout reports separately. ``skipped`` is here because #1261's gap
#: arrived as skipped rows and was invisible to a count of failed ones (CLAUDE.md).
_READOUT_STATUSES = ("failed", "skipped")


def typed_checks_by_check(cfg: SetConfig, cycle_id: str, impl_run: str | None) -> dict:
    """Per-check row counts by status over the run's stored typed-check evaluations, the
    prediction readouts derived from them, and ``checks_by_environment`` — which role's
    container each evaluation ran in (the artifact's task type names the producing role;
    rule B puts every emission-time evaluation there, #1229).

    Every field is in the vocabulary (#1445): without an implementation run, or without a
    stored evaluation, they are unaskable; a prediction check no row of which was
    evaluated is unaskable for that check rather than "0 failed, 0 skipped"; and
    ``required_files_rows`` — H1's first source — is unaskable on every roll, because the
    seam filters the framework's row out of the artifact by design.
    """
    by_check: dict[str, dict[str, dict[str, int]]] = {}
    by_env: dict[str, int] = {}
    evaluations_stored = 0
    for art in artifact_dirs(cfg, cycle_id, impl_run) if impl_run else []:
        for path in art.glob("typed_check_evaluation_*.json"):
            try:
                doc = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            evaluations_stored += 1
            task_type = str(doc.get("task_type") or "")
            role = task_type.split(".", 1)[0] if task_type else "?"
            env = f"agent:{role}"
            for row in doc.get("evaluations") or []:
                name = str(row.get("check") or "").removeprefix("acceptance:")
                status = str(row.get("status") or "?")
                reason = str(row.get("reason") or "unstated")
                reasons = by_check.setdefault(name, {}).setdefault(status, {})
                reasons[reason] = reasons.get(reason, 0) + 1
                by_env[env] = by_env.get(env, 0) + 1
    readouts = {
        key: {
            status: dict(
                sorted(
                    by_check.get(check, {}).get(status, {}).items(),
                    key=lambda kv: (-kv[1], kv[0]),
                )
            )
            for status in _READOUT_STATUSES
        }
        for key, check in _PREDICTION_CHECKS.items()
    }
    fields = {
        "by_check": by_check,
        "checks_by_environment": by_env,
        "stale_evaluations": _stale_evaluations(cfg, cycle_id, impl_run) if impl_run else [],
        **readouts,
        "required_files_rows": by_check.get("required_files", {}),
    }
    context = {
        "no_implementation_run": impl_run is None,
        "no_typed_check_evaluation_stored": evaluations_stored == 0,
        "filtered_at_typed_check_seam": "required_files" not in by_check,
        **{
            f"check_never_evaluated:{check}": check not in by_check
            for check in _PREDICTION_CHECKS.values()
        },
    }
    return with_states("typed_checks", fields, context)


def _stale_evaluations(cfg: SetConfig, cycle_id: str, impl_run: str) -> list[dict]:
    """Evaluations stored more than once WITHOUT being re-run — L3's blind spot (#1318).

    L3 (#1271) reads "the summary's failed rows against the last stored evaluation". On
    1.7.2 roll 1 the last stored evaluation of the builder task WAS failed, so that read
    said L3 held — while the artifact was a byte-identical re-store of the pre-patch
    evaluation, written eleven milliseconds before the patch's own file landed. The miss
    is only visible by comparing ``evaluated_at`` and ``workspace_revision_id`` across
    versions of the same evaluation file: a later STORE carrying an earlier EVALUATION is
    a run being judged on a tree that no longer exists.

    Reports one row per such file, so a readout that cannot see its own miss is replaced
    by one that names it.
    """
    versions: dict[str, list[tuple[str, str, str, list[str]]]] = {}
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        meta = _metadata(art)
        stored = str((meta or {}).get("created_at") or "")
        for path in art.glob("typed_check_evaluation_*.json"):
            try:
                doc = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            failed = sorted(
                {
                    str(row.get("check") or "")
                    for row in doc.get("evaluations") or []
                    if str(row.get("status") or "") in ("failed", "error")
                }
            )
            versions.setdefault(path.name, []).append(
                (
                    stored,
                    str(doc.get("evaluated_at") or ""),
                    str(doc.get("workspace_revision_id") or "")[:12],
                    failed,
                )
            )
    stale: list[dict] = []
    for name, rows in sorted(versions.items()):
        if len(rows) < 2:
            continue
        rows.sort()
        first, last = rows[0], rows[-1]
        if last[1] == first[1] and last[2] == first[2]:
            stale.append(
                {
                    "artifact": name,
                    "stored_versions": len(rows),
                    "first_stored": first[0],
                    "last_stored": last[0],
                    "evaluated_at": last[1],
                    "workspace_revision_id": last[2],
                    "failed_rows_carried": last[3],
                }
            )
    return stale


def fill_merge_evidence(cfg: SetConfig, cycle_id: str, impl_run: str) -> list[dict]:
    """Every qa task's stored ``fill_merge_evidence.json`` (#999) — the fill-merge
    dispositions, counts, assertion strength and additive-containment findings, read from
    the tree and never from a log. Each entry names the task the artifact came from."""
    out: list[dict] = []
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        m = _metadata(art)
        if not m or m.get("filename") != "fill_merge_evidence.json":
            continue
        try:
            payload = json.loads((REPO / m["vault_uri"]).read_text())
        except (OSError, KeyError, ValueError):
            continue
        fill = payload.get("fill_merge") or {}
        out.append(
            {
                "task_id": (m.get("metadata") or {}).get("task_id"),
                "counts": fill.get("counts"),
                "assertion_strength": fill.get("assertion_strength"),
                "additive_containment": fill.get("additive_containment", []),
                "self_eval_fills": len(payload.get("self_eval_fills") or []),
            }
        )
    return out


def uncollected_suites(cfg: SetConfig, cycle_id: str, impl_run: str) -> list[dict] | None:
    """The suites each stored ``test_report.md`` names as never collected (#1540), or ``None``
    when the run stored no report — an unasked question, not an empty answer.

    A suite the runner does not collect fails nothing: 1.7.3's accepted Next.js shakeout
    (``cyc_d988c11c71f5``) stored ``__tests__/runs-ui.test.tsx`` as run-nothing and its record
    read clean, and the shape recurred on 1.8.0 deploy A (#1534). Read from the report, the
    only persisted carrier, with the qa handler's own label. Each entry names the task and
    whether the report was banked with a failed emission (#971) or stored as the task's.
    """
    from squadops.capabilities.handlers.cycle.qa_test import UNCOLLECTED_REPORT_LABEL

    reports = 0
    out: list[dict] = []
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        m = _metadata(art)
        if not m or m.get("filename") != "test_report.md":
            continue
        try:
            text = (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            continue
        reports += 1
        _, found, rest = text.partition(UNCOLLECTED_REPORT_LABEL)
        files = re.findall(r"`([^`]+)`", rest.split("\n", 1)[0]) if found else []
        if files:
            meta = m.get("metadata") or {}
            out.append(
                {
                    "task_id": meta.get("task_id"),
                    "banked": "failed" if meta.get("emission_status") == "failed" else "stored",
                    "files": files,
                }
            )
    return out if reports else None


def _render_candidate_identities(entries: list[dict]) -> str:
    """``2 accepted, verified = persisted on 2`` — and the tasks where they did not agree."""
    entries = entries or []
    disagree = [str(e.get("task")) for e in entries if not e.get("agree")]
    text = f"{len(entries)} accepted, verified = persisted on {len(entries) - len(disagree)}"
    return text + (f"; MISMATCH on {', '.join(disagree)}" if disagree else "")


def _render_revision_forms(entries: list[dict]) -> str:
    """``development_correction_repair_handler whole_file (app/page.tsx; offered 1; replaced
    100% app/page.tsx)`` per repair — the files re-emitted whole that the repair was offered to
    revise in place are named, and every file's replaced span is read against its size (SIP-0107
    §46o), so a structural rewrite of a whole file does not read like a five-line edit."""
    parts = []
    for e in entries or []:
        if "unparsed" in e:
            parts.append("UNPARSED line")
            continue
        detail = [f"offered {len(e.get('offered') or {})}"]
        if e.get("modes"):
            detail.insert(0, "/".join(e["modes"]))
        if e.get("whole_file_offered"):
            detail.insert(0, ", ".join(e["whole_file_offered"]))
        if e.get("whole_file_unoffered"):
            # §46p: re-emitted whole without ever being offered the edit form (#1583).
            detail.insert(0, "never offered: " + ", ".join(e["whole_file_unoffered"]))
        if e.get("accepted") is not None:
            detail.append("accepted" if e["accepted"] else f"refused ({e.get('refusals', 0)})")
        if e.get("fragment_anchors"):
            detail.append(f"{e['fragment_anchors']} fragment anchor(s)")
        for path, span in sorted((e.get("replaced") or {}).items()):
            pct = span.get("pct") if isinstance(span, dict) else None
            detail.append(f"replaced {pct if pct is not None else '?'}% {path}")
        parts.append(f"{e.get('handler')} {e.get('form')} ({'; '.join(detail)})")
    return " · ".join(parts)


def _render_uncollected(entries: list[dict]) -> str:
    """``__tests__/runs-ui.test.tsx`` (3 reports: 1 failed, 2 stored) — per file, so a suite
    that ran nothing on every attempt reads differently from one a repair renamed."""
    by_file: dict[str, list[str]] = {}
    for entry in entries or []:
        for name in entry.get("files") or []:
            by_file.setdefault(name, []).append(str(entry.get("banked")))
    if not by_file:
        return "0"
    parts = []
    for name, banked in sorted(by_file.items()):
        counts = ", ".join(f"{banked.count(k)} {k}" for k in ("failed", "stored") if k in banked)
        parts.append(f"`{name}` ({len(banked)} report{'s' if len(banked) != 1 else ''}: {counts})")
    return "; ".join(parts)


def _fill_rejections(cfg: SetConfig, cycle_id: str, impl_run: str) -> list[str] | None:
    """The fill layer's rejection lines across the qa-authored scaffold suites, or ``None``
    when no such suite was stored to read — an unasked question, not an empty answer."""
    found = set()
    suites_read = 0
    for art in artifact_dirs(cfg, cycle_id, impl_run):
        m = _metadata(art)
        if not m or not str(m.get("filename", "")).startswith("__tests__/scaffold/"):
            continue
        if (m.get("metadata") or {}).get("role") != "qa":
            continue
        try:
            text = (REPO / m["vault_uri"]).read_text()
        except (OSError, KeyError):
            continue
        suites_read += 1
        found.update(
            line.strip()  # whole, not a window of it (#1330)
            for line in text.splitlines()
            if "fill layer:" in line and "rejected" in line
        )
    return sorted(found) if suites_read else None


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


#: How each state prints. ``asked_none`` is words, not ``0``, so a zero that was asked and a
#: field that could not be asked never share a glyph with each other or with an observed 0.
_ASKED_NONE_WORD = "none (asked)"
_UNASKABLE_WORD = "UNASKABLE"
_INFERRED_NOTE = " (state inferred: pre-#1445 record)"
_NOT_IN_RECORD = "— (not in record)"


def _show(ev: Evidence | None, fmt: Callable[[Any], str] = str) -> str:
    """One field in one of three visibly different shapes (#1445).

    ``fmt`` renders an OBSERVED value only; it is never handed an absence, so no formatter
    can turn ``unaskable`` into ``0`` or ``—``.
    """
    if ev is None:
        return _NOT_IN_RECORD
    note = "" if ev.declared else _INFERRED_NOTE
    if ev.state == UNASKABLE:
        return f"{_UNASKABLE_WORD} — {ev.reason}"
    if ev.state == ASKED_NONE:
        return _ASKED_NONE_WORD + note
    return fmt(ev.value) + note


def _show_at(rec: Mapping[str, Any], path: str, fmt: Callable[[Any], str] = str) -> str:
    return _show(evidence_at(rec, path), fmt)


def _count(value: Any) -> str:
    return str(len(value)) if isinstance(value, (list, dict)) else str(value)


def _render_by_reason(counts: Mapping[str, int] | None) -> str:
    """``2 missing_tooling, 1 file_not_found`` — never a bare integer (#1276)."""
    if not counts:
        return "0"
    return ", ".join(f"{count} {reason}" for reason, count in counts.items())


def _render_readout(readout: Mapping[str, Mapping[str, int]] | None) -> str:
    """One prediction check's rows: failed by reason, then non-execution by reason."""
    if not readout:
        return "—"
    return " · ".join(
        f"{status} {_render_by_reason(readout.get(status))}" for status in _READOUT_STATUSES
    )


def _render_stale(rows: list[dict]) -> str:
    """L3's own blind spot, named (#1318): a later STORE carrying an earlier EVALUATION.

    ``-`` means every stored evaluation was actually re-run against the tree it judged.
    """
    if not rows:
        return "-"
    return " · ".join(
        f"`{r['artifact']}` x{r['stored_versions']} @ ws `{r['workspace_revision_id']}` "
        f"carrying {', '.join(r['failed_rows_carried']) or 'no failed rows'}"
        for r in rows
    )


def _render_deploy(cfg: SetConfig, rec: dict) -> list[str]:
    """The deploy as OBSERVED at launch, kept apart from the config's typed pin (#1296).

    `frozen_deploy_commit` is a string an operator writes into the set config, and nothing
    can check it: the commit an image was built from is not recoverable from the image
    (`SOURCE_HASH` is a build arg for cache-busting, not an ENV or LABEL). The image ids
    and the loaded-module checks below ARE observed, and they are what identifies the
    deploy — so they belong in the record rather than only in the launch log.
    """
    ident = rec.get("deploy") or {}
    if not ident:
        return []
    # #1445: the probes in the vocabulary — from the record's own field, or derived from the
    # raw identity for a record written before the field existed (the derivation is exact:
    # the identity carries the error string).
    loaded = rec.get("loaded_checks") or loaded_check_evidence(ident)
    images = {k: v for k, v in ident.items() if k != "head" and not k.endswith(":loaded")}
    lines = [
        "## Deploy — observed at launch, not asserted here",
        "",
        f"- driver HEAD `{ident.get('head', '?')}`",
        f"- set config `frozen_deploy_commit`: "
        f"{f'`{cfg.frozen_deploy_commit}`' if cfg.frozen_deploy_commit else '**unset** (typed, not measured)'}",
        "",
        "| service | image id |",
        "|---|---|",
        *(f"| {svc} | `{img}` |" for svc, img in sorted(images.items())),
        "",
    ]
    if loaded:
        lines += [
            "**Loaded, not built** — each is a live call with its paired control; a probe "
            "that could not run is an unasked question, never an answer (#1425):",
            "",
            *(
                f"- `{name}` → {_show(Evidence.read(ev), lambda v: f'`{v}`')}"
                for name, ev in sorted(loaded.items())
            ),
            "",
        ]
    return lines


def _qa_tokens(by_handler: Mapping[str, Mapping[str, Any]]) -> str:
    """The qa handlers' spend, one figure per handler — the record's texture row (#1285)."""
    rows = [
        f"{name}: {row.get('completion_tokens', 0)} / {row.get('reasoning_tokens', 0)}"
        f" ({row.get('emissions', 0)} em)"
        for name, row in sorted(by_handler.items())
        if name.startswith("qa_")
    ]
    return "; ".join(rows) if rows else "—"


def _overruns(value: Mapping[str, Any]) -> str:
    return f"{value.get('overruns')} {value.get('by_service') or ''}".rstrip()


def _fill_strengths(entries: list[dict]) -> str:
    return str([(e.get("task_id"), e.get("assertion_strength")) for e in entries])


def _render_unaskable(rec: Mapping[str, Any]) -> list[str]:
    """Every registered field that was unaskable on this roll, with its reason, and every
    field whose state was inferred off a pre-#1445 value — so the table above is never
    the only place a reader can see what the roll could not ask."""
    unaskable: list[str] = []
    inferred: list[str] = []
    for path in _registered_paths(rec):
        ev = evidence_at(rec, path)
        if ev is None:
            continue
        if ev.state == UNASKABLE:
            unaskable.append(f"- `{path}` — {ev.reason}")
        elif not ev.declared:
            inferred.append(f"`{path}`")
    lines = [f"**Unaskable on this roll ({len(unaskable)})** — not zeros, not absences:", ""]
    lines += unaskable or ["- none: every registered field was asked"]
    if inferred:
        lines += [
            "",
            f"**State inferred, not declared ({len(inferred)})** — read off a pre-#1445 "
            "value; an empty one cannot say whether it was asked: " + ", ".join(inferred),
        ]
    return lines


def _registered_paths(rec: Mapping[str, Any]) -> list[str]:
    """The registry's paths as they occur in this record — the wildcard groups expanded."""
    paths: list[str] = []
    for path in EVIDENCE_FIELDS:
        group, _, leaf = path.rpartition(".")
        if leaf == "*":
            paths += [f"{group}.{name}" for name in sorted(rec.get(group) or {})]
        else:
            paths.append(path)
    return paths


def restate(rec: dict) -> tuple[dict, list[str]]:
    """A stored record's registered fields re-read in the vocabulary (#1445).

    A record written before the vocabulary carries bare values. The conditions that can be
    derived from the record itself are applied — no implementation run, no correction
    round, no emission-shape line, no retry aimed, no fill-merge artifact, the seam filter
    — and the fields those decide are declared. The conditions the record does not carry
    (whether the runtime-api window was empty, whether a qa scaffold suite was stored,
    whether an evaluation artifact existed and which checks it evaluated) are returned by
    name; the fields they govern are left with their state inferred and so marked. A
    record already in the vocabulary passes through unchanged.
    """
    out = json.loads(json.dumps(rec))
    texture = out.get("loop_texture") or {}
    typed = out.get("typed_checks") or {}
    correction = value_at(out, "correction_rounds", 0) or 0
    by_check = value_at(out, "typed_checks.by_check", {}) or {}
    context: dict[str, bool | None] = {
        "no_implementation_run": not out.get("impl_run_id"),
        "runtime_window_empty": None,
        "no_correction_round": not correction_entered(
            [
                str(v)
                for key in ("patch_verifications", "retests", "refunded_rounds")
                for v in (value_at(out, f"loop_texture.{key}", []) or [])
            ],
            correction,
        ),
        "no_emission_shape_lines": (value_at(out, "loop_texture.emissions_logged", 0) or 0) == 0,
        "no_emission_retry_aimed": not value_at(out, "loop_texture.emission_retries", []),
        "no_correction_decision_stored": correction == 0,
        "no_fill_merge_artifact": not value_at(out, "loop_texture.fill_merge_evidence", []),
        "no_test_report_stored": None,
        "no_qa_scaffold_suite": None,
        "logged_in_the_agent_container": True,
        "no_typed_check_evaluation_stored": None if not by_check else False,
        "filtered_at_typed_check_seam": "required_files" not in by_check,
        **{
            f"check_never_evaluated:{check}": (check not in by_check) if by_check else None
            for check in _PREDICTION_CHECKS.values()
        },
    }
    underivable = sorted(k for k, v in context.items() if v is None)

    def restated(path: str, value: Any) -> Any:
        # A field already declared in the vocabulary is the producer's word: it passes
        # through, never re-derived from a weaker context (the live roll could state
        # `runtime_window_empty`; a stored record cannot).
        if path in _NOT_EVIDENCE or Evidence.read(value).declared:
            return value
        return evidence_for(path, value, context).record()

    for key in ("correction_rounds", "failed_emission_artifacts_banked", "failed_emissions_banked"):
        if key in out:
            out[key] = restated(key, out[key])
    if texture:
        out["loop_texture"] = {k: restated(f"loop_texture.{k}", v) for k, v in texture.items()}
    if typed:
        typed.setdefault("required_files_rows", by_check.get("required_files", {}))
        out["typed_checks"] = {k: restated(f"typed_checks.{k}", v) for k, v in typed.items()}
    if out.get("deploy") and not out.get("loaded_checks"):
        out["loaded_checks"] = loaded_check_evidence(out["deploy"])
    return out, underivable


def cmd_rerender(cfg: SetConfig, record: Path, out: Path) -> int:
    rec, underivable = restate(json.loads(record.read_text()))
    md = render(cfg, f"re-rendered from {record.name} (#1445)", rec)
    if underivable:
        md += (
            "\n## Conditions this stored record cannot state\n\n"
            "The fields these govern are marked *state inferred* above rather than declared:\n\n"
            + "\n".join(f"- `{c}` — {unaskable_reason(c)}" for c in underivable)
            + "\n"
        )
    out.write_text(md)
    print(md)
    return 0


def render(cfg: SetConfig, title: str, rec: dict) -> str:
    audit = rec.get("boot_audit", {})
    functional = rec.get("verdict") == "accepted" and audit.get("passed") is True
    lines = [
        f"# {cfg.name} — {title}",
        "",
        f"**Cycle** `{rec['cycle_id']}` · stack `{rec.get('stack')}` · deploy "
        f"`{cfg.frozen_deploy_commit or rec.get('deploy', {}).get('head') or '?'}` · "
        f"config `{(rec.get('config_hash') or cfg.expected_config_hash_prefix or '?')[:12]}` · "
        f"squad snapshot `{(rec.get('squad_profile_snapshot_ref') or '?')[:12]}`",
        "",
        # #80: what the cycle record says created it, observed — beside the typed deploy pin
        # above, so the two can be read against each other.
        f"**Code, from the cycle record** framework "
        f"{_show_at(rec, 'lineage.framework_version', lambda v: f'`{v}`')} · commit "
        f"{_show_at(rec, 'lineage.framework_git_sha', lambda v: f'`{v}`')} · request profile "
        f"{_show_at(rec, 'lineage.request_profile', lambda v: f'`{v}`')}",
        "",
        "## Headline",
        "",
        *(
            [
                "- **DIAGNOSTIC — injected fault(s): "
                f"{', '.join(sorted(declared_fault_names(cfg.overrides)))}"
                "**. This cycle carried a deliberate emission defect (#1251): its verdict is "
                "not a verdict about the squad, and it must not be counted.",
                *(
                    f"- seam reached — `{name}`: **{_seam_state(r)}** — "
                    f"{r.get('seam') or 'no readout for this fault'} (#1310)"
                    + _applied_words(r)
                    + (
                        " — **read over unaskable field(s)**: "
                        + "; ".join(f"`{p}` — {why}" for p, why in r["unaskable"].items())
                        if r.get("unaskable")
                        else ""
                    )
                    for name, r in sorted((rec.get("seam_reached") or {}).items())
                ),
                "",
            ]
            if declared_fault_names(cfg.overrides)
            else []
        ),
        f"- verdict: **{rec.get('verdict')}**",
        *(
            [f"- ended with NO implementation run — {rec['ended_without_implementation']}"]
            if rec.get("ended_without_implementation")
            else []
        ),
        f"- boot audit: **{'PASS' if audit.get('passed') else 'FAIL' if audit.get('ran') else 'NOT RUN'}**"
        + (
            f" — {audit.get('detail', '')}" if audit.get("ran") else f" ({audit.get('reason', '')})"
        ),
        f"- functional (verdict AND audit AND zero intervention): **{'yes' if functional else 'no'}**",
        f"- P0 (seeded tree vs manifest): **{_p0_word(rec.get('static_checks', {}).get('p0'))}**",
        f"- wall clock: {rec['wall_clock_seconds'] // 60} min",
        "",
        "## Texture",
        "",
        f"Every registered field reads one of three states (#1445): a value — **observed**; "
        f"`{_ASKED_NONE_WORD}` — asked and absent or zero; `{_UNASKABLE_WORD} — reason` — "
        "the producer could not ask it on this roll. The unaskable fields are listed again "
        "below the table; no line here folds one into a count.",
        "",
        "| field | value |",
        "|---|---|",
        f"| framing runs / re-rolls | {rec['framing_runs']} / {rec['framing_rerolls']} |",
        f"| correction rounds | {_show_at(rec, 'correction_rounds')} |",
        f"| failed checks | {', '.join(rec['failed_checks']) or '—'} |",
        f"| criteria verified / total | {rec['criteria_verified']} / {rec['criteria_total']} |",
        "| criteria NOT verified — a row was produced, not credited | "
        f"{', '.join(rec.get('criteria_adverse') or []) or '—'} |",
        "| criteria unevidenced — no row in either direction | "
        f"{', '.join(rec['criteria_unevidenced']) or '—'} |",
        "| failed emission ARTIFACTS banked (#971) | "
        f"{_show_at(rec, 'failed_emission_artifacts_banked')} |",
        "| failed EMISSIONS banked (#1436, from the attempt stamp) | "
        f"{_show_at(rec, 'failed_emissions_banked')} |",
        "| contentless emissions (L1) | "
        f"{_show_at(rec, 'loop_texture.contentless_by_handler', _render_by_reason)}"
        f" of {_show_at(rec, 'loop_texture.emissions_logged')} logged |",
        "| 1.7.4 H1 required files the roll's rows named (#1312) | "
        f"{_show_at(rec, 'loop_texture.required_files_declared', ', '.join)} |",
        "| 1.7.4 H1 required_files rows in the typed-check artifact | "
        f"{_show_at(rec, 'typed_checks.required_files_rows')} |",
        "| 1.7.4 F1 framework rows re-derived on the patched set (#1374) | "
        f"{_show_at(rec, 'loop_texture.framework_rows_rederived')} |",
        "| accepted patches whose verified and persisted identities agree (SIP-0107 §20) | "
        f"{_show_at(rec, 'loop_texture.candidate_identities', _render_candidate_identities)} |",
        "| repair responses by revision form — offered, and taken (SIP-0107 §46a) | "
        f"{_show_at(rec, 'loop_texture.repair_revision_forms', _render_revision_forms)} |",
        "| 1.7.4 R1 emission retries aimed / with fact / blind (#1372) | "
        f"{_show_at(rec, 'loop_texture.emission_retries', _count)} / "
        f"{_show_at(rec, 'loop_texture.retried_with_fact', _count)} / "
        f"{_show_at(rec, 'loop_texture.retried_blind', _count)} |",
        "| 1.7.4 Prefect loop overruns in the window (#330) | "
        f"{_show_at(rec, 'loop_texture.prefect_loop_overruns', _overruns)} |",
        "| 1.7.4 B1 non-root fixture tables: suites read / mentions (#1087) | "
        f"{_b1_words((rec.get('static_checks') or {}).get('non_root_fixture_tables'))} |",
        "| R1 assertion_kinds_match rows | "
        f"{_show_at(rec, 'typed_checks.assertion_kinds_match_rows', _render_readout)} |",
        f"| R2 qa-owned routed | {_show_at(rec, 'loop_texture.qa_owned_routed', _count)} |",
        "| R3 dom_anchor_queries rows | "
        f"{_show_at(rec, 'typed_checks.dom_anchor_queries_rows', _render_readout)} |",
        "| R4 repair briefs (cases, from, tests_pass rows) / absent-anchor routed | "
        f"{_show_at(rec, 'loop_texture.repair_brief_case_counts')} / "
        f"{_show_at(rec, 'loop_texture.absent_anchor_routed', _count)} |",
        "| R5 additive_containment rows | "
        f"{_show_at(rec, 'typed_checks.additive_containment_rows', _render_readout)} |",
        "| R6 undefined_names rows | "
        f"{_show_at(rec, 'typed_checks.undefined_names_rows', _render_readout)} |",
        "| R7 decided by agent / unverifiable by reason | "
        f"{_show_at(rec, 'loop_texture.decided_by_agent')} / "
        f"{_show_at(rec, 'loop_texture.unverifiable_by_reason', _render_by_reason)} |",
        "| non-execution by skip reason (all patch verifications) | "
        f"{_show_at(rec, 'loop_texture.no_execution_by_skip_reason', _render_by_reason)} |",
        "| ...of which on a verification that PASSED | "
        f"{_show_at(rec, 'loop_texture.no_execution_on_passed_verifications', _render_by_reason)} |",
        "| suites the runner never collected, per stored test report (#1540) | "
        f"{_show_at(rec, 'loop_texture.uncollected_suites', _render_uncollected)} |",
        "| fill-merge assertion strength per qa task (#999) | "
        f"{_show_at(rec, 'loop_texture.fill_merge_evidence', _fill_strengths)} |",
        "| fill layer rejections in the stored qa suites | "
        f"{_show_at(rec, 'loop_texture.fill_rejections')} |",
        "| qa emission tokens (completion / reasoning, handlers starting `qa_`) | "
        f"{_show_at(rec, 'loop_texture.emission_tokens_by_handler', _qa_tokens)} |",
        "| L8a extractor strips of `path/` (model emitted under it) / L8b stored under `path/` | "
        f"{_show_at(rec, 'loop_texture.placeholder_strips', _count)} / "
        f"{_show_at(rec, 'loop_texture.stored_under_placeholder')} |",
        f"| checks by environment | {_show_at(rec, 'typed_checks.checks_by_environment')} |",
        "| container_packaging rows (reporting-only) | "
        f"{_show_at(rec, 'typed_checks.container_packaging_rows', _render_readout)} |",
        "| L3 stale evaluations (re-stored, not re-run) | "
        f"{_show_at(rec, 'typed_checks.stale_evaluations', _render_stale)} |",
        "",
        *_render_unaskable(rec),
        "",
        *_render_deploy(cfg, rec),
        "## Gate decisions (decider recorded verbatim, never inferred)",
        "",
    ]
    lines += [
        f"- `{g['gate']}` → **{g['decision']}** by `{g['decided_by']}`"
        for g in rec["gate_decisions"]
    ]
    lines += [
        "",
        "## Runs",
        "",
        "| # | workload | status | min | failure |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['run_number']} | {r['workload']} | {r['status']} | {r['seconds'] // 60} | {r['failure_reason'] or '—'} |"
        for r in rec["runs"]
    ]
    lines += [
        "",
        "## Scoring — NOT decided here",
        "",
        "Validity (void / reset / counted) is a reading made at the roll boundary.",
        "The driver reports; the pre-registration decides.",
        "",
    ]
    return "\n".join(lines)


def _b1_words(b1: dict | None) -> str:
    if not b1:
        return "—"
    if b1.get("refused"):
        return f"REFUSED — {b1['refused']}"
    mentions = b1.get("mentions") or []
    return f"{b1.get('suites_read', 0)} / {mentions or 'none'}"


def _p0_word(p0: dict | None) -> str:
    if not p0:
        return "not run"
    if p0.get("refused"):
        return f"REFUSED — {p0['refused']}"
    return "held" if p0.get("passed") else "FALSIFIED"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def identity_mismatch(expected_prefix: str, actual: str) -> bool:
    """True when a pinned identity is set and the roll's value does not carry it."""
    return bool(expected_prefix) and not (actual or "").startswith(expected_prefix)


def _write_record(cfg: SetConfig, stem: str, rec: dict, md: str) -> None:
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (cfg.records_path / f"{stem}-{stamp}.json").write_text(json.dumps(rec, indent=2))
    (cfg.records_path / f"{stem}-{stamp}.md").write_text(md)


def _run_cycle(
    cfg: SetConfig,
    stack: str,
    notes: str,
    *,
    title: str,
    stem: str,
    assert_hash: bool,
    identity: Mapping[str, str],
) -> int:
    launched_at = log_since(datetime.now(UTC))
    cyc, run, chash = launch(cfg, notes)
    log(f"{title} launched: {cyc} / {run} config-hash {chash[:12]} stack {stack}")
    if cfg.expected_config_hash_prefix and not chash.startswith(cfg.expected_config_hash_prefix):
        log(f"!! config hash {chash[:12]} != the set's {cfg.expected_config_hash_prefix}")
        if assert_hash:
            log("   the roll is NOT comparable; recording and stopping")
            return 3
    ended_early = drive(cfg, cyc)
    rec = collect(cfg, cyc)
    # #1296: the identity this cycle was actually launched against, in the record rather
    # than only in the log. `render`'s fallback to it has been dead since the field was
    # written, because nothing ever put a `deploy` key here — so a shakeout, the one cycle
    # whose deploy is by definition unpinned, printed `deploy ?`.
    rec["deploy"] = dict(identity)
    rec["ended_without_implementation"] = ended_early
    rec["stack"] = stack
    rec["config_hash"] = chash
    rec["launched_at"] = launched_at
    if identity_mismatch(cfg.expected_squad_snapshot_prefix, rec["squad_profile_snapshot_ref"]):
        log(
            f"!! squad-profile snapshot {rec['squad_profile_snapshot_ref'][:16]} != the set's "
            f"{cfg.expected_squad_snapshot_prefix} — a different squad configuration"
        )
        if assert_hash:
            log("   the roll is NOT comparable; recording and stopping")
            _write_record(cfg, stem, rec, render(cfg, title, rec))
            return 3
    framing = completed_framing_run(cyc)
    rec["static_checks"] = static_checks(cfg, stack, cyc, rec["impl_run_id"], framing)
    rec["ledger_checks"] = ledger_checks(rec)
    rec["loop_texture"] = loop_texture(
        cfg,
        cyc,
        rec["impl_run_id"],
        launched_at,
        until=cycle_log_until(cyc),
        correction_rounds=value_at(rec, "correction_rounds", 0),
    )
    # #1445: always produced — without an implementation run every field is unaskable,
    # which is a different record from `{}`.
    rec["typed_checks"] = typed_checks_by_check(cfg, cyc, rec["impl_run_id"])
    rec["loaded_checks"] = loaded_check_evidence(identity)
    # #1310: a diagnostic is read by the seam it reached, not by whether its fault fired.
    faults = declared_fault_names(cfg.overrides)
    rec["seam_reached"] = seam_readouts(faults, rec) if faults else {}
    rec["boot_audit"] = (
        boot_audit(cfg, cyc, rec["impl_run_id"])
        if rec["impl_run_id"]
        else {"ran": False, "reason": "no implementation run"}
    )
    # SIP-0108 §4.4/§10i on the record: which arm produced this roll, and the substrate it
    # was admitted under. A reviewer reconstructs why a pair was comparable from the record,
    # never from a value that existed only while the driver ran.
    rec["arm"] = cfg.arm
    rec["arm_substrate"] = arm_substrate(cfg) if cfg.arm else {}
    # §10i item 6, over the COMPLETED run: a framing document, a failure analysis or a
    # correction decision means the solo arm did not run without them, whatever its profile
    # declared. A contaminated roll is named in the record and excluded, not quietly counted.
    rec["solo_absences"] = (
        solo_absence_problems(cfg, cyc, rec["impl_run_id"])
        if cfg.arm == SOLO_ARM and rec["impl_run_id"]
        else []
    )
    if rec["solo_absences"]:
        for problem in rec["solo_absences"]:
            log(f"!! {problem}")
        log("   the roll did not run the solo arm; recording and excluding it")
        rec["excluded_from_comparison"] = True
    md = render(cfg, title, rec)
    _write_record(cfg, stem, rec, md)
    print()
    print(md)
    print("STATIC CHECKS:", json.dumps(rec["static_checks"], indent=2))
    print("LEDGER CHECKS:", json.dumps(rec["ledger_checks"], indent=2))
    print("LOOP TEXTURE:", json.dumps(rec["loop_texture"], indent=2))
    p0 = rec["static_checks"].get("p0") or {}
    if p0.get("refused"):
        return 4
    # A red framing is a recorded outcome, not a silent zero: a chained set or a watcher
    # reading only the exit code would otherwise treat "never built anything" as a pass.
    return 5 if ended_early else 0


def cmd_preflight(cfg: SetConfig, counting: bool, identity: dict[str, str]) -> int:
    problems = preflight(cfg, counting=counting, identity=identity)
    if problems:
        print("PREFLIGHT FAILED — nothing launched:")
        for p in problems:
            print(f"  ✗ {p}")
        return 2
    log("preflight clean")
    return 0


def cmd_shakeout(cfg: SetConfig, dry_run: bool) -> int:
    # The identity is taken BEFORE preflight and handed to it: preflight judges the very
    # readout that lands in the record, rather than a second one taken moments later.
    ident = deploy_identity(cfg)
    rc = cmd_preflight(cfg, counting=False, identity=ident)
    if rc:
        return rc
    stack = stack_for(cfg)
    log(f"stack {stack}; deploy identity: {json.dumps(ident)}")
    if dry_run:
        return 0
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    (cfg.records_path / "shakeout-deploy.json").write_text(json.dumps(ident, indent=2))
    return _run_cycle(
        cfg,
        stack,
        cfg.shakeout_notes,
        title="shakeout (non-counting)",
        stem="shakeout",
        assert_hash=False,
        identity=ident,
    )


def cmd_roll(cfg: SetConfig, roll: int, dry_run: bool) -> int:
    ident = deploy_identity(cfg)
    rc = cmd_preflight(cfg, counting=True, identity=ident)
    if rc:
        return rc
    stack = stack_for(cfg)
    # #1296: observed for a counted roll too, not only a shakeout. The image-id pin above
    # already refuses a changed deploy; this puts the identity that passed that check —
    # and the loaded-module checks — into the roll's own record, so "loaded, not built" is
    # re-verified per roll instead of once per shakeout and inherited by assertion.
    log(f"stack {stack}; deploy identity: {json.dumps(ident)}")
    if dry_run:
        return 0
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    if not cfg.head_pin.exists():
        cfg.head_pin.write_text(sh(f"git -C {REPO} rev-parse --short HEAD"))
    notes = render_launch_notes(cfg.launch_notes, roll, cfg.n_rolls)
    return _run_cycle(
        cfg,
        stack,
        notes,
        title=f"roll {roll} of {cfg.n_rolls}",
        stem=f"roll-{roll:02d}",
        assert_hash=True,
        identity=ident,
    )


# ---------------------------------------------------------------------------
# The comparison window — pairs, executed as they are analysed (SIP-0108 §4.4, plan §4.3)
# ---------------------------------------------------------------------------

#: The squad arm's name, the counterpart of ``SOLO_ARM``. One constant each, so a set config
#: and the pairing cannot disagree about which arm is which.
SQUAD_ARM = "squad"

#: The window's running state, written after every roll so a window that spans a day can be
#: resumed from the last completed roll rather than re-run from pair 1.
WINDOW_STATE = "window-state.json"

#: Why a roll VOIDS its pair, by the runner's exit code — plan §4.3: "a pair is void only for
#: pre-run identity or infrastructure invalidity named by the rule, never for outcome."
#: Exit 0 (a verdict) and 5 (a red framing) are outcomes and never void: a roll that never
#: built anything is a roll that is not accepted-functional, which is what the predicate reads.
VOID_BY_EXIT: dict[int, str] = {
    2: "preflight refused the launch — pre-run identity or infrastructure",
    3: "the roll's config hash or squad snapshot did not match the arm's pins",
    4: "P0 refused — the seeded tree did not match the manifest (infrastructure)",
}


def pair_order(k: int) -> tuple[str, str]:
    """Pair *k*'s execution order, pre-registered and alternating (plan §4.3).

    Odd pairs run Squad then Solo, even pairs Solo then Squad — never six of one arm and then
    six of the other. Pairs are matched trials; alternating removes the temporal confounds a
    serial order carries (model and cache warming, host thermal state, accumulated state).
    """
    return (SQUAD_ARM, SOLO_ARM) if k % 2 == 1 else (SOLO_ARM, SQUAD_ARM)


def roll_functional(rec: Mapping[str, Any]) -> bool:
    """The predicate's unit: accepted AND the boot audit passed — the same reading ``render``
    prints as ``functional``, so the window and the roll record cannot disagree."""
    audit = rec.get("boot_audit") or {}
    return rec.get("verdict") == "accepted" and audit.get("passed") is True


def pair_outcome(squad_functional: bool, solo_functional: bool) -> str:
    """Per pair, binary on accepted-functional (plan §4.3, §8 decision 7).

    A Squad win when Squad is accepted-functional and Solo is not; a Solo win when Solo is and
    Squad is not; otherwise a tie — both functional and neither functional are both ties. The
    verification-quality proxy and efficiency are reported beside this and never break it.
    """
    if squad_functional and not solo_functional:
        return SQUAD_ARM
    if solo_functional and not squad_functional:
        return SOLO_ARM
    return "tie"


def emission_tokens_total(rec: Mapping[str, Any]) -> int | None:
    """Completion tokens summed over every handler, or ``None`` when the record could not ask
    (an arm that never reached implementation). Efficiency is reported per pair, never a
    tie-breaker (plan §4.3)."""
    field = (rec.get("loop_texture") or {}).get("emission_tokens_by_handler") or {}
    if field.get("state") != "observed":
        return None
    total = 0
    for entry in (field.get("value") or {}).values():
        if isinstance(entry, Mapping):
            try:
                total += int(entry.get("completion_tokens") or 0)
            except (TypeError, ValueError):
                continue
    return total


def window_tally(pairs: Sequence[Mapping[str, Any]], required: int, max_attempts: int) -> dict:
    """The window's reading over its attempted pairs, in the words the plan fixes.

    Always renders Squad wins / Solo wins / ties over the VALID pairs; the directional
    criterion is at least four wins of six valid for either arm, read as ``squad``, ``solo``
    or ``neither``. A window with fewer valid pairs than required after the attempt budget is
    ``complete: False`` and says so — the criterion is then not read at all rather than read
    over a short count.
    """
    # A pair is valid only once BOTH rolls landed and neither voided; a pair whose mate is
    # still owed (a window resumed mid-pair) is neither valid nor void yet.
    valid = [p for p in pairs if not p.get("void") and p.get("outcome") is not None]
    wins = {SQUAD_ARM: 0, SOLO_ARM: 0, "tie": 0}
    for p in valid:
        wins[p["outcome"]] += 1
    complete = len(valid) >= required
    threshold = (2 * required + 2) // 3  # four of six; scales with the registered count
    if not complete:
        criterion = "not read — the window closed incomplete"
    elif wins[SQUAD_ARM] >= threshold:
        criterion = SQUAD_ARM
    elif wins[SOLO_ARM] >= threshold:
        criterion = SOLO_ARM
    else:
        criterion = "neither"
    return {
        "squad_wins": wins[SQUAD_ARM],
        "solo_wins": wins[SOLO_ARM],
        "ties": wins["tie"],
        "valid_pairs": len(valid),
        "void_pairs": sum(1 for p in pairs if p.get("void")),
        "attempted_pairs": len(pairs),
        "required_pairs": required,
        "max_attempts": max_attempts,
        "threshold": threshold,
        "complete": complete,
        "criterion": criterion,
    }


def _latest_record(cfg: SetConfig, stem: str) -> dict | None:
    paths = sorted(cfg.records_path.glob(f"{stem}-*.json"))
    if not paths:
        return None
    return json.loads(paths[-1].read_text())


def _window_roll(cfg: SetConfig, arm: str, k: int, required: int) -> dict:
    """One arm's roll of pair *k*: preflight, launch, and the void reading in one record."""
    ident = deploy_identity(cfg)
    isolation = run_state_isolation_problems(cfg)
    if isolation:
        for problem in isolation:
            log(f"!! {problem}")
        return {"arm": arm, "launched": False, "void": isolation[0]}
    rc = cmd_preflight(cfg, counting=True, identity=ident)
    if rc:
        return {"arm": arm, "launched": False, "void": VOID_BY_EXIT.get(rc, f"preflight exit {rc}")}
    stack = stack_for(cfg)
    log(f"pair {k} {arm} arm — stack {stack}; deploy identity: {json.dumps(ident)}")
    cfg.records_path.mkdir(parents=True, exist_ok=True)
    if not cfg.head_pin.exists():
        cfg.head_pin.write_text(sh(f"git -C {REPO} rev-parse --short HEAD"))
    stem = f"pair-{k:02d}-{arm}"
    rc = _run_cycle(
        cfg,
        stack,
        render_launch_notes(cfg.launch_notes, k, required),
        title=f"pair {k} of {required} — {arm} arm",
        stem=stem,
        assert_hash=True,
        identity=ident,
    )
    rec = _latest_record(cfg, stem) or {}
    out = {
        "arm": arm,
        "launched": True,
        "exit": rc,
        "cycle_id": rec.get("cycle_id"),
        "verdict": rec.get("verdict"),
        "functional": roll_functional(rec),
        "wall_clock_seconds": value_at(rec, "wall_clock_seconds", None),
        "completion_tokens": emission_tokens_total(rec),
        "void": None,
    }
    if rc in VOID_BY_EXIT:
        out["void"] = VOID_BY_EXIT[rc]
    elif rec.get("excluded_from_comparison"):
        out["void"] = "§10i: the solo roll stored an artifact the arm is defined by not producing"
    return out


def _window_state_path(squad_cfg: SetConfig) -> Path:
    return squad_cfg.records_path / WINDOW_STATE


def _save_window_state(squad_cfg: SetConfig, state: dict) -> None:
    squad_cfg.records_path.mkdir(parents=True, exist_ok=True)
    _window_state_path(squad_cfg).write_text(json.dumps(state, indent=2))


def render_window(state: dict, tally: dict) -> str:
    lines = [
        f"# {state['name']} — the comparison window",
        "",
        f"Squad arm `{state['squad_set']}` · Solo arm `{state['solo_set']}` · "
        f"{tally['required_pairs']} valid pairs required of at most {tally['max_attempts']} "
        f"attempted · started {state['started_at']}",
        "",
        "## Reading",
        "",
        f"- **Squad wins / Solo wins / ties: {tally['squad_wins']} / {tally['solo_wins']} / "
        f"{tally['ties']}** over {tally['valid_pairs']} valid pair(s) "
        f"({tally['void_pairs']} void of {tally['attempted_pairs']} attempted)",
        f"- directional criterion (at least {tally['threshold']} wins of "
        f"{tally['required_pairs']} valid, either arm): **{tally['criterion']}**",
        f"- window closed **{'complete' if tally['complete'] else 'INCOMPLETE'}**",
        "",
        "The claim is stated as measured — this PRD, this model, this deploy, the squad's "
        "organization against one generalist process — and is not generalized (plan §4.3, "
        "§8 decision 9). Quality is a verification-quality proxy and efficiency is reported "
        "per pair; neither breaks a tie.",
        "",
        "## Pairs",
        "",
        "| pair | order | squad cycle | squad functional | solo cycle | solo functional | "
        "outcome | void | wall clock s (squad / solo) | completion tokens (squad / solo) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in state["pairs"]:
        squad = p["rolls"].get(SQUAD_ARM) or {}
        solo = p["rolls"].get(SOLO_ARM) or {}

        def cell(r: Mapping[str, Any], key: str) -> str:
            if not r.get("launched"):
                return "not launched"
            v = r.get(key)
            return "unaskable" if v is None else str(v)

        lines.append(
            f"| {p['k']} | {' → '.join(p['order'])} | `{squad.get('cycle_id') or '—'}` | "
            f"{cell(squad, 'functional')} | `{solo.get('cycle_id') or '—'}` | "
            f"{cell(solo, 'functional')} | {p.get('outcome') or '—'} | {p.get('void') or '—'} | "
            f"{cell(squad, 'wall_clock_seconds')} / {cell(solo, 'wall_clock_seconds')} | "
            f"{cell(squad, 'completion_tokens')} / {cell(solo, 'completion_tokens')} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def window_problems(squad_cfg: SetConfig, solo_cfg: SetConfig) -> list[str]:
    """Why two configs are not a registered pair — read before anything launches.

    The pair is the two configs SUPPLIED: ``compare_with`` must name the counterpart's own
    file (one way or reciprocally), never merely some file that exists — otherwise the
    per-launch gate could compare one arm against a third config while the runner pairs it
    with another. The sample and attempt budget are the configs' registered values, declared
    on both and equal.
    """
    problems: list[str] = []
    if squad_cfg.arm != SQUAD_ARM:
        problems.append(f"{squad_cfg.name}: arm is {squad_cfg.arm!r}, expected {SQUAD_ARM!r}")
    if solo_cfg.arm != SOLO_ARM:
        problems.append(f"{solo_cfg.name}: arm is {solo_cfg.arm!r}, expected {SOLO_ARM!r}")
    names_other = {
        squad_cfg.name: squad_cfg.compare_with == solo_cfg.source,
        solo_cfg.name: solo_cfg.compare_with == squad_cfg.source,
    }
    if not any(names_other.values()):
        problems.append(
            f"neither config names the other in compare_with (squad: {squad_cfg.compare_with!r}, "
            f"solo: {solo_cfg.compare_with!r}; the supplied files are {squad_cfg.source!r} and "
            f"{solo_cfg.source!r}) — a pair the gate never admitted is not a pair"
        )
    for cfg in (squad_cfg, solo_cfg):
        if cfg.compare_with and not names_other[cfg.name]:
            problems.append(
                f"{cfg.name}: compare_with names {cfg.compare_with!r}, not the supplied "
                "counterpart — the gate would compare against a config the runner is not pairing"
            )
        # The per-launch gate reloads a counterpart from SET_CONFIG_DIR by name, so a supplied
        # file that only SHARES that name would be admitted here and substituted there.
        canonical = str((SET_CONFIG_DIR / cfg.source).resolve())
        if cfg.source_path and cfg.source_path != canonical:
            problems.append(
                f"{cfg.name}: supplied from {cfg.source_path}, not the registered set config "
                f"{canonical} — a same-name file elsewhere is not the registered arm"
            )
    pairs, attempts = squad_cfg.window_pairs, squad_cfg.window_max_attempts
    if (pairs, attempts) != (solo_cfg.window_pairs, solo_cfg.window_max_attempts):
        problems.append(
            f"the arms register different windows: squad {pairs}/{attempts}, solo "
            f"{solo_cfg.window_pairs}/{solo_cfg.window_max_attempts} (pairs/max attempts)"
        )
    if pairs < 1 or attempts < pairs:
        problems.append(
            f"window_pairs {pairs} / window_max_attempts {attempts} — both registered on the "
            "configs, at least one pair, the budget at least the sample"
        )
    return problems


def _window_state(
    squad_cfg: SetConfig, solo_cfg: SetConfig, pairs: int, max_attempts: int, resume: bool
) -> dict:
    state_path = _window_state_path(squad_cfg)
    if resume and state_path.exists():
        state = json.loads(state_path.read_text())
        registered = (
            state.get("squad_set"),
            state.get("solo_set"),
            state.get("required_pairs"),
            state.get("max_attempts"),
        )
        supplied = (squad_cfg.name, solo_cfg.name, pairs, max_attempts)
        if registered != supplied:
            raise SystemExit(
                f"resume refused: the recorded window is {registered} and the supplied "
                f"registration is {supplied} — a window's arms, sample and budget do not "
                "change after results exist"
            )
        log(f"resuming the window from {state_path} — {len(state['pairs'])} pair(s) recorded")
        return state
    return {
        "name": f"{squad_cfg.name} vs {solo_cfg.name}",
        "squad_set": squad_cfg.name,
        "solo_set": solo_cfg.name,
        "started_at": log_since(datetime.now(UTC)),
        "required_pairs": pairs,
        "max_attempts": max_attempts,
        "pairs": [],
    }


def _next_pair(state: dict) -> dict:
    """The pair to run next: one whose mate is still owed, else a new sequential pair."""
    pending = [p for p in state["pairs"] if not p.get("void") and p.get("outcome") is None]
    if pending:
        return pending[0]
    k = len(state["pairs"]) + 1
    pair = {"k": k, "order": list(pair_order(k)), "rolls": {}, "outcome": None, "void": None}
    state["pairs"].append(pair)
    return pair


def _run_pair(pair: dict, cfgs: Mapping[str, SetConfig], required: int, save: Callable) -> None:
    """Both rolls of a pair in its registered order; a void on the first stops the mate."""
    for arm in pair["order"]:
        if arm in pair["rolls"]:
            continue
        roll = _window_roll(cfgs[arm], arm, pair["k"], required)
        pair["rolls"][arm] = roll
        if roll.get("void"):
            pair["void"] = f"{arm}: {roll['void']}"
            log(f"!! pair {pair['k']} VOID — {pair['void']}; replaced by the next pair")
            save()
            return
        save()
    pair["outcome"] = pair_outcome(
        bool(pair["rolls"][SQUAD_ARM].get("functional")),
        bool(pair["rolls"][SOLO_ARM].get("functional")),
    )
    save()


def cmd_window(squad_cfg: SetConfig, solo_cfg: SetConfig, *, dry_run: bool, resume: bool) -> int:
    """Run the window as the pairs it is analysed as (plan §4.3, §8 decisions 5–7).

    No arm is observed until the exact registered pair and its frozen parameters have passed
    the comparison gate: ``window_problems`` proves the two configs name each other and
    register the same sample and budget, and ``comparison_problems`` reads both arms from the
    deploy BEFORE pair 1's first roll — not, as a per-launch preflight alone would, when the
    second arm launches with the first already observed. The per-launch preflight stays, to
    catch drift between launches.

    Interleaved and alternating by pair; a void — pre-run identity or infrastructure
    invalidity only, never outcome — removes its pair in full and is replaced by the next
    sequential pair, up to the registered budget; the mate of a roll that voided before launch
    is not launched. The reading is rendered whichever way it goes, and a window with fewer
    valid pairs than required after the budget closes INCOMPLETE and says so.

    Exit 0: closed complete. 6: closed incomplete. 2: the arms are not a registered pair or
    the gate refused them.
    """
    problems = window_problems(squad_cfg, solo_cfg)
    if not problems:
        # The exact two configs supplied, as loaded — never a counterpart re-read by name.
        problems = (
            pair_comparison_problems(solo_cfg, squad_cfg)
            if solo_cfg.compare_with
            else pair_comparison_problems(squad_cfg, solo_cfg)
        )
    if problems:
        for p in problems:
            log(f"!! {p}")
        return 2
    pairs, max_attempts = squad_cfg.window_pairs, squad_cfg.window_max_attempts
    cfgs = {SQUAD_ARM: squad_cfg, SOLO_ARM: solo_cfg}
    if dry_run:
        for arm, cfg in cfgs.items():
            rc = cmd_preflight(cfg, counting=True, identity=deploy_identity(cfg))
            log(f"{arm} arm preflight exit {rc}")
        return 0
    state = _window_state(squad_cfg, solo_cfg, pairs, max_attempts, resume)

    def valid_count() -> int:
        # Landed and not void — a pair whose mate is owed is not valid yet, so a resumed
        # window finishes it instead of reading it as done.
        return sum(1 for p in state["pairs"] if not p.get("void") and p.get("outcome") is not None)

    def owed() -> bool:
        # A pair with one roll landed and its mate not yet run was already attempted; the
        # attempt budget bounds NEW pairs, never the finishing of one in flight.
        return any(not p.get("void") and p.get("outcome") is None for p in state["pairs"])

    while valid_count() < pairs and (owed() or len(state["pairs"]) < max_attempts):
        pair = _next_pair(state)
        _run_pair(pair, cfgs, pairs, lambda: _save_window_state(squad_cfg, state))
        if pair.get("outcome"):
            log(f"pair {pair['k']}: {pair['outcome']} — {valid_count()} valid of {pairs}")

    tally = window_tally(state["pairs"], pairs, max_attempts)
    state["tally"] = tally
    _save_window_state(squad_cfg, state)
    md = render_window(state, tally)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (squad_cfg.records_path / f"window-{stamp}.json").write_text(json.dumps(state, indent=2))
    (squad_cfg.records_path / f"window-{stamp}.md").write_text(md)
    print(md)
    return 0 if tally["complete"] else 6


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("preflight", "shakeout", "roll"):
        p = sub.add_parser(name)
        p.add_argument(
            "--set",
            required=True,
            type=Path,
            help="set-config YAML (the pre-registration §1 as data)",
        )
        if name != "preflight":
            p.add_argument(
                "--dry-run", action="store_true", help="preflight + identity only, launch nothing"
            )
        if name == "roll":
            p.add_argument("--roll", type=int, required=True)
        if name == "preflight":
            p.add_argument(
                "--counting", action="store_true", help="also assert the frozen deploy and HEAD pin"
            )
    sub.add_parser(
        "registry",
        help="print EVIDENCE_FIELDS — every record field and when it is unaskable (#1445)",
    )
    p = sub.add_parser(
        "rerender",
        help="re-render a stored record's JSON through the current driver (#1445)",
    )
    p.add_argument("--set", required=True, type=Path)
    p.add_argument("--record", required=True, type=Path, help="a stored roll-*.json")
    p.add_argument("--out", required=True, type=Path, help="where the markdown goes")
    p = sub.add_parser(
        "window",
        help="run the comparison window as interleaved pairs with the void rule (plan §4.3)",
    )
    p.add_argument("--squad-set", required=True, type=Path, help="the squad arm's set config")
    p.add_argument("--solo-set", required=True, type=Path, help="the solo arm's set config")
    # The sample and the attempt budget are the configs' registered values (window_pairs,
    # window_max_attempts), never flags: nothing about a registered window is an argument.
    p.add_argument("--dry-run", action="store_true", help="both arms' preflight, launch nothing")
    p.add_argument(
        "--resume", action="store_true", help="continue from the window's recorded state"
    )
    args = ap.parse_args(argv)
    if args.command == "window":
        return cmd_window(
            load_set_config(args.squad_set),
            load_set_config(args.solo_set),
            dry_run=args.dry_run,
            resume=args.resume,
        )
    if args.command == "registry":
        print(registry_table())
        return 0
    cfg = load_set_config(args.set)
    if args.command == "rerender":
        return cmd_rerender(cfg, args.record, args.out)
    if args.command == "preflight":
        return cmd_preflight(cfg, counting=args.counting, identity=deploy_identity(cfg))
    if args.command == "shakeout":
        return cmd_shakeout(cfg, args.dry_run)
    return cmd_roll(cfg, args.roll, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
