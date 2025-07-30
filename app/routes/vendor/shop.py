from flask import request, jsonify
from datetime import datetime
import logging
from models import db
from models.shop import Shop, ShopHours, ShopActionLog
from app.services import shop_service
from app.services.shop_service import ValidationError as ShopValidationError
from app.utils import (
    auth_required,
    role_required,
    transactional,
    error,
    internal_error_response,
    has_required_fields,
)
from . import vendor_bp


@vendor_bp.route("/shop", methods=["POST"])
@auth_required
@role_required(["vendor"])
def create_shop():
    user = request.user
    data = request.get_json()
    try:
        with transactional("Failed to create shop"):
            shop_service.create_shop_for_vendor(user, data)
        return jsonify({"status": "success", "message": "Shop created"}), 200
    except ShopValidationError as e:
        return error(str(e), status=400)
    except Exception as e:
        logging.error("Failed to create shop: %s", e, exc_info=True)
        return internal_error_response()


@vendor_bp.route("/shop/edit", methods=["POST"])
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


@vendor_bp.route("/shop/my", methods=["GET"])
@auth_required
@role_required(["vendor"])
def get_vendor_shop():
    user = request.user
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
        "featured": shop.featured,
    }
    return jsonify({"status": "success", "data": result}), 200


@vendor_bp.route("/shop/hours", methods=["POST"])
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
    ShopHours.query.filter_by(shop_id=shop.id).delete()
    for entry in weekly_hours:
        day = entry.get("day_of_week")
        open_time = entry.get("open_time")
        close_time = entry.get("close_time")
        if day is None or open_time in [None, "", "Closed"] or close_time in [None, "", "Closed"]:
            continue
        try:
            open_dt = datetime.strptime(open_time, "%H:%M").time()
            close_dt = datetime.strptime(close_time, "%H:%M").time()
        except ValueError:
            continue
        new_hour = ShopHours(
            shop_id=shop.id,
            day_of_week=day,
            open_time=open_dt,
            close_time=close_dt,
        )
        db.session.add(new_hour)
    try:
        with transactional("Failed to update shop hours"):
            pass
    except Exception as e:
        logging.error("Failed to update shop hours: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Shop hours updated"}), 200


@vendor_bp.route("/shop/toggle-status", methods=["POST"])
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
