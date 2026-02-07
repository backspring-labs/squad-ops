"""SDK isolation guardrail test (SIP-0061).

Scans all .py files under src/squadops/ and asserts zero lines match
`import langfuse` or `from langfuse`. The LangFuse SDK MUST only appear
in adapters/telemetry/langfuse/.
"""

from pathlib import Path

import pytest


def test_no_langfuse_imports_in_core_domain():
    """Ensure langfuse SDK is never imported inside src/squadops/."""
    src_dir = Path(__file__).resolve().parent.parent.parent.parent / "src" / "squadops"
    assert src_dir.exists(), f"src/squadops/ not found at {src_dir}"

    violations = []
    for py_file in src_dir.rglob("*.py"):
        lines = py_file.read_text(encoding="utf-8").splitlines()
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith("#"):
                continue
            if "import langfuse" in stripped or "from langfuse" in stripped:
                rel_path = py_file.relative_to(src_dir.parent.parent)
                violations.append(f"{rel_path}:{line_num}: {stripped}")

    if violations:
        pytest.fail(
            "LangFuse SDK imports found in src/squadops/ (must only be in adapters/):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
