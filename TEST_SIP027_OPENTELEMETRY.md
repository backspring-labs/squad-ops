# SIP-027 OpenTelemetry Setup Testing Plan

## Current Status
Phase 0 infrastructure setup complete:
- ✅ OpenTelemetry packages added to requirements
- ✅ BaseAgent SDK configuration
- ✅ Helper methods added
- ✅ Docker Compose services configured
- ✅ Configuration files created

## Testing Strategy

### 1. Syntax & Import Validation

**Test: Python syntax check**
```bash
python3 -m py_compile agents/base_agent.py
```

**Test: Import validation**
- Verify OpenTelemetry imports work (in container)
- Check ResourceAttributes import path is correct
- Validate graceful degradation when OpenTelemetry not available

**Test: Docker Compose validation**
```bash
docker-compose config --quiet
```

### 2. Unit Tests

**Run integration tests:**
```bash
pytest tests/integration/test_opentelemetry_setup.py -v
```

**Expected results:**
- BaseAgent has telemetry attributes
- Helper methods exist and are callable
- Metrics recording doesn't raise errors
- Context managers work correctly

### 3. Container Build Test

**Test: Build agents with OpenTelemetry packages**
```bash
docker-compose build max neo
```

**Expected results:**
- Packages install successfully
- No import errors
- OpenTelemetry initializes gracefully

### 4. Service Startup Test

**Test: Start observability services**
```bash
docker-compose up -d prometheus grafana otel-collector
```

**Check service health:**
- Prometheus: `curl http://localhost:9090/-/healthy`
- Grafana: `curl http://localhost:3000/api/health`
- OpenTelemetry Collector: `curl http://localhost:4318/`

### 5. Agent Initialization Test

**Test: Start agents and verify telemetry initialization**
```bash
docker-compose up -d max neo
docker-compose logs max | grep -i "opentelemetry\|telemetry"
docker-compose logs neo | grep -i "opentelemetry\|telemetry"
```

**Expected logs:**
- "OpenTelemetry initialized successfully" or
- "OpenTelemetry not available, telemetry disabled" (graceful degradation)

### 6. Metrics Endpoint Test

**Test: Prometheus metrics endpoints (if HTTP server is configured)**
```bash
# This would require HTTP server setup for PrometheusMetricReader
# For now, metrics go through OTLP collector
```

**Alternative: Check OTLP export**
- Verify agents can send traces/metrics to collector
- Check collector receives data

### 7. Prometheus Scraping Test

**Test: Prometheus can scrape metrics**
- Open Prometheus UI: http://localhost:9090
- Check Targets: http://localhost:9090/targets
- Verify agents appear in scrape targets (if HTTP endpoints configured)

**Note:** Current setup uses OTLP → Collector → Prometheus flow, not direct scraping yet.

### 8. Grafana Dashboard Test

**Test: Grafana dashboard loads**
1. Open Grafana: http://localhost:3000
2. Login: admin/admin123
3. Navigate to Dashboards → WarmBoot Telemetry
4. Verify datasource is Prometheus
5. Check panels load (may be empty until metrics flow)

### 9. End-to-End Flow Test

**Test: Complete telemetry pipeline**
1. Trigger a WarmBoot run
2. Verify agents create spans/metrics
3. Check collector receives data
4. Verify Prometheus stores metrics
5. Validate Grafana displays data

## Known Issues to Address

1. **PrometheusMetricReader HTTP Server:**
   - Current implementation uses `PrometheusMetricReader()` but doesn't start HTTP server
   - Need to either:
     - Add HTTP server manually (using prometheus_client)
     - Use OTLP exporter to send to collector (already configured)
     - Use different exporter pattern

2. **ResourceAttributes Import:**
   - Changed from `opentelemetry.semantic.resource` to `opentelemetry.semconv.resource`
   - Need to verify this is correct in actual OpenTelemetry package

3. **Docker Compose Version Warning:**
   - Remove `version: '3.8'` from docker-compose.yml (obsolete)

## Next Steps After Testing

1. **Fix any import/path issues** found during testing
2. **Add HTTP server for Prometheus** if direct scraping needed
3. **Instrument agent operations** (Phase 0.4) once setup validated
4. **Create comprehensive dashboards** once metrics are flowing
5. **Add integration tests** for complete telemetry pipeline

## Test Commands Summary

```bash
# 1. Syntax check
python3 -m py_compile agents/base_agent.py

# 2. Docker Compose validation
docker-compose config --quiet

# 3. Run unit tests
pytest tests/integration/test_opentelemetry_setup.py -v

# 4. Build containers
docker-compose build max neo

# 5. Start services
docker-compose up -d prometheus grafana otel-collector

# 6. Start agents
docker-compose up -d max neo

# 7. Check logs
docker-compose logs max neo | grep -i telemetry

# 8. Check service health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health
```

