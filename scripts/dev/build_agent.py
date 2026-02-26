#!/usr/bin/env python3
"""
Build script for validating agent packages.

For the new architecture (SIP-0.8.8), Docker installs the squadops package directly.
This script validates the role exists and provides build instructions.

Usage:
    python scripts/dev/build_agent.py <role>
    python scripts/dev/build_agent.py lead
    python scripts/dev/build_agent.py dev
"""

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_git_commit(base_path: Path) -> str | None:
    """Get git commit hash.

    Args:
        base_path: Base path of repository

    Returns:
        Git commit hash or None
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=base_path,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def validate_agent_build(role: str, base_path: Path) -> None:
    """Validate agent build configuration.

    For the new architecture, Docker installs the squadops package directly.
    This function validates the role exists and provides build info.

    Args:
        role: Agent role name (lead, dev, qa, strat, data)
        base_path: Repository base path
    """
    logger.info(f"Validating agent build for role: {role}")

    # Check role module exists
    role_module = base_path / "src" / "squadops" / "agents" / "roles" / f"{role}.py"
    if not role_module.exists():
        raise FileNotFoundError(f"Role module not found: {role_module}")

    # Check skills directory exists for this role
    skills_dir = base_path / "src" / "squadops" / "agents" / "skills" / role
    if not skills_dir.exists():
        logger.warning(f"No role-specific skills found at: {skills_dir}")

    # Check entry point exists
    entrypoint = base_path / "src" / "squadops" / "agents" / "entrypoint.py"
    if not entrypoint.exists():
        raise FileNotFoundError(f"Entry point not found: {entrypoint}")

    # Check Dockerfile exists
    dockerfile = base_path / "agents" / "Dockerfile"
    if not dockerfile.exists():
        raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")

    # Check requirements.txt exists
    requirements = base_path / "requirements.txt"
    if not requirements.exists():
        raise FileNotFoundError(f"Requirements not found: {requirements}")

    # List skills for this role
    skills = []
    if skills_dir.exists():
        for skill_file in skills_dir.glob("*.py"):
            if skill_file.name != "__init__.py":
                skills.append(skill_file.stem)

    # Also include shared skills
    shared_skills_dir = base_path / "src" / "squadops" / "agents" / "skills" / "shared"
    if shared_skills_dir.exists():
        for skill_file in shared_skills_dir.glob("*.py"):
            if skill_file.name != "__init__.py":
                skills.append(f"shared.{skill_file.stem}")

    # Get git commit
    git_commit = get_git_commit(base_path)

    logger.info(f"Agent build validated successfully: {role}")
    logger.info(f"   Role module: {role_module.name}")
    logger.info(f"   Skills: {', '.join(sorted(skills)) if skills else 'none'}")
    logger.info("   Entry point: python -m squadops.agents.entrypoint")
    logger.info("   Dockerfile: agents/Dockerfile")
    if git_commit:
        logger.info(f"   Git commit: {git_commit[:8]}")
    logger.info("")
    logger.info("To build the Docker image:")
    logger.info(
        f"   docker build --build-arg AGENT_ROLE={role} -t squadops-{role} -f agents/Dockerfile ."
    )


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate agent build configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/dev/build_agent.py lead
    python scripts/dev/build_agent.py dev
    python scripts/dev/build_agent.py qa

Available roles: lead, dev, qa, strat, data
        """,
    )
    parser.add_argument(
        "role",
        help="Agent role to validate (lead, dev, qa, strat, data)",
    )

    args = parser.parse_args()
    role = args.role
    base_path = Path.cwd()

    try:
        validate_agent_build(role, base_path)
    except Exception as e:
        logger.error(f"Build validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
