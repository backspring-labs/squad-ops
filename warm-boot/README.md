# WarmBoot Applications & Runs

This directory contains applications built by AI agents through WarmBoot runs and their associated run history.

## Directory Structure

```
warm-boot/
├── apps/                    # Active applications built by agents
│   └── [app-name]/         # Individual application directories
├── runs/                   # WarmBoot run history and documentation
│   ├── run-001/           # Individual run directories
│   │   ├── run-001-summary.md
│   │   ├── run-001-logs.json
│   │   └── release_manifest.yaml
│   ├── run-002/
│   │   ├── run-002-requirements.md
│   │   ├── run-002-summary.md
│   │   ├── run-002-logs.json
│   │   └── release_manifest.yaml
│   ├── run-005/
│   │   ├── run-005-summary.md
│   │   └── run-005-logs.json
│   └── ...
├── prd/                    # Product Requirements Documents
│   └── PRD-001-HelloSquad.md  # Hello Squad PRD
├── business-processes/     # Business process documentation
│   └── BP-001-HelloSquad.md   # Hello Squad business process
├── use-cases/             # Use case documentation
│   └── UC-001-HelloSquad.md   # Hello Squad use cases
├── testing/               # Testing documentation
│   └── test_cases/        # Test case documentation
│       └── TC-001-HelloSquad.md  # Hello Squad test cases
├── archive/                # Archived applications and versions
│   └── hello-squad-v0.1.5/    # Archived Hello Squad v0.1.5
└── README.md              # This file
```

## Current Status

### Active Applications
- **None** - All applications archived for fresh start

### Archived Applications
- **Hello Squad v0.1.5** - Archived after WarmBoot runs 001-005
  - Location: `archive/hello-squad-v0.1.5/`
  - Final Version: v0.1.5
  - Status: 100% real agent work achieved
  - Replaced by: Fresh Hello Squad v0.2.0 (from-scratch build)

## WarmBoot Run History

### Run-001: Initial Hello Squad Build
- Built basic Hello Squad application
- Simple API and HTML page
- Basic agent collaboration

### Run-002: Version Tracking Enhancement
- Added version tracking capabilities
- Enhanced footer display
- Improved agent coordination

### Run-003: Real Agent Work
- First real RabbitMQ communication
- Actual file modifications by agents
- Real LLM responses via Ollama

### Run-004: File Operations Breakthrough
- Agents gained file modification capabilities
- Real implementation of features
- 80% real agent work achieved

### Run-005: 100% Real Agent Work
- **BREAKTHROUGH**: 100% real agent work achieved
- Comprehensive feature implementation
- Backend APIs, frontend components, database schema
- Integration testing and documentation
- **Paradigm shift** from simulation to real autonomous collaboration

## Next Steps

### Fresh Start Approach
- **Hello Squad v0.2.0**: Build from scratch using standard PRD
- **User-focused requirements**: Business value over technical implementation
- **Agent translation**: Max translates business requirements into technical tasks
- **Pure creation**: Test agents' ability to build complete applications from nothing

### Framework Enhancements
- **Archive system**: Proper archiving of previous versions
- **Clean slate**: Fresh apps directory for new builds
- **Version management**: Clear versioning and traceability
- **Documentation**: Comprehensive run history and achievements

## Usage

### Getting the Next Run ID

The next sequential run ID is tracked in the database and can be retrieved via:

```bash
# Via API endpoint
curl http://localhost:8000/warmboot/next-run-id

# Returns: {"run_id": "run-056"}
```

The WarmBoot submission form automatically populates this field.

### Starting a New WarmBoot Run

#### For From-Scratch Builds
1. **Simple Git-based approach**:
   ```bash
   # Archive current work
   git tag v0.1.5-hello-squad-archived
   git add . && git commit -m "Archive Hello Squad v0.1.5"
   
   # Clean slate for fresh build
   rm -rf warm-boot/apps/hello-squad
   mkdir -p warm-boot/apps/hello-squad
   ```

2. **Agent-managed approach** (Recommended):
   - Let **Max (Lead Agent)** read the PRD from `warm-boot/prd/`
   - **Max** creates tasks for **Neo** to archive old version and build new
   - **Neo** handles archiving, building, and deployment
   - **Agents** manage the entire lifecycle

#### For Incremental Builds
1. Continue with existing application
2. Let agents enhance and modify existing code
3. No archiving required

### Archiving Applications
**Agent-managed archiving** (Recommended):
- **Neo (Dev Agent)** handles archiving as part of from-scratch build
- **Agents** create archive documentation
- **Agents** update docker-compose.yml and manage containers
- **Agents** ensure proper versioning and traceability

---

**Note**: This directory structure supports both incremental enhancement and fresh start approaches for WarmBoot runs, providing flexibility for different testing scenarios and development strategies.