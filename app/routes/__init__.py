from .onboarding.auth import auth_bp
from .onboarding.user import user_bp
from .vendor import vendor_bp
from .vendor.items import item_bp
from .consumer import consumer_bp
from .admin import admin_bp
try:
    from .consumer.agent import agent_bp
except Exception:  # pragma: no cover - agent optional
    agent_bp = None


__all__ = [
    'auth_bp',
    'user_bp',
    'vendor_bp',
    'consumer_bp',
    'admin_bp',
    'agent_bp',
    'item_bp',
]
