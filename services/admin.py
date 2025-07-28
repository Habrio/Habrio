from flask import Blueprint, jsonify
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from models.user import UserProfile
from models.shop import Shop
from models.order import Order

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route("/users", methods=["GET"])
@auth_required
@role_required("admin")
def list_users():
    users = UserProfile.query.limit(50).all()
    return jsonify({"status": "success", "users": [u.phone for u in users]}), 200

@admin_bp.route("/shops", methods=["GET"])
@auth_required
@role_required("admin")
def list_shops():
    shops = Shop.query.limit(50).all()
    return jsonify({"status": "success", "shops": [{"id": s.id, "name": s.shop_name} for s in shops]}), 200

@admin_bp.route("/orders", methods=["GET"])
@auth_required
@role_required("admin")
def list_orders():
    orders = Order.query.order_by(Order.id.desc()).limit(50).all()
    return jsonify({"status": "success", "orders": [{"id": o.id, "status": o.status} for o in orders]}), 200
