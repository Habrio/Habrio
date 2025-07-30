from app.routes import (
    auth_bp,
    user_bp,
    vendor_bp,
    shop_bp,
    item_bp,
    consumer_bp,
    wallet_bp,
    order_bp,
    admin_bp,
    agent_bp,
)
import os
import logging


def register_api_v1(app):
    """Register blueprint routes under the API version prefix."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(vendor_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(item_bp)
    app.register_blueprint(consumer_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(admin_bp)
    if os.environ.get("OPENAI_API_KEY") and agent_bp:
        logging.info("Agent blueprint enabled")
        app.register_blueprint(agent_bp)
    else:
        logging.info("Agent blueprint not enabled")

