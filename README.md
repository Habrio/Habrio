# Habrio Backend

This repository contains the backend API built with Flask.

## Database Migrations (Flask-Migrate / Alembic)

**Setup (first time in repo):**
```bash
export APP_ENV=development  # or testing/staging
flask db init
```

**Create a migration:**
```bash
flask db-migrate-safe -m "describe change"
```

**Apply migrations:**
```bash
flask db-upgrade-safe
```

**Stamp an existing database:**
```bash
flask db-stamp-safe head
```

Set `ALLOW_DB_MIGRATIONS=true` in production to permit upgrades or stamping.


## API Versioning
- All business endpoints are served under `/api/v1/...`.
- Consumer-facing routes live under `/api/v1/consumer/...` (onboarding, profile, orders, etc.).
- Vendor-facing routes live under `/api/v1/vendor/...` (shop management, orders, payouts, etc.).
- Common operations like OTP, login and basic onboarding remain directly under `/api/v1/`.
- Admin endpoints stay under `/api/v1/admin/...`.
- Error handlers remain global (no prefix).
- Test-only routes remain unversioned and, in testing, also available under `/api/v1/test_support/...`.
- Clients should update their base path to `/api/v1`.

### Code Structure

Routes are organized in subpackages under `app/routes`:

- `consumer/` for consumer-facing endpoints
- `vendor/` for vendor endpoints
- `admin/` for admin actions

Each subpackage defines its own blueprint and modules like `profile.py`,
`orders.py`, or `wallet.py` that register routes on that blueprint.

### Auth

* Access token (lifetime ≈ 15 min) – send via `Authorization: Bearer <token>`.
* Refresh token (lifetime ≈ 30 days) – POST to `/api/v1/auth/refresh` to obtain new pair.
* Tokens are signed HS256 with `JWT_SECRET`.
* Old secrets can be supplied via `JWT_PREVIOUS_SECRETS` (comma-separated) to
  allow graceful key rotation. When rotating, place the former secret in this
  list so older tokens remain valid until they expire.
* User roles are always validated against the database on each request, so
  tampering with the `role` claim in a token will not grant extra privileges.
### Role-scoped permissions (Step 9)
Decorators now accept `role:action` scopes, e.g.:
  @role_required("vendor:modify_order")
Actions are defined in `app/auth/permissions.py`. `admin` has wildcard `*`.

### Rate limiting
All APIs are now protected by Flask-Limiter.
Sensitive endpoints (OTP, login, order) have both per-IP and per-user limits.
Hitting a rate limit returns JSON 429 with an explanatory message.

### API Documentation and Observability (Step 11)

- **Interactive API docs**: Swagger UI available at `/docs/`
- **OpenAPI JSON spec**: Available at `/apispec.json`
- **Prometheus metrics**: Accessible at `/metrics`

### Postman collection

- Import `postman/Habrio.postman_collection.json` into Postman (File → Import) to access curated requests for auth, onboarding, consumer, vendor, admin, and the optional agent APIs.
- Before sending requests, configure the collection variables (or attach an environment) with your `baseUrl` and the relevant JWT tokens so that headers such as `Authorization: Bearer {{consumerAccessToken}}` resolve correctly.

### Admin endpoints:

Basic admin endpoints protected by JWT auth and `admin` role:

- `GET /api/v1/admin/users` - List recent users
- `GET /api/v1/admin/shops` - List recent shops
- `GET /api/v1/admin/orders` - List recent orders

Example consumer routes:
- `POST /api/v1/consumer/onboarding`
- `GET /api/v1/consumer/profile/me`

Example vendor routes:
- `POST /api/v1/vendor/shop`
- `GET /api/v1/vendor/orders`

### Optional AI assistant

If `OPENAI_API_KEY` is provided in the environment, the service exposes `/api/v1/agent/query` for chat-based assistance. The endpoint requires authentication and returns the assistant's answer along with suggestions.

### Background workers

Celery with Redis powers asynchronous tasks for heavy operations such as sending notifications or processing item uploads. Set `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` to point at your Redis instance. Workers can be started with `celery -A celery_app worker -l info`.

## Tracing

The service uses OpenTelemetry to trace HTTP requests, database queries and outbound API calls.
Traces are exported via OTLP and can be viewed using Jaeger.

### Local Jaeger

Run Jaeger in Docker and point the app to it:

```bash
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
```

Start the Flask app with `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` and visit `http://localhost:16686` to browse traces.

## Docker

The application can be run in a container using the included `Dockerfile`. It
uses a multi-stage build based on `python:3.12-slim` and installs all
dependencies in a builder stage. The runtime image runs as an unprivileged
`appuser` account and expects a read-only root filesystem.

### Build
```bash
docker build -t habrio .
```

### Run
```bash
docker run -p 80:80 \
  --read-only \
  --tmpfs /tmp \
  -e SECRET_KEY=changeme \
  -e DATABASE_URL=sqlite:///data.db \
  habrio
```

Set `APP_ENV=production` by default in the image. Provide `SECRET_KEY` and
`DATABASE_URL` at runtime via environment variables or Docker secrets. When
running with Docker Compose the web service is configured with `read_only: true`
and a temporary filesystem mounted at `/tmp`.

A `docker-compose.yml` is included for local development with PostgreSQL.

## Continuous Integration

GitHub Actions runs the test suite on every push and pull request to `main`.
The workflow installs dependencies, executes the tests with `pytest-cov`, and
fails if overall coverage drops below 90%. A Docker image is built for each
run and scanned with [Trivy](https://github.com/aquasecurity/trivy) to detect
critical or high severity vulnerabilities.

## Monitoring with Prometheus

A basic Prometheus configuration is provided in `monitoring/prometheus.yml` with
Alertmanager rules defined in `monitoring/alert_rules.yml`. To run Prometheus
locally and scrape the application metrics:

```bash
docker run --network=host \
  -v $(pwd)/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml \
  -v $(pwd)/monitoring/alert_rules.yml:/etc/prometheus/alert_rules.yml \
  prom/prometheus
```

Navigate to `http://localhost:9090` to explore the metrics dashboard. The
`/metrics` endpoint of the Flask app exposes request latency histograms,
database query durations and error counters which feed the provided alerting
rules.

## Dependency Management

All runtime dependencies are pinned to exact versions in `requirements.txt` and
`pyproject.toml`. Continuous integration installs these exact versions and runs
`pip-audit` to check for known vulnerabilities. The workflow fails if any
issues are reported.

To update a package:
1. Create a new branch and bump the version in both files.
2. Run `pip-audit` locally and ensure the audit passes.
3. Submit a pull request. CI will re-run `pip-audit` and the test suite.

Security advisories should be addressed within a week. Subscribe to relevant
package feeds or GitHub alerts so that new CVEs are reviewed promptly.
