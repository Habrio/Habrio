from flask import Blueprint, jsonify
from app.version import API_PREFIX
from app.utils import auth_required, role_required
from models.user import UserProfile
from models.shop import Shop
from models.order import Order

admin_bp = Blueprint("admin", __name__, url_prefix=f"{API_PREFIX}/admin")


@admin_bp.before_request
@auth_required
@role_required("admin")
def _enforce_admin_role():
    """Ensure the requester is an authenticated admin."""
    return None

@admin_bp.route("/users", methods=["GET"])
def list_users():
    users = UserProfile.query.limit(50).all()
    return jsonify({"status": "success", "users": [u.phone for u in users]}), 200

@admin_bp.route("/shops", methods=["GET"])
def list_shops():
    shops = Shop.query.limit(50).all()
    return jsonify({"status": "success", "shops": [{"id": s.id, "name": s.shop_name} for s in shops]}), 200

@admin_bp.route("/orders", methods=["GET"])
def list_orders():
    orders = Order.query.order_by(Order.id.desc()).limit(50).all()
    return jsonify({"status": "success", "orders": [{"id": o.id, "status": o.status} for o in orders]}), 200
