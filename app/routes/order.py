from flask import Blueprint, request, jsonify, current_app
from app.version import API_PREFIX
from flask_limiter.util import get_remote_address
from extensions import limiter
from models import db
from models.order import (
    Order,
    OrderItem,
    OrderStatusLog,
    OrderActionLog,
    OrderMessage,
    OrderRating,
    OrderIssue,
    OrderReturn,
)
from decimal import Decimal
from app.utils import auth_required
from app.utils import role_required
from app.utils import internal_error_response
from app.utils import error, transactional
from app.services.order_service import (
    complete_return as service_complete_return,
    ValidationError,
)
from app.services.wallet_ops import InsufficientFunds
from models.shop import Shop

order_bp = Blueprint("order", __name__, url_prefix=f"{API_PREFIX}/order")

