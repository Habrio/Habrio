from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import BigInteger, Integer

# Use BigInteger in production but fall back to Integer for SQLite
BIGINT = BigInteger().with_variant(Integer, "sqlite")

db = SQLAlchemy()

# Re-export common models for convenience
from .user import UserProfile  # noqa: F401
from .shop import Shop  # noqa: F401
from .order import Order  # noqa: F401
