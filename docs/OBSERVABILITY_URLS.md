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
- Password: `admin123`

**What you can do:**
- View WarmBoot telemetry dashboard
- Create custom dashboards
- Query Prometheus data
- Set up alerts

**Pre-configured:**
- **Prometheus Data Source:** Automatically configured
- **WarmBoot Telemetry Dashboard:** Available in dashboards folder

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
- ✅ Grafana: http://localhost:3000 (accessible, admin/admin123)
- ✅ OpenTelemetry Collector: Running (no UI, endpoints on 4317/4318)
- ✅ Agents: Running with OpenTelemetry initialized

## 🚀 Next Steps

1. **Access Grafana:** http://localhost:3000 (login with admin/admin123)
2. **Check Prometheus:** http://localhost:9090/targets (verify targets)
3. **View Dashboard:** Grafana → Dashboards → WarmBoot Telemetry
4. **Query Metrics:** Prometheus → Graph (once instrumentation is added)

## 📝 Notes

- Prometheus is scraping every 15 seconds
- Grafana dashboards may be empty until agents start emitting metrics
- WarmBoot telemetry dashboard will populate once we instrument agent operations
- OTLP endpoints are ready to receive telemetry from agents

