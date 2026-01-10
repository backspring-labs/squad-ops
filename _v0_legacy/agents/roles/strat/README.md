# Nat - Strategy Agent

## Overview

Nat is the Strategy Agent (Strat role) in the SquadOps framework, specializing in product strategy and PRD (Product Requirements Document) capabilities. Nat uses abductive reasoning to explore product opportunities and validate requirements.

## Capabilities

### product.draft_prd_from_prompt

Drafts a Product Requirements Document from a requirement/objective prompt using a template structure.

**Usage:**
```python
{
    "action": "product.draft_prd_from_prompt",
    "payload": {
        "requirement": "Build a todo application",
        "objective": "Help users manage tasks efficiently",
        "app_name": "TodoApp"
    }
}
```

**Returns:**
- `prd_content`: Generated PRD markdown string
- `prd_path`: Path where PRD was saved (e.g., `warm-boot/prd/PRD-002-TodoApp.md`)
- `sections_generated`: List of sections that were filled

**Example:**
```json
{
    "prd_content": "# PRD - TodoApp\n...",
    "prd_path": "warm-boot/prd/PRD-002-TodoApp.md",
    "sections_generated": ["1. Executive Summary", "2. Functional Requirements", ...]
}
```

### product.validate_acceptance_criteria

Validates PRD acceptance criteria against a deployed application by fetching the app HTML and comparing it against the criteria.

**Usage:**
```python
{
    "action": "product.validate_acceptance_criteria",
    "payload": {
        "prd_path": "warm-boot/prd/PRD-002-TodoApp.md",
        "app_url": "http://localhost:8080/todo-app/"  // optional, defaults to hello-squad
    }
}
```

**Returns:**
- `criteria_met`: List of criteria that match the deployed app
- `criteria_unmet`: List of criteria that don't match
- `criteria_partial`: List of criteria partially met
- `validation_score`: Float (0.0-1.0) percentage of criteria met
- `details`: Dictionary with validation details

**Example:**
```json
{
    "criteria_met": [
        {"criterion_id": "criteria_001", "description": "Application loads correctly", ...}
    ],
    "criteria_unmet": [],
    "criteria_partial": [],
    "validation_score": 0.95,
    "details": {
        "total_criteria": 5,
        "testable_criteria": 5,
        "app_url": "http://localhost:8080/todo-app/"
    }
}
```

### comms.chat

Handles interactive chat messages from the console. Nat can respond to questions about product strategy, PRD drafting, and validation.

**Usage:**
```python
{
    "action": "comms.chat",
    "payload": {
        "message": "What capabilities do you have?",
        "session_id": "console-session-123"
    }
}
```

## Architecture

Nat follows the domain-based architecture pattern where:

- **Capabilities** are organized by work domain (product, delivery, qa, ops)
- **Skills** are reusable building blocks organized by domain
- **Agent** is a thin routing layer with no business logic

### Domain Organization

- **Product Domain**: `product.draft_prd_from_prompt`, `product.validate_acceptance_criteria`
- **Skills Used**:
  - `product.format_prd_prompt` - Formats LLM prompts for PRD generation
  - `product.parse_prd_acceptance_criteria` - Extracts criteria from PRD content
  - `qa.compare_app_output_to_criteria` - Compares deployed app against criteria
  - `shared.text_match` - Semantic text matching for validation

## Configuration

Nat is configured in:
- `agents/instances/instances.yaml` - Agent instance registration (id: `nat`)
- `agents/roles/strat/config.yaml` - Agent capabilities and constraints
- `agents/capability_bindings.yaml` - Capability-to-agent mappings

## Examples

### Drafting a PRD

```bash
# Via console chat
chat nat
> Draft a PRD for a fitness tracking app that helps users monitor workouts

# Via AgentRequest
{
    "action": "product.draft_prd_from_prompt",
    "payload": {
        "requirement": "Build a fitness tracking app",
        "objective": "Help users monitor workouts and track progress",
        "app_name": "FitnessTracker"
    }
}
```

### Validating Acceptance Criteria

```bash
# Via console chat
chat nat
> Validate the acceptance criteria for PRD-002-TodoApp.md against the deployed app

# Via AgentRequest
{
    "action": "product.validate_acceptance_criteria",
    "payload": {
        "prd_path": "warm-boot/prd/PRD-002-TodoApp.md",
        "app_url": "http://localhost:8080/todo-app/"
    }
}
```

## Cross-Domain Usage

The `product.validate_acceptance_criteria` capability can be used by other agents:
- **EVE (QA Agent)** can use it for automated acceptance testing
- **Max (Lead Agent)** can use it for validation during WarmBoot runs

This demonstrates the domain-based architecture where capabilities are organized by work domain, not agent role.

