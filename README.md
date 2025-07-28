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
