---
sip_uid: "17642554775914219"
sip_number: 27
title: "Telemetry-Implementation-Execution-Plan-Multi-Cloud"
status: "implemented"
author: "Unknown"
approver: "None"
created_at: "BaseAgent to Use TelemetryClient"
updated_at: "2025-11-27T10:12:48.895643Z"
original_filename: "SIP-027-EXECUTION-PLAN.md"
---

# SIP-027 Telemetry Implementation Execution Plan (Multi-Cloud)

**Date**: 2024-12-XX  
**Status**: In Progress  
**Framework Version Target**: 0.4.0

## Architecture Decision: Telemetry Abstraction Layer

**Problem**: Direct OpenTelemetry SDK in agent code creates tight coupling and doesn't support multi-cloud deployment.

**Solution**: Follow the `LLMClient` pattern - create `TelemetryClient` abstraction with platform-specific implementations:
- `OpenTelemetryClient` - Local/Prometheus setup (current)
- `AWSTelemetryClient` - AWS CloudWatch/X-Ray
- `AzureTelemetryClient` - Azure Application Insights  
- `GCPTelemetryClient` - GCP Cloud Trace/Monitoring
- `NullTelemetryClient` - No-op for testing/disabled

**Benefits**:
- ✅ Agent code uses `TelemetryClient`, not OpenTelemetry directly
- ✅ Zero agent code changes needed for cloud migration
- ✅ Platform-aware selection via unified config
- ✅ Consistent with existing LLM abstraction pattern

## Current State Analysis

### What's Working
- Event-driven completion detection (Neo → Max) ✅
- Basic telemetry collection via `_collect_telemetry()` ✅
- Wrap-up markdown generation ✅
- Volume mount configured (`./warm-boot:/app/warm-boot`) ✅
- Database metrics via Task API ✅
- System metrics (CPU, memory via psutil) ✅
- Basic artifact hashes ✅
- Unified config supports platform profiles (`config/environments/{platform}.yaml`) ✅

### Gaps Identified
1. **Telemetry Abstraction Missing**:
   - Direct OpenTelemetry SDK in `BaseAgent` (tight coupling)
   - No support for cloud-specific exporters (AWS, Azure, GCP)
   - No platform-aware telemetry selection

2. **Telemetry Sources Missing** (per SIP-027 Section 179-192):
   - Ollama JSONL reasoning logs not collected
   - GPU utilization not tracked
   - Token usage shows 0 (not tracked)
   - RabbitMQ detailed stats (only message count)
   - Docker container lifecycle events need improvement
   - Execution duration not calculated

3. **Wrap-up Format** (per SIP-027 Section 356-453):
   - Missing detailed reasoning trace sections per agent
   - Missing resource utilization charts format
   - Missing metrics snapshot with target comparisons
   - Missing comprehensive event timeline
   - Token usage and reasoning entries need accurate data

4. **Event Payload** (per SIP-027 Section 131-157):
   - Neo emits events but duration_seconds and tokens_used are 0
   - Missing artifact hash details in payload

5. **Health Check Dashboard**:
   - Missing Prometheus health status
   - Missing Grafana health status
   - Missing OpenTelemetry Collector health status

## Implementation Plan

### Phase 0: Telemetry Abstraction Layer (Multi-Cloud OpenTelemetry Infrastructure)

#### Task 0.1: Create TelemetryClient Protocol
- **File**: `agents/telemetry/client.py` (new file)
- **Action**:
  - Define `TelemetryClient` Protocol similar to `LLMClient`
  - Methods: `create_span()`, `record_counter()`, `record_gauge()`, `record_histogram()`, `get_tracer()`, `get_meter()`
  - Follow pattern from `agents/llm/client.py` (Protocol-based abstraction)
  - Cloud-agnostic interface - agent code doesn't know about OpenTelemetry or cloud providers
- **Location**: New file, similar structure to `agents/llm/client.py`
- **Benefits**: Agent code uses `TelemetryClient`, not OpenTelemetry directly (same pattern as LLM)

#### Task 0.2: Create OpenTelemetryClient Implementation (Local/Prometheus)
- **File**: `agents/telemetry/providers/opentelemetry_client.py` (new file)
- **Action**:
  - Implement `TelemetryClient` protocol
  - Wrap OpenTelemetry SDK (TracerProvider, MeterProvider, OTLP/Prometheus exporters)
  - Configure for local deployment: OTLP → Collector → Prometheus/Grafana
  - Handle graceful degradation if OpenTelemetry unavailable
  - Similar to `OllamaClient` implementing `LLMClient`
- **Location**: New file in `agents/telemetry/providers/`
- **Dependencies**: OpenTelemetry packages (opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, opentelemetry-exporter-prometheus)
- **Benefits**: Encapsulates OpenTelemetry implementation details for local/Prometheus setup

#### Task 0.2b: Create AWS TelemetryClient Implementation
- **File**: `agents/telemetry/providers/aws_client.py` (new file)
- **Action**:
  - Implement `TelemetryClient` protocol
  - Use AWS Distro for OpenTelemetry (AWS OTEL Collector or direct OTLP to AWS services)
  - Configure exporters for CloudWatch Metrics, X-Ray Traces
  - Use unified config platform profile (`config/environments/aws.yaml`) for AWS-specific config
  - Support AWS credentials via environment variables or IAM roles
  - Handle graceful degradation if AWS credentials unavailable
- **Location**: New file in `agents/telemetry/providers/`
- **Dependencies**: `opentelemetry-exporter-otlp-proto-grpc`, AWS credentials/config
- **Platform Profile**: `config/environments/aws.yaml` (new file)
  - Example structure:
    ```yaml
    telemetry:
      backend: aws
      otlp_endpoint: "http://aws-otel-collector:4317"
      cloudwatch_logs_group: "squadops/agents"
      xray_tracing_enabled: true
      region: "${AWS_REGION}"
    ```
- **Benefits**: Native AWS integration (CloudWatch, X-Ray) without agent code changes

#### Task 0.2c: Create Azure TelemetryClient Implementation
- **File**: `agents/telemetry/providers/azure_client.py` (new file)
- **Action**:
  - Implement `TelemetryClient` protocol
  - Use Azure Monitor OpenTelemetry Distro (OTLP to Application Insights)
  - Configure exporters for Application Insights (traces, metrics, logs)
  - Use unified config platform profile (`config/environments/azure.yaml`) for Azure-specific config
  - Support Azure connection string via environment variables
  - Handle graceful degradation if Azure connection string unavailable
- **Location**: New file in `agents/telemetry/providers/`
- **Dependencies**: `opentelemetry-exporter-otlp-proto-grpc`, Azure connection string
- **Platform Profile**: `config/environments/azure.yaml` (new file)
  - Example structure:
    ```yaml
    telemetry:
      backend: azure
      otlp_endpoint: "https://[region].in.applicationinsights.azure.com/v2.1/track"
      connection_string: "${AZURE_CONNECTION_STRING}"
      instrumentation_key: "${AZURE_INSTRUMENTATION_KEY}"
    ```
- **Benefits**: Native Azure integration (Application Insights) without agent code changes

#### Task 0.2d: Create GCP TelemetryClient Implementation
- **File**: `agents/telemetry/providers/gcp_client.py` (new file)
- **Action**:
  - Implement `TelemetryClient` protocol
  - Use GCP native OTLP support (Cloud Trace, Cloud Monitoring)
  - Configure exporters for Cloud Trace (traces) and Cloud Monitoring (metrics)
  - Use unified config platform profile (`config/environments/gcp.yaml`) for GCP-specific config
  - Support GCP credentials via environment variables or service accounts
  - Handle graceful degradation if GCP credentials unavailable
- **Location**: New file in `agents/telemetry/providers/`
- **Dependencies**: `opentelemetry-exporter-otlp-proto-grpc`, GCP credentials
- **Platform Profile**: `config/environments/gcp.yaml` (new file)
  - Example structure:
    ```yaml
    telemetry:
      backend: gcp
      otlp_endpoint: "https://cloudtrace.googleapis.com/v1/projects/${GCP_PROJECT_ID}/traces"
      project_id: "${GCP_PROJECT_ID}"
      credentials_path: "${GOOGLE_APPLICATION_CREDENTIALS}"
    ```
- **Benefits**: Native GCP integration (Cloud Trace, Cloud Monitoring) without agent code changes

#### Task 0.3: Create NullTelemetryClient Implementation
- **File**: `agents/telemetry/providers/null_client.py` (new file)
- **Action**:
  - Implement `TelemetryClient` protocol with no-op methods
  - Used when telemetry unavailable (local dev, testing, disabled)
  - Similar to mock LLM client when `USE_LOCAL_LLM=false`
- **Location**: New file in `agents/telemetry/providers/`
- **Benefits**: Graceful degradation, easier testing

#### Task 0.4: Create TelemetryRouter Factory (Multi-Cloud)
- **File**: `agents/telemetry/router.py` (new file)
- **Action**:
  - Similar to `LLMRouter`, select telemetry implementation based on platform
  - Use unified config `get_platform()` to detect platform (local, aws, azure, gcp, jetson)
  - Load telemetry config from platform profile (`config/environments/{platform}.yaml`)
  - Return appropriate TelemetryClient:
    - `local`: `OpenTelemetryClient` (Prometheus/Grafana)
    - `aws`: `AWSTelemetryClient` (CloudWatch/X-Ray)
    - `azure`: `AzureTelemetryClient` (Application Insights)
    - `gcp`: `GCPTelemetryClient` (Cloud Trace/Monitoring)
    - `jetson`: `OpenTelemetryClient` (lightweight, OTLP only)
    - Fallback: `NullTelemetryClient` if unavailable
  - Follow pattern from `agents/llm/router.py`
  - Support `TELEMETRY_BACKEND` env var override (for testing or manual selection)
- **Location**: New file
- **Benefits**: 
  - Platform-aware selection - agents automatically use correct backend for cloud deployment
  - Zero agent code changes needed for cloud migration
  - Unified config system provides platform-specific telemetry endpoints/credentials

#### Task 0.5: Update BaseAgent to Use TelemetryClient
- **File**: `agents/base_agent.py`
- **Action**:
  - Remove direct OpenTelemetry SDK imports and setup (current setup from Phase 0)
  - Initialize `self.telemetry_client` via `TelemetryRouter.from_config()`
  - Update helper methods to delegate to `self.telemetry_client`:
    - `get_tracer()` → `self.telemetry_client.get_tracer()`
    - `get_meter()` → `self.telemetry_client.get_meter()`
    - `create_span()` → `self.telemetry_client.create_span()`
    - `record_counter()`, `record_gauge()`, `record_histogram()` → delegate to `self.telemetry_client`
  - Agent code uses `self.telemetry_client.create_span()`, etc., not OpenTelemetry directly
  - Remove OpenTelemetry-specific code (keep abstraction only)
- **Location**: Lines 150-250 (telemetry setup), helper methods (260-350)
- **Benefits**: Complete abstraction - agents don't know about OpenTelemetry or cloud providers

#### Task 0.6: Update Unified Config for Telemetry
- **File**: `config/unified_config.py`
- **Action**:
  - Add `get_telemetry_config()` method to `SquadOpsConfig`
  - Load telemetry config from platform profile if exists
  - Return telemetry backend, endpoints, credentials from platform profile
  - Support `TELEMETRY_BACKEND` env var override
  - Follow pattern from `get_llm_config()`
- **Location**: Lines 150-182 (after LLM config), add new section
- **Benefits**: Centralized telemetry configuration via platform profiles

#### Task 0.7-0.10: [Already Complete - Docker services, configs, etc. - See SIP-027-TEST-RESULTS.md]

#### Task 0.12: Set Up HTTP Server to Expose Prometheus Metrics
- **Files**: 
  - `agents/telemetry/metrics_server.py` (new file)
  - `agents/base_agent.py` (update run method)
  - `agents/telemetry/providers/opentelemetry_client.py` (update to expose prometheus_reader)
- **Action**:
  - Create `MetricsHTTPServer` class using `aiohttp` to expose `/metrics` endpoint on port 8888
  - Integrate metrics server startup into `BaseAgent.run()` method
  - Start metrics server when telemetry client has `PrometheusMetricReader` available
  - Use `PrometheusMetricReader` to collect metrics and format them in Prometheus text format
  - Handle graceful degradation if metrics server fails to start
  - Stop metrics server in `BaseAgent.cleanup()` method
- **Location**: 
  - New file: `agents/telemetry/metrics_server.py`
  - Lines 635-660 in `agents/base_agent.py` (metrics server startup)
  - Lines 878-886 in `agents/base_agent.py` (metrics server cleanup)
- **Dependencies**: `aiohttp` (already available), `prometheus-client` (optional, for bridge if needed)
- **Benefits**: Enables Prometheus to scrape agent metrics directly, allowing Grafana visualization

#### Task 0.11: Update Health Check App for Observability Services
- **File**: `infra/health-check/main.py`
- **Action**:
  - Add `check_prometheus()` method to HealthChecker class
  - Check health via `http://prometheus:9090/-/healthy`
  - Get version from Prometheus API or scrape config
  - Return status dict matching existing pattern
  - Add `check_grafana()` method to HealthChecker class
  - Check health via `http://grafana:3000/api/health`
  - Get version from Grafana API
  - Return status dict matching existing pattern
  - Add `check_otel_collector()` method to HealthChecker class
  - Check health via HTTP endpoint `http://otel-collector:4318/v1/metrics` (test POST)
  - Check container status via Docker API or simple connection test
  - Return status dict matching existing pattern
  - **Note**: For cloud platforms, add cloud-specific health checks (CloudWatch, Application Insights, Cloud Trace endpoints)
  - Update `health_infra()` endpoint to include new observability services in `asyncio.gather()`
  - Update health dashboard HTML rendering (should auto-display new services in infrastructure table)
- **Location**: 
  - Lines 215-230: Add new check methods to HealthChecker class (after check_prefect)
  - Lines 573-582: Update health_infra() to include new checks in asyncio.gather
  - No HTML changes needed - dashboard auto-displays all infra_checks entries
- **Dependencies**: `prometheus-service`, `grafana-service`, `otel-collector` (local) or cloud observability services
- **Benefits**: Single dashboard view of all infrastructure health including observability stack

### Phase 1: Enhanced Telemetry Collection (Manual + OpenTelemetry)

#### Task 1.1: Add Ollama JSONL Log Collection
- **File**: `agents/roles/lead/agent.py` method `_collect_telemetry()`
- **Action**: 
  - Add logic to read Ollama JSONL logs from agent log directories
  - Parse JSONL entries for reasoning traces per agent (Max, Neo)
  - Extract timestamps, prompts, and responses
  - Create telemetry spans via `self.telemetry_client.create_span()` for LLM calls
  - Link Ollama log entries to telemetry trace IDs
- **Location**: Lines 939-1070, add new section for `reasoning_logs['ollama_logs']`
- **Integration**: Link with telemetry traces from Task 0.5 (now via TelemetryClient abstraction)

#### Task 1.2: Add GPU Utilization Tracking
- **File**: `agents/roles/lead/agent.py` method `_collect_telemetry()`
- **Action**:
  - Use `nvidia-smi` command to get GPU utilization (if available)
  - Gracefully handle when GPU is not available
  - Store as `system_metrics['gpu_utilization']`
  - Record as telemetry gauge metric via `self.telemetry_client.record_gauge()`
- **Location**: Lines 991-1003, enhance `system_metrics` collection

#### Task 1.3: Track Token Usage (Enhanced with TelemetryClient)
- **Files**: 
  - `agents/roles/dev/agent.py` method `_emit_developer_completion_event()` (line 809)
  - `agents/roles/lead/agent.py` method `_collect_telemetry()` (line 939)
  - `agents/llm/client.py` (update LLMClient protocol)
- **Action**:
  - Update `LLMClient` protocol to return token counts in response
  - Track token usage from LLM client calls (add return value tracking)
  - Record `agent_tokens_used_total` metric via `self.telemetry_client.record_counter()`
  - Sum tokens across all agent calls for the ECID
  - Query telemetry backend for token metrics by ECID (primary source)
    - Local: Query Prometheus for token metrics
    - AWS: Query CloudWatch for token metrics
    - Azure: Query Application Insights for token metrics
    - GCP: Query Cloud Monitoring for token metrics
  - Store in telemetry as `reasoning_logs['tokens_used']` and `reasoning_logs['tokens_by_agent']` (fallback)
- **Note**: Telemetry backend provides primary source, manual tracking is fallback
- **Integration**: Uses TelemetryClient abstraction from Task 0.5

#### Task 1.4: Enhance RabbitMQ Metrics Collection
- **File**: `agents/roles/lead/agent.py` method `_collect_telemetry()`
- **Action**:
  - Use `rabbitmqctl list_queues` to get detailed queue stats (manual collection)
  - Use telemetry instrumentation if available (automatic spans via `self.telemetry_client.create_span()`)
  - Collect message counts, ack ratios, consumer counts per queue
  - Record `rabbitmq_messages_total` metric via `self.telemetry_client.record_counter()`
  - Store as `rabbitmq_metrics['queue_stats']` with per-queue breakdown
  - Query telemetry backend for RabbitMQ metrics if available (primary source)
- **Location**: Lines 987-989, enhance RabbitMQ collection
- **Integration**: Combines TelemetryClient instrumentation with manual collection

#### Task 1.5: Improve Docker Events Collection
- **File**: `agents/roles/lead/agent.py` method `_collect_telemetry()`
- **Action**:
  - Calculate execution cycle duration from ECID start time
  - Filter Docker events by ECID timeframe
  - Collect container lifecycle events (create, start, stop, remove)
  - Track image builds and container updates
  - Store as structured `docker_events['containers']`, `docker_events['images']`, `docker_events['events']`
- **Location**: Lines 1005-1019, enhance Docker events collection

#### Task 1.6: Calculate Execution Duration
- **File**: `agents/roles/lead/agent.py` method `_collect_telemetry()`
- **Action**:
  - Get execution cycle start time from Task API
  - Calculate duration from start to telemetry collection
  - Store as `telemetry['execution_duration']` in seconds
- **Location**: Lines 962-985, add duration calculation

### Phase 2: Enhanced Wrap-up Format

#### Task 2.1: Update Wrap-up Template to Match SIP-027
- **File**: `agents/roles/lead/agent.py` method `_generate_wrapup_markdown()` (line 1100)
- **Action**: 
  - Restructure markdown to match SIP-027 Section 356-453 template exactly
  - Add sections: "PRD Interpretation (Max)", "Task Execution (Neo)", "Artifacts Produced", 
  "Resource & Event Summary", "Metrics Snapshot", "Event Timeline"
  - Include reasoning trace quotes with proper formatting
  - Add resource utilization table with CPU/GPU/Memory metrics
  - Add metrics snapshot with target comparisons
  - Add comprehensive event timeline from communication log
- **Location**: Lines 1128-1253, rewrite template

#### Task 2.2: Add Reasoning Trace Extraction
- **File**: `agents/roles/lead/agent.py` method `_extract_real_ai_reasoning()` (line 1072)
- **Action**:
  - Enhance to extract from both communication_log and Ollama JSONL logs
  - Format reasoning traces with proper quote blocks
  - Include agent name and timestamp for each reasoning entry
  - Support multiple agents (Max, Neo) with separate sections
- **Location**: Lines 1072-1098, enhance reasoning extraction

#### Task 2.3: Add Artifact Details with Hashes
- **File**: `agents/roles/lead/agent.py` method `_generate_wrapup_markdown()` (line 1100)
- **Action**:
  - Extract artifact paths and hashes from telemetry
  - Format as bullet list with full SHA256 hashes (not truncated)
  - Include file sizes if available
  - Match SIP-027 format: `- `hello-squad/app.py` — FastAPI application`
- **Location**: Lines 1164-1166, enhance artifact formatting

#### Task 2.4: Enhance Metrics Snapshot Section
- **File**: `agents/roles/lead/agent.py` method `_generate_wrapup_markdown()` (line 1100)
- **Action**:
  - Add target comparisons (e.g., "Tokens Used: 4,120 | < 5,000 | ✅ Under budget")
  - Include all metrics from SIP-027 template: Tasks Executed, Tokens Used, Reasoning Entries,
  Pulse Count, Rework Cycles, Test Pass Rate
  - Add status indicators (✅, ⚠️, ❌) based on targets
- **Location**: Lines 1184-1194, enhance metrics snapshot

### Phase 3: Neo Event Payload Enhancement

#### Task 3.1: Track Actual Duration in Neo
- **File**: `agents/roles/dev/agent.py` method `_emit_developer_completion_event()` (line 809)
- **Action**:
  - Track task start time when task begins
  - Calculate actual duration when emitting completion event
  - Store in `metrics['duration_seconds']` (currently 0)
- **Location**: Lines 851-856, add duration tracking

#### Task 3.2: Track Token Usage in Neo (Enhanced with TelemetryClient)
- **Files**: 
  - `agents/roles/dev/agent.py` 
  - `agents/roles/dev/app_builder.py`
- **Action**:
  - Track token counts from LLM calls in AppBuilder
  - Record `agent_tokens_used_total` metric via `self.telemetry_client.record_counter()` with labels (agent, ecid, task_id)
  - Sum tokens across all LLM calls for the task
  - Include in completion event payload `metrics['tokens_used']`
  - Query telemetry backend if available (primary source)
- **Note**: Telemetry backend provides primary source, manual tracking is fallback
- **Integration**: Uses TelemetryClient abstraction from Task 0.5

#### Task 3.3: Include Artifact Hashes in Event Payload
- **File**: `agents/roles/dev/agent.py` method `_emit_developer_completion_event()` (line 809)
- **Action**:
  - Calculate SHA256 hashes for generated artifacts
  - Include full hash in `artifacts` array as `{"path": "app.py", "hash": "sha256:abc123..."}`
  - Match SIP-027 event schema format
- **Location**: Lines 840-850, enhance artifact payload

### Phase 4: Testing & Validation

#### Task 4.1: Update Unit Tests
- **File**: `tests/unit/test_base_agent.py`, `tests/unit/test_lead_agent.py`
- **Action**:
  - Mock `TelemetryClient` instead of OpenTelemetry SDK
  - Test TelemetryRouter selection logic for different platforms
  - Test TelemetryClient implementations (OpenTelemetry, AWS, Azure, GCP, Null)
  - Update `test_collect_telemetry` to verify new telemetry sources
  - Add tests for GPU detection, token tracking, Ollama log parsing
  - Add tests for telemetry initialization and metric recording via TelemetryClient
  - Mock telemetry backend queries for telemetry collection (Prometheus, CloudWatch, Application Insights, Cloud Monitoring)
  - Update `test_generate_wrapup_markdown` to verify new format matches SIP-027
- **Location**: Lines 1051-1164, enhance existing tests

#### Task 4.2: Integration Testing for Observability Stack
- **Files**: `tests/integration/test_telemetry.py` (new file)
- **Action**:
  - Test TelemetryClient abstraction initialization in agents
  - Test TelemetryRouter platform selection (local, aws, azure, gcp)
  - Verify Prometheus exporter exposes `/metrics` endpoint (local)
  - Verify Prometheus scrapes agent metrics (local)
  - Verify Grafana connects to Prometheus (local)
  - Verify metrics flow from agents → Prometheus → Grafana (local)
  - Test wrap-up generation with telemetry metrics (all platforms)
  - Test cloud-specific exporters (AWS, Azure, GCP) - mock or integration
- **Location**: New integration test file

#### Task 4.3: Validate Wrap-up Format and Observability Stack
- **Action**: 
  - Run a WarmBoot and verify wrap-up matches SIP-027 template
  - Check all sections are present and properly formatted
  - Verify telemetry data is accurate and comprehensive (both manual and telemetry backend)
  - Verify Grafana dashboard displays WarmBoot metrics correctly (local)
  - Verify Prometheus metrics are queryable and accurate (local)
  - Verify CloudWatch/Application Insights/Cloud Monitoring display metrics correctly (cloud platforms)
  - Verify health check dashboard shows observability services
  - Compare with SIP-027 Section 356-453 example
  - Validate telemetry trace correlation with wrap-up (all platforms)
- **Benefits**: End-to-end validation of telemetry collection and visualization across all platforms

## Implementation Notes

### Dependencies
- OpenTelemetry packages (opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc, opentelemetry-exporter-prometheus)
- Platform-specific packages (optional, only for cloud deployments):
  - AWS: `boto3` (for CloudWatch/X-Ray integration)
  - Azure: `azure-monitor-opentelemetry` (for Application Insights integration)
  - GCP: `google-cloud-trace`, `google-cloud-monitoring` (for Cloud Trace/Monitoring integration)
- Prometheus (for local metrics storage and querying)
- Grafana (for local visualization)
- OpenTelemetry Collector (optional, for centralized collection)
- `nvidia-smi` command available for GPU metrics (optional, graceful fallback)
- Ollama JSONL logs accessible from agent log directories
- `rabbitmqctl` command available for detailed queue stats
- Docker daemon accessible for events (already configured)

### Error Handling
- All new telemetry sources should gracefully handle failures
- TelemetryClient implementations should initialize gracefully if backend unavailable (local-only mode)
- Cloud TelemetryClient implementations should gracefully degrade to NullTelemetryClient if credentials unavailable
- Missing sources should not block wrap-up generation
- Log warnings for missing optional data (GPU, Ollama logs, telemetry backend)
- Use try-except blocks around each telemetry collection method

### Backward Compatibility
- Existing wrap-up generation must continue to work
- TelemetryClient abstraction is additive (agents work without it, but enhanced with it)
- Manual telemetry collection remains as fallback if TelemetryClient unavailable
- Prometheus/Grafana are optional services for local deployment (wrap-up still works without them)
- Cloud observability services are optional for cloud deployment (agents work without them)
- Missing data should show "N/A" or be omitted, not cause errors

### Deployment Strategy
- **Development (Local)**: TelemetryClient → OpenTelemetryClient → Prometheus/Grafana
- **Production (Local)**: TelemetryClient → OpenTelemetryClient → OTLP Collector → Prometheus/Grafana
- **Production (AWS)**: TelemetryClient → AWSTelemetryClient → CloudWatch/X-Ray
- **Production (Azure)**: TelemetryClient → AzureTelemetryClient → Application Insights
- **Production (GCP)**: TelemetryClient → GCPTelemetryClient → Cloud Trace/Cloud Monitoring
- **Edge (Jetson Nano)**: TelemetryClient → OpenTelemetryClient (lightweight, OTLP only, no Prometheus)
- Agents always work standalone, observability stack enhances but doesn't require
- Platform selection via `SQUADOPS_PLATFORM` env var or platform profile

### Platform Configuration Files

Create example platform profiles for reference (not required for agents to run):

- `config/environments/local.yaml` - Local/Prometheus setup (optional, defaults used)
- `config/environments/aws.yaml` - AWS CloudWatch/X-Ray setup
- `config/environments/azure.yaml` - Azure Application Insights setup
- `config/environments/gcp.yaml` - GCP Cloud Trace/Monitoring setup
- `config/environments/jetson.yaml` - Jetson Nano lightweight setup

## Success Criteria

- ✅ All telemetry sources from SIP-027 Phase 1 collected
- ✅ TelemetryClient abstraction implemented (matching LLMClient pattern)
- ✅ Platform-aware telemetry selection (local, aws, azure, gcp)
- ✅ OpenTelemetryClient working for local/Prometheus deployment
- ✅ AWSTelemetryClient ready for AWS deployment (CloudWatch/X-Ray)
- ✅ AzureTelemetryClient ready for Azure deployment (Application Insights)
- ✅ GCPTelemetryClient ready for GCP deployment (Cloud Trace/Monitoring)
- ✅ Zero agent code changes needed for cloud migration
- ✅ Prometheus collecting metrics from agents (local)
- ✅ Grafana dashboard displaying WarmBoot telemetry (local)
- ✅ Health check dashboard showing observability services health
- ✅ Wrap-up format matches SIP-027 template exactly
- ✅ Token usage accurately tracked and reported (via TelemetryClient + manual fallback)
- ✅ GPU utilization collected (when available)
- ✅ Ollama JSONL logs parsed and included in reasoning traces
- ✅ RabbitMQ detailed stats collected (via TelemetryClient + manual fallback)
- ✅ Docker events comprehensive and structured
- ✅ Execution duration calculated and displayed
- ✅ All unit tests updated and passing (with TelemetryClient mocks)
- ✅ All integration tests passing (telemetry stack across platforms)
- ✅ Wrap-up generated in < 2 minutes after Neo completion (per SIP-027)
- ✅ Framework version bumped to 0.4.0 upon completion

## Files to Create/Modify

### New Files
1. `agents/telemetry/client.py` - TelemetryClient Protocol
2. `agents/telemetry/router.py` - TelemetryRouter Factory
3. `agents/telemetry/providers/__init__.py` - Provider exports
4. `agents/telemetry/providers/opentelemetry_client.py` - Local/Prometheus implementation
5. `agents/telemetry/providers/aws_client.py` - AWS CloudWatch/X-Ray implementation
6. `agents/telemetry/providers/azure_client.py` - Azure Application Insights implementation
7. `agents/telemetry/providers/gcp_client.py` - GCP Cloud Trace/Monitoring implementation
8. `agents/telemetry/providers/null_client.py` - Null/no-op implementation
9. `config/environments/aws.yaml` - AWS platform profile (example)
10. `config/environments/azure.yaml` - Azure platform profile (example)
11. `config/environments/gcp.yaml` - GCP platform profile (example)

### Modified Files
1. `agents/base_agent.py` - Replace OpenTelemetry SDK with TelemetryClient abstraction
2. `config/unified_config.py` - Add `get_telemetry_config()` method
3. `agents/roles/lead/agent.py` - Use TelemetryClient, instrument operations, enhance telemetry collection
4. `agents/roles/dev/agent.py` - Use TelemetryClient, instrument operations, enhance event payload
5. `agents/roles/dev/app_builder.py` - Use TelemetryClient, track tokens
6. `agents/llm/client.py` - Update protocol to return token counts
7. `infra/health-check/main.py` - Add Prometheus, Grafana, OTLP Collector health checks
8. `tests/unit/test_base_agent.py` - Update tests for TelemetryClient abstraction
9. `tests/unit/test_lead_agent.py` - Update tests for TelemetryClient abstraction
10. `tests/integration/test_telemetry.py` - New integration tests for TelemetryClient across platforms

### Already Complete
11. `agents/requirements.txt` - OpenTelemetry packages ✅
12. `infra/task-api/requirements.txt` - OpenTelemetry packages ✅
13. `docker-compose.yml` - OTLP Collector, Prometheus, Grafana services ✅
14. `infra/prometheus/prometheus.yml` - Prometheus configuration ✅
15. `infra/grafana/dashboards/warmboot-telemetry.json` - Grafana dashboard ✅
16. `infra/otel-collector/config.yaml` - Collector configuration ✅
17. `tests/integration/test_opentelemetry_setup.py` - OpenTelemetry setup tests ✅

## Estimated Effort

- Phase 0.1-0.4: Telemetry Abstraction Layer - 4-6 hours
- Phase 0.5: BaseAgent Migration - 2-3 hours
- Phase 0.6: Unified Config Updates - 1 hour
- Phase 0.11: Health Check Updates - 1-2 hours
- Phase 1 (Telemetry Collection): 4-6 hours
- Phase 2 (Wrap-up Format): 2-3 hours  
- Phase 3 (Neo Events): 2-3 hours
- Phase 4 (Testing): 3-4 hours
- **Total**: 19-28 hours

