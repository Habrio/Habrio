from flask import Blueprint
from app.version import API_PREFIX
from app.utils import auth_required, role_required

consumer_bp = Blueprint("consumer", __name__, url_prefix=f"{API_PREFIX}/consumer")


@consumer_bp.before_request
@auth_required
@role_required("consumer")
def _enforce_consumer_role():
    """Ensure the requester is an authenticated consumer."""
    return None

from . import profile  # noqa: E402
from . import cart  # noqa: E402
from . import wallet  # noqa: E402
from . import orders  # noqa: E402
from . import shops  # noqa: E402
from . import agent  # noqa: E402
from . import items  # noqa: E402
