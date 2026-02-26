"""
Unit tests for CLI output formatting (SIP-0065 §6.5).
"""

import json

from squadops.cli.output import (
    print_detail,
    print_error,
    print_json,
    print_success,
    print_table,
)


class TestPrintTable:
    """Table output formatting."""

    def test_quiet_mode_tab_separated(self, capsys):
        print_table(["Name", "Status"], [["proj1", "active"]], quiet=True)
        out = capsys.readouterr().out
        assert "proj1\tactive" in out

    def test_quiet_mode_multiple_rows(self, capsys):
        rows = [["a", "1"], ["b", "2"]]
        print_table(["K", "V"], rows, quiet=True)
        lines = capsys.readouterr().out.strip().split("\n")
        assert len(lines) == 2
        assert "a\t1" in lines[0]
        assert "b\t2" in lines[1]

    def test_rich_mode_contains_headers(self, capsys):
        print_table(["Name", "Status"], [["proj1", "active"]])
        out = capsys.readouterr().out
        assert "Name" in out
        assert "Status" in out
        assert "proj1" in out


class TestPrintDetail:
    """Detail key-value output."""

    def test_quiet_mode_tab_separated(self, capsys):
        print_detail({"name": "proj1", "status": "active"}, quiet=True)
        out = capsys.readouterr().out
        assert "name\tproj1" in out
        assert "status\tactive" in out

    def test_rich_mode_shows_keys(self, capsys):
        print_detail({"name": "proj1"})
        out = capsys.readouterr().out
        assert "name" in out
        assert "proj1" in out


class TestPrintJson:
    """JSON output formatting."""

    def test_valid_json(self, capsys):
        print_json({"key": "value", "count": 42})
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["key"] == "value"
        assert parsed["count"] == 42

    def test_json_indented(self, capsys):
        print_json({"a": 1})
        out = capsys.readouterr().out
        assert "  " in out  # indent=2


class TestPrintMessages:
    """Error and success messages go to correct streams."""

    def test_print_error_to_stderr(self, capsys):
        print_error("something broke")
        err = capsys.readouterr().err
        assert "something broke" in err

    def test_print_success_to_stdout(self, capsys):
        print_success("all good")
        out = capsys.readouterr().out
        assert "all good" in out
