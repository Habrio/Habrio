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
- All business endpoints are now served under `/api/v1/...`.
- Error handlers remain global (no prefix).
- Test-only routes remain unversioned and, in testing, also available under `/api/v1/test_support/...`.
- Clients should update their base path to `/api/v1`.

### Auth

* Access token (lifetime ≈ 15 min) – send via `Authorization: Bearer <token>`.
* Refresh token (lifetime ≈ 30 days) – POST to `/api/v1/auth/refresh` to obtain new pair.
* Tokens are signed HS256 with `JWT_SECRET`.
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

### Admin endpoints:

Basic admin endpoints protected by JWT auth and `admin` role:

- `GET /api/v1/admin/users` - List recent users
- `GET /api/v1/admin/shops` - List recent shops
- `GET /api/v1/admin/orders` - List recent orders

### Optional AI assistant

If `OPENAI_API_KEY` is provided in the environment, the service exposes `/api/v1/agent/query` for chat-based assistance. The endpoint requires authentication and returns the assistant's answer along with suggestions.
