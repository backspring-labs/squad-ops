"""``scripts/dev/host_quiet_reading.py``: the worker's Mac, as the certification window reads it.

What bugs would these catch?
- A reading that can't be taken left out of the document, so two sets read as comparable on a
  reading neither has.
- One of the owner's apps named in a record that goes on a public Release.
- `vm_stat` read wrongly: a kind of page missing, or pages taken as bytes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "host_quiet_reading.py"
_spec = importlib.util.spec_from_file_location("host_quiet_reading", _SCRIPT)
quiet = importlib.util.module_from_spec(_spec)
sys.modules["host_quiet_reading"] = quiet
_spec.loader.exec_module(quiet)

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                               10243.
Pages active:                            475374.
Pages inactive:                          474553.
Pages speculative:                         1210.
Pages wired down:                        187717.
Pages occupied by compressor:            367186.
"""
PS = """\
  101   12.5  204800 /Applications/RobloxStudio.app/Contents/MacOS/RobloxStudio -task EditFile
  102    1.0   51200 /Users/me/Code/squad-ops/.venv/bin/python -m squadops.remote_execution.worker_main
  103    3.0  102400 /Applications/Docker.app/Contents/MacOS/com.docker.backend
  104    0.5   10240 /opt/homebrew/bin/ollama serve
  105   40.0  409600 /Applications/Secret Diary.app/Contents/MacOS/Secret Diary --open my-notes.txt
  106    2.0   20480 /usr/libexec/somedaemon
"""
OUTPUTS = {
    "sysctl": "{ 2.46 4.68 4.83 }\n",
    "vm_stat": VM_STAT,
    "memory_pressure": "System-wide memory free percentage: 63%\n",
    "ollama": "NAME           ID    SIZE   PROCESSOR  UNTIL\nqwen2.5:14b    abc   9 GB   100% GPU   4 minutes\n",
    "docker": "a1\nb2\n",
    "ps": PS,
}


def _run(failing: set[str] = frozenset()):
    def run(command: list[str]) -> str:
        if command[0] in failing:
            raise OSError(f"{command[0]} isn't there")
        return OUTPUTS[command[0]]

    return run


NOW = lambda: datetime(2026, 11, 27, 3, 0, tzinfo=UTC)  # noqa: E731


def test_each_reading_is_taken_and_only_our_processes_are_named():
    document = quiet.reading(_run(), NOW)

    assert document["load_average"] == [2.46, 4.68, 4.83]
    assert document["memory_bytes"] == {
        "free": 10243 * 16384,
        "active": 475374 * 16384,
        "inactive": 474553 * 16384,
        "wired": 187717 * 16384,
        "compressed": 367186 * 16384,
    }
    assert (document["memory_free_percent"], document["models_loaded"]) == (63, ["qwen2.5:14b"])
    assert document["docker"] == {"answers": True, "containers_running": 2}
    assert document["processes"] == {
        "studio": {"count": 1, "cpu_percent": 12.5, "rss_mb": 200.0},
        "worker": {"count": 1, "cpu_percent": 1.0, "rss_mb": 50.0},
        "docker": {"count": 1, "cpu_percent": 3.0, "rss_mb": 100.0},
        "ollama": {"count": 1, "cpu_percent": 0.5, "rss_mb": 10.0},
        "other": {"count": 2, "cpu_percent": 42.0, "rss_mb": 420.0},
    }
    whole = json.dumps(document)
    assert "Secret Diary" not in whole and "my-notes" not in whole and "somedaemon" not in whole


@pytest.mark.parametrize(
    ("failing", "key"),
    [
        ({"sysctl"}, "load_average"),
        ({"vm_stat"}, "memory_bytes"),
        ({"memory_pressure"}, "memory_free_percent"),
        ({"ollama"}, "models_loaded"),
        ({"ps"}, "processes"),
    ],
)
def test_a_reading_that_cant_be_taken_says_so_and_is_never_left_out(failing, key):
    document = quiet.reading(_run(failing), NOW)

    assert document[key] == {"unread": f"OSError: {next(iter(failing))} isn't there"}


def test_docker_that_doesnt_answer_is_read_as_not_answering():
    assert quiet.reading(_run({"docker"}), NOW)["docker"] == {
        "answers": False,
        "why": "docker isn't there",
    }


@pytest.mark.parametrize(
    ("text", "why"),
    [
        ("Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 1.\n", "read no"),
        ("Pages free: 1.\n", "names no page size"),
    ],
)
def test_a_vm_stat_missing_a_kind_of_page_is_unread_never_zero(text, why):
    with pytest.raises(ValueError, match=why):
        quiet.memory(text)
