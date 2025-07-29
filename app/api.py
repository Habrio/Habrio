from app.routes import (
    auth_bp,
    user_bp,
    vendor_bp,
    shop_bp,
    item_bp,
    cart_bp,
    wallet_bp,
    order_bp,
    admin_bp,
)


def register_api_v1(app):
    """Register blueprint routes under the API version prefix."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(vendor_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(item_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(wallet_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(admin_bp)

