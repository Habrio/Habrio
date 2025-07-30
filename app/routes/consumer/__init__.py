from flask import Blueprint
from app.version import API_PREFIX

consumer_bp = Blueprint("consumer", __name__, url_prefix=f"{API_PREFIX}/consumer")

from . import profile  # noqa: E402
from . import cart  # noqa: E402
from . import wallet  # noqa: E402
from . import orders  # noqa: E402
from . import shops  # noqa: E402
from . import agent  # noqa: E402
from . import items  # noqa: E402
