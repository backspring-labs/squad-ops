"""Unit tests for fenced code block parser.

Tests extract_fenced_files() from
``squadops.capabilities.handlers.fenced_parser``.

Part of SIP-Enhanced-Agent-Build-Capabilities, Phase 1.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.handlers.fenced_parser import extract_fenced_files

pytestmark = [pytest.mark.domain_capabilities]


class TestSingleFence:
    def test_single_fence_extraction(self):
        response = "Here is the code:\n```python:src/main.py\nprint('hello')\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "src/main.py"
        assert result[0]["content"] == "print('hello')"
        assert result[0]["language"] == "python"

    def test_single_fence_multiline_content(self):
        response = (
            "```python:app.py\n"
            "def main():\n"
            "    print('hello')\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert "def main():" in result[0]["content"]
        assert "main()" in result[0]["content"]


class TestThinkBlockStripping:
    """#130: Qwen3-family ``<think>...</think>`` reasoning blocks are stripped
    before fence scanning. Thinking-mode traces routinely contain stray fenced
    blocks (or consume the whole response), which corrupted extraction."""

    def test_fence_inside_think_block_is_ignored(self):
        """A throwaway fenced file inside the reasoning trace must NOT be
        extracted — only the real file outside the think block."""
        response = (
            "<think>\n"
            "Let me sketch it first:\n"
            "```python:scratch/draft.py\n"
            "x = 1  # throwaway\n"
            "```\n"
            "</think>\n"
            "```python:src/main.py\n"
            "print('real')\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "src/main.py"
        assert result[0]["content"] == "print('real')"

    def test_response_that_is_only_a_think_block_yields_nothing(self):
        """The exact #130 failure: thinking mode emits a fence but no real
        output. After stripping the trace, there are no files to extract — the
        handler can then fail cleanly instead of using throwaway reasoning."""
        response = (
            "<think>\n"
            "I should build a FastAPI app...\n"
            "```python:plan.py\n"
            "# just thinking out loud\n"
            "```\n"
            "</think>\n"
        )
        assert extract_fenced_files(response) == []

    def test_think_prose_before_real_file_does_not_break_extraction(self):
        """Reasoning prose ahead of the real output is fine, and the tag match
        is case-insensitive (models emit <think> and <THINK>)."""
        response = "<THINK>weighing the design</THINK>\n```python:app.py\nprint('ok')\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "app.py"
        assert result[0]["content"] == "print('ok')"


class TestNoFencedBlocksLogging:
    """#130: a zero-extraction failure must surface the raw LLM response in the
    agent logs (truncated) — otherwise it's only buried in a build_warnings.md
    artifact, leaving no signal to triage thinking-mode vs prompt/scope failure."""

    def test_logs_truncated_raw_response(self, caplog):
        import logging

        from squadops.capabilities.handlers.cycle_tasks import DevelopmentDevelopHandler

        handler = DevelopmentDevelopHandler()
        raw = ("A" * 1500) + "TAIL_MARKER_BEYOND_EXCERPT"

        with caplog.at_level(logging.WARNING):
            handler._log_no_fenced_blocks(raw, excerpt=1000)

        warnings = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING and "no fenced code blocks extracted" in r.getMessage()
        ]
        assert len(warnings) == 1
        msg = warnings[0]
        assert "AAAA" in msg  # the raw prefix is captured
        assert "TAIL_MARKER" not in msg  # ...but truncated to the excerpt window
        assert str(len(raw)) in msg  # full response length reported


class TestMultipleFences:
    def test_multiple_fences(self):
        response = (
            "```python:src/models.py\n"
            "class User:\n"
            "    pass\n"
            "```\n"
            "\n"
            "And the tests:\n"
            "```python:tests/test_models.py\n"
            "def test_user():\n"
            "    assert True\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 2
        assert result[0]["filename"] == "src/models.py"
        assert result[1]["filename"] == "tests/test_models.py"

    def test_mixed_languages(self):
        response = (
            "```python:main.py\n"
            "print('hi')\n"
            "```\n"
            "```yaml:config.yaml\n"
            "key: value\n"
            "```\n"
            "```json:data.json\n"
            '{"a": 1}\n'
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 3
        assert result[0]["language"] == "python"
        assert result[1]["language"] == "yaml"
        assert result[2]["language"] == "json"


class TestPathSecurity:
    def test_path_traversal_rejection(self):
        response = "```python:../etc/passwd\nmalicious\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_absolute_path_rejection(self):
        response = "```python:/etc/passwd\nmalicious\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_mid_path_traversal_rejection(self):
        response = "```python:src/../../../etc/shadow\nmalicious\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_dotdot_in_filename_is_ok(self):
        """Filenames containing '..' not as a path segment are fine."""
        response = "```python:src/foo..bar.py\ncode\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "src/foo..bar.py"

    def test_colon_in_filename_rejected(self):
        """Colons in filenames are rejected (invalid on macOS/Windows, LLM artifact)."""
        response = "```python:test_board:play_game/board.py\ndef test_board():\n    pass\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_colon_in_nested_path_rejected(self):
        """Colons anywhere in the path are rejected."""
        response = "```python:src/foo:bar.py\ncode\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_valid_and_invalid_mixed(self):
        """Valid fences are kept, invalid (traversal) are dropped."""
        response = (
            "```python:good.py\n"
            "ok\n"
            "```\n"
            "```python:../bad.py\n"
            "bad\n"
            "```\n"
            "```python:also_good.py\n"
            "ok\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 2
        assert result[0]["filename"] == "good.py"
        assert result[1]["filename"] == "also_good.py"


class TestEdgeCases:
    def test_empty_returns_empty_list(self):
        assert extract_fenced_files("") == []

    def test_none_string_returns_empty(self):
        assert extract_fenced_files("") == []

    def test_no_tagged_fences(self):
        """Untagged fences (no lang:path) are ignored."""
        response = "```python\nprint('hi')\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_no_closing_fence(self):
        """Unclosed fence is skipped."""
        response = "```python:main.py\nprint('hi')\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_malformed_header_with_space(self):
        """Fence headers with spaces in the path are not matched."""
        response = "```python:my file.py\ncode\n```\n"
        # Space in path means \S+ won't match the space part
        # Actually "my" will match and "file.py" is leftover — but the regex
        # requires no trailing content after path except whitespace, so
        # "my file.py" won't match since "my" is followed by " file.py"
        # which isn't whitespace-only. Let's verify:
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_deeply_nested_path(self):
        response = "```python:src/squadops/capabilities/handlers/build.py\ncode\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "src/squadops/capabilities/handlers/build.py"

    def test_empty_file_content(self):
        response = "```python:empty.py\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["content"] == ""

    def test_prose_between_fences(self):
        """Prose between fences does not interfere."""
        response = (
            "Here's the first file:\n\n"
            "```python:a.py\n"
            "a = 1\n"
            "```\n"
            "\n"
            "And now here's the second file:\n\n"
            "```python:b.py\n"
            "b = 2\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 2
        assert result[0]["content"] == "a = 1"
        assert result[1]["content"] == "b = 2"


class TestSpecialFilenameInLanguageSlot:
    """Models commonly emit ``` ```Dockerfile``` ``` (no path) for files whose
    name *is* the canonical language tag. Treat the language slot as the
    filename for an allowlist of well-known names."""

    def test_dockerfile_in_language_slot(self):
        response = "```Dockerfile\nFROM python:3.11\nCOPY . /app\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "Dockerfile"
        assert "FROM python:3.11" in result[0]["content"]
        assert result[0]["language"] == "dockerfile"

    def test_makefile_in_language_slot(self):
        response = "```Makefile\nbuild:\n\tgo build\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "Makefile"

    def test_lowercase_dockerfile_does_not_match(self):
        """Lowercase 'dockerfile' is a language, not a filename — must NOT
        be auto-resolved (filename must come from heading or comment)."""
        response = "```dockerfile\nFROM python:3.11\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0


class TestHeadingPrecedingFence:
    """Models often write ``### path/to/file.py`` then a plain
    ``` ```python``` `` fence."""

    def test_heading_directly_before_fence(self):
        response = "### backend/models.py\n```python\nclass Run: pass\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "backend/models.py"
        assert result[0]["content"] == "class Run: pass"

    def test_heading_with_blank_line_before_fence(self):
        response = "### models.py\n\n```python\nclass Run: pass\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "models.py"

    def test_heading_with_backticked_filename(self):
        """``### `models.py``` ``-style headings are common in chat UIs."""
        response = "### `backend/models.py`\n```python\nx = 1\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "backend/models.py"

    def test_dockerfile_heading(self):
        response = "## Dockerfile\n```\nFROM python:3.11\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "Dockerfile"

    def test_prose_heading_does_not_match(self):
        """Headings like '## Implementation Notes' are not filenames."""
        response = "## Implementation Notes\n```python\nx = 1\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_far_heading_is_not_used(self):
        """Heading separated by many lines of prose does not label the fence."""
        response = (
            "### models.py\n"
            "\n"
            "Here is a very long description.\n"
            "It spans multiple lines.\n"
            "And another line.\n"
            "And yet another.\n"
            "And one more line of prose.\n"
            "\n"
            "```python\n"
            "x = 1\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 0

    def test_heading_consumed_only_once(self):
        """A heading labels the *next* fence, not subsequent unlabelled fences."""
        response = "### a.py\n```python\na = 1\n```\n```python\nb = 2\n```\n"
        result = extract_fenced_files(response)
        # First fence resolves via heading; second has no heading and no
        # comment, so it's dropped (not silently attributed to a.py).
        assert len(result) == 1
        assert result[0]["filename"] == "a.py"

    def test_two_headings_two_fences(self):
        response = "### a.py\n```python\na = 1\n```\n### b.py\n```python\nb = 2\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 2
        assert result[0]["filename"] == "a.py"
        assert result[1]["filename"] == "b.py"


class TestFirstLineFilenameComment:
    """Models often emit ``` ```python\\n# path/to/file.py\\n...``` `` — a
    comment on line 1 of the body that names the file."""

    def test_python_comment_filename(self):
        response = "```python\n# backend/models.py\nclass Run: pass\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "backend/models.py"
        # The filename comment line must NOT appear in the extracted content.
        assert result[0]["content"] == "class Run: pass"

    def test_js_double_slash_comment_filename(self):
        response = "```javascript\n// frontend/src/App.jsx\nexport default function App() {}\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "frontend/src/App.jsx"
        assert "App()" in result[0]["content"]
        assert "frontend/src/App.jsx" not in result[0]["content"]

    def test_filename_comment_only_first_line(self):
        """A filename-shaped comment on a later line does NOT count."""
        response = (
            "```python\n"
            "import os\n"
            "# helpers/util.py is imported below\n"
            "from helpers import util\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        # No first-line filename, no heading, no strict format → dropped.
        assert len(result) == 0

    def test_prose_comment_does_not_match(self):
        """First line is a comment but doesn't look like a filename."""
        response = (
            "```python\n# This module implements the run repository.\nclass Repo: pass\n```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 0


class TestStrictWinsOverPermissive:
    """When both strict and permissive signals are present, strict wins."""

    def test_strict_overrides_heading(self):
        response = "### wrong.py\n```python:right.py\nx = 1\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "right.py"

    def test_strict_overrides_first_line_comment(self):
        response = "```python:right.py\n# wrong.py\nx = 1\n```\n"
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "right.py"
        # First-line comment is NOT stripped when strict format won.
        assert result[0]["content"] == "# wrong.py\nx = 1"


class TestRealWorldFailurePatterns:
    """Reproduces the format-drift patterns observed on cyc_b7cf604aed46
    where Bob and Eve produced output the strict-only parser dropped."""

    def test_bobs_likely_fullstack_assemble_output(self):
        """Bob assembling fullstack: Dockerfile via language slot,
        docker-compose.yaml via heading, qa_handoff.md via heading."""
        response = (
            "Here's the deployment package:\n\n"
            "```Dockerfile\n"
            "FROM python:3.11\n"
            "WORKDIR /app\n"
            "```\n\n"
            "### docker-compose.yaml\n"
            "```yaml\n"
            "services:\n"
            "  backend:\n"
            "    image: app\n"
            "```\n\n"
            "### qa_handoff.md\n"
            "```markdown\n"
            "## How to Run\n"
            "uvicorn main:app\n"
            "## How to Test\n"
            "pytest\n"
            "## Expected Behavior\n"
            "200 on GET /runs\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        filenames = [r["filename"] for r in result]
        assert "Dockerfile" in filenames
        assert "docker-compose.yaml" in filenames
        assert "qa_handoff.md" in filenames
        qa_handoff = next(r for r in result if r["filename"] == "qa_handoff.md")
        assert "## How to Run" in qa_handoff["content"]


class TestNestedFences:
    """#430: a block body may legitimately contain fenced examples; the parser
    must close the block at its own fence, not the first nested close."""

    def test_nested_example_content_retained(self):
        """Regression pin for #430: cyc_8830cfc78a1e clipped qa_handoff.md at
        the close of its first embedded bash example, discarding every later
        section, on all three assemble attempts."""
        response = (
            "```markdown:qa_handoff.md\n"
            "# QA Handoff\n"
            "## How to Test\n"
            "```bash\n"
            "cd backend\n"
            "pytest\n"
            "```\n"
            "## Expected Behavior\n"
            "All endpoints return JSON.\n"
            "## Known Limitations\n"
            "In-memory store only.\n"
            "```\n"
        )
        [record] = extract_fenced_files(response)
        assert record["filename"] == "qa_handoff.md"
        assert "```bash\ncd backend\npytest\n```" in record["content"]
        assert "## Expected Behavior" in record["content"]
        assert record["content"].endswith("In-memory store only.")

    def test_multiple_nested_examples_in_one_block(self):
        response = (
            "```markdown:docs/guide.md\n"
            "## Backend\n"
            "```bash\n"
            "uvicorn main:app\n"
            "```\n"
            "## Frontend\n"
            "```bash\n"
            "npm run dev\n"
            "```\n"
            "Done.\n"
            "```\n"
        )
        [record] = extract_fenced_files(response)
        assert record["content"].count("```bash") == 2
        assert record["content"].endswith("Done.")

    def test_scan_resumes_correctly_after_nested_block(self):
        """A file following a nested-fence block must still be extracted with
        its own content — the scanner must advance past the OUTER close."""
        response = (
            "```markdown:docs/guide.md\n"
            "Example:\n"
            "```bash\n"
            "make test\n"
            "```\n"
            "End of guide.\n"
            "```\n"
            "\n"
            "```python:app.py\n"
            "print('hello')\n"
            "```\n"
        )
        records = extract_fenced_files(response)
        assert [r["filename"] for r in records] == ["docs/guide.md", "app.py"]
        assert records[0]["content"].endswith("End of guide.")
        assert records[1]["content"] == "print('hello')"

    def test_unmatched_nested_opener_abandons_block_but_recovers_later_files(self):
        """An inner tokened fence that never closes leaves the outer block
        unclosed: the block is dropped whole (documented #430 trade-off), and
        the scanner still recovers subsequent well-formed files."""
        response = (
            "```markdown:docs/broken.md\n"
            "Example that never closes:\n"
            "```python\n"
            "x = 1\n"
            "\n"
            "```json:config.json\n"
            '{"ok": true}\n'
            "```\n"
        )
        records = extract_fenced_files(response)
        assert [r["filename"] for r in records] == ["config.json"]
        assert records[0]["content"] == '{"ok": true}'


class TestFirstLinePathPrefix:
    """#470: a bare ```<lang> fence whose first body line is ``path:code`` (the
    filename as a colon-prefix of the first code line, no comment marker). Each
    occurrence otherwise dropped a whole task and cost a full generation round."""

    def test_the_reported_variant_extracts_the_file(self):
        # verbatim shape from the issue: qa suite emitted as ```python\npath:code
        response = (
            "```python\n"
            "tests/test_api.py:import pytest\n"
            "\n"
            "def test_health():\n"
            "    assert True\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "tests/test_api.py"
        # the code after the colon becomes the first content line — prefix stripped
        assert result[0]["content"].startswith("import pytest\n")
        assert "def test_health():" in result[0]["content"]

    def test_bare_extension_filename_without_slash(self):
        # a slash-less path is accepted via the source-extension guard
        result = extract_fenced_files("```python\nmain.py:import sys\n```")
        assert result == [{"filename": "main.py", "content": "import sys", "language": "python"}]

    def test_path_colon_alone_takes_code_from_next_line(self):
        # ``path:`` with nothing after the colon — code starts on the next line,
        # and no empty first line is prepended
        result = extract_fenced_files(
            "```python\nbackend/main.py:\nfrom fastapi import FastAPI\n```"
        )
        assert result[0]["filename"] == "backend/main.py"
        assert result[0]["content"] == "from fastapi import FastAPI"

    def test_multiple_path_prefix_fences(self):
        response = "```python\na/one.py:x = 1\n```\n```js\nb/two.js:y = 2\n```"
        result = extract_fenced_files(response)
        assert [(r["filename"], r["content"]) for r in result] == [
            ("a/one.py", "x = 1"),
            ("b/two.js", "y = 2"),
        ]

    def test_strict_header_still_wins_over_body_prefix(self):
        # an explicit ```<lang>:<path> header is authoritative; a path:code first
        # body line is left untouched as content, not treated as the filename
        result = extract_fenced_files("```python:real.py\nother.py:import os\n```")
        assert result[0]["filename"] == "real.py"
        assert result[0]["content"] == "other.py:import os"

    def test_host_port_first_line_is_not_a_filename(self):
        # guard: no slash and a non-source extension (.com) -> not a file (would
        # otherwise mis-read config/prose colon lines as filenames)
        assert extract_fenced_files("```yaml\nexample.com:8080\nfoo: bar\n```") == []

    def test_prose_colon_first_line_is_not_a_filename(self):
        assert extract_fenced_files("```text\nNote:this is important\n```") == []

    def test_absolute_and_traversal_prefixes_rejected(self):
        # the shared safety check still applies to a strategy-5 path
        assert extract_fenced_files("```python\n/etc/evil.py:import os\n```") == []
        assert extract_fenced_files("```python\n../esc.py:bad\n```") == []


class TestFirstLineBareFilename:
    """Strategy 6 (#502): the whole first body line is the bare path — no
    comment marker, no colon. The live shape that burned shakedown-3's
    m009 qa.test attempt 1 (eve emitted ```jsx, then the path on its own
    line, then code; zero blocks extracted)."""

    def test_bare_path_first_line_resolves_filename(self):
        # verbatim shape from the live failure
        response = (
            "```jsx\n"
            "frontend/src/views/CreateRunView.jsx\n"
            'import { useState } from "react";\n'
            "\n"
            "export default function CreateRunView() {}\n"
            "```\n"
        )
        result = extract_fenced_files(response)
        assert len(result) == 1
        assert result[0]["filename"] == "frontend/src/views/CreateRunView.jsx"
        # the path line is stripped; content starts at the real code
        assert result[0]["content"].startswith('import { useState } from "react";')

    def test_slashless_bare_filename_accepted_via_extension_guard(self):
        result = extract_fenced_files("```python\nmain.py\nimport sys\n```")
        assert result == [{"filename": "main.py", "content": "import sys", "language": "python"}]

    def test_multiple_bare_filename_fences(self):
        response = "```python\na/one.py\nx = 1\n```\n```js\nb/two.js\ny = 2\n```"
        assert [(r["filename"], r["content"]) for r in extract_fenced_files(response)] == [
            ("a/one.py", "x = 1"),
            ("b/two.js", "y = 2"),
        ]

    def test_code_first_line_is_never_stolen(self):
        # a real first code line must not be mis-read as a filename and stripped
        assert extract_fenced_files("```python\nimport os\n```") == []
        assert extract_fenced_files("```text\nplain prose here\n```") == []

    def test_prose_word_with_dot_is_not_a_filename(self):
        # no slash + non-source extension -> guard rejects (same as #470)
        assert extract_fenced_files("```text\nversion.1a\nbody\n```") == []

    def test_traversal_and_absolute_bare_paths_rejected(self):
        assert extract_fenced_files("```python\n/etc/evil.py\nimport os\n```") == []
        assert extract_fenced_files("```python\n../esc.py\nbad\n```") == []

    def test_comment_strategy_still_wins_over_bare(self):
        # a first-line COMMENT filename resolves via strategy 4, not 6
        result = extract_fenced_files("```python\n# real.py\nimport os\n```")
        assert result[0]["filename"] == "real.py"
        assert result[0]["content"] == "import os"
