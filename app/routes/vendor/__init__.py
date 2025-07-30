from flask import Blueprint
from app.version import API_PREFIX

vendor_bp = Blueprint("vendor", __name__, url_prefix=f"{API_PREFIX}/vendor")

from . import profile  # noqa: E402
from . import shop  # noqa: E402
from . import orders  # noqa: E402
from . import wallet  # noqa: E402
