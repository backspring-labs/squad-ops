# WarmBoot Run-004 Requirements: 100% Real Agent Implementation

**Run ID:** run-004  
**PID:** PID-001 (HelloSquad enhancement)  
**PRD:** PRD-001-HelloSquad.md (enhancement)  
**Date:** 2025-10-05  
**Status:** Ready for 100% REAL agent execution  

## Enhancement Overview

Update the HelloSquad application footer to display WarmBoot run-004 through **100% real agent collaboration** - no AI assistant intervention. This will be the first WarmBoot run where agents handle all aspects: communication, file modification, implementation, and deployment.

## Requirements

### Functional Requirements

1. **Footer Display Update**
   - Change footer from "WarmBoot: run-003" to "WarmBoot: run-004"
   - Maintain existing version format: "Version: 1.1.0 | WarmBoot: run-004 | Built: 10/5/2025"
   - Ensure dynamic loading from API continues to work

2. **API Endpoint Update**
   - Update `/api/version` endpoint to return `"run_id": "run-004"`
   - Maintain all other version metadata
   - Ensure backward compatibility

3. **100% Real Agent Collaboration**
   - Max creates task and delegates to Neo via RabbitMQ
   - Neo receives task, processes with real LLM, implements changes
   - Neo modifies files directly using new file modification capabilities
   - Neo reports completion back to Max via RabbitMQ
   - Full task tracking in PostgreSQL
   - **NO AI ASSISTANT INTERVENTION**

### Technical Requirements

1. **Backend Changes (by Neo)**
   - Update server environment variables for run-004
   - Modify Docker build process to inject run-004
   - Ensure API returns correct run_id

2. **Frontend Changes (by Neo)**
   - Footer automatically updates when API changes
   - No frontend code changes needed (already dynamic)

3. **Build Integration (by Neo)**
   - Update Docker build args for run-004
   - Capture new git hash and timestamp
   - Deploy updated application

## Acceptance Criteria

- ✅ Footer displays "Version: 1.1.0 | WarmBoot: run-004 | Built: 10/5/2025"
- ✅ `/api/version` returns `"run_id": "run-004"`
- ✅ Real agent communication via RabbitMQ
- ✅ Task completion tracked in PostgreSQL
- ✅ All existing functionality preserved
- ✅ Application deployed and accessible
- ✅ **100% agent work - NO AI assistant intervention**

## Agent Collaboration Flow

1. **Max (LeadAgent)**:
   - Creates task assignment for footer update
   - Sends task to Neo via RabbitMQ
   - Monitors task completion
   - Verifies implementation

2. **Neo (DevAgent)**:
   - Receives task assignment via RabbitMQ
   - Processes task with real LLM
   - **Uses new file modification capabilities**
   - **Implements changes directly**
   - **Handles deployment**
   - Reports completion to Max

3. **Infrastructure**:
   - RabbitMQ message passing
   - PostgreSQL task tracking
   - Docker deployment
   - Health monitoring

## Success Metrics

- Real agent communication established
- Task successfully delegated and completed
- Footer updated to show run-004
- All tests passing
- Complete audit trail maintained
- **100% agent implementation achieved**

## Deliverables

- Updated HelloSquad application with run-004 footer
- Real agent collaboration demonstration
- Run-004 documentation and logs
- Git tag: `v0.4-warmboot-004`
- Complete task tracking in database
- **Proof of 100% real agent work**
