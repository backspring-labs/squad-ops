# Test Case: HelloSquad (TC-001)

**PID:** PID-001  
**PRD:** PRD-001-HelloSquad.md  
**UC:** docs/framework/use-cases/UC-001-HelloSquad.md  
**Status:** Active  

## Test Case Overview

**Objective:** Validate HelloSquad application functionality and agent collaboration  
**Test Type:** Integration Testing  
**Priority:** High  

## Test Scenarios

### TC-API-001: API Endpoint Validation
**Description:** Verify `/api/hello` endpoint returns correct JSON response  
**Steps:**
1. Send GET request to `/api/hello`
2. Verify response status is 200
3. Verify response contains expected JSON structure
4. Verify response includes agent collaboration metadata

**Expected Result:**
```json
{
  "status": "Hello Squad is running!",
  "agents": ["Max (LeadAgent)", "Neo (DevAgent)"],
  "names_count": 0,
  "timestamp": "2025-10-05T00:37:38.809Z"
}
```

### TC-API-002: API Method Validation
**Description:** Verify incorrect HTTP methods return proper error  
**Steps:**
1. Send POST request to `/api/hello`
2. Verify response status is 405 (Method Not Allowed)

**Expected Result:** HTTP 405 with appropriate error message

### TC-HTML-001: HTML Page Rendering
**Description:** Verify `/hello` page renders correctly  
**Steps:**
1. Navigate to `/hello` endpoint
2. Verify page loads successfully
3. Verify page contains greeting message
4. Verify page shows agent collaboration info

**Expected Result:** HTML page displays "Hello, Squad!" with agent info

### TC-HTML-002: API Integration
**Description:** Verify HTML page fetches data from API  
**Steps:**
1. Load `/hello` page
2. Verify JavaScript fetches data from `/api/hello`
3. Verify page updates with API response
4. Verify error handling if API fails

**Expected Result:** Page dynamically updates with API data

### TC-INT-001: Agent Collaboration
**Description:** Verify end-to-end agent collaboration workflow  
**Steps:**
1. Verify Max (LeadAgent) is online
2. Verify Neo (DevAgent) is online
3. Verify agents can communicate via RabbitMQ
4. Verify task assignment and execution logging
5. Verify application deployment success

**Expected Result:** Complete agent collaboration cycle successful

## Test Data

- **Base URL:** http://localhost:3000
- **API Endpoint:** /api/hello
- **HTML Endpoint:** /hello
- **Expected Agents:** Max (LeadAgent), Neo (DevAgent)

## Test Environment

- **Platform:** Docker containers
- **Infrastructure:** RabbitMQ, PostgreSQL, Redis
- **LLM Mode:** Real (Ollama local models)

## Pass/Fail Criteria

**Pass:** All test scenarios execute successfully  
**Fail:** Any test scenario fails or returns unexpected results

## Test Execution

- **Automated:** API tests via curl/HTTP requests
- **Manual:** HTML page validation
- **Integration:** Agent collaboration verification

## Related Artifacts

- WarmBoot Run: run-001-summary.md
- Business Process: docs/framework/business-processes/BP-001-HelloSquad.md
