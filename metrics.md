# Metrics and Alerts

The application exposes Prometheus metrics at `/metrics`. The default
`prometheus-flask-exporter` integration provides request counters and latency
histograms. Additional metrics are defined to capture database query durations
and HTTP error counts.

## Database metrics
- `db_query_duration_seconds` – histogram of SQL execution time.
- `flask_error_total` – counter of responses with status codes >= 400.

## Running Prometheus locally
Use the provided configuration files in the `monitoring/` directory:

```bash
docker run --network=host \
  -v $(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml \
  prom/prometheus
```

Open <http://localhost:9090> to query metrics and inspect the dashboards.
Alerts defined in `alert_rules.yml` fire when SLO thresholds are violated.
