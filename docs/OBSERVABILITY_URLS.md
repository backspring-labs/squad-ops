# SquadOps Observability Stack - Access URLs

## 🌐 Quick Access URLs

### Prometheus - Metrics Storage & Querying
**URL:** http://localhost:9090

**What you can do:**
- View metrics targets: http://localhost:9090/targets
- Query metrics: http://localhost:9090/graph
- View alerts: http://localhost:9090/alerts
- Check service discovery: http://localhost:9090/service-discovery
- Status page: http://localhost:9090/-/healthy

**Key Pages:**
- **Targets:** http://localhost:9090/targets (see what Prometheus is scraping)
- **Graph:** http://localhost:9090/graph (run PromQL queries)
- **Alerts:** http://localhost:9090/alerts (configured alerts)

### Grafana - Visualization Dashboard
**URL:** http://localhost:3000

**Login Credentials:**
- Username: `admin`
- Password: `GRAFANA_ADMIN_PASSWORD` in `.env`, the deploy's own (#2006)

**What you can do:**
- View the Spark health and NVIDIA DCGM dashboards
- Create custom dashboards
- Query Prometheus data
- Set up alerts

**Pre-configured:**
- **Prometheus Data Source:** Automatically configured (uid pinned in
  `infra/grafana/provisioning/datasources/prometheus.yml`, so dashboards and alert rules can name it)
- **Spark health** (`infra/grafana/dashboards/Spark/spark-health.json`): the GPU's temperature, utilisation and
  power, the seven ACPI board zones against the 98 °C alert line and the 104 °C power-off, CPU load, memory
  available, and free disk on the host root against the runbook's 150 GiB floor
- **NVIDIA DCGM Exporter Dashboard** (`infra/grafana/dashboards/Spark/nvidia-dcgm.json`, grafana.com 12239
  revision 2): its framebuffer-memory and tensor-core panels stay empty on the Spark, whose GPU has unified
  memory and whose exporter reports neither metric
- **Alert "Spark board zone above 98 °C"** (`infra/grafana/provisioning/alerting/spark-thermals.yml`): any
  ACPI zone above 98 °C for 5 minutes, one alert per zone, named. It goes to Grafana's default contact
  point, so it notifies nobody until a channel is chosen; it shows under Alerting meanwhile
- **Squad model calls** (`infra/grafana/dashboards/Squad/squad-model-calls.json`, in the **Squad** folder): the
  agents' model calls during cycles, from the metrics they send through the collector. Engine, model and role
  filter every panel. It shows:
  - calls and tokens generated per 10 minutes, by role;
  - the decode rate of calls of 1,000+ tokens against shorter calls, per engine;
  - time to first token (prefill and model load) per engine, and prompt size and call time by role;
  - a table by engine and task type.

  The counts are exact: each agent process exports its own series, and `increase()` misses a series' first
  value (on 2026-10-11 it read 25 of 53 calls), so the queries subtract each series' value before the window
  instead. Each histogram has its own bucket sizes from #2260, so a percentile can be read with
  `histogram_quantile`. Calls recorded before #2260 carry no engine label and show as "unlabelled"; all of them
  were Ollama's
- The Spark dashboards and the alert are in Grafana's **Spark** folder. Dashboards reload from the checkout
  within 10 s; alert rules are read at Grafana's startup

**Key Areas:**
- Dashboards: http://localhost:3000/dashboards
- Data Sources: http://localhost:3000/connections/datasources
- Explore: http://localhost:3000/explore (ad-hoc queries)

### OpenTelemetry Collector
**No Web UI** - Collector doesn't have a web interface, but endpoints are available:

**OTLP Endpoints:**
- GRPC: `localhost:4317` (for traces/metrics/logs)
- HTTP: `localhost:4318` (for traces/metrics/logs)
- Prometheus Metrics Export: `localhost:8889/metrics`

**Test Endpoints:**
- HTTP Health: `curl http://localhost:4318/v1/metrics`
- GRPC: `grpcurl localhost:4317 list` (if grpcurl installed)

### Agent Containers
**No Web UI** - Access via logs:
- Max logs: `docker-compose logs max`
- Neo logs: `docker-compose logs neo`

**Health Checks:**
- Agents report health to Task API
- Check via: http://localhost:8000/health (health-check service)

## 🔍 Useful Queries & Checks

### Prometheus Queries (once metrics are flowing)
```
# Task duration
rate(task_duration_seconds_sum[5m])

# Token usage by agent
sum by (agent) (rate(agent_tokens_used_total[5m]))

# System resources
system_cpu_usage_percent
system_memory_usage_percent
```

### Check Prometheus Targets
Visit: http://localhost:9090/targets

Expected targets:
- `prometheus` (self-monitoring)
- `squadops-agents` (max:8888, neo:8888, task-api:8888)
- `otel-collector` (otel-collector:8889)

**Note:** Direct agent scraping may not work yet (requires HTTP server setup). Current flow: Agents → OTLP → Collector → Prometheus.

## 📊 Current Status

- ✅ Prometheus: http://localhost:9090 (accessible)
- ✅ Grafana: http://localhost:3000 (accessible, `admin` with `GRAFANA_ADMIN_PASSWORD` from `.env`)
- ✅ OpenTelemetry Collector: Running (no UI, endpoints on 4317/4318)
- ✅ Agents: Running with OpenTelemetry initialized

## 🚀 Next Steps

1. **Access Grafana:** http://localhost:3000 (`admin`, with `GRAFANA_ADMIN_PASSWORD` from `.env`)
2. **Check Prometheus:** http://localhost:9090/targets (verify targets)
3. **View Dashboard:** Grafana → Dashboards → Spark → Spark health
4. **Query Metrics:** Prometheus → Graph (once instrumentation is added)

## 📝 Notes

- Prometheus is scraping every 15 seconds
- Grafana dashboards may be empty until agents start emitting metrics
- OTLP endpoints are ready to receive telemetry from agents

