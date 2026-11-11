"""A frozen scenario's declaration: read strictly, checked against its reader's vocabulary,
digested, and judged on the baseline (SIP-0117 R3.7, R5.7, R5.8; #3044).

**A scenario is declarative, never code.** It declares actions, observations and an expected
value per assertion. The provider's harness executes it under a vocabulary the provider owns,
and nothing a declaration holds runs as code. Core names no engine: a vocabulary is a value
handed in (``ScenarioVocabulary``), shipped as data where SIP-0117 R4.6 lets a platform be
named (the development profile, the adapter).

**Frozen by its digest.** The declaration's canonical text (sorted keys, no whitespace, UTF-8,
no NaN) is digested as ``sha256:<hex>``. The text names its reader, its setup, its steps and
its expected values, so one digest freezes all four. A provider digests the text it is handed
and refuses a difference (``handed_scenario_defects``).

**Reading is strict.** A key outside the schema, a kind outside the vocabulary or a value of
the wrong kind is refused with every defect named (``ScenarioRefused``); nothing is dropped or
filled in.

**The baseline rule lives here once** (``baseline_verdict``). The baseline step before
development calls it, and so does Campaign acceptance's discrimination read (#3053).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from squadops.remote_execution.models import AssertionOutcome, Scenario
from squadops.sandbox.models import compute_revision_id

SCHEMA = "squadops.scenario/1"
MAX_STEPS = 32
MAX_SETUP = 8
MAX_ASSERTIONS = 16
MAX_DEADLINE_SECONDS = 60.0
#: A digest as this module writes it.
DIGEST_PREFIX = "sha256:"


class _Absent:
    """What an observation of an instance that isn't there observes. A value of its own, so a
    property whose text happens to read "absent" is never taken for a missing instance."""

    def __repr__(self) -> str:
        return "<absent>"


#: An observation of an absent path observes this, and executes: it is compared like any value.
ABSENT = _Absent()

_DECLARATION_KEYS = frozenset(
    {"schema", "scenario_id", "reader", "setup", "steps", "assertions", "named_assertion"}
)
_ASSERTION_KEYS = frozenset({"id", "observe", "expect"})


class ExpectOp(StrEnum):
    """How an observed value is compared with the expected one."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    #: The observed instance isn't there. Takes no value.
    ABSENT = "absent"


class ArgumentKind(StrEnum):
    """The kinds of value a vocabulary's action or observation takes."""

    #: Non-empty text: an instance path, a property name, a key.
    TEXT = "text"
    #: A finite number.
    NUMBER = "number"
    #: A finite number of seconds, above zero and at most ``MAX_DEADLINE_SECONDS``.
    SECONDS = "seconds"
    #: Three finite numbers.
    POINT = "point"
    #: An observation, in the vocabulary's own terms.
    OBSERVATION = "observation"
    #: An expectation (``{op, value}``).
    EXPECTATION = "expectation"


@dataclass(frozen=True)
class ScenarioVocabulary:
    """What one reader executes: its actions and observations, each with its arguments, and
    the contexts an observation can be read in. A provider ships its own, as data."""

    reader: str
    actions: Mapping[str, Mapping[str, ArgumentKind]]
    observations: Mapping[str, Mapping[str, ArgumentKind]]
    contexts: frozenset[str]

    @classmethod
    def from_document(cls, document: Any) -> ScenarioVocabulary:
        """A vocabulary from its data document, read strictly. Raises ``ValueError``."""
        if not isinstance(document, Mapping):
            raise ValueError("a scenario vocabulary is an object")
        unknown = sorted(set(document) - {"reader", "actions", "observations", "contexts"})
        missing = sorted({"reader", "actions", "observations", "contexts"} - set(document))
        if unknown or missing:
            raise ValueError(f"scenario vocabulary: unknown keys {unknown}, missing keys {missing}")
        reader = document["reader"]
        if not isinstance(reader, str) or not reader.strip():
            raise ValueError("scenario vocabulary: 'reader' is non-empty text")
        contexts = document["contexts"]
        if (
            not isinstance(contexts, list)
            or not contexts
            or any(not isinstance(c, str) or not c for c in contexts)
        ):
            raise ValueError("scenario vocabulary: 'contexts' is a non-empty list of names")
        return cls(
            reader=reader,
            actions=_kinds(document["actions"], "actions"),
            observations=_kinds(document["observations"], "observations"),
            contexts=frozenset(contexts),
        )

    def to_document(self) -> dict[str, Any]:
        """The vocabulary as the data document ``from_document`` reads."""
        return {
            "reader": self.reader,
            "contexts": sorted(self.contexts),
            "actions": {
                k: {a: v.value for a, v in args.items()} for k, args in self.actions.items()
            },
            "observations": {
                k: {a: v.value for a, v in args.items()} for k, args in self.observations.items()
            },
        }


def _kinds(value: Any, where: str) -> dict[str, dict[str, ArgumentKind]]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"scenario vocabulary: '{where}' is a non-empty object")
    kinds: dict[str, dict[str, ArgumentKind]] = {}
    for kind, arguments in value.items():
        if not isinstance(arguments, Mapping):
            raise ValueError(f"scenario vocabulary: {where}.{kind} is an object of arguments")
        try:
            kinds[kind] = {name: ArgumentKind(arg) for name, arg in arguments.items()}
        except ValueError as e:
            raise ValueError(f"scenario vocabulary: {where}.{kind}: {e}") from e
    return kinds


class ScenarioRefused(ValueError):
    """A declaration that can't be frozen or run, with every defect named."""

    def __init__(self, defects: list[str]) -> None:
        self.defects = tuple(defects)
        super().__init__("; ".join(defects))


@dataclass(frozen=True)
class Expectation:
    op: ExpectOp
    #: A JSON scalar; ``None`` only for ``absent``.
    value: str | int | float | bool | None = None


@dataclass(frozen=True)
class Observation:
    kind: str
    context: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class DeclaredAssertion:
    assertion_id: str
    observe: Observation
    expect: Expectation


@dataclass(frozen=True)
class Action:
    action: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ScenarioDeclaration:
    """A declaration as read: its id, its reader, the setup that establishes its world, the
    steps a player takes, its assertions, and the one it names as the criterion's."""

    scenario_id: str
    reader: str
    setup: tuple[Action, ...]
    steps: tuple[Action, ...]
    assertions: tuple[DeclaredAssertion, ...]
    named_assertion: str

    @property
    def assertion_ids(self) -> tuple[str, ...]:
        return tuple(a.assertion_id for a in self.assertions)

    @property
    def preconditions(self) -> tuple[str, ...]:
        """Every declared assertion but the named one: what must already hold on the
        baseline for the scenario's world to be the baseline's."""
        return tuple(i for i in self.assertion_ids if i != self.named_assertion)


def canonical_text(document: Mapping[str, Any]) -> str:
    """A declaration's canonical text: the one form that is digested and placed."""
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def scenario_digest(text: str) -> str:
    """The digest of a declaration's text, exactly as handed."""
    return DIGEST_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()


def staged_revision(source_files: Mapping[str, str]) -> str:
    """The revision of exactly the tree a request stages. The wire carries text files and no
    executable bit, so none is hashed: every lane that binds a reading to a revision calls
    this, on the mapping it put on the request."""
    return compute_revision_id(source_files)


def parse_text(text: str) -> Any:
    """A declaration's JSON, refusing a repeated key and NaN rather than keeping one of them."""

    def no_repeats(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [k for k, _ in pairs]
        repeated = sorted({k for k in keys if keys.count(k) > 1})
        if repeated:
            raise ScenarioRefused([f"the declaration repeats the keys {repeated}"])
        return dict(pairs)

    def no_constant(name: str) -> Any:
        raise ScenarioRefused([f"the declaration holds {name}, which isn't a JSON number"])

    try:
        return json.loads(text, object_pairs_hook=no_repeats, parse_constant=no_constant)
    except json.JSONDecodeError as e:
        raise ScenarioRefused([f"the declaration isn't JSON: {e}"]) from e


def read_declaration(document: Any, vocabulary: ScenarioVocabulary) -> ScenarioDeclaration:
    """The declaration ``document`` holds, checked against ``vocabulary``. Raises
    ``ScenarioRefused`` naming every defect."""
    defects: list[str] = []
    if not isinstance(document, Mapping):
        raise ScenarioRefused(["a declaration is a JSON object"])
    unknown = sorted(set(document) - _DECLARATION_KEYS)
    missing = sorted(_DECLARATION_KEYS - set(document))
    if unknown:
        defects.append(f"keys outside {SCHEMA}: {unknown}")
    if missing:
        defects.append(f"missing keys: {missing}")
    if missing:
        raise ScenarioRefused(defects)
    if document["schema"] != SCHEMA:
        defects.append(f"'schema' is {document['schema']!r}, and this reader reads {SCHEMA!r}")
    scenario_id = document["scenario_id"]
    if not _is_text(scenario_id):
        defects.append("'scenario_id' is non-empty text")
    if document["reader"] != vocabulary.reader:
        defects.append(
            f"'reader' is {document['reader']!r}, and the vocabulary is {vocabulary.reader!r}"
        )
    setup = _actions(document["setup"], "setup", MAX_SETUP, vocabulary, defects, allow_empty=True)
    steps = _actions(document["steps"], "steps", MAX_STEPS, vocabulary, defects, allow_empty=True)
    assertions = _assertions(document["assertions"], vocabulary, defects)
    named = document["named_assertion"]
    ids = [a.assertion_id for a in assertions]
    if not _is_text(named):
        defects.append("'named_assertion' is non-empty text")
    elif assertions and named not in ids:
        defects.append(f"'named_assertion' is {named!r}, which no assertion declares")
    if defects:
        raise ScenarioRefused(defects)
    return ScenarioDeclaration(
        scenario_id=scenario_id,
        reader=document["reader"],
        setup=setup,
        steps=steps,
        assertions=assertions,
        named_assertion=named,
    )


def frozen_scenario(document: Mapping[str, Any], vocabulary: ScenarioVocabulary) -> Scenario:
    """Freeze a declaration: check it, then take its canonical text and that text's digest.
    What the change request stores and the operation task carries."""
    declaration = read_declaration(document, vocabulary)
    text = canonical_text(document)
    return Scenario(
        scenario_id=declaration.scenario_id,
        digest=scenario_digest(text),
        assertions=declaration.assertion_ids,
        named_assertion=declaration.named_assertion,
        document=text,
    )


def handed_scenario_defects(
    scenario: Scenario, vocabulary: ScenarioVocabulary
) -> tuple[ScenarioDeclaration | None, list[str]]:
    """What a provider checks before it runs anything: the text it was handed is the frozen
    one (its digest), it is for this provider's reader, it reads under the vocabulary, and the
    request's ids are the declaration's. Returns the declaration, or ``None`` with the defects.
    """
    actual = scenario_digest(scenario.document)
    if actual != scenario.digest:
        return None, [
            f"the scenario handed has digest {actual}, and the frozen scenario is "
            f"{scenario.digest}: it was changed after it was frozen"
        ]
    try:
        declaration = read_declaration(parse_text(scenario.document), vocabulary)
    except ScenarioRefused as refused:
        return None, list(refused.defects)
    defects = []
    if declaration.scenario_id != scenario.scenario_id:
        defects.append(
            f"the request names scenario {scenario.scenario_id!r}, and the declaration "
            f"{declaration.scenario_id!r}"
        )
    if declaration.assertion_ids != tuple(scenario.assertions):
        defects.append(
            f"the request names assertions {list(scenario.assertions)}, and the declaration "
            f"{list(declaration.assertion_ids)}"
        )
    if declaration.named_assertion != scenario.named_assertion:
        defects.append(
            f"the request names {scenario.named_assertion!r} as the criterion's assertion, and "
            f"the declaration {declaration.named_assertion!r}"
        )
    return (None, defects) if defects else (declaration, [])


def expectation_met(expect: Expectation, observed: Any) -> bool:
    """Whether ``observed`` meets ``expect``. ``observed`` is a JSON scalar or ``ABSENT``. An
    ordering or containment against a value of another kind is not met, never coerced."""
    if expect.op is ExpectOp.ABSENT:
        return observed is ABSENT
    if observed is ABSENT:
        return expect.op is ExpectOp.NOT_EQUALS
    if expect.op is ExpectOp.EQUALS:
        return _same_kind(observed, expect.value) and observed == expect.value
    if expect.op is ExpectOp.NOT_EQUALS:
        return not (_same_kind(observed, expect.value) and observed == expect.value)
    if expect.op is ExpectOp.CONTAINS:
        return (
            isinstance(observed, str)
            and isinstance(expect.value, str)
            and (expect.value in observed)
        )
    if not (_is_number(observed) and _is_number(expect.value)):
        return False
    if expect.op is ExpectOp.GREATER_THAN:
        return observed > expect.value
    return observed < expect.value


class BaselineVerdict(StrEnum):
    """§5 of #3044's shape: what a reading on the accepted baseline allows."""

    #: An assertion the scenario declares didn't execute: nothing can be judged.
    BLOCKED = "blocked"
    #: The named assertion already passes: the scenario proves nothing about the work.
    PASSES_ON_BASELINE = "scenario_passes_on_baseline"
    #: A precondition failed: the scenario's world isn't the baseline's.
    PRECONDITION_FAILS = "precondition_fails"
    #: The named assertion executed and failed, and every precondition passed.
    MAY_START = "may_start"


def baseline_verdict(
    outcomes: Mapping[str, AssertionOutcome], named_assertion: str
) -> tuple[BaselineVerdict, str]:
    """The baseline rule, judged in this order: a gap blocks first, then a named assertion
    that passes, then a precondition that fails. ``outcomes`` holds every declared assertion
    (``models.outcomes_by_assertion``); a named assertion it lacks is missing."""
    named = outcomes.get(named_assertion, AssertionOutcome.MISSING)
    gaps = {
        assertion_id: outcome
        for assertion_id, outcome in {**outcomes, named_assertion: named}.items()
        if not outcome.executed
    }
    if gaps:
        return BaselineVerdict.BLOCKED, "not executed on the baseline: " + ", ".join(
            f"{assertion_id} ({outcome.value})" for assertion_id, outcome in sorted(gaps.items())
        )
    if named is AssertionOutcome.PASSED:
        return (
            BaselineVerdict.PASSES_ON_BASELINE,
            f"{named_assertion} already passes on the baseline",
        )
    failed = sorted(
        assertion_id
        for assertion_id, outcome in outcomes.items()
        if assertion_id != named_assertion and outcome is AssertionOutcome.FAILED
    )
    if failed:
        return (
            BaselineVerdict.PRECONDITION_FAILS,
            "preconditions failed on the baseline: " + ", ".join(failed),
        )
    return BaselineVerdict.MAY_START, f"{named_assertion} executed and failed on the baseline"


# --- reading ---------------------------------------------------------------------------------


def _is_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _is_scalar(value: Any) -> bool:
    return isinstance(value, str | bool) or _is_number(value)


def _same_kind(a: Any, b: Any) -> bool:
    """``True == 1`` in Python; a declaration that expects ``true`` never matches ``1``."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool)
    if _is_number(a) or _is_number(b):
        return _is_number(a) and _is_number(b)
    return type(a) is type(b)


def _actions(
    value: Any,
    where: str,
    limit: int,
    vocabulary: ScenarioVocabulary,
    defects: list[str],
    *,
    allow_empty: bool,
) -> tuple[Action, ...]:
    if not isinstance(value, list):
        defects.append(f"'{where}' is a list")
        return ()
    if not value and not allow_empty:
        defects.append(f"'{where}' declares nothing")
    if len(value) > limit:
        defects.append(f"'{where}' declares {len(value)}, and at most {limit} are read")
    actions: list[Action] = []
    for index, raw in enumerate(value):
        at = f"{where}[{index}]"
        if not isinstance(raw, Mapping) or not isinstance(raw.get("action"), str):
            defects.append(f"{at} is an object naming its 'action'")
            continue
        kind = raw["action"]
        spec = vocabulary.actions.get(kind)
        if spec is None:
            defects.append(f"{at}: action {kind!r} is outside {vocabulary.reader}'s vocabulary")
            continue
        arguments = {k: v for k, v in raw.items() if k != "action"}
        _arguments(arguments, spec, at, vocabulary, defects)
        actions.append(Action(kind, arguments))
    return tuple(actions)


def _assertions(
    value: Any, vocabulary: ScenarioVocabulary, defects: list[str]
) -> tuple[DeclaredAssertion, ...]:
    if not isinstance(value, list) or not value:
        defects.append(
            "'assertions' is a non-empty list: a scenario that asserts nothing verifies nothing"
        )
        return ()
    if len(value) > MAX_ASSERTIONS:
        defects.append(f"'assertions' declares {len(value)}, and at most {MAX_ASSERTIONS} are read")
    assertions: list[DeclaredAssertion] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        at = f"assertions[{index}]"
        if not isinstance(raw, Mapping):
            defects.append(f"{at} is an object")
            continue
        unknown = sorted(set(raw) - _ASSERTION_KEYS)
        missing = sorted(_ASSERTION_KEYS - set(raw))
        if unknown or missing:
            defects.append(f"{at}: unknown keys {unknown}, missing keys {missing}")
            continue
        assertion_id = raw["id"]
        if not _is_text(assertion_id):
            defects.append(f"{at}: 'id' is non-empty text")
            continue
        if assertion_id in seen:
            defects.append(f"{at}: assertion {assertion_id!r} is declared twice")
        seen.add(assertion_id)
        observe = _observation(raw["observe"], f"{at}.observe", vocabulary, defects)
        expect = _expectation(raw["expect"], f"{at}.expect", defects)
        if observe is not None and expect is not None:
            assertions.append(DeclaredAssertion(assertion_id, observe, expect))
    return tuple(assertions)


def _observation(
    value: Any, at: str, vocabulary: ScenarioVocabulary, defects: list[str]
) -> Observation | None:
    if not isinstance(value, Mapping) or not isinstance(value.get("kind"), str):
        defects.append(f"{at} is an object naming its 'kind'")
        return None
    kind = value["kind"]
    spec = vocabulary.observations.get(kind)
    if spec is None:
        defects.append(f"{at}: observation {kind!r} is outside {vocabulary.reader}'s vocabulary")
        return None
    context = value.get("context")
    if context not in vocabulary.contexts:
        defects.append(
            f"{at}: 'context' is {context!r}, and {vocabulary.reader} reads in "
            f"{sorted(vocabulary.contexts)}"
        )
    arguments = {k: v for k, v in value.items() if k not in ("kind", "context")}
    _arguments(arguments, spec, at, vocabulary, defects)
    return Observation(kind, str(context), arguments)


def _expectation(value: Any, at: str, defects: list[str]) -> Expectation | None:
    if not isinstance(value, Mapping) or not isinstance(value.get("op"), str):
        defects.append(f"{at} is an object naming its 'op'")
        return None
    try:
        op = ExpectOp(value["op"])
    except ValueError:
        defects.append(f"{at}: 'op' is {value['op']!r}, one of {[o.value for o in ExpectOp]}")
        return None
    unknown = sorted(set(value) - {"op", "value"})
    if unknown:
        defects.append(f"{at}: unknown keys {unknown}")
    if op is ExpectOp.ABSENT:
        if "value" in value:
            defects.append(f"{at}: 'absent' takes no value")
        return Expectation(op)
    if "value" not in value or not _is_scalar(value["value"]):
        defects.append(f"{at}: 'value' is a JSON scalar (text, a finite number or a boolean)")
        return None
    expected = value["value"]
    if op in (ExpectOp.GREATER_THAN, ExpectOp.LESS_THAN) and not _is_number(expected):
        defects.append(f"{at}: {op.value} compares with a number")
    if op is ExpectOp.CONTAINS and not isinstance(expected, str):
        defects.append(f"{at}: contains looks for text")
    return Expectation(op, expected)


def _arguments(
    arguments: Mapping[str, Any],
    spec: Mapping[str, ArgumentKind],
    at: str,
    vocabulary: ScenarioVocabulary,
    defects: list[str],
) -> None:
    unknown = sorted(set(arguments) - set(spec))
    missing = sorted(set(spec) - set(arguments))
    if unknown or missing:
        defects.append(f"{at}: unknown arguments {unknown}, missing arguments {missing}")
    for name, kind in spec.items():
        if name not in arguments:
            continue
        value = arguments[name]
        where = f"{at}.{name}"
        if kind is ArgumentKind.TEXT and not _is_text(value):
            defects.append(f"{where} is non-empty text")
        elif kind is ArgumentKind.NUMBER and not _is_number(value):
            defects.append(f"{where} is a finite number")
        elif kind is ArgumentKind.SECONDS and not (
            _is_number(value) and 0 < value <= MAX_DEADLINE_SECONDS
        ):
            defects.append(
                f"{where} is a number of seconds above 0, at most {MAX_DEADLINE_SECONDS:g}"
            )
        elif kind is ArgumentKind.POINT and not (
            isinstance(value, list) and len(value) == 3 and all(_is_number(v) for v in value)
        ):
            defects.append(f"{where} is three finite numbers")
        elif kind is ArgumentKind.OBSERVATION:
            _observation(value, where, vocabulary, defects)
        elif kind is ArgumentKind.EXPECTATION:
            _expectation(value, where, defects)
