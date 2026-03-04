#!/usr/bin/env python3
"""
Integration Test Validator

Enforces that integration tests use REAL services, not mocks.
This script MUST pass before any integration test changes are committed.

Violations cause immediate test failure.
"""

import re
import sys
from pathlib import Path


def check_integration_tests():
    """Check all integration tests for mock usage violations."""
    violations = []
    # Get the project root (parent of tests directory)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent.parent
    integration_dir = project_root / "tests/integration"

    if not integration_dir.exists():
        print("⚠️  Integration test directory not found")
        return []

    # Files that are allowed to have mocks (configuration wrappers only)
    allowed_files = {"conftest.py", "__init__.py", "agent_manager.py"}

    # Patterns that indicate mock usage
    mock_patterns = [
        r"from unittest\.mock",
        r"import.*Mock",
        r"@patch\(",
        r"MagicMock\(",
        r"AsyncMock\(",
        r"Mock\(",
        r"unittest\.mock",
    ]

    for test_file in integration_dir.rglob("*.py"):
        # Skip allowed files
        if test_file.name in allowed_files:
            continue

        # Skip validation file itself
        if test_file.name == "validate_integration_tests.py":
            continue

        try:
            content = test_file.read_text()

            # Check for mock patterns
            for pattern in mock_patterns:
                if re.search(pattern, content):
                    # Check if it's a comment explaining why mock is OK
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if re.search(pattern, line):
                            # Check if previous line is a comment explaining exception
                            if i > 0 and (
                                "# ALLOWED" in lines[i - 1] or "# EXCEPTION" in lines[i - 1]
                            ):
                                continue
                            violations.append(
                                {
                                    "file": str(test_file.relative_to(Path.cwd())),
                                    "line": i + 1,
                                    "pattern": pattern,
                                    "content": line.strip(),
                                }
                            )
        except Exception as e:
            print(f"⚠️  Error reading {test_file}: {e}")

    return violations


def main():
    """Main validation function."""
    print("🔍 Validating integration tests...")
    print("   Checking for mock usage violations...")

    violations = check_integration_tests()

    if violations:
        print("\n" + "=" * 70)
        print("❌ VIOLATION: Integration tests are using mocks!")
        print("=" * 70)
        print("\nIntegration tests MUST use real services, not mocks.")
        print("\nViolations found:")
        print("-" * 70)

        for v in violations:
            print(f"\nFile: {v['file']}")
            print(f"Line {v['line']}: {v['content']}")
            print(f"Pattern: {v['pattern']}")

        print("\n" + "=" * 70)
        print("REFERENCE:")
        print("  tests/integration/README.md line 238:")
        print("    'Use real services - Avoid mocking external services in integration tests'")
        print("\n  tests/integration/README.md line 257:")
        print("    'Real Integration - Tests use actual services, not mocks'")
        print("\n  SQUADOPS_BUILD_PARTNER_PROMPT.md:")
        print("    'No deceptive simulations - real implementation or nothing'")
        print("=" * 70)
        print("\n💡 FIX: Rewrite tests to use real components:")
        print("   - Real PostgreSQL: asyncpg.create_pool")
        print("   - Real adapters: SqlAdapter(db_pool)")
        print("   - Real agents: via AgentRunner and handler pipeline")
        print("   - Real services: No mocks, no patches")
        print("\n" + "=" * 70)
        sys.exit(1)

    print("✅ All integration tests use real services (no mocks found)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
