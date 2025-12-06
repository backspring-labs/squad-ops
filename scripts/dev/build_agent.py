#!/usr/bin/env python3
"""
Build script for assembling container-ready agent packages.

This script reads agent config.yaml, resolves dependencies, and assembles
only the required files into dist/agents/{role}/ for container builds.
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Capability name to module path mapping (from loader.py)
CAPABILITY_MAP = {
    'task.create': 'agents.capabilities.task_creator',
    'prd.read': 'agents.capabilities.prd_processor',
    'prd.analyze': 'agents.capabilities.prd_processor',
    'prd.process': 'agents.capabilities.prd_processor',
    'task.delegate': 'agents.capabilities.task_delegator',
    'task.determine_target': 'agents.capabilities.task_delegator',
    'build.requirements.generate': 'agents.capabilities.build_requirements_generator',
    'build.artifact': 'agents.capabilities.build_artifact',
    'manifest.generate': 'agents.capabilities.manifest_generator',
    'docker.build': 'agents.capabilities.docker_builder',
    'docker.deploy': 'agents.capabilities.docker_deployer',
    'version.archive': 'agents.capabilities.version_archiver',
    'task.completion.handle': 'agents.capabilities.task_completion_handler',
    'task.completion.emit': 'agents.capabilities.task_completion_emitter',
    'warmboot.wrapup': 'agents.capabilities.wrapup_generator',
    'warmboot.memory': 'agents.capabilities.warmboot_memory_handler',
    'validate.warmboot': 'agents.capabilities.warmboot_validator',
    'telemetry.collect': 'agents.capabilities.telemetry_collector',
    'governance.approval': 'agents.capabilities.governance_approval',
    'governance.escalation': 'agents.capabilities.governance_escalation',
    'governance.task_coordination': 'agents.capabilities.governance_task_coordination',
    'comms.documentation': 'agents.capabilities.documentation_creator',
    'comms.reasoning.emit': 'agents.capabilities.reasoning_event_emitter',
    'comms.chat': 'agents.capabilities.comms_chat',
    'product.draft_prd_from_prompt': 'agents.capabilities.product.draft_prd_from_prompt',
    'product.validate_acceptance_criteria': 'agents.capabilities.product.validate_acceptance_criteria',
    'qa.test_design': 'agents.capabilities.qa.test_design',
    'qa.test_dev': 'agents.capabilities.qa.test_dev',
    'qa.test_execution': 'agents.capabilities.qa.test_execution',
    'test.run': 'agents.capabilities.qa.test_execution',  # Alias for test.run
    'data.collect_cycle_snapshot': 'agents.capabilities.data.collect_cycle_snapshot',
    'data.profile_cycle_metrics': 'agents.capabilities.data.profile_cycle_metrics',
    'data.compose_cycle_summary': 'agents.capabilities.data.compose_cycle_summary',
}


def get_capability_module_path(capability_name: str) -> str:
    """Get module path for a capability name."""
    return CAPABILITY_MAP.get(capability_name)


def module_path_to_file_path(module_path: str, base_path: Path) -> Path:
    """Convert module path to file system path."""
    # Convert 'agents.capabilities.qa.test_design' to 'agents/capabilities/qa/test_design.py'
    parts = module_path.split('.')
    if parts[0] == 'agents':
        # Remove 'agents' prefix, join rest with /
        file_path = base_path / '/'.join(parts[1:]) + '.py'
    else:
        file_path = base_path / '/'.join(parts) + '.py'
    return file_path


def get_capability_directory(module_path: str) -> str:
    """Extract directory path from module path."""
    # e.g., 'agents.capabilities.qa.test_design' -> 'agents/capabilities/qa'
    parts = module_path.split('.')
    if len(parts) >= 3:
        return '/'.join(parts[:3])  # agents/capabilities/qa
    return '/'.join(parts[:-1])  # Fallback


def copy_capability_files(capability_name: str, src_base: Path, dst_base: Path) -> set[str]:
    """Copy capability files and return set of directories copied."""
    module_path = get_capability_module_path(capability_name)
    if not module_path:
        logger.warning(f"Unknown capability: {capability_name}, skipping")
        return set()
    
    copied_dirs = set()
    
    # Convert module path to file path to find the actual file
    # e.g., 'agents.capabilities.qa.test_design' -> 'agents/capabilities/qa/test_design.py'
    parts = module_path.split('.')
    if parts[0] == 'agents':
        file_path_parts = parts[1:]  # Remove 'agents' prefix
        file_name = file_path_parts[-1] + '.py'
        dir_parts = file_path_parts[:-1]
        
        # Try to copy the entire capability directory (e.g., agents/capabilities/qa/)
        # This ensures we get __init__.py and related files
        if len(dir_parts) >= 2:  # Has subdirectory (e.g., qa, product)
            cap_dir = 'agents/' + '/'.join(dir_parts)
            src_dir = src_base / cap_dir
            if src_dir.exists() and src_dir.is_dir():
                dst_dir = dst_base / cap_dir
                if dst_dir.exists():
                    # Merge directories
                    for item in src_dir.iterdir():
                        src_item = src_dir / item.name
                        dst_item = dst_dir / item.name
                        if src_item.is_dir():
                            copy_directory(src_item, dst_item, f"capability {item.name}")
                        else:
                            shutil.copy2(src_item, dst_item)
                else:
                    copy_directory(src_dir, dst_dir, f"capability {dir_parts[-1]}")
                copied_dirs.add(cap_dir)
        else:
            # Top-level capability (e.g., agents/capabilities/task_creator.py)
            file_path = src_base / 'agents' / 'capabilities' / file_name
            if file_path.exists():
                dst_path = dst_base / 'agents' / 'capabilities' / file_name
                copy_directory(file_path, dst_path, f"capability {file_name}")
                copied_dirs.add('agents/capabilities')
    
    return copied_dirs


def copy_directory(src: Path, dst: Path, description: str = ""):
    """Copy file or directory recursively."""
    if not src.exists():
        logger.warning(f"Source does not exist: {src}")
        return
    
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        logger.debug(f"Copied {description}: {src.name}")
    else:
        shutil.copy2(src, dst)
        logger.debug(f"Copied {description}: {src.name}")


def get_git_commit(base_path: Path, build_arg: str | None = None) -> str | None:
    """
    Get git commit hash.
    
    Priority:
    1. Docker build arg (GIT_COMMIT) if provided
    2. Git command (git rev-parse HEAD)
    3. None if unavailable
    
    Args:
        base_path: Base path of repository
        build_arg: Optional git commit from Docker build arg
        
    Returns:
        Git commit hash or None
    """
    # First try: Docker build arg (from CI/CD)
    if build_arg:
        return build_arg.strip()
    
    # Second try: Git command
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=base_path,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        # Git not available or not a git repo
        pass
    
    # Fallback: None
    return None


def get_build_hash(dist_dir: Path) -> str:
    """
    Compute deterministic build hash of all files in dist directory.
    
    Excludes manifest.json and agent_info.json from hash computation
    to avoid circular dependency.
    
    Args:
        dist_dir: Directory containing built agent package
        
    Returns:
        SHA256 hash prefixed with 'sha256:'
    """
    excluded_files = {'manifest.json', 'agent_info.json'}
    file_hashes = []
    
    # Collect all files, sorted for determinism
    all_files = sorted(dist_dir.rglob('*'))
    
    for file_path in all_files:
        if not file_path.is_file():
            continue
        
        # Skip excluded files
        if file_path.name in excluded_files:
            continue
        
        # Get relative path for consistent hashing
        rel_path = file_path.relative_to(dist_dir)
        
        try:
            # Read file content and hash
            with open(file_path, 'rb') as f:
                content = f.read()
                file_hash = hashlib.sha256(content).hexdigest()
                file_hashes.append(f"{rel_path}:{file_hash}")
        except Exception as e:
            logger.warning(f"Failed to hash file {rel_path}: {e}")
    
    # Hash concatenated file hashes
    combined = '\n'.join(file_hashes).encode('utf-8')
    build_hash = hashlib.sha256(combined).hexdigest()
    
    return f"sha256:{build_hash}"


def get_skills_list(dist_dir: Path, role: str) -> list[str]:
    """
    Get list of skills included in the agent package.
    
    Scans agents/skills/{role}/ and agents/skills/shared/ directories
    for .py files (excluding __init__.py and __pycache__).
    
    Args:
        dist_dir: Directory containing built agent package
        role: Agent role name
        
    Returns:
        Sorted list of skill module names
    """
    skills = []
    skills_base = dist_dir / "agents" / "skills"
    
    # Check role-specific skills
    role_skills_dir = skills_base / role
    if role_skills_dir.exists():
        for file_path in role_skills_dir.rglob('*.py'):
            if file_path.name != '__init__.py' and '__pycache__' not in str(file_path):
                # Extract skill name (e.g., agents/skills/qa/test_runner.py -> qa.test_runner)
                rel_path = file_path.relative_to(skills_base)
                skill_name = str(rel_path).replace('/', '.').replace('.py', '')
                skills.append(skill_name)
    
    # Check shared skills
    shared_skills_dir = skills_base / "shared"
    if shared_skills_dir.exists():
        for file_path in shared_skills_dir.rglob('*.py'):
            if file_path.name != '__init__.py' and '__pycache__' not in str(file_path):
                # Extract skill name (e.g., agents/skills/shared/text_match.py -> shared.text_match)
                rel_path = file_path.relative_to(skills_base)
                skill_name = str(rel_path).replace('/', '.').replace('.py', '')
                skills.append(skill_name)
    
    return sorted(skills)


def get_files_list(dist_dir: Path) -> list[str]:
    """
    Get list of all files included in the agent package.
    
    Args:
        dist_dir: Directory containing built agent package
        
    Returns:
        Sorted list of relative file paths
    """
    files = []
    
    for file_path in dist_dir.rglob('*'):
        if file_path.is_file():
            rel_path = file_path.relative_to(dist_dir)
            files.append(str(rel_path))
    
    return sorted(files)


def generate_manifest(
    role: str,
    dist_dir: Path,
    base_path: Path,
    capabilities: list[str],
    skills: list[str],
    files: list[str],
    build_hash: str,
    git_commit_arg: str | None = None
) -> dict[str, Any]:
    """
    Generate manifest.json with build artifact metadata.
    
    Args:
        role: Agent role name
        dist_dir: Directory containing built agent package
        base_path: Base path of repository
        capabilities: List of capability names
        skills: List of skill names
        files: List of file paths
        build_hash: Build hash
        git_commit_arg: Optional git commit from build arg
        
    Returns:
        Manifest dictionary
    """
    # Get SquadOps version
    try:
        sys.path.insert(0, str(base_path))
        from config.version import get_framework_version
        squadops_version = get_framework_version()
    except ImportError:
        squadops_version = "unknown"
    
    # Get git commit
    git_commit = get_git_commit(base_path, git_commit_arg)
    
    # Build shared_modules list (machine-readable)
    shared_modules = ["llm", "memory", "telemetry", "specs", "utils", "factory", "instances"]
    
    # Build resolver_graph (capability -> skills mapping)
    # For now, we'll build a simple mapping - can be enhanced later with actual resolution
    resolver_graph = {
        "capabilities": {}
    }
    # Note: Full resolver_graph would require capability loader analysis
    # For MVP, we'll include empty structure - can be populated in future enhancement
    
    # Build manifest
    manifest = {
        "manifest_version": "1.0",
        "role": role,
        "capabilities": sorted(capabilities),
        "skills": skills,  # Already sorted
        "shared_dependencies": [
            "base_agent.py",
            "memory/",
            "telemetry/",
            "llm/",
            "specs/",
            "utils/",
            "factory/",
            "instances/"
        ],
        "shared_modules": shared_modules,
        "resolver_graph": resolver_graph,
        "files_included": files,  # Already sorted
        "build_hash": build_hash,
        "git_commit": git_commit,
        "build_time_utc": datetime.utcnow().isoformat() + "Z",
        "squadops_version": squadops_version,
        "build_script_version": "1.0"
    }
    
    return manifest


def generate_agent_info(
    role: str,
    capabilities: list[str],
    skills: list[str],
    build_hash: str
) -> dict[str, Any]:
    """
    Generate agent_info.json template with build-time fields.
    
    Runtime fields (runtime_env, startup_time_utc, container_hash) are
    left as None and will be filled by BaseAgent at startup.
    
    Args:
        role: Agent role name
        capabilities: List of capability names
        skills: List of skill names
        build_hash: Build hash
        
    Returns:
        Agent info dictionary template
    """
    agent_info = {
        "agent_info_version": "1.0",
        "role": role,
        "agent_id": None,  # Will be filled from self.name at runtime
        "agent_entrypoint": "agent.py",
        "capabilities": sorted(capabilities),
        "skills": skills,  # Already sorted
        "build_hash": build_hash,
        "container_hash": None,  # Will be filled at runtime
        "runtime_env": None,  # Will be filled at runtime
        "startup_time_utc": None,  # Will be filled at runtime
        "image_version": None  # Optional, can be set via env var
    }
    
    return agent_info


def build_agent_package(role: str, base_path: Path) -> None:
    """Build container-ready package for an agent role."""
    logger.info(f"Building agent package for role: {role}")
    
    # Paths
    role_dir = base_path / "agents" / "roles" / role
    config_file = role_dir / "config.yaml"
    dist_dir = base_path / "dist" / "agents" / role
    
    # Load agent config
    if not config_file.exists():
        raise FileNotFoundError(f"Agent config not found: {config_file}")
    
    with open(config_file) as f:
        config = yaml.safe_load(f)
    
    # Get capabilities from implements list
    capabilities = []
    for impl in config.get('implements', []):
        cap_name = impl.get('capability')
        if cap_name:
            capabilities.append(cap_name)
    
    logger.info(f"Found {len(capabilities)} capabilities: {', '.join(capabilities)}")
    
    # Clean and create dist directory
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    # Track copied capability directories to avoid duplicates
    copied_cap_dirs = set()
    
    # Copy required capabilities
    for cap_name in capabilities:
        dirs = copy_capability_files(cap_name, base_path, dist_dir)
        copied_cap_dirs.update(dirs)
    
    # Copy capability loader and catalog (always needed)
    copy_directory(
        base_path / "agents" / "capabilities" / "loader.py",
        dist_dir / "agents" / "capabilities" / "loader.py",
        "capability loader"
    )
    copy_directory(
        base_path / "agents" / "capabilities" / "catalog.yaml",
        dist_dir / "agents" / "capabilities" / "catalog.yaml",
        "capability catalog"
    )
    copy_directory(
        base_path / "agents" / "capabilities" / "__init__.py",
        dist_dir / "agents" / "capabilities" / "__init__.py",
        "capabilities __init__"
    )
    
    # Copy shared infrastructure (always needed)
    shared_dirs = [
        ("agents/base_agent.py", "base agent"),
        ("agents/llm", "LLM client"),
        ("agents/memory", "memory adapters"),
        ("agents/telemetry", "telemetry"),
        ("agents/specs", "agent specs"),
        ("agents/utils", "utilities"),
        ("agents/factory", "agent factory"),
        ("agents/instances", "agent instances"),
    ]
    
    for rel_path, description in shared_dirs:
        src = base_path / rel_path
        dst = dist_dir / rel_path
        copy_directory(src, dst, description)
    
    # Copy tools directory (needed for dev role)
    if role == 'dev':
        copy_directory(
            base_path / "agents" / "tools",
            dist_dir / "agents" / "tools",
            "dev tools"
        )
    
    # Copy skills (role-specific + shared)
    skills_src = base_path / "agents" / "skills"
    skills_dst = dist_dir / "agents" / "skills"
    
    # Copy shared skills
    if (skills_src / "shared").exists():
        copy_directory(
            skills_src / "shared",
            skills_dst / "shared",
            "shared skills"
        )
    
    # Copy role-specific skills
    if (skills_src / role).exists():
        copy_directory(
            skills_src / role,
            skills_dst / role,
            f"{role} skills"
        )
    
    # Copy skills __init__ and registry
    if (skills_src / "__init__.py").exists():
        copy_directory(
            skills_src / "__init__.py",
            skills_dst / "__init__.py",
            "skills __init__"
        )
    if (skills_src / "registry.yaml").exists():
        copy_directory(
            skills_src / "registry.yaml",
            skills_dst / "registry.yaml",
            "skills registry"
        )
    
    # Copy config files
    copy_directory(
        base_path / "agents" / "capability_bindings.yaml",
        dist_dir / "agents" / "capability_bindings.yaml",
        "capability bindings"
    )
    
    # Copy role-specific files
    copy_directory(
        role_dir / "agent.py",
        dist_dir / "agent.py",
        "agent entry point"
    )
    copy_directory(
        role_dir / "config.yaml",
        dist_dir / "agents" / "roles" / role / "config.yaml",
        "agent config"
    )
    copy_directory(
        role_dir / "requirements.txt",
        dist_dir / "requirements.txt",
        "requirements"
    )
    
    # Copy registry.yaml (needed for role context)
    copy_directory(
        base_path / "agents" / "roles" / "registry.yaml",
        dist_dir / "agents" / "roles" / "registry.yaml",
        "role registry"
    )
    
    # Copy config directory
    copy_directory(
        base_path / "config",
        dist_dir / "config",
        "config directory"
    )
    
    # Generate metadata artifacts
    logger.info("Generating metadata artifacts...")
    
    # Get skills and files lists
    skills = get_skills_list(dist_dir, role)
    files = get_files_list(dist_dir)
    
    # Compute build hash (must be after all files copied)
    build_hash = get_build_hash(dist_dir)
    
    # Get git commit from environment (Docker build arg)
    git_commit_arg = os.getenv('GIT_COMMIT')
    
    # Generate manifest.json
    manifest = generate_manifest(
        role=role,
        dist_dir=dist_dir,
        base_path=base_path,
        capabilities=capabilities,
        skills=skills,
        files=files,
        build_hash=build_hash,
        git_commit_arg=git_commit_arg
    )
    
    manifest_path = dist_dir / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Generated manifest.json: {manifest_path}")
    
    # Generate agent_info.json
    agent_info = generate_agent_info(
        role=role,
        capabilities=capabilities,
        skills=skills,
        build_hash=build_hash
    )
    
    agent_info_path = dist_dir / "agent_info.json"
    with open(agent_info_path, 'w') as f:
        json.dump(agent_info, f, indent=2)
    logger.info(f"Generated agent_info.json: {agent_info_path}")
    
    logger.info(f"✅ Agent package built successfully: {dist_dir}")
    logger.info(f"   Capabilities: {len(capabilities)}")
    logger.info(f"   Skills: {len(skills)}")
    logger.info(f"   Files: {len(files)}")
    logger.info(f"   Build hash: {build_hash}")
    logger.info(f"   Package size: {sum(f.stat().st_size for f in dist_dir.rglob('*') if f.is_file()) / 1024:.1f} KB")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/dev/build_agent.py <role>")
        print("Example: python scripts/dev/build_agent.py qa")
        sys.exit(1)
    
    role = sys.argv[1]
    base_path = Path.cwd()
    
    try:
        build_agent_package(role, base_path)
    except Exception as e:
        logger.error(f"Failed to build agent package: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

