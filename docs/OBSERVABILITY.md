# 📡 M3TAL Observability & Log Export

The M3TAL Control Plane is designed for high observability. This guide explains how to aggregate and visualize your system data.

---

## 📊 Native Telemetry

- **Dashboard**: `http://localhost:8080` (or `DASHBOARD_PORT`)
- **API Health**: `GET /api/health`
- **Liveness**: `GET /healthz`

---

## 🪵 Log Aggregation (Enterprise Strategy)

### 1. Centralized Logging with Promtail/Loki

To export M3TAL agent logs to a central Grafana instance, add a `promtail` config:

```yaml
scrape_configs:
- job_name: m3tal-agents
  static_configs:
  - targets: [localhost]
    labels:
      job: m3tal
      __path__: /path/to/M3tal-Media-Server/control-plane/state/logs/*.log
```

### 2. Docker Cloud Logging

Configure your `daemon.json` to send container logs to a remote syslog or loki endpoint:

```json
{
  "log-driver": "loki",
  "log-opts": {
    "loki-url": "http://your-loki-server:3100/loki/api/v1/push",
    "loki-external-labels": "container_name={{.Name}}"
  }
}
```

---

## 📈 Uptime Monitoring

M3TAL provides a standard `/healthz` endpoint. You can hook this into:

1. **Uptime Kuma** (Self-hosted)
2. **BetterStack** (Cloud)
3. **Checkly** (E2E)

Target: `http://<your-ip>:<dashboard-port>/healthz`
Expected Code: `200`
Response: `{"status": "ready"}`
