#!/usr/bin/env python3
"""
SquadOps Version Management CLI

Manages framework version across pyproject.toml and src/squadops/__init__.py.
Agent configurations are managed via agents/instances/instances.yaml.

Usage:
    python scripts/maintainer/version_cli.py version          # Show current version
    python scripts/maintainer/version_cli.py bump <version>   # Bump framework version
    python scripts/maintainer/version_cli.py list             # List all agents
    python scripts/maintainer/version_cli.py show <agent>     # Show agent details
"""

import re
import sys
from pathlib import Path

import yaml

# Resolve paths relative to repo root
REPO_ROOT = Path(__file__).parent.parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
INIT_PATH = REPO_ROOT / "src" / "squadops" / "__init__.py"
INSTANCES_PATH = REPO_ROOT / "agents" / "instances" / "instances.yaml"


def get_framework_version() -> str:
    """Get framework version from squadops package."""
    try:
        # Try importing directly
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from squadops import __version__

        return __version__
    except ImportError:
        # Fall back to parsing pyproject.toml
        content = PYPROJECT_PATH.read_text()
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        return match.group(1) if match else "unknown"


def get_agents() -> list[dict]:
    """Load agent instances from instances.yaml."""
    if not INSTANCES_PATH.exists():
        return []

    with open(INSTANCES_PATH) as f:
        data = yaml.safe_load(f)

    return data.get("instances", [])


def show_framework_version():
    """Show current framework version."""
    version = get_framework_version()
    print(f"SquadOps Framework v{version}")


def list_agents():
    """List all agents and their configurations."""
    version = get_framework_version()
    agents = get_agents()

    print(f"SquadOps Framework v{version}")
    print()
    print("Agent Instances")
    print("=" * 70)
    print(f"{'ID':<12} {'NAME':<15} {'ROLE':<8} {'MODEL':<25} {'ENABLED'}")
    print("-" * 70)

    for agent in agents:
        agent_id = agent.get("id", "?")
        name = agent.get("display_name", "?")
        role = agent.get("role", "?")
        model = agent.get("model", "?")
        enabled = "yes" if agent.get("enabled", False) else "no"
        print(f"{agent_id:<12} {name:<15} {role:<8} {model:<25} {enabled}")

    print()
    print(f"Total: {len(agents)} agents")


def show_agent_details(agent_id: str):
    """Show detailed information for a specific agent."""
    agents = get_agents()

    agent = next((a for a in agents if a.get("id") == agent_id), None)
    if not agent:
        print(f"Agent '{agent_id}' not found")
        print()
        print("Available agents:")
        for a in agents:
            print(f"  - {a.get('id')}")
        return

    print(f"Agent: {agent.get('display_name', agent_id)}")
    print("=" * 50)
    print(f"  ID:          {agent.get('id')}")
    print(f"  Role:        {agent.get('role')}")
    print(f"  Model:       {agent.get('model')}")
    print(f"  Enabled:     {agent.get('enabled', False)}")
    print(f"  Description: {agent.get('description', 'N/A')}")
    print()
    print(f"Config file: {INSTANCES_PATH}")


def bump_version(new_version: str):
    """Bump framework version in pyproject.toml and __init__.py."""
    old_version = get_framework_version()

    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+(-[\w.]+)?$", new_version):
        print(f"Invalid version format: {new_version}")
        print("Expected format: X.Y.Z or X.Y.Z-suffix")
        return False

    errors = []

    # Update pyproject.toml — only the [project] version line, not tool config
    # like target-version (ruff) or python_version (mypy).
    if PYPROJECT_PATH.exists():
        content = PYPROJECT_PATH.read_text()
        new_content = re.sub(
            r'^(version\s*=\s*")[^"]+(")',
            rf"\g<1>{new_version}\g<2>",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if new_content != content:
            PYPROJECT_PATH.write_text(new_content)
            print("  Updated: pyproject.toml")
        else:
            errors.append("pyproject.toml: version pattern not found")
    else:
        errors.append("pyproject.toml: file not found")

    # Update src/squadops/__init__.py
    if INIT_PATH.exists():
        content = INIT_PATH.read_text()

        # Update __version__
        new_content = re.sub(r'(__version__\s*=\s*")[^"]+(")', rf"\g<1>{new_version}\g<2>", content)

        # Update docstring version
        new_content = re.sub(r"(Framework Version:\s*)\S+", rf"\g<1>{new_version}", new_content)

        if new_content != content:
            INIT_PATH.write_text(new_content)
            print("  Updated: src/squadops/__init__.py")
        else:
            errors.append("__init__.py: version pattern not found")
    else:
        errors.append("src/squadops/__init__.py: file not found")

    if errors:
        print()
        print("Warnings:")
        for err in errors:
            print(f"  - {err}")

    print()
    print(f"Version bumped: {old_version} -> {new_version}")
    print()
    print("Next steps:")
    print("  git add pyproject.toml src/squadops/__init__.py")
    print(f"  git commit -m 'chore: bump framework version to {new_version}'")

    return True


def main():
    if len(sys.argv) < 2:
        print("SquadOps Version Management CLI")
        print()
        print("Commands:")
        print("  version              Show current framework version")
        print("  bump <version>       Bump framework version (e.g., 0.9.0)")
        print("  list                 List all agent instances")
        print("  show <agent_id>      Show agent details (e.g., max, neo)")
        print()
        print("Examples:")
        print("  python scripts/maintainer/version_cli.py version")
        print("  python scripts/maintainer/version_cli.py bump 0.9.0")
        print("  python scripts/maintainer/version_cli.py list")
        print("  python scripts/maintainer/version_cli.py show max")
        return

    command = sys.argv[1].lower()

    if command == "version":
        show_framework_version()

    elif command == "bump":
        if len(sys.argv) < 3:
            print("Usage: bump <version>")
            print("Example: python scripts/maintainer/version_cli.py bump 0.9.0")
            return
        bump_version(sys.argv[2])

    elif command == "list":
        list_agents()

    elif command == "show":
        if len(sys.argv) < 3:
            print("Usage: show <agent_id>")
            print("Example: python scripts/maintainer/version_cli.py show max")
            return
        show_agent_details(sys.argv[2])

    else:
        print(f"Unknown command: {command}")
        print("Run without arguments to see usage.")


if __name__ == "__main__":
    main()
