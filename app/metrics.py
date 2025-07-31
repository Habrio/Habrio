from flask import request
from prometheus_client import Histogram, Counter
from sqlalchemy import event
import time

from models import db

# Histogram buckets for DB query durations
DB_QUERY_DURATION = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Counter for HTTP errors
ERROR_COUNTER = Counter(
    "flask_error_total",
    "Count of HTTP responses with status >= 400",
    ["endpoint", "method", "code"],
)


def init_app(app):
    """Attach metric hooks to the app and database."""

    with app.app_context():
        engine = db.engine

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault("_query_start_time", []).append(time.time())

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            start = conn.info.get("_query_start_time").pop(-1)
            DB_QUERY_DURATION.observe(time.time() - start)

    @app.after_request
    def track_errors(resp):
        if resp.status_code >= 400:
            endpoint = request.endpoint or "unknown"
            ERROR_COUNTER.labels(endpoint, request.method, resp.status_code).inc()
        return resp
