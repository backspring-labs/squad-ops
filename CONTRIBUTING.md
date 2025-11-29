# Contributing to SquadOps

## Local Development Setup

### Python Version Requirements

SquadOps requires **Python 3.11 or higher**. The project uses Python 3.11.14 in production (Docker containers) and for local development.

### Setting Up Python with pyenv (Recommended)

We use [pyenv](https://github.com/pyenv/pyenv) for Python version management to ensure consistency between local development and production.

#### 1. Install pyenv

```bash
# macOS (using Homebrew)
brew install pyenv

# Configure your shell (add to ~/.zshrc or ~/.bashrc)
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
```

Then restart your terminal or run:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

#### 2. Install Python 3.11.14

```bash
pyenv install 3.11.14
```

#### 3. Set Local Python Version

The project includes a `.python-version` file that pyenv will automatically detect:

```bash
cd squad-ops
pyenv local 3.11.14  # This creates/updates .python-version
```

#### 4. Create Virtual Environment

```bash
# Create virtual environment using pyenv Python
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Verify Python version
python --version  # Should show Python 3.11.14
```

#### 5. Install Dependencies

```bash
# Install test dependencies (includes agent runtime deps for unit tests)
pip install -r tests/requirements.txt
```

**Note**: `tests/requirements.txt` includes agent runtime dependencies because unit tests import and test agent code. You don't need to install `agents/requirements.txt` separately for testing.

### Verifying Your Setup

Run the test script to verify everything is configured correctly:

```bash
./tests/run_tests.sh smoke
```

**Note**: The test script automatically activates the virtual environment if it exists, so you don't need to activate it manually.

This will check:
- ✅ Python version (must be >= 3.11)
- ✅ Required dependencies (pytest, pytest-asyncio, agent runtime deps)

**Dependency Structure**: 
- `tests/requirements.txt` includes both test framework dependencies AND agent runtime dependencies
- This is necessary because unit tests import agent code (e.g., `from agents.base_agent import BaseAgent`)
- Agent dependencies are required for tests to import and test agent modules

### Automatic Virtual Environment Activation (Optional)

#### Option 1: Use direnv (Recommended for Development)

[direnv](https://direnv.net/) automatically activates the virtual environment when you `cd` into the project:

```bash
# Install direnv
brew install direnv

# Configure your shell (add to ~/.zshrc)
eval "$(direnv hook zsh)"

# Create .envrc file in project root
echo 'source .venv/bin/activate' > .envrc
direnv allow
```

Now the virtual environment activates automatically when you enter the project directory!

#### Option 2: Manual Activation (Current)

For interactive terminal use, activate manually:
```bash
source .venv/bin/activate
```

#### Option 3: Scripts Auto-Activate

All project scripts (like `./tests/run_tests.sh`) automatically activate the virtual environment, so you can run them without manual activation.

### Troubleshooting

**Problem**: `python --version` shows Python 3.9.x or older
- **Solution**: Make sure pyenv is configured in your shell and `.python-version` file exists in the project root

**Problem**: `pyenv: command not found`
- **Solution**: Restart your terminal or run `source ~/.zshrc` (or `source ~/.bashrc`)

**Problem**: Tests fail with `TypeError: unsupported operand type(s) for |`
- **Solution**: You're using Python < 3.10. Upgrade to Python 3.11+ using pyenv

### Alternative: Using Homebrew Python Directly

If you prefer not to use pyenv, you can use Homebrew Python directly:

```bash
# Install Python 3.11
brew install python@3.11

# Create virtual environment with explicit path
/opt/homebrew/bin/python3.11 -m venv .venv

# Activate
source .venv/bin/activate
```

**Note**: pyenv is recommended for better project isolation and automatic version switching.

---

## SIP (SquadOps Improvement Proposal) Workflow

SIPs are governance artifacts that define protocols, standards, and improvements for the SquadOps framework. This document describes how to create, submit, and manage SIPs.

### Directory Structure

SIPs are organized in the `sips/` directory:

```
sips/
  registry.yaml          # Canonical registry of all numbered SIPs
  proposals/             # Unnumbered SIPs (drafts, proposals)
  accepted/              # Accepted SIPs (numbered, approved)
  implemented/           # Implemented SIPs (framework matches specification)
  deprecated/           # Deprecated SIPs (superseded or retired)
```

### SIP Lifecycle

SIPs move through four states:

1. **proposed** - Unnumbered, lives in `sips/proposals/`
2. **accepted** - Numbered, approved by maintainer, lives in `sips/accepted/`
3. **implemented** - Framework functionality matches the SIP specification, lives in `sips/implemented/`
4. **deprecated** - Superseded or retired, but preserved for historical reference, lives in `sips/deprecated/`

**File Naming Convention:**
- When a SIP is accepted, the filename is automatically normalized to `SIP-00NN-Word1-Word2-Word3-Word4.md` format
- Only the first 4 words from the title are used in the filename
- Example: "Cycle Data Layout, Project Registry, and CycleDataStore Contract" → `SIP-0047-Cycle-Data-Layout-Project.md`

### Creating a New SIP

#### For Contributors

1. **Create a draft SIP** in `sips/proposals/`:
   ```bash
   # Install script dependencies (if not already installed)
   pip install -r scripts/dev/requirements.txt
   
   # Generate a ULID for your SIP
   python3 scripts/dev/generate_sip_uid.py
   
   # Create your SIP file (filename can be descriptive, will be normalized to 4 words when accepted)
   touch sips/proposals/SIP-My-Idea.md
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
   original_filename: "SIP-My-Idea.md"
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

2. **Update SIP status** (proposed → accepted):
   ```bash
   python3 scripts/maintainer/update_sip_status.py sips/proposals/SIP-My-Idea.md accepted
   ```

   This script will:
   - Assign the next available SIP number
   - Update the SIP file metadata
   - Move the file from `sips/proposals/` to `sips/accepted/`
   - Rename the file to `SIP-00NN-Word1-Word2-Word3-Word4.md` format (maximum 4 words from title)
   - Update `sips/registry.yaml`

3. **Update SIP status** (accepted → implemented, implemented → deprecated):
   ```bash
   # Mark as implemented
   python3 scripts/maintainer/update_sip_status.py sips/accepted/SIP-0046-Title.md implemented
   
   # Mark as deprecated
   python3 scripts/maintainer/update_sip_status.py sips/implemented/SIP-0021-Title.md deprecated
   ```

   This script will:
   - Update the SIP file metadata (status, updated_at)
   - Move the file to the appropriate lifecycle folder
   - Update `sips/registry.yaml` (status, path, updated_at)

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
- Update SIP status using `update_sip_status.py` (handles all transitions including number assignment)
- Modify the registry

### Unknown or Uncertain SIPs

If you're unsure about a SIP's status or lifecycle state, it should be placed in `sips/proposals/`. The conservative approach ensures no SIPs are lost or misplaced.

### Additional Resources

- See `sips/registry.yaml` for all numbered SIPs
- Review existing SIPs in `sips/` for examples

