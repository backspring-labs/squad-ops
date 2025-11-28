# Implement Strategy Agent (Nat) with PRD Capabilities - Domain-Based Python Architecture

## Overview
Transform the strategy agent (Nat) from placeholder implementation to a real, capability-driven agent modeled after LeadAgent and DevAgent. Implement two new PRD capabilities using a domain-based architecture where capabilities and skills are organized by work domain (product, qa, dev, ops, delivery), not agent role.

**Key Architectural Principles:**
- **Capabilities**: Organized by domain/lifecycle (product, delivery, qa, ops) - "things a user asks an agent to do"
- **Skills**: Organized by domain/work type (product, qa, dev, ops, shared) - reusable building blocks
- **Python Classes**: Keep existing Python class approach, just reorganize by domain
- **Simple & Maintainable**: No YAML overhead, keep type safety and IDE support

## Phase 0: Create Domain-Based Directory Structure

### 0.1 Create Capabilities Domain Structure
**New Structure**:
```
agents/capabilities/
  ├── product/
  │   ├── __init__.py
  │   ├── draft_prd_from_prompt.py      # New for Nat
  │   └── validate_acceptance_criteria.py # New for Nat (EVE can use later)
  ├── delivery/
  │   ├── __init__.py
  │   └── generate_task_plan_from_prd.py # Max uses (future migration)
  ├── qa/
  │   ├── __init__.py
  │   └── (future capabilities)
  ├── ops/
  │   ├── __init__.py
  │   └── (future capabilities)
  └── (existing flat files can stay for now, migrate incrementally)
```

### 0.2 Create Skills Domain Structure
**New Structure**:
```
agents/skills/
  ├── product/
  │   ├── __init__.py
  │   ├── format_prd_prompt.py          # New for PRD drafting (formats prompt for LLM)
  │   └── parse_prd_acceptance_criteria.py # New for validation
  ├── qa/
  │   ├── __init__.py
  │   └── compare_app_output_to_criteria.py # New for validation
  ├── dev/
  │   ├── __init__.py
  │   └── (existing skills can migrate here)
  ├── ops/
  │   ├── __init__.py
  │   └── (future skills)
  └── shared/
      ├── __init__.py
      └── text_match.py                 # New for criteria comparison
```

## Phase 1: Create PRD Template

### 1.1 Create PRD Template File
**File**: `warm-boot/prd/PRD-template.md`

- Create template file based on `PRD-001-HelloSquad.md` structure
- Replace specific HelloSquad content with placeholders:
  - `{{APP_NAME}}` - Application name placeholder
  - `{{PROBLEM}}` - Problem statement placeholder
  - `{{SOLUTION}}` - Solution description placeholder
  - `{{CORE_FEATURES}}` - Core features placeholder (keep structure, replace content)
  - `{{SUCCESS_CRITERIA}}` - Success criteria placeholder
  - `{{TECHNICAL_REQUIREMENTS}}` - Technical requirements placeholder
  - `{{DATA_SOURCES}}` - Data sources placeholder
  - `{{ENV_VARS}}` - Environment variables placeholder
  - `{{DESIGN_GUIDELINES}}` - Design guidelines placeholder
- Keep all section headers, structure, and formatting intact
- This template serves as the input structure for PRD drafting

## Phase 2: Create Product Domain Skills

### 2.1 Create `format_prd_prompt` Skill
**File**: `agents/skills/product/format_prd_prompt.py`

- Create `FormatPRDPrompt` class (Python class)
- Method: `format_prompt(requirement: str, objective: str, app_name: str, template_content: str) -> str`
- Takes PRD template content (passed as parameter) and requirement/objective
- Formats prompt that instructs LLM to:
  - Fill in template placeholders (`{{APP_NAME}}`, `{{PROBLEM}}`, `{{SOLUTION}}`, etc.)
  - Use requirement and objective to generate appropriate content for each section
  - Maintain template structure and formatting
- Returns formatted prompt string for LLM
- Deterministic skill (prompt formatting only, no side effects)

### 2.2 Create `parse_prd_acceptance_criteria` Skill
**File**: `agents/skills/product/parse_prd_acceptance_criteria.py`

- Create `ParsePRDAcceptanceCriteria` class (Python class)
- Method: `extract(prd_content: str) -> List[Dict[str, Any]]`
- Parses PRD markdown to identify:
  - Success Criteria section
  - Functional Requirements with testable outcomes
  - Technical Requirements with measurable metrics
- Returns structured list with:
  - `criterion_id`: Unique identifier
  - `description`: Criterion text
  - `type`: 'functional', 'technical', 'design'
  - `testable`: Boolean indicating if it can be validated against deployed app
- Deterministic skill (parsing logic only, no side effects)

### 2.3 Create `compare_app_output_to_criteria` Skill
**File**: `agents/skills/qa/compare_app_output_to_criteria.py`

- Create `CompareAppOutputToCriteria` class (Python class)
- Method: `compare(app_url: str, criteria_list: List[Dict[str, Any]]) -> Dict[str, Any]`
- Fetches deployed app HTML using `aiohttp` (async HTTP)
- Parses HTML content to extract:
  - Text content (headings, paragraphs, footer)
  - Version information
  - Build information
  - System status indicators
  - API endpoints referenced
- Uses `shared/text_match.py` skill for semantic matching
- Compares each criterion against app content
- Classifies as `met`, `unmet`, or `partial`
- Returns comparison results: `{criteria_met: [], criteria_unmet: [], criteria_partial: []}`
- Not deterministic (requires HTTP fetch)

### 2.4 Create `text_match` Shared Skill
**File**: `agents/skills/shared/text_match.py`

- Create `TextMatch` class (Python class)
- Method: `match(text: str, pattern: str, threshold: float = 0.7) -> Dict[str, Any]`
- Implements semantic text matching for criteria validation
- Can use simple keyword matching for MVP, LLM-based semantic matching later
- Returns:
  - `match_score`: Float (0.0 to 1.0 similarity score)
  - `matched`: Boolean (True if score > threshold)
- Deterministic skill (text processing only)

## Phase 3: Create Product Domain Capabilities

### 3.1 Create `draft_prd_from_prompt` Capability
**File**: `agents/capabilities/product/draft_prd_from_prompt.py`

- Create `DraftPRDFromPrompt` class
- Method: `draft(requirement: str, objective: str, app_name: str) -> Dict[str, Any]`
- Loads PRD template from `warm-boot/prd/PRD-template.md` using `self.agent.read_file()`
- Uses `FormatPRDPrompt` skill (`agents.skills.product.format_prd_prompt`) to format prompt
- Calls LLM (`self.agent.llm_client.complete()`) to generate PRD content by filling template placeholders
- LLM prompt instructs: "Fill in the PRD template structure with content based on the requirement and objective. Replace all {{PLACEHOLDER}} markers with appropriate content."
- Saves PRD to `warm-boot/prd/PRD-XXX-{AppName}.md` format
- Returns:
  - `prd_content`: Generated PRD markdown string
  - `prd_path`: Path where PRD was saved
  - `sections_generated`: List of sections that were filled

### 3.2 Create `validate_acceptance_criteria` Capability
**File**: `agents/capabilities/product/validate_acceptance_criteria.py`

- Create `ValidateAcceptanceCriteria` class
- Method: `validate(prd_path: str, app_url: str = "http://localhost:8080/hello-squad/") -> Dict[str, Any]`
- Loads PRD content from `prd_path` using `self.agent.read_file()`
- Uses `ParsePRDAcceptanceCriteria` skill (`agents.skills.product.parse_prd_acceptance_criteria`) to extract criteria
- Uses `CompareAppOutputToCriteria` skill (`agents.skills.qa.compare_app_output_to_criteria`) to fetch app HTML and compare
- Calculates validation score (percentage of criteria met: `len(criteria_met) / len(all_criteria)`)
- Returns:
  - `criteria_met`: List of criteria that match
  - `criteria_unmet`: List of criteria that don't match
  - `criteria_partial`: List of criteria partially met
  - `validation_score`: Float (0.0-1.0) percentage of criteria met
  - `details`: Dict with detailed comparison results

## Phase 4: Update Capability Infrastructure

### 4.1 Update Capability Loader
**File**: `agents/capabilities/loader.py`

- Update `CAPABILITY_MAP` to include new capabilities:
  - `'product.draft_prd_from_prompt': ('agents.capabilities.product.draft_prd_from_prompt', 'DraftPRDFromPrompt', 'draft')`
  - `'product.validate_acceptance_criteria': ('agents.capabilities.product.validate_acceptance_criteria', 'ValidateAcceptanceCriteria', 'validate')`
- Add to `CALLING_CONVENTIONS` under appropriate convention (likely `payload_as_is` for both)
- Update loader to support domain-based imports (scan `product/`, `qa/`, `delivery/`, `ops/` directories if needed)

### 4.2 Update Capability Catalog
**File**: `agents/capabilities/catalog.yaml`

- Add entries for:
```yaml
- name: product.draft_prd_from_prompt
  capability_version: 1.0.0
  description: "Draft PRD from requirement/objective prompt using template structure"
  result:
    keys:
      - prd_content
      - prd_path
      - sections_generated

- name: product.validate_acceptance_criteria
  capability_version: 1.0.0
  description: "Validate PRD acceptance criteria against deployed application"
  result:
    keys:
      - criteria_met
      - criteria_unmet
      - criteria_partial
      - validation_score
      - details
```

### 4.3 Update Capability Bindings
**File**: `agents/capability_bindings.yaml`

- Add:
  - `product.draft_prd_from_prompt: nat`
  - `product.validate_acceptance_criteria: nat`
- Note: EVE can use `product.validate_acceptance_criteria` later (as noted in comments)
- Remove or update placeholder bindings:
  - `strategy.market_analysis: nat` → Remove (replaced)
  - `strategy.product_planning: nat` → Remove (replaced)

### 4.4 Update Skills Registry
**File**: `agents/skills/registry.yaml`

- Add entries for new skills:
```yaml
- name: product.format_prd_prompt
  skill_version: 1.0.0
  description: "Format prompt for LLM to generate PRD content from requirement/objective using template"
  domain: product
  determinism: "Deterministic - prompt formatting only"

- name: product.parse_prd_acceptance_criteria
  skill_version: 1.0.0
  description: "Extract acceptance criteria from PRD content"
  domain: product
  determinism: "Deterministic - parsing logic only"

- name: qa.compare_app_output_to_criteria
  skill_version: 1.0.0
  description: "Fetch deployed app HTML, parse content, and compare against acceptance criteria"
  domain: qa
  determinism: "Non-deterministic - requires HTTP fetch"

- name: shared.text_match
  skill_version: 1.0.0
  description: "Semantic text matching for criteria validation"
  domain: shared
  determinism: "Deterministic - text processing only"
```

## Phase 5: Refactor Strat Agent

### 5.1 Clean Up Strat Agent
**File**: `agents/roles/strat/agent.py`

- Remove placeholder methods:
  - `_handle_market_analysis()` (replaced by `product.draft_prd_from_prompt`)
  - `_handle_product_planning()` (replaced by `product.validate_acceptance_criteria`)
  - `process_task()` (placeholder implementation with mock logic)
  - `generate_hypotheses()`, `evaluate_hypotheses()`, `create_product_strategy()`, `validate_strategy()`
  - `handle_strategy_request()`, `handle_opportunity_alert()`, `handle_hypothesis_query()`
- Remove unused instance variables:
  - `self.priority_queue`, `self.opportunity_cache`, `self.hypothesis_space`

### 5.2 Model After Lead/Dev Agents
**File**: `agents/roles/strat/agent.py`

- Update `__init__()`:
  - Fix `base_path` calculation for Docker: `Path(__file__).parent` (like dev agent)
  - Remove unused instance variables
  - Keep schema validator initialization
- Update `handle_agent_request()`:
  - Remove hardcoded `if action == "strategy.market_analysis"` and `elif action == "strategy.product_planning"` checks
  - Use generic capability routing via `self.capability_loader.prepare_capability_args()` and `self.capability_loader.execute()`
  - Follow pattern from `LeadAgent.handle_agent_request()` (lines 67-150)
- Add `process_task()` method:
  - Use generic routing via `self.capability_loader.get_capability_for_task()`
  - Follow pattern from `DevAgent.process_task()` (lines 124-200)
- Update `handle_message()`:
  - Keep generic message handling, remove strategy-specific handlers

### 5.3 Update Agent Requirements
**File**: `agents/roles/strat/requirements.txt`

- Ensure `aiohttp` is included for HTTP requests to deployed app
- Ensure `beautifulsoup4` or `lxml` is included for HTML parsing

## Phase 6: Testing

### 6.1 Unit Tests
**File**: `tests/unit/test_draft_prd_from_prompt.py`

- Test PRD generation from requirement/objective
- Test template loading and placeholder replacement
- Test file path generation
- Test skill integration (`FormatPRDPrompt`)

**File**: `tests/unit/test_validate_acceptance_criteria.py`

- Test PRD parsing and criteria extraction (`ParsePRDAcceptanceCriteria` skill)
- Test app content parsing (`CompareAppOutputToCriteria` skill)
- Test criteria comparison logic (`TextMatch` skill)
- Test validation scoring
- Mock HTTP requests for app fetching

**File**: `tests/unit/test_strat_agent.py`

- Test generic capability routing
- Test `handle_agent_request()` with new capabilities
- Test `process_task()` with PRD-related tasks
- Remove tests for deleted placeholder methods

**File**: `tests/unit/test_product_skills.py`

- Test `FormatPRDPrompt.format_prompt()`
- Test `ParsePRDAcceptanceCriteria.extract()`
- Test `TextMatch.match()`

**File**: `tests/unit/test_qa_skills.py`

- Test `CompareAppOutputToCriteria.compare()` with mocked HTTP responses

### 6.2 Integration Tests
- Test end-to-end PRD drafting workflow
- Test end-to-end acceptance criteria validation workflow
- Verify deployed hello-squad app can be accessed and parsed
- Test domain-based capability/skill imports

## Phase 7: Documentation

### 7.1 Update Agent Documentation
- Document Nat's new capabilities (`product.draft_prd_from_prompt`, `product.validate_acceptance_criteria`)
- Update agent role description
- Add examples of PRD drafting and validation usage
- Document domain-based architecture approach

## Implementation Notes

- **Domain-Based Organization**: Capabilities and skills organized by work domain (product, qa, dev, ops, delivery), not agent role
- **Python Classes**: Keep existing Python class approach - simple, maintainable, type-safe
- **Cross-Domain Usage**: `product.validate_acceptance_criteria` can be used by Nat now, EVE later
- **Shared Skills**: `shared/text_match.py` provides cross-cutting functionality for criteria comparison
- Follow SIP-040 principles: agents are thin routing layers, capabilities contain business logic
- Skills are deterministic, no side effects (except HTTP fetch in `qa/compare_app_output_to_criteria`)
- Use LLM client from `self.agent.llm_client` for PRD generation
- Use `aiohttp` for fetching deployed app content (async)
- PRD template (`PRD-template.md`) provides structure, LLM fills content based on requirement/objective
- Validation handles partial matches using semantic matching via `shared/text_match.py`
- Default hello-squad app URL: `http://localhost:8080/hello-squad/`
- **Incremental Migration**: Existing flat capability/skill files can stay, migrate to domain structure incrementally


