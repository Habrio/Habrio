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

