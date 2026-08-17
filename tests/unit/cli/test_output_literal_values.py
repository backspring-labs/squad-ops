"""CLI output renders data as itself, never as Rich markup (#931).

Bug this guards: Rich reads `[...]` in a string as a style tag and removes it, so a
Next.js dynamic route arrived on screen as `app/runs//page.tsx` — the segment silently
deleted. The artifact table is the first surface a person reads when triaging a cycle,
and it was showing a filename that does not exist while looking authoritative.
"""

from __future__ import annotations

import pytest

from squadops.cli import output

pytestmark = [pytest.mark.domain_cli]

_DYNAMIC_ROUTE = "app/runs/[run_id]/page.tsx"


@pytest.fixture
def rendered(monkeypatch):
    """Capture what the console actually writes, at a width nothing wraps at."""
    import io

    from rich.console import Console

    buf = io.StringIO()
    monkeypatch.setattr(output, "_console", Console(file=buf, width=200))
    return buf


class TestBracketedValuesSurvive:
    def test_a_dynamic_route_keeps_its_parameter_segment(self, rendered):
        output.print_table(["Filename"], [[_DYNAMIC_ROUTE]])
        assert "[run_id]" in rendered.getvalue()
        assert "runs//page" not in rendered.getvalue()

    def test_the_detail_view_keeps_it_too(self, rendered):
        """Same defect, second surface — `cycles show` interpolated the value into an
        f-string alongside its own bold markup."""
        output.print_detail({"path": _DYNAMIC_ROUTE})
        assert "[run_id]" in rendered.getvalue()

    @pytest.mark.parametrize(
        "value",
        [
            "['art_d9b2cb4140c8', 'art_1a54818c341d']",  # a JSON list of artifact ids
            "/api/runs/{run_id}",  # a parameterised path (braces are safe, pinned anyway)
            "[bold red]not a style[/bold red]",  # data that looks exactly like markup
            "expected=['__tests__/runs.test.ts']",  # a log line pasted into a field
        ],
    )
    def test_any_bracketed_data_survives(self, rendered, value):
        output.print_table(["Value"], [[value]])
        out = rendered.getvalue()
        # every non-space character of the input reaches the screen
        assert all(ch in out for ch in value if not ch.isspace())

    def test_a_value_that_looks_like_markup_is_not_styled(self, rendered):
        """The dangerous half: `[bold red]` as DATA must not silently become a style and
        vanish. If it renders as markup the text disappears and the row lies."""
        output.print_table(["Value"], [["[bold red]"]])
        assert "[bold red]" in rendered.getvalue()


class TestNothingElseMoved:
    def test_quiet_mode_is_unchanged(self, capsys):
        """Quiet mode never went through Rich, so it never had the bug — and must not
        acquire chrome now."""
        output.print_table(["A", "B"], [[_DYNAMIC_ROUTE, "x"]], quiet=True)
        assert capsys.readouterr().out == f"{_DYNAMIC_ROUTE}\tx\n"

    def test_headers_and_values_both_appear(self, rendered):
        output.print_table(["Artifact ID", "Filename"], [["art_1", _DYNAMIC_ROUTE]])
        out = rendered.getvalue()
        assert "Artifact ID" in out and "art_1" in out and "[run_id]" in out

    def test_the_detail_label_is_still_emphasised(self, rendered):
        """The label is ours and may carry markup; only the value is data."""
        output.print_detail({"status": "completed"})
        assert "status:" in rendered.getvalue()
        assert "completed" in rendered.getvalue()
