from .auth import auth_bp
from .user import user_bp
from .vendor import vendor_bp
from .shop import shop_bp
from .item import item_bp
from .cart import cart_bp
from .wallet import wallet_bp
from .order import order_bp
from .admin import admin_bp
try:
    from .agent import agent_bp
except Exception:  # pragma: no cover - agent optional
    agent_bp = None


__all__ = [
    'auth_bp',
    'user_bp',
    'vendor_bp',
    'shop_bp',
    'item_bp',
    'cart_bp',
    'wallet_bp',
    'order_bp',
    'admin_bp',
    'agent_bp',
]
