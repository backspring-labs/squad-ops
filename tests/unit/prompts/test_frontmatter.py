"""The shared frontmatter parser's two readings (#579).

The characterization golden pins that every stored asset reads the same as before the
extraction. These pin the contract the call sites now rely on, which the stored assets do not
exercise: where a block may start, and what each reading does with a header that is absent,
unparseable, empty, or not a mapping.

Bug caught: a lenient reader that raises on a broken asset header and takes a prompt render
down, or a strict reader that lets a model's missing header through as an empty mapping, the
silent default #109 removed.
"""

from __future__ import annotations

import pytest

from squadops.prompts.frontmatter import (
    INVALID_YAML,
    MISSING,
    NOT_MAPPING,
    FrontmatterError,
    parse_frontmatter,
    read_frontmatter,
    split_frontmatter,
)

pytestmark = [pytest.mark.domain_contracts]


@pytest.mark.parametrize(
    ("content", "header", "body"),
    [
        ("---\na: 1\n---\nBody\n", "a: 1", "Body\n"),
        ("---\r\na: 1\r\n---\r\nBody", "a: 1\r", "Body"),
        # Anchored at the first character: a block anywhere else is body text.
        ("\n---\na: 1\n---\nBody\n", None, "\n---\na: 1\n---\nBody\n"),
        ("Intro\n---\na: 1\n---\nBody\n", None, "Intro\n---\na: 1\n---\nBody\n"),
        # The closing fence needs its newline; the first closing fence ends the block.
        ("---\na: 1\n---", None, "---\na: 1\n---"),
        ("---\na: 1\n---\nB\n---\nc: 2\n---\nC\n", "a: 1", "B\n---\nc: 2\n---\nC\n"),
    ],
    ids=["plain", "crlf", "leading-blank-line", "text-before", "no-final-newline", "two-blocks"],
)
def test_split_reads_only_a_block_at_the_start(content, header, body):
    assert split_frontmatter(content) == (header, body)


@pytest.mark.parametrize(
    "content",
    ["Body only\n", "---\na: [unclosed\n---\nBody\n", "---\n\n---\nBody\n", "---\n[]\n---\nB"],
    ids=["no-block", "invalid-yaml", "empty-header", "empty-list"],
)
def test_the_lenient_reading_treats_a_missing_or_broken_header_as_none(content):
    header, _ = read_frontmatter(content)
    assert header == {}


@pytest.mark.parametrize("header", ["- a\n- b", "just text", "42"])
def test_the_lenient_reading_still_refuses_a_header_that_is_not_a_mapping(header):
    """It crashed every lenient copy with AttributeError; it stays loud, and named."""
    with pytest.raises(FrontmatterError) as excinfo:
        read_frontmatter(f"---\n{header}\n---\nBody\n")
    assert excinfo.value.kind == NOT_MAPPING


@pytest.mark.parametrize(
    ("content", "kind", "message"),
    [
        ("Body only\n", MISSING, "missing YAML frontmatter (expected --- delimiters)"),
        ("---\na: [unclosed\n---\nBody\n", INVALID_YAML, "invalid YAML frontmatter: "),
        ("---\n\n---\nBody\n", NOT_MAPPING, "YAML frontmatter is not a mapping"),
        ("---\n- a\n---\nBody\n", NOT_MAPPING, "YAML frontmatter is not a mapping"),
    ],
    ids=["missing", "invalid-yaml", "empty-header", "list-header"],
)
def test_the_strict_reading_refuses_what_a_model_left_out_or_broke(content, kind, message):
    with pytest.raises(FrontmatterError) as excinfo:
        parse_frontmatter(content)
    assert excinfo.value.kind == kind
    assert str(excinfo.value).startswith(message)


def test_both_readings_agree_on_a_valid_header():
    content = "---\nversion: '2'\nrequired_variables: [a]\n---\nBody {{a}}\n"
    expected = ({"version": "2", "required_variables": ["a"]}, "Body {{a}}\n")
    assert read_frontmatter(content) == parse_frontmatter(content) == expected
