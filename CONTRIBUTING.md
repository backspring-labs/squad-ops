# Contributing to SquadOps

## SIP (SquadOps Improvement Proposal) Workflow

SIPs are governance artifacts that define protocols, standards, and improvements for the SquadOps framework. This document describes how to create, submit, and manage SIPs.

### Directory Structure

SIPs are organized in the `sips/` directory:

```
sips/
  registry.yaml          # Canonical registry of all numbered SIPs
  proposals/             # Unnumbered SIPs (drafts, proposals)
  SIP-00NN-TITLE.md      # Numbered SIPs (accepted, implemented, deprecated)
```

### SIP Lifecycle

SIPs move through four states:

1. **proposed** - Unnumbered, lives in `sips/proposals/`
2. **accepted** - Numbered, approved by maintainer, lives in `sips/`
3. **implemented** - Framework functionality matches the SIP specification
4. **deprecated** - Superseded or retired, but preserved for historical reference

### Creating a New SIP

#### For Contributors

1. **Create a draft SIP** in `sips/proposals/`:
   ```bash
   # Generate a ULID for your SIP
   python3 scripts/maintainer/generate_sip_uid.py
   
   # Create your SIP file
   touch sips/proposals/SIP-PROPOSAL-My-Idea.md
   ```

2. **Add required metadata** at the top of your SIP file:
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
   original_filename: "SIP-PROPOSAL-My-Idea.md"
   ---
   ```

3. **Write your SIP** following the standard format:
   - Summary
   - Motivation
   - Proposal
   - Implementation details
   - Acceptance criteria

4. **Open a PR** for review

#### For Maintainers

After a SIP is approved:

1. **Set the maintainer flag**:
   ```bash
   export SQUADOPS_MAINTAINER=1
   ```

2. **Assign a SIP number**:
   ```bash
   python3 scripts/maintainer/assign_sip_number.py sips/proposals/SIP-PROPOSAL-My-Idea.md
   ```

   This script will:
   - Assign the next available SIP number
   - Update the SIP file metadata
   - Move the file from `sips/proposals/` to `sips/`
   - Rename the file to `SIP-00NN-TITLE.md` format
   - Update `sips/registry.yaml`

### SIP Metadata Requirements

Each SIP must include the following metadata in YAML frontmatter:

- `sip_uid`: Immutable ULID generated at creation
- `sip_number`: null (for proposals) or integer (for numbered SIPs)
- `title`: Descriptive title
- `status`: "proposed" | "accepted" | "implemented" | "deprecated"
- `author`: Author name
- `approver`: null or maintainer name
- `created_at`: ISO 8601 timestamp
- `updated_at`: ISO 8601 timestamp
- `original_filename`: Original filename for traceability

### SIP Registry

The `sips/registry.yaml` file is the canonical index of all numbered SIPs. It is maintained automatically by maintainer scripts and should not be edited manually.

### Rules

**Contributors may:**
- Create SIP drafts in `sips/proposals/`
- Generate `sip_uid` for new SIPs
- Set `sip_number: null` for proposals
- Open PRs for review

**Contributors may NOT:**
- Assign SIP numbers
- Modify `sips/registry.yaml`
- Move SIPs into `sips/` root directory

**Maintainers may:**
- Assign SIP numbers using `assign_sip_number.py`
- Update SIP status
- Modify the registry

### Unknown or Uncertain SIPs

If you're unsure about a SIP's status or lifecycle state, it should be placed in `sips/proposals/`. The conservative approach ensures no SIPs are lost or misplaced.

### Additional Resources

- See `sips/registry.yaml` for all numbered SIPs
- Check `sips/MIGRATION_INVENTORY.json` for migration history
- Review existing SIPs in `sips/` for examples

