from flask import Flask
from models import db
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
from prometheus_flask_exporter import PrometheusMetrics
# from agent.query_handler import ask_agent_handler
from dotenv import load_dotenv
from app.config import get_config_class
import os
import logging
from flask_cors import CORS
from app.errors import errors_bp
from app.logging import configure_logging
from flask_migrate import Migrate
from app.cli import register_cli
from flask import request, g
from app.api import register_api_v1
import uuid

# --- Load Environment Variables ---
load_dotenv()

# Create app and load configuration
app = Flask(__name__)
app.config.from_object(get_config_class())
configure_logging(app)
register_cli(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=app.config.get("RATELIMIT_STORAGE_URL", "memory://"),
    strategy="fixed-window",
    default_limits=["200 per hour"],
)
app.limiter = limiter
from models import user, vendor, shop, item, order, wallet, cart  # noqa: F401
migrate = Migrate(app, db, compare_type=True, render_as_batch=True)
swagger = Swagger(app, config={
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec',
            "route": '/apispec.json',
            "rule_filter": lambda rule: rule.rule.startswith('/api/v1/'),
            "model_filter": lambda tag: True,
        }
    ],
    "swagger_ui": True,
    "specs_route": "/docs/"
})
metrics = PrometheusMetrics(app, path='/metrics')
# Avoid duplicated app_info metrics if this module gets imported multiple times
if not app.config.get("TESTING") and not os.environ.get("METRICS_APP_INFO_SET"):
    metrics.info("app_info", "Application info", version="1.0.0")
    os.environ["METRICS_APP_INFO_SET"] = "1"

# Configure CORS based on allowed origins
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
        resp.headers["Access-Control-Expose-Headers"] = (
            existing
            + ("," if existing and not existing.endswith(",") else "")
            + "X-Request-ID"
        ).strip(",")
    return resp

db.init_app(app)
with app.app_context():
    db.create_all()
    logging.info("✅ Tables created")

# ========================== Health Check ==========================
register_api_v1(app)
@app.route("/health")
def health():
    return {"status": "ok", "base_url": "https://2e6bee57-c137-4144-90f2-64265943227d-00-c6d7jiueybzk.pike.replit.dev"}, 200


# ========================== Run ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
