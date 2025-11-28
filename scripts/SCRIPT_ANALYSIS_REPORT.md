# Script Analysis Report

**Date**: 2025-11-27  
**Purpose**: Categorize all scripts for proper organization

## Script Categorization

### Temporary Migration Scripts → `scripts/dev/migrations/temp_*.py`

1. **`apply_memory_migration.py`**
   - **Type**: Database migration (one-time)
   - **Purpose**: Adds `memory_count` column to `agent_status` table
   - **Status**: Migration likely already applied
   - **Action**: Move to `temp_apply_memory_migration.py`

2. **`migrate_task_schema.py`**
   - **Type**: Database migration (one-time)
   - **Purpose**: Migrates from `agent_task_logs` to `execution_cycle` and `agent_task_log` tables
   - **Status**: Migration likely already applied (SIP-024/025 implemented)
   - **Action**: Move to `temp_migrate_task_schema.py`

### Reusable Development Utilities → `scripts/dev/`

3. **`build_agent.py`**
   - **Type**: Build tool (reusable)
   - **Purpose**: Assembles container-ready agent packages
   - **Usage**: Referenced in `rebuild_and_deploy.sh`, used regularly
   - **Action**: Move to `scripts/dev/build_agent.py`

4. **`build_all_agents.py`**
   - **Type**: Build tool (reusable)
   - **Purpose**: Builds all agent packages
   - **Usage**: Used for bulk builds
   - **Action**: Move to `scripts/dev/build_all_agents.py`

5. **`validate_capabilities.py`**
   - **Type**: Validation tool (reusable)
   - **Purpose**: Validates capability catalog and bindings (SIP-046)
   - **Usage**: Could be used in CI/CD, development validation
   - **Action**: Move to `scripts/dev/validate_capabilities.py`

### Maintainer Tools

6. **`version_cli.py`**
   - **Type**: Maintainer CLI tool
   - **Purpose**: Version management CLI for framework and agents
   - **Usage**: Maintainer use for version management
   - **Action**: Move to `scripts/maintainer/version_cli.py`

## Summary

- **Temporary migrations**: 2 scripts → Move to `scripts/dev/migrations/temp_*.py`
- **Reusable utilities**: 3 scripts → Move to `scripts/dev/`
- **CLI tools**: 1 script → Keep at root

