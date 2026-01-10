# SquadOps Improvement Proposals (SIPs)

This directory contains all SquadOps Improvement Proposals (SIPs) - governance artifacts that define protocols, standards, and improvements for the SquadOps framework.

## Overview

SIPs are organized by lifecycle status in subdirectories:

```
sips/
  registry.yaml          # Canonical registry of all numbered SIPs
  proposals/             # Unnumbered SIPs (drafts, proposals)
  accepted/              # Accepted SIPs (numbered, approved)
  implemented/           # Implemented SIPs (framework matches specification)
  deprecated/           # Deprecated SIPs (superseded or retired)
```

The `registry.yaml` file is the authoritative index of all numbered SIPs and is maintained automatically by maintainer scripts.

## SIP Lifecycle

SIPs move through four states in a linear progression:

```
proposed → accepted → implemented → deprecated
```

### Status Definitions

1. **proposed** - Unnumbered draft SIP, lives in `sips/proposals/`
   - Created by contributors
   - Awaiting maintainer review and approval
   - Has `sip_uid` but `sip_number: null`

2. **accepted** - Numbered, approved by maintainer, lives in `sips/accepted/`
   - Assigned a SIP number automatically during transition
   - Filename normalized to `SIP-00NN-Word1-Word2-Word3-Word4.md` format
   - Added to `registry.yaml`

3. **implemented** - Framework functionality matches the SIP specification, lives in `sips/implemented/`
   - Code changes have been completed
   - Framework behavior aligns with SIP requirements
   - Ready for production use

4. **deprecated** - Superseded or retired, but preserved for historical reference, lives in `sips/deprecated/`
   - No longer active or recommended
   - Kept for historical context and traceability

### Valid Transitions

| From | To | Description |
|------|-----|-------------|
| `proposed` | `accepted` | Maintainer approves and assigns SIP number |
| `accepted` | `implemented` | Implementation complete, framework matches spec |
| `accepted` | `deprecated` | SIP superseded before implementation |
| `implemented` | `deprecated` | Implemented SIP superseded by newer version |

## Status Progression Workflow

### For Maintainers

**Always use the official script** - Never manually move files or edit the registry.

#### Prerequisites

Set the maintainer flag:
```bash
export SQUADOPS_MAINTAINER=1
```

#### Transition: proposed → accepted

```bash
python3 scripts/maintainer/update_sip_status.py sips/proposals/SIP-My-Idea.md accepted
```

**What the script does automatically:**
- Assigns the next available SIP number
- Updates SIP file metadata (status, sip_number, updated_at)
- Moves file from `sips/proposals/` to `sips/accepted/`
- Renames file to normalized format: `SIP-00NN-Word1-Word2-Word3-Word4.md` (max 4 words from title)
- Adds entry to `sips/registry.yaml`
- Cleans up any duplicate files with the same `sip_uid` or `sip_number`

#### Transition: accepted → implemented

```bash
python3 scripts/maintainer/update_sip_status.py sips/accepted/SIP-0052-Title.md implemented
```

**What the script does automatically:**
- Updates SIP file metadata (status, updated_at)
- Moves file from `sips/accepted/` to `sips/implemented/`
- Updates `sips/registry.yaml` (status, path, updated_at)
- Cleans up any duplicate files with the same `sip_uid` or `sip_number`
- Validates registry path matches canonical file

#### Transition: implemented → deprecated

```bash
python3 scripts/maintainer/update_sip_status.py sips/implemented/SIP-0021-Title.md deprecated
```

**What the script does automatically:**
- Updates SIP file metadata (status, updated_at)
- Moves file from `sips/implemented/` to `sips/deprecated/`
- Updates `sips/registry.yaml` (status, path, updated_at)
- Cleans up any duplicate files

### For Contributors

To request SIP progression, open a PR or issue with a clear request:

**Recommended phrases:**
- "Transition SIP-XXXX to [status] using the update_sip_status script"
- "Use the SIP status update script to move SIP-XXXX from [current] to [new status]"
- "Run update_sip_status.py to progress SIP-XXXX to [status]"

**What to include:**
- SIP number or filename
- Current status
- Desired new status
- Brief reason (optional but helpful)

**What NOT to do:**
- Don't manually copy files between folders
- Don't manually edit `sips/registry.yaml`
- Don't manually rename files
- Don't manually update YAML frontmatter status fields

### For AI Assistants

**Critical Convention:** Always use `scripts/maintainer/update_sip_status.py` for status transitions.

**Required phrases when user requests SIP progression:**
- "using the update_sip_status script"
- "via the maintainer script"
- "using scripts/maintainer/update_sip_status.py"

**What the script handles automatically (do NOT do manually):**
- File moves between lifecycle folders
- Registry updates in `sips/registry.yaml`
- SIP number assignment (for proposed → accepted)
- Filename normalization
- Duplicate file cleanup
- Metadata updates (status, updated_at)

**Never:**
- Manually copy files between folders
- Manually edit `sips/registry.yaml`
- Manually rename SIP files
- Manually update YAML frontmatter

## Script Usage

### Location

`scripts/maintainer/update_sip_status.py`

### Command Syntax

```bash
export SQUADOPS_MAINTAINER=1
python3 scripts/maintainer/update_sip_status.py <sip_file> <new_status>
```

### Examples

```bash
# Transition proposed → accepted
export SQUADOPS_MAINTAINER=1
python3 scripts/maintainer/update_sip_status.py sips/proposals/SIP-My-Idea.md accepted

# Transition accepted → implemented
export SQUADOPS_MAINTAINER=1
python3 scripts/maintainer/update_sip_status.py sips/accepted/SIP-0052-Secrets-Management.md implemented

# Transition implemented → deprecated
export SQUADOPS_MAINTAINER=1
python3 scripts/maintainer/update_sip_status.py sips/implemented/SIP-0021-Agent-Memory-Protocol.md deprecated
```

### What the Script Does

The script performs the following operations automatically:

1. **Validates transition** - Ensures the requested transition is allowed
2. **Detects duplicates** - Scans all lifecycle folders for files with the same `sip_uid` or `sip_number`
3. **Cleans up duplicates** - Removes duplicate files before proceeding
4. **Updates metadata** - Modifies YAML frontmatter (status, sip_number if needed, updated_at)
5. **Moves file** - Relocates file to appropriate lifecycle folder
6. **Normalizes filename** - For proposed → accepted, renames to `SIP-00NN-Word1-Word2-Word3-Word4.md`
7. **Updates registry** - Modifies `sips/registry.yaml` with new status, path, and timestamp
8. **Validates registry** - Checks for registry path mismatches and warns if found

## Registry Management

### Structure

The `sips/registry.yaml` file contains:

```yaml
last_assigned: 53
sips:
  - sip_uid: "01KDP28PVHN0A20WQ2W8WNST44"
    sip_number: 52
    title: "Secrets Management"
    path: "sips/implemented/SIP-0052-Secrets-Management.md"
    status: "implemented"
    author: "Jason Ladd"
    approver: "jladd"
    created_at: "2025-12-29T00:00:00Z"
    updated_at: "2026-01-10T09:29:09.433242Z"
```

### Automatic Updates

The registry is updated automatically by `update_sip_status.py`:
- New entries added when SIP transitions from `proposed → accepted`
- Existing entries updated when SIP status changes
- Paths updated when files are moved
- Timestamps updated on every change

### Manual Edits

**Generally not needed** - The script handles all registry updates. Manual edits should only be done:
- To fix data corruption (rare)
- To correct metadata errors (with caution)
- Under maintainer supervision

## Common Workflows

### Creating a New SIP Proposal

1. Generate ULID:
   ```bash
   python3 scripts/dev/generate_sip_uid.py
   ```

2. Create SIP file in `sips/proposals/`:
   ```bash
   touch sips/proposals/SIP-My-Idea.md
   ```

3. Add YAML frontmatter:
   ```yaml
   ---
   sip_uid: "<ulid-from-step-1>"
   sip_number: null
   title: "My Improvement Idea"
   status: "proposed"
   author: "Your Name"
   approver: null
   created_at: "2025-11-27T00:00:00Z"
   updated_at: "2025-11-27T00:00:00Z"
   original_filename: "SIP-My-Idea.md"
   ---
   ```

4. Write SIP content following standard format

5. Open PR for review

### Finding SIP Information

**By SIP number:**
```bash
grep -r "sip_number: 52" sips/
```

**By title:**
```bash
grep -r "Secrets Management" sips/
```

**In registry:**
```bash
grep "SIP-0052" sips/registry.yaml
```

**List all SIPs in a status:**
```bash
ls sips/implemented/
```

### Checking for Duplicates

The script automatically detects and cleans up duplicates, but you can manually check:

```bash
# Find files with same sip_uid
grep -r "sip_uid: 01KDP28PVHN0A20WQ2W8WNST44" sips/
```

## Troubleshooting

### Error: "SQUADOPS_MAINTAINER environment variable not set"

**Solution:**
```bash
export SQUADOPS_MAINTAINER=1
```

### Error: "Invalid transition: X → Y"

**Cause:** The requested transition is not allowed.

**Valid transitions:**
- `proposed → accepted`
- `accepted → implemented`
- `accepted → deprecated`
- `implemented → deprecated`

**Solution:** Check current status and request a valid transition.

### Error: "SIP file location doesn't match current status"

**Cause:** File is in wrong lifecycle folder.

**Solution:** The script will still proceed, but verify the file location is correct for the current status.

### Warning: "Registry path doesn't match canonical file"

**Cause:** Registry points to a different file than the one being transitioned.

**Solution:** The script will warn but continue. Review registry entry after transition to ensure it's correct.

### Duplicate Files Found

**Cause:** Multiple files exist with the same `sip_uid` or `sip_number`.

**Solution:** The script automatically cleans up duplicates. If manual cleanup is needed:

```bash
# Find duplicates
grep -r "sip_uid: <uid>" sips/

# Review and manually remove if needed (be careful!)
```

### File Permission Errors

**Cause:** Insufficient permissions to move/delete files.

**Solution:** Ensure you have write permissions to the `sips/` directory and subdirectories.

## SIP Metadata Requirements

Each SIP must include the following metadata in YAML frontmatter:

| Field | Type | Description |
|-------|------|-------------|
| `sip_uid` | string | Immutable ULID generated at creation |
| `sip_number` | int \| null | null for proposals, integer for numbered SIPs |
| `title` | string | Descriptive title |
| `status` | string | "proposed" \| "accepted" \| "implemented" \| "deprecated" |
| `author` | string | Author name |
| `approver` | string \| null | null or maintainer name |
| `created_at` | string | ISO 8601 timestamp |
| `updated_at` | string | ISO 8601 timestamp |
| `original_filename` | string | Original filename for traceability |

## Rules

### Contributors May:
- Create SIP drafts in `sips/proposals/`
- Generate `sip_uid` for new SIPs using `scripts/dev/generate_sip_uid.py`
- Set `sip_number: null` for proposals
- Open PRs for review

### Contributors May NOT:
- Assign SIP numbers (maintainer-only)
- Modify `sips/registry.yaml` (maintainer-only)
- Move SIPs between lifecycle folders (use script)
- Manually rename SIP files (script handles this)

### Maintainers May:
- Update SIP status using `update_sip_status.py` (handles all transitions)
- Modify the registry (rarely needed, script handles most cases)
- Review and approve SIP proposals

## Related Documentation

- **[SIP-0019: SIP Management Workflow Protocol](implemented/SIP-0019-SIP-Management-Workflow-Protocol.md)** - Formal protocol specification
- **[CONTRIBUTING.md](../CONTRIBUTING.md)** - General contributor guidelines and SIP creation workflow
- **[Script Location](../scripts/maintainer/update_sip_status.py)** - Status update script implementation

## Quick Reference

### Command Template

```bash
export SQUADOPS_MAINTAINER=1
python3 scripts/maintainer/update_sip_status.py <sip_file> <new_status>
```

### Valid Status Transitions

| Transition | Command Example |
|------------|----------------|
| `proposed → accepted` | `python3 scripts/maintainer/update_sip_status.py sips/proposals/SIP-File.md accepted` |
| `accepted → implemented` | `python3 scripts/maintainer/update_sip_status.py sips/accepted/SIP-0052-Title.md implemented` |
| `accepted → deprecated` | `python3 scripts/maintainer/update_sip_status.py sips/accepted/SIP-XXXX-Title.md deprecated` |
| `implemented → deprecated` | `python3 scripts/maintainer/update_sip_status.py sips/implemented/SIP-XXXX-Title.md deprecated` |

### Environment Variable

**Required for all status transitions:**
```bash
export SQUADOPS_MAINTAINER=1
```

---

**Last Updated:** 2026-01-10  
**Maintainer Script:** `scripts/maintainer/update_sip_status.py`
