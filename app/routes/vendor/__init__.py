from flask import Blueprint
from app.version import API_PREFIX
from app.utils import auth_required, role_required

vendor_bp = Blueprint("vendor", __name__, url_prefix=f"{API_PREFIX}/vendor")


@vendor_bp.before_request
@auth_required
@role_required("vendor")
def _enforce_vendor_role():
    """Ensure the requester is an authenticated vendor."""
    return None

from . import profile  # noqa: E402
from . import shop  # noqa: E402
from . import orders  # noqa: E402
from . import wallet  # noqa: E402
from . import items  # noqa: E402
