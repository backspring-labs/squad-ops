# Migration Scripts Directory

## Purpose

This directory contains **temporary migration and one-time-use scripts** that are used for data migrations, repository restructuring, or other one-time operations.

## Naming Convention

All migration scripts use the `temp_` prefix to clearly indicate they are temporary:

```
temp_<description>.py
```

Examples:
- `temp_migrate_sips.py` - One-time SIP migration script
- `temp_inventory_sips.py` - One-time SIP inventory script
- `temp_reorganize_sips.py` - One-time SIP reorganization script

## When to Use This Directory

Use `scripts/dev/migrations/temp_*.py` for:

- ✅ **One-time data migrations** (e.g., database schema migrations, file reorganizations)
- ✅ **Repository restructuring scripts** (e.g., moving files, renaming directories)
- ✅ **Bulk data transformation scripts** (e.g., updating metadata, cleaning up files)
- ✅ **Temporary analysis scripts** (e.g., one-time analysis reports)

**Do NOT use this directory for:**

- ❌ Permanent maintainer tools (use `scripts/maintainer/`)
- ❌ Reusable development utilities (use `scripts/dev/`)
- ❌ Production scripts (use appropriate production location)

## Script Lifecycle

1. **Create**: Script created with `temp_` prefix in this directory
2. **Use**: Script executed for the migration/operation
3. **Verify**: Migration verified and documented
4. **Archive**: Script remains in this directory for historical reference
5. **Cleanup**: After sufficient time (e.g., 1+ release cycles), scripts can be archived or removed

## Documentation

Each migration script should include:

- Clear description of what it does
- Prerequisites and dependencies
- Usage instructions
- Expected output/results
- Rollback procedures (if applicable)

## Related Directories

- `scripts/maintainer/` - Permanent maintainer tools (e.g., `assign_sip_number.py`)
- `scripts/dev/` - Reusable development utilities
- `scripts/` - Other project scripts

## Examples

### Completed Migrations

- `temp_migrate_sips.py` - Migrated SIPs from `docs/SIPs/` to `sips/` structure
- `temp_reorganize_sips.py` - Reorganized SIPs into lifecycle folders with clean naming
- `temp_inventory_sips.py` - Created inventory of all SIPs before migration
- `temp_apply_memory_migration.py` - Database migration for memory_count column
- `temp_migrate_task_schema.py` - Database migration for task management schema (SIP-024/025)

