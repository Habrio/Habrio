from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

# Global limiter instance used across the app
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATELIMIT_STORAGE_URL", "memory://"),
    strategy="fixed-window",
    default_limits=["200 per hour"],
)
