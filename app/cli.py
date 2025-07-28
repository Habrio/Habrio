import os
import click
from flask import current_app
from flask.cli import with_appcontext
from flask_migrate import upgrade as alembic_upgrade, stamp as alembic_stamp, migrate as alembic_migrate


def _assert_safe_for_upgrade():
    # Prevent accidental prod upgrades unless explicitly allowed
    env = (current_app.config.get("ENV") or "").lower()
    app_env = (os.getenv("APP_ENV") or "").lower()
    if app_env == "production" or env == "production":
        if (os.getenv("ALLOW_DB_MIGRATIONS") or "").lower() not in ("1", "true", "yes"):
            raise click.ClickException("Refusing to run DB migration in production without ALLOW_DB_MIGRATIONS=true")


@click.command("db-migrate-safe")
@click.option("-m", "--message", default="auto migration", help="Migration message")
@with_appcontext
def db_migrate_safe(message):
    """Generate a new migration script from current models."""
    alembic_migrate(message=message)
    click.echo("Migration script generated.")


@click.command("db-upgrade-safe")
@with_appcontext
def db_upgrade_safe():
    """Apply migrations to the configured database."""
    _assert_safe_for_upgrade()
    alembic_upgrade()
    click.echo("Database upgraded.")


@click.command("db-stamp-safe")
@click.option("--revision", default="head", help="Revision to stamp, default 'head'")
@with_appcontext
def db_stamp_safe(revision):
    """Mark the database at a given revision without running migrations."""
    _assert_safe_for_upgrade()
    alembic_stamp(revision)
    click.echo(f"Database stamped at {revision}.")


def register_cli(app):
    app.cli.add_command(db_migrate_safe)
    app.cli.add_command(db_upgrade_safe)
    app.cli.add_command(db_stamp_safe)

