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
from flask import request, g
import uuid

# --- Load Environment Variables ---
load_dotenv()

# Create app and load configuration
app = Flask(__name__)
app.config.from_object(get_config_class())
configure_logging(app)

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
@app.route("/health")
def health():
    return {"status": "ok", "base_url": "https://2e6bee57-c137-4144-90f2-64265943227d-00-c6d7jiueybzk.pike.replit.dev"}, 200

# ===================== Auth Routes and basic onboarding ====================
app.add_url_rule("/send-otp", view_func=auth_services.send_otp_handler, methods=["POST"])
app.add_url_rule("/verify-otp", view_func=auth_services.verify_otp_handler, methods=["POST"])
app.add_url_rule("/logout", view_func=auth_services.logout_handler, methods=["POST"])
app.add_url_rule("/onboarding/basic", view_func=user_services.basic_onboarding, methods=["POST"])

# ========================== Consumer Routes ==========================
# Onboarding
app.add_url_rule("/onboarding/consumer", view_func=user_services.consumer_onboarding, methods=["POST"])

# Profile
app.add_url_rule("/profile/me", view_func=user_services.get_consumer_profile, methods=["GET"])
app.add_url_rule("/profile/edit", view_func=user_services.edit_consumer_profile, methods=["POST"])

# Wallet
app.add_url_rule("/wallet", view_func=wallet_services.get_or_create_wallet, methods=["GET"])
app.add_url_rule("/wallet/history", view_func=wallet_services.wallet_transaction_history, methods=["GET"])
app.add_url_rule("/wallet/load", view_func=wallet_services.load_wallet, methods=["POST"])
app.add_url_rule("/wallet/debit", view_func=wallet_services.debit_wallet, methods=["POST"])
app.add_url_rule("/wallet/refund", view_func=wallet_services.refund_wallet, methods=["POST"])

# Shops & Items
app.add_url_rule("/shops", view_func=shop_services.list_shops, methods=["GET"])
app.add_url_rule("/shops/search", view_func=shop_services.search_shops, methods=["GET"])
app.add_url_rule("/items/shop/<int:shop_id>", view_func=item_services.view_items_by_shop, methods=["GET"])

# Cart
app.add_url_rule("/cart/add", view_func=cart_services.add_to_cart, methods=["POST"])
app.add_url_rule("/cart/view", view_func=cart_services.view_cart, methods=["GET"])
app.add_url_rule("/cart/update", view_func=cart_services.update_cart_quantity, methods=["POST"])
app.add_url_rule("/cart/remove", view_func=cart_services.remove_item, methods=["POST"])
app.add_url_rule("/cart/clear", view_func=cart_services.clear_cart, methods=["POST"])

# Consumer Orders
app.add_url_rule("/order/confirm", view_func=consumer_order_services.confirm_order, methods=["POST"])
app.add_url_rule("/order/history", view_func=consumer_order_services.get_order_history, methods=["GET"])
app.add_url_rule("/order/consumer/confirm-modified/<int:order_id>", view_func=consumer_order_services.confirm_modified_order, methods=["POST"])
app.add_url_rule("/order/consumer/cancel/<int:order_id>", view_func=consumer_order_services.cancel_order_consumer, methods=["POST"])
app.add_url_rule("/order/consumer/message/send/<int:order_id>", view_func=consumer_order_services.send_order_message_consumer, methods=["POST"])
app.add_url_rule("/order/consumer/messages/<int:order_id>", view_func=consumer_order_services.get_order_messages_consumer, methods=["GET"])
app.add_url_rule("/order/rate/<int:order_id>", view_func=consumer_order_services.rate_order, methods=["POST"])
app.add_url_rule("/order/issue/<int:order_id>", view_func=consumer_order_services.raise_order_issue, methods=["POST"])
app.add_url_rule("/order/return/raise/<int:order_id>", view_func=consumer_order_services.request_return, methods=["POST"])

# ========================== Vendor Routes ==========================
# Onboarding & Shop Setup
app.add_url_rule("/vendor/profile", view_func=vendor_services.vendor_profile_setup, methods=["POST"])
app.add_url_rule("/vendor/upload-document", view_func=vendor_services.upload_vendor_document, methods=["POST"])
app.add_url_rule("/vendor/create-shop", view_func=shop_services.create_shop, methods=["POST"])
app.add_url_rule("/vendor/payout/setup", view_func=vendor_services.setup_payout_bank, methods=["POST"])

# Shop Management
app.add_url_rule("/shop/update-hours", view_func=shop_services.update_shop_hours, methods=["POST"])
app.add_url_rule("/shop/edit", view_func=shop_services.edit_shop, methods=["POST"])
app.add_url_rule("/shop/my", view_func=shop_services.get_my_shop, methods=["GET"])
app.add_url_rule("/vendor/shop/toggle_status", view_func=shop_services.toggle_shop_status, methods=["POST"])

# Items
app.add_url_rule("/item/add", view_func=item_services.add_item, methods=["POST"])
app.add_url_rule("/item/bulk-upload", view_func=item_services.bulk_upload_items, methods=["POST"])
app.add_url_rule("/item/<int:item_id>/toggle", view_func=item_services.toggle_item_availability, methods=["POST"])
app.add_url_rule("/item/update/<int:item_id>", view_func=item_services.update_item, methods=["POST"])
app.add_url_rule("/item/my", view_func=item_services.get_items, methods=["GET"])

# Vendor Wallet
app.add_url_rule("/vendor/wallet", view_func=wallet_services.get_vendor_wallet, methods=["GET"])
app.add_url_rule("/vendor/wallet/history", view_func=wallet_services.get_vendor_wallet_history, methods=["GET"])
app.add_url_rule("/vendor/wallet/credit", view_func=wallet_services.credit_vendor_wallet, methods=["POST"])
app.add_url_rule("/vendor/wallet/debit", view_func=wallet_services.debit_vendor_wallet, methods=["POST"])
app.add_url_rule("/vendor/wallet/withdraw", view_func=wallet_services.withdraw_vendor_wallet, methods=["POST"])

# Vendor Orders
app.add_url_rule("/order/vendor", view_func=vendor_order_services.get_shop_orders, methods=["GET"])
app.add_url_rule("/order/vendor/status/<int:order_id>", view_func=vendor_order_services.update_order_status, methods=["POST"])
app.add_url_rule("/order/vendor/modify/<int:order_id>", view_func=vendor_order_services.modify_order_item, methods=["POST"])
app.add_url_rule("/order/vendor/cancel/<int:order_id>", view_func=vendor_order_services.cancel_order_vendor, methods=["POST"])
app.add_url_rule("/order/vendor/message/send/<int:order_id>", view_func=vendor_order_services.send_order_message_vendor, methods=["POST"])
app.add_url_rule("/order/vendor/messages/<int:order_id>", view_func=vendor_order_services.get_order_messages_vendor, methods=["GET"])
app.add_url_rule("/order/vendor/issues", view_func=vendor_order_services.get_issues_for_order, methods=["GET"])
app.add_url_rule("/order/return/vendor/accept/<int:order_id>", view_func=vendor_order_services.accept_return, methods=["POST"])
app.add_url_rule("/order/return/complete/<int:order_id>", view_func=vendor_order_services.complete_return, methods=["POST"])
app.add_url_rule("/order/return/vendor/initiate/<int:order_id>", view_func=vendor_order_services.vendor_initiate_return, methods=["POST"])

# ========================== Run ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
