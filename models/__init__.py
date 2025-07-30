from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Re-export common models for convenience
from .user import UserProfile  # noqa: F401
from .shop import Shop  # noqa: F401
from .order import Order  # noqa: F401
