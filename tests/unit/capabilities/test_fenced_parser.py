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
