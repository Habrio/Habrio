from flask import Flask
from models import db
from services import (
    auth as auth_services,
    user as user_services,
    vendor as vendor_services,
    shop as shop_services,
    item as item_services,
    cart as cart_services,
    wallet as wallet_services,
    consumerorder as consumer_order_services,
    vendororder as vendor_order_services
)
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
from models import user, vendor, shop, item, order, wallet, cart  # noqa: F401
migrate = Migrate(app, db, compare_type=True, render_as_batch=True)

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
