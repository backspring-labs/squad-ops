"""Tests for the proposer typed-acceptance vocabulary renderer (issue #182).

Background: SIP-0093 proposers were handed only check *names* (via task-type
fragments) with no params or examples, and `{{typed_acceptance_vocabulary}}`
was injected as an empty string. Models guessed param names and `count_at_least`
(the only check with two required params) failed plan validation, dropping the
whole proposal → empty plan.

`render_typed_acceptance_vocabulary()` now generates the vocabulary from
`CHECK_SPECS` so the proposer sees exact param names + a parser-valid example
per check. These tests guard that the rendered content is actually correct and
that it can never silently regress to the empty/under-specified state.
"""

import pytest
import yaml

from squadops.cycles.acceptance_check_spec import (
    CHECK_SPECS,
    _format_example_value,
    render_typed_acceptance_vocabulary,
)
from squadops.cycles.implementation_plan import TypedCheck, _parse_acceptance_criteria

pytestmark = [pytest.mark.domain_orchestration]


@pytest.mark.parametrize("check_name", sorted(CHECK_SPECS))
def test_every_check_example_is_parser_valid(check_name):
    """The example we show proposers for each check must parse cleanly through
    the real validator. If it doesn't, we'd be teaching models malformed YAML —
    exactly the failure mode of issue #182. This is the load-bearing guarantee
    and fails loudly if a new check is added without a valid example."""
    spec = CHECK_SPECS[check_name]
    assert spec.example, f"{check_name} has no example to render"

    criterion = {"check": check_name, **spec.example, "severity": "error"}
    parsed = _parse_acceptance_criteria([criterion], task_index=0)

    assert len(parsed) == 1
    assert isinstance(parsed[0], TypedCheck)
    assert parsed[0].check == check_name


@pytest.mark.parametrize("check_name", sorted(CHECK_SPECS))
def test_rendered_vocabulary_shows_each_check_and_its_required_params(check_name):
    """The whole point of the fix: the model must see the check name AND its
    exact required param names. Listing the name without params is what caused
    #182 (models guessed `count`/`count_min` instead of `glob`/`min_count`)."""
    rendered = render_typed_acceptance_vocabulary()
    assert f"`{check_name}`" in rendered
    for param in CHECK_SPECS[check_name].required_params:
        assert param in rendered, f"required param {param!r} of {check_name} not shown"


def test_count_at_least_shows_both_required_params():
    """Direct regression for #182: count_at_least must surface BOTH glob and
    min_count (the params dev and qa proposers each omitted)."""
    rendered = render_typed_acceptance_vocabulary()
    assert "count_at_least" in rendered
    assert "glob" in rendered
    assert "min_count" in rendered


def test_rendered_vocabulary_is_not_empty():
    """The literal #182 root cause was the variable being injected as "".
    A non-trivial rendered block guards against regressing to that state."""
    rendered = render_typed_acceptance_vocabulary()
    assert rendered.strip()
    # Sanity: every check is represented, so length scales with the registry.
    assert rendered.count("- check:") == len(CHECK_SPECS)


def _yaml_example_blocks(rendered: str) -> list[str]:
    """Pull the fenced ```yaml example blocks out of the rendered vocabulary."""
    blocks: list[str] = []
    current: list[str] = []
    inside = False
    for line in rendered.splitlines():
        if line.strip() == "```yaml":
            inside, current = True, []
        elif inside and line.strip() == "```":
            blocks.append("\n".join(current))
            inside = False
        elif inside:
            current.append(line)
    return blocks


def test_format_example_value_backslash_regex_round_trips():
    """The #182-follow-up dev-proposer failure (cyc_82c9b3f5a2c1): a regex value
    with a backslash escape must survive yaml.safe_load to the SAME string.
    Double-quoting made YAML read \\. / \\w as escape sequences and raise
    'unknown escape character', which dropped the entire proposal. Single-quoted
    scalars don't process backslashes, so they round-trip."""
    pattern = r"participant|participants?.*length|\.length"
    loaded = yaml.safe_load(f"value: {_format_example_value(pattern)}")
    assert loaded["value"] == pattern


def test_format_example_value_escapes_embedded_single_quote():
    """A value containing a single quote must stay parseable — YAML single-quoted
    scalars escape ' by doubling it. Without the escaping the scalar terminates
    early and the loaded value is corrupted."""
    value = "can't stop"
    loaded = yaml.safe_load(f"value: {_format_example_value(value)}")
    assert loaded["value"] == value


def test_rendered_vocabulary_examples_all_parse_as_yaml():
    """Integration guard: every fenced example we hand proposers must round-trip
    through the same yaml.safe_load the merger runs on proposals. The regex_match
    example now carries a backslash escape, so a regression to double-quoting
    fails here with the exact error that dropped the dev proposal."""
    blocks = _yaml_example_blocks(render_typed_acceptance_vocabulary())
    assert len(blocks) == len(CHECK_SPECS)
    for block in blocks:
        loaded = yaml.safe_load(block)
        assert isinstance(loaded, list) and len(loaded) == 1
        assert "check" in loaded[0]


def test_regex_example_demonstrates_a_backslash_in_single_quotes():
    """The regex_match exemplar must show a real backslash escape in single
    quotes — that is what teaches proposers the safe style. A backslash-free or
    double-quoted exemplar would silently re-teach the broken pattern."""
    rendered = render_typed_acceptance_vocabulary()
    assert r"pattern: 'def test_\w+'" in rendered
    assert r'pattern: "def test_\w+"' not in rendered
