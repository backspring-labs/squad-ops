# Adding a New Agent: Lessons Learned

**Date:** November 16, 2025  
**Agent:** Nat (Strategy Agent)  
**Context:** Implementation of first fully capability-driven agent using domain-based architecture  
**Status:** ✅ Complete - Production-ready

---

## Executive Summary

This document captures all lessons learned from adding Nat (the Strategy Agent) to SquadOps. The implementation revealed critical patterns, common pitfalls, and best practices for adding new agents to the system. These lessons should be followed for all future agent implementations.

---

## 📋 Pre-Implementation Checklist

### 1. Agent Architecture & Code Structure

#### ✅ Remove All Placeholder Code
- **Critical:** Agents must contain **NO dummy code** for things that should be externalized as skills and capabilities
- **Pattern:** Agents are thin routing layers (SIP-040) - all business logic goes in capabilities/skills
- **Action Items:**
  - Remove placeholder methods (e.g., `_handle_market_analysis`, `_handle_product_planning`)
  - Remove hardcoded return values
  - Remove instance variables for capabilities (use `CapabilityLoader` instead)

#### ✅ Implement Generic Capability Routing
- **Pattern:** Use `CapabilityLoader` for all capability execution
- **Implementation:**
  ```python
  # agents/roles/<role>/agent.py
  async def handle_agent_request(self, request: AgentRequest) -> AgentResponse:
      # Validate request
      is_valid, error_msg = self.validator.validate_request(request)
      if not is_valid:
          return AgentResponse.failure(...)
      
      # Validate constraints
      is_valid, error_msg = self._validate_constraints(request)
      if not is_valid:
          return AgentResponse.failure(...)
      
      # Route to capability via Loader
      action = request.action
      args = self.capability_loader.prepare_capability_args(action, request.payload, request.metadata)
      result = await self.capability_loader.execute(action, self, *args)
      
      return AgentResponse.success(result=result, ...)
  ```

#### ✅ Use Unified Path Resolver
- **Critical:** Always use `PathResolver.get_base_path()` instead of manual path detection
- **Why:** Ensures consistent path resolution in both local development and Docker containers
- **Implementation:**
  ```python
  from agents.utils.path_resolver import PathResolver
  base_path = PathResolver.get_base_path()
  self.validator = SchemaValidator(base_path)
  ```

### 2. Capability Configuration

#### ✅ Register Capabilities in Multiple Places
- **`agents/capabilities/catalog.yaml`:** Add capability definition with version, description, result keys
- **`agents/capability_bindings.yaml`:** Bind capability to agent ID
- **`agents/roles/<role>/config.yaml`:** List capability in `implements` section with `min_version`

**Example:**
```yaml
# agents/capabilities/catalog.yaml
- name: product.draft_prd_from_prompt
  capability_version: 1.0.0
  description: "Draft a PRD from a user prompt"
  result:
    keys:
      - prd_path
      - prd_content

# agents/capability_bindings.yaml
bindings:
  product.draft_prd_from_prompt: nat

# agents/roles/strat/config.yaml
implements:
  - capability: product.draft_prd_from_prompt
    min_version: 1.0.0
```

#### ✅ Support Console Chat (`comms.chat`)
- **Critical:** All agents must support `comms.chat` for health-check console interaction
- **Steps:**
  1. Add `comms.chat` to `agents/capabilities/catalog.yaml` (if not already present)
  2. Bind `comms.chat` to agent in `agents/capability_bindings.yaml`
  3. Add `comms.chat` to agent's `config.yaml` `implements` section
  4. Ensure `ChatHandler` is registered in `agents/capabilities/loader.py` `CAPABILITY_MAP`

**Common Mistake:** Forgetting to add `comms.chat` to `config.yaml` even though it's bound in `capability_bindings.yaml` - **both are required!**

### 3. Memory Support

#### ✅ Initialize Memory Providers
- **Pattern:** Memory providers are initialized automatically by `BaseAgent._initialize_memory_providers()`
- **Dependencies:** Add to `agents/roles/<role>/requirements.txt`:
  ```
  lancedb==0.8.2
  sentence-transformers>=2.7.0
  pyarrow>=14.0.0
  pandas>=2.0.0
  ```
- **Verification:** Check logs for `"Memory providers initialized"` and `"Created LanceDB table: <agent>_memories"`

#### ✅ Record Memories in Capabilities
- **Pattern:** Capabilities should record memories for their actions
- **Implementation:**
  ```python
  # In capability methods
  await self.agent.record_memory(
      kind="prd_drafted",
      payload={"prd_path": prd_path, "prompt": prompt},
      ns="role",  # Agent-level memory
      importance=0.7
  )
  ```

### 4. Model Configuration

#### ✅ Configure Model in `config.yaml` (Single Source of Truth)
- **Pattern:** Model configuration lives in `agents/roles/<role>/config.yaml` `defaults.model`
- **Format:** `ollama:<model-name>` (e.g., `ollama:llama3.1:8b-instruct-q4_K_M`)
- **Critical:** Do NOT use `AGENT_MODEL` environment variable in `docker-compose.yml` - it's deprecated
- **Implementation:**
  ```yaml
  # agents/roles/<role>/config.yaml
  defaults:
    model: ollama:llama3.1:8b-instruct-q4_K_M
  ```

#### ✅ Download Model in Ollama
- **Action:** Pull model before testing: `ollama pull <model-name>`
- **Verification:** Check model exists: `ollama list | grep <model-name>`
- **Model Selection:** Choose appropriate model size for hardware:
  - Large models (e.g., `mixtral:8x7b`) may timeout on limited hardware
  - Smaller models (e.g., `llama3.1:8b-instruct-q4_K_M`) are faster and more reliable

#### ✅ Model Name Format
- **Ollama Format:** Uses colons for model variants (e.g., `llama3.1:8b-instruct-q4_K_M`)
- **Config Format:** `ollama:<ollama-model-name>` (e.g., `ollama:llama3.1:8b-instruct-q4_K_M`)
- **Common Mistake:** Using hyphens instead of colons (e.g., `mixtral-8x7b` ❌ vs `mixtral:8x7b` ✅)

### 5. Docker Configuration

#### ✅ Build-Time Assembly Approach
- **Pattern:** Use build script to assemble container-ready packages, then multi-stage Dockerfiles
- **Benefits:**
  - ✅ No more forgotten files - Build script determines dependencies automatically
  - ✅ Deterministic builds - Same input = same output
  - ✅ Testable - Can inspect `dist/agents/{role}/` before building
  - ✅ Standard Docker patterns - Multi-stage builds with layer caching
  - ✅ Cloud compatible - Works with ECR/GCR/ACR
  - ✅ Edge ready - Minimal final image size

#### ✅ Building Agent Packages
- **Step 1:** Build agent package using build script:
  ```bash
  python scripts/build_agent.py <role>
  ```
- **Step 2:** Verify package contents:
  ```bash
  ls -la dist/agents/<role>/
  ```
- **Step 3:** Build Docker image (build script runs automatically in Dockerfile):
  ```bash
  docker build -t squadops/<agent>:latest --build-arg AGENT_ROLE=<role> -f agents/roles/<role>/Dockerfile .
  ```

#### ✅ Dockerfile Pattern (Multi-Stage Build)
- **Standard Pattern:**
  ```dockerfile
  # Stage 1: Build agent package
  FROM python:3.11-slim as builder
  WORKDIR /build
  
  # Copy source code
  COPY agents/ ./agents/
  COPY scripts/build_agent.py ./scripts/
  COPY config/ ./config/
  
  # Build agent package
  ARG AGENT_ROLE=qa
  RUN python scripts/build_agent.py ${AGENT_ROLE}
  
  # Stage 2: Runtime image
  FROM python:3.11-slim
  WORKDIR /app
  ENV SQUADOPS_BASE_PATH=/app
  
  # Copy assembled agent package
  COPY --from=builder /build/dist/agents/${AGENT_ROLE}/ ./
  
  # Install dependencies
  RUN pip install --no-cache-dir -r requirements.txt
  
  # Create required directories
  RUN mkdir -p /app/logs /app/data/memory_db
  
  CMD ["python", "agent.py"]
  ```

#### ✅ Special Cases
- **Dev Role:** Add Docker CLI installation in Stage 2 (before pip install):
  ```dockerfile
  RUN apt-get update && apt-get install -y docker-ce-cli
  ```
- **Lead Role:** May need `gcc` and `python3-dev` for some dependencies

#### ✅ Build Script Dependencies
- **Automatic Resolution:** Build script reads `config.yaml` and resolves:
  - Required capabilities (from `implements` list)
  - Required skills (role-specific + shared)
  - Shared infrastructure (always included)
  - Config files (capability_bindings.yaml, registry.yaml, etc.)
- **No Manual COPY Statements:** Build script handles all file copying
- **Verification:** If container missing files, check `dist/agents/{role}/` to see what was assembled

#### ✅ Verify Path Resolution in Container
- **Test:** Check logs for path-related errors (e.g., `catalog.yaml not found`)
- **Common Issues:**
  - Missing `ENV SQUADOPS_BASE_PATH=/app` in Dockerfile
  - Incorrect COPY paths
  - Missing `config.yaml` copy

#### ✅ Agent Metadata Artifacts
- **Pattern:** Build script automatically generates `manifest.json` and `agent_info.json` metadata artifacts
- **manifest.json:** Build artifact metadata (what was built)
  - Includes: `manifest_version`, `role`, `capabilities`, `skills`, `shared_modules`, `resolver_graph`, `files_included`, `build_hash`, `git_commit`, `build_time_utc`, `squadops_version`
  - **Purpose:** Deterministic build tracking, debugging, RCA
  - **Location:** `dist/agents/{role}/manifest.json` (build-time), `/app/manifest.json` (runtime)
- **agent_info.json:** Runtime identity metadata (who is running)
  - Includes: `agent_info_version`, `role`, `agent_id`, `capabilities`, `skills`, `build_hash`, `container_hash`, `runtime_env`, `startup_time_utc`, `agent_entrypoint`
  - **Purpose:** Runtime introspection, observability, debugging container drift
  - **Location:** `dist/agents/{role}/agent_info.json` (build-time), `/app/agent_info.json` (runtime)
- **Schema Versioning:** Both artifacts include mandatory version fields (`manifest_version: "1.0"`, `agent_info_version: "1.0"`) for future compatibility
- **Build Hash:** SHA256 hash of all files in `dist` directory (excluding manifest files) - ensures deterministic builds
  - Propagates through both `manifest.json` and `agent_info.json`
  - Can be used as Docker LABEL via `--build-arg BUILD_HASH=<hash>` in CI/CD
- **Structured Logging:** BaseAgent logs `agent_runtime_identity` event with agent_info for observability tools
- **Docker LABEL:** Dockerfiles support `LABEL squadops.build_hash="${BUILD_HASH}"` for registry-level introspection
  - CI/CD should extract build_hash from `manifest.json` and pass as `--build-arg BUILD_HASH=<hash>`
  - Defaults to "unknown" if not provided
- **Verification:** Check logs for `"Agent runtime identity:"` JSON output after agent startup

### 6. Agent Registration

#### ✅ Register in `instances.yaml`
- **File:** `agents/instances/instances.yaml`
- **Required Fields:**
  ```yaml
  - id: nat
    display_name: Nat
    role: strat
    model: llama3.1:8b-instruct-q4_K_M
    enabled: true
    description: "Strategy agent for product planning and PRD drafting"
  ```
- **Verification:** Agent appears in health-check app agent listing

#### ✅ Verify Health-Check Visibility
- **Action:** Rebuild health-check after updating `instances.yaml`: `docker-compose build health-check && docker-compose up -d health-check`
- **Verification:** Check health-check dashboard shows new agent

### 7. Dependencies

#### ✅ Add All Required Dependencies
- **File:** `agents/roles/<role>/requirements.txt`
- **Common Dependencies:**
  ```
  # Core dependencies (always needed)
  aiohttp>=3.9.0
  aiofiles>=23.2.1
  pyyaml>=6.0
  jsonschema>=4.20.0
  
  # Memory support
  lancedb==0.8.2
  sentence-transformers>=2.7.0
  pyarrow>=14.0.0
  pandas>=2.0.0
  
  # OpenTelemetry packages (required for telemetry)
  opentelemetry-api>=1.22.0
  opentelemetry-sdk>=1.22.0
  opentelemetry-instrumentation
  opentelemetry-exporter-otlp-proto-grpc>=1.22.0
  opentelemetry-exporter-prometheus
  opentelemetry-semantic-conventions
  
  # Domain-specific (add as needed)
  beautifulsoup4>=4.12.0  # For HTML parsing
  ```
- **Critical:** OpenTelemetry packages are **required** - missing them causes `'NoneType' object has no attribute 'create'` errors during telemetry initialization
- **Verification:** Check Docker logs for `ModuleNotFoundError` or OpenTelemetry initialization errors - indicates missing dependencies

### 8. Repository Constraints

#### ✅ Configure `repo_allow` Constraint
- **Pattern:** Define allowed repositories in `config.yaml`
- **Implementation:**
  ```yaml
  constraints:
    repo_allow: ["squad_ops/*"]
  ```
- **Critical:** Chat messages don't have `repo`/`project` fields - ensure `_validate_constraints()` only validates when these fields are present
- **Fix:** In `agents/base_agent.py`:
  ```python
  def _validate_constraints(self, request: AgentRequest) -> Tuple[bool, Optional[str]]:
      # ... existing code ...
      
      # Only validate repo_allow if repo/project is present
      if repo_allow and (payload_repo or payload_project):
          # Validate repository constraint
          ...
  ```

### 9. Testing

#### ✅ Unit Tests
- **Pattern:** Test agent's `handle_agent_request()` with mocked capabilities
- **Key Mocks:**
  - `agent.validator` - SchemaValidator instance
  - `agent._validate_constraints` - Constraint validation
  - `agent.capability_loader.execute()` - Capability execution
  - `agent.llm_client` - LLM client (if needed)

#### ✅ Integration Tests
- **Pattern:** Test end-to-end capability execution
- **Coverage:** Include delegation cases if agent delegates to other agents

#### ✅ Model Configuration Test
- **File:** `tests/integration/test_agent_model_validation.py`
- **Purpose:** Verify configured model exists in Ollama and is functional
- **Action:** Add agent to test if it's a lead/dev/strat agent

### 10. Version Management

#### ✅ Update Agent Version
- **Tool:** Use `version_cli.py` - **NEVER manually edit `config/version.py`**
- **Command:** `python version_cli.py update <agent-id> <version> [notes]`
- **Example:** `python version_cli.py update nat 0.6.3 "Added PRD capabilities"`

---

## 🚨 Common Pitfalls & Solutions

### Pitfall #1: Path Resolution Errors
**Symptom:** `[Errno 2] No such file or directory: '/agents/capabilities/catalog.yaml'`

**Root Cause:** Manual path detection fails in Docker containers

**Solution:** Use `PathResolver.get_base_path()` everywhere

### Pitfall #2: Chat Not Working
**Symptom:** Agent receives chat message but doesn't respond

**Root Causes:**
1. `comms.chat` not in `config.yaml` `implements` section
2. Model timeout (model too large for hardware)
3. RabbitMQ response queue not configured

**Solutions:**
1. Add `comms.chat` to `config.yaml`
2. Use smaller model (e.g., `llama3.1:8b-instruct-q4_K_M` instead of `mixtral:8x7b`)
3. Verify `response_queue` in request metadata

### Pitfall #3: Model Not Found
**Symptom:** `Ollama API error 404: {"error":"model 'xxx' not found"}`

**Root Causes:**
1. Model name mismatch (hyphen vs colon)
2. Model not pulled in Ollama
3. `AGENT_MODEL` env var overriding `config.yaml`

**Solutions:**
1. Use correct format: `ollama:llama3.1:8b-instruct-q4_K_M` (colons, not hyphens)
2. Pull model: `ollama pull llama3.1:8b-instruct-q4_K_M`
3. Remove `AGENT_MODEL` from `docker-compose.yml` - use `config.yaml` only

### Pitfall #4: Repository Constraint Violation for Chat
**Symptom:** `[Error: Repository not allowed: ]` for chat messages

**Root Cause:** `_validate_constraints()` validates `repo_allow` even when no repo is present

**Solution:** Only validate `repo_allow` when `repo`/`project` fields are present in payload

### Pitfall #5: Missing Dependencies or Imported Modules
**Symptom:** `ModuleNotFoundError: No module named 'agents.xxx'` in Docker logs OR `'NoneType' object has no attribute 'create'` error during telemetry initialization

**Root Causes:**
1. Dependency not in `requirements.txt` (external packages)
2. Capability not listed in `config.yaml` `implements` list (build script won't copy it)
3. OpenTelemetry packages missing (common issue - causes telemetry initialization to fail)

**Solutions:**
1. **For external packages:** Add missing dependency to `agents/roles/<role>/requirements.txt` and rebuild
2. **For internal modules:** Add capability to `config.yaml` `implements` list if it's a capability, or ensure it's in shared infrastructure (build script handles this automatically)
3. **Always include OpenTelemetry packages** - they are required for telemetry system:
   ```
   opentelemetry-api>=1.22.0
   opentelemetry-sdk>=1.22.0
   opentelemetry-instrumentation
   opentelemetry-exporter-otlp-proto-grpc>=1.22.0
   opentelemetry-exporter-prometheus
   opentelemetry-semantic-conventions
   ```
4. **Prevention:** 
   - Add capabilities to `config.yaml` `implements` list
   - Verify build script includes module: `python scripts/build_agent.py <role>` then check `dist/agents/<role>/`
   - If module is missing, it may need to be added to build script's shared infrastructure list

### Pitfall #6: Agent Not Visible in Health-Check
**Symptom:** Agent doesn't appear in health-check dashboard

**Root Causes:**
1. Not registered in `instances.yaml`
2. Health-check not restarted after `instances.yaml` update

**Solutions:**
1. Add agent entry to `instances.yaml`
2. Rebuild/restart health-check: `docker-compose build health-check && docker-compose up -d health-check`

---

## 📝 Implementation Checklist

Use this checklist when adding a new agent:

- [ ] **Code Structure**
  - [ ] Remove all placeholder/dummy code
  - [ ] Implement generic capability routing via `CapabilityLoader`
  - [ ] Use `PathResolver.get_base_path()` for path resolution
  - [ ] Initialize `SchemaValidator` with resolved base path

- [ ] **Capabilities**
  - [ ] Add capability definitions to `agents/capabilities/catalog.yaml`
  - [ ] Bind capabilities to agent in `agents/capability_bindings.yaml`
  - [ ] List capabilities in `agents/roles/<role>/config.yaml` `implements` section
  - [ ] Register capabilities in `agents/capabilities/loader.py` `CAPABILITY_MAP`
  - [ ] Add `comms.chat` capability support

- [ ] **Memory**
  - [ ] Add memory dependencies to `requirements.txt` (lancedb, sentence-transformers, etc.)
  - [ ] Record memories in capabilities (use `agent.record_memory()`)

- [ ] **Model Configuration**
  - [ ] Configure model in `agents/roles/<role>/config.yaml` `defaults.model`
  - [ ] Use format: `ollama:<model-name>` (colons, not hyphens)
  - [ ] Pull model in Ollama: `ollama pull <model-name>`
  - [ ] Verify model exists: `ollama list | grep <model-name>`
  - [ ] Do NOT add `AGENT_MODEL` to `docker-compose.yml`

- [ ] **Docker Setup**
  - [ ] Use multi-stage Dockerfile pattern (build script runs automatically)
  - [ ] Add `ENV SQUADOPS_BASE_PATH=/app` to Dockerfile Stage 2
  - [ ] Test build script: `python scripts/build_agent.py <role>`
  - [ ] Verify package contents: `ls -la dist/agents/<role>/`
  - [ ] Build Docker image: `docker build -t squadops/<agent>:latest --build-arg AGENT_ROLE=<role> -f agents/roles/<role>/Dockerfile .`
  - [ ] **Note:** Build script automatically includes all required modules based on `config.yaml` `implements` list

- [ ] **Agent Registration**
  - [ ] Add agent entry to `agents/instances/instances.yaml`
  - [ ] Rebuild health-check after `instances.yaml` update
  - [ ] Verify agent appears in health-check dashboard

- [ ] **Dependencies**
  - [ ] Add all required dependencies to `requirements.txt`
  - [ ] **Include OpenTelemetry packages** (required for telemetry - missing causes NoneType errors)
  - [ ] Include domain-specific dependencies (e.g., beautifulsoup4 for HTML parsing)

- [ ] **Constraints**
  - [ ] Configure `repo_allow` in `config.yaml` if needed
  - [ ] Ensure `_validate_constraints()` only validates when repo/project present

- [ ] **Testing**
  - [ ] Write unit tests for agent's `handle_agent_request()`
  - [ ] Write integration tests for capabilities
  - [ ] Add agent to model validation test if lead/dev/strat

- [ ] **Version Management**
  - [ ] Update agent version using `version_cli.py update <agent> <version>`

- [ ] **Verification**
  - [ ] Agent builds successfully
  - [ ] Agent starts and initializes (check logs)
  - [ ] Agent responds to console chat
  - [ ] Agent appears in health-check dashboard
  - [ ] Model loads and responds without timeout

---

## 🎯 Key Takeaways

1. **Agents are thin routing layers** - All business logic goes in capabilities/skills
2. **Use unified path resolution** - `PathResolver.get_base_path()` everywhere
3. **Model config is single source of truth** - `config.yaml` `defaults.model`, not env vars
4. **Support console chat** - Add `comms.chat` to `config.yaml` and `capability_bindings.yaml`
5. **Memory is automatic** - Just add dependencies and use `record_memory()` in capabilities
6. **OpenTelemetry packages are required** - Always include in `requirements.txt` or telemetry initialization fails with NoneType errors
7. **Build script handles module copying** - Add capabilities to `config.yaml` `implements` list, build script automatically includes required modules
8. **Test model configuration** - Verify model exists and works before deploying
9. **Follow the checklist** - Missing steps cause hard-to-debug issues
10. **Test build script output** - Run `python scripts/build_agent.py <role>` and verify `dist/agents/<role>/` contains all required files before building Docker image

---

## 📚 Related Documentation

- **SIP-040:** Capability System & Loader MVP
- **SIP-042:** Memory Protocol (LanceDB)
- **Path Resolution:** `agents/utils/path_resolver.py`
- **Capability System:** `agents/capabilities/loader.py`
- **Model Configuration:** `agents/base_agent.py` `_initialize_llm_client()`

---

**Last Updated:** November 16, 2025  
**Author:** SquadOps Build Partner  
**Status:** ✅ Production-ready checklist

