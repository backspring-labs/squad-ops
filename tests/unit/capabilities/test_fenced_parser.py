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
