from flask import Flask, request, g
from dotenv import load_dotenv
from app.config import get_config_class
from app.logging import configure_logging
from app.errors import errors_bp
from app.cli import register_cli
from app.api import register_api_v1
from app.routes.onboarding import auth as auth_routes
from app.version import API_PREFIX
from flask_cors import CORS
from flasgger import Swagger
from prometheus_flask_exporter import PrometheusMetrics
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
import extensions
import logging
import os
import uuid
from opentelemetry.trace import get_current_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from app.telemetry import init_tracing
from models import db


def create_app(config_object=None):
    """Application factory."""
    load_dotenv()
    app = Flask(__name__)

    if config_object is not None:
        if isinstance(config_object, str):
            app.config.from_object(config_object)
        else:
            app.config.from_object(config_object)
    else:
        app.config.from_object(get_config_class())

    configure_logging(app)
    register_cli(app)
    auth_routes.init_twilio(app)

    # Optional OpenAI configuration for the assistant
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai
            openai.api_key = openai_key
            app.logger.info("OpenAI integration enabled")
        except Exception as e:  # pragma: no cover - runtime configuration
            app.logger.error("OpenAI init failed: %s", e)

    # Initialize extensions
    limiter = extensions.limiter
    limiter.init_app(app)
    app.limiter = limiter

    migrate = Migrate(app, db, compare_type=True, render_as_batch=True)
    swagger = Swagger(
        app,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/apispec.json",
                    "rule_filter": lambda rule: rule.rule.startswith(
                        f"{API_PREFIX}/"
                    ),
                    "model_filter": lambda tag: True,
                }
            ],
            "swagger_ui": True,
            "specs_route": "/docs/",
        },
        template={
            "tags": [
                {"name": "Consumer", "description": "Consumer-facing endpoints"},
                {"name": "Vendor", "description": "Vendor-facing endpoints"},
            ]
        },
    )
    metrics = PrometheusMetrics(app, path='/metrics')
    if not app.config.get("TESTING") and not os.environ.get("METRICS_APP_INFO_SET"):
        metrics.info("app_info", "Application info", version="1.0.0")
        os.environ["METRICS_APP_INFO_SET"] = "1"

    # Configure CORS
    allowed = app.config.get("CORS_ALLOWED_ORIGINS", "*")
    if isinstance(allowed, str):
        allowed = allowed.strip()
        origins = "*" if allowed == "*" else [o.strip() for o in allowed.split(",") if o.strip()]
    else:
        origins = allowed or "*"
    CORS(
        app,
        origins=origins,
        supports_credentials=True,
        expose_headers=["X-Request-ID"],
    )

    app.register_blueprint(errors_bp)
    if app.config.get("TESTING"):
        from app.test_support import test_support_bp
        app.register_blueprint(test_support_bp)
        app.register_blueprint(test_support_bp, url_prefix="/api/v1/test_support", name="test_support_bp_v1")

    register_api_v1(app)

    @app.before_request
    def _set_request_id():
        incoming = request.headers.get("X-Request-ID")
        rid = (incoming or uuid.uuid4().hex)[:100]
        g.request_id = rid
        app.logger.info(f"request start {request.method} {request.path}")

    @app.after_request
    def _add_request_id_header(resp):
        try:
            rid = getattr(g, "request_id", None)
            if rid:
                resp.headers["X-Request-ID"] = rid
        except Exception:
            pass
        return resp

    @app.after_request
    def _set_security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        existing = resp.headers.get("Access-Control-Expose-Headers", "")
        if "X-Request-ID" not in existing:
            existing = (
                existing
                + ("," if existing and not existing.endswith(",") else "")
                + "X-Request-ID"
            ).strip(",")
        if "traceparent" not in existing:
            existing = (
                existing
                + ("," if existing and not existing.endswith(",") else "")
                + "traceparent"
            ).strip(",")
        resp.headers["Access-Control-Expose-Headers"] = existing
        return resp

    @app.after_request
    def _add_trace_header(resp):
        carrier = {}
        TraceContextTextMapPropagator().inject(carrier)
        tp = carrier.get("traceparent")
        if tp:
            resp.headers["traceparent"] = tp
        return resp

    db.init_app(app)
    init_tracing(app)
    if app.config.get("DEBUG") or app.config.get("TESTING"):
        with app.app_context():
            db.create_all()
            logging.info("✅ Tables created")

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app
