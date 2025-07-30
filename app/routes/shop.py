from flask import Blueprint
from flask import request, jsonify
from app.version import API_PREFIX
from models.shop import Shop, ShopHours, ShopActionLog
from datetime import datetime
from models import db
from app.utils import auth_required
from app.utils import role_required
import logging
shop_bp = Blueprint("shop", __name__, url_prefix=API_PREFIX)

from app.utils import internal_error_response
from app.utils import error, transactional
from app.services import shop_service
from app.services.shop_service import ValidationError

# --- Create shop by vendor ---
@shop_bp.route("/vendor/create-shop", methods=["POST"])
@auth_required
@role_required(["vendor"])
def create_shop():
    user = request.user
    data = request.get_json()
    try:
        with transactional("Failed to create shop"):
            shop_service.create_shop_for_vendor(user, data)
        return jsonify({"status": "success", "message": "Shop created"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception as e:
        logging.error("Failed to create shop: %s", e, exc_info=True)
        return internal_error_response()

@shop_bp.route("/shop/edit", methods=["POST"])
# --- Edit shop by vendor ---
@auth_required
@role_required(["vendor"])
def edit_shop():
    user = request.user
    data = request.get_json()

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return error("Shop not found", status=404)

    shop.shop_name = data.get("shop_name", shop.shop_name)
    shop.shop_type = data.get("shop_type", shop.shop_type)
    shop.society = data.get("society", shop.society)
    shop.description = data.get("description", shop.description)
    shop.delivers = data.get("delivers", shop.delivers)
    shop.appointment_only = data.get("appointment_only", shop.appointment_only)
    shop.is_open = data.get("is_open", shop.is_open)
    shop.category_tags = data.get("category_tags", shop.category_tags)
    shop.logo_url = data.get("logo_url", shop.logo_url)
    shop.featured = data.get("featured", shop.featured)
    shop.verified = data.get("verified", shop.verified)

    try:
        with transactional("Failed to edit shop"):
            pass
    except Exception as e:
        logging.error("Failed to edit shop: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Shop updated"}), 200

# --- Get shop by vendor ---
@shop_bp.route("/shop/my", methods=["GET"])
@auth_required
@role_required(["vendor", "admin"])
def get_my_shop():
    user = request.user

    if user.role == "vendor":
        shop = Shop.query.filter_by(phone=user.phone).first()
        if not shop:
            return error("Shop not found", status=404)

        result = {
            "id": shop.id,
            "shop_name": shop.shop_name,
            "shop_type": shop.shop_type,
            "society": shop.society,
            "phone": shop.phone,
            "description": shop.description,
            "delivers": shop.delivers,
            "appointment_only": shop.appointment_only,
            "is_open": shop.is_open,
            "logo_url": shop.logo_url,
            "category_tags": shop.category_tags,
            "verified": shop.verified,
            "featured": shop.featured
        }
        return jsonify({"status": "success", "data": result}), 200

    else:  # admin sees all shops
        shops = Shop.query.all()
        result = [{
            "id": s.id,
            "shop_name": s.shop_name,
            "shop_type": s.shop_type,
            "society": s.society,
            "phone": s.phone,
            "description": s.description,
            "delivers": s.delivers,
            "appointment_only": s.appointment_only,
            "is_open": s.is_open,
            "logo_url": s.logo_url,
            "category_tags": s.category_tags,
            "verified": s.verified,
            "featured": s.featured
        } for s in shops]
        return jsonify({"status": "success", "data": result}), 200

# --- Update shop hours ---
@shop_bp.route("/shop/update-hours", methods=["POST"])
@auth_required
@role_required(["vendor"])
def update_shop_hours():
    user = request.user
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not shop:
        return error("Shop not found", status=404)

    data = request.get_json()
    weekly_hours = data.get("weekly_hours")

    if not weekly_hours:
        return error("No hours data provided", status=400)

    # Clear previous hours
    ShopHours.query.filter_by(shop_id=shop.id).delete()

    for entry in weekly_hours:
        day = entry.get("day_of_week")
        open_time = entry.get("open_time")
        close_time = entry.get("close_time")

        # Skip if closed or incomplete
        if day is None or open_time in [None, "", "Closed"] or close_time in [None, "", "Closed"]:
            continue

        try:
            open_dt = datetime.strptime(open_time, "%H:%M").time()
            close_dt = datetime.strptime(close_time, "%H:%M").time()
        except ValueError:
            continue  # Skip invalid time format

        new_hour = ShopHours(
            shop_id=shop.id,
            day_of_week=day,
            open_time=open_dt,
            close_time=close_dt
        )
        db.session.add(new_hour)

    try:
        with transactional("Failed to update shop hours"):
            pass
    except Exception as e:
        logging.error("Failed to update shop hours: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Shop hours updated"}), 200

# Toggle shop status --------------------

@shop_bp.route("/vendor/shop/toggle_status", methods=["POST"])
@auth_required
@role_required(["vendor"])
def toggle_shop_status():
    user = request.user
    data = request.get_json()
    new_status = data.get("is_open")

    if new_status not in [True, False]:
        return error("Invalid is_open value", status=400)

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return error("Shop not found", status=404)

    shop.is_open = new_status
    timestamp = datetime.utcnow()

    if new_status:
        shop.last_opened_at = timestamp
        action = "opened"
    else:
        shop.last_closed_at = timestamp
        action = "closed"

    log = ShopActionLog(shop_id=shop.id, action=action, timestamp=timestamp)
    db.session.add(log)
    try:
        with transactional("Failed to toggle shop status"):
            pass
    except Exception as e:
        logging.error("Failed to toggle shop status: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": f"Shop marked as {action}"}), 200

