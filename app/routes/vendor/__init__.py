from flask import Blueprint, request, jsonify
from app.version import API_PREFIX
from models import db
from app.utils import auth_required
from app.utils import role_required
import logging
from app.utils import internal_error_response
from app.utils import error, transactional
from app.services import vendor_service
from app.services.vendor_service import ValidationError
from app.services import shop_service
from app.services.shop_service import ValidationError as ShopValidationError
from models.shop import Shop, ShopHours, ShopActionLog
from datetime import datetime
from decimal import Decimal
from models.order import (
    Order,
    OrderItem,
    OrderStatusLog,
    OrderActionLog,
    OrderMessage,
    OrderIssue,
    OrderReturn,
)
from app.services.order_service import (
    update_status_by_vendor,
    cancel_order_by_vendor,
    ValidationError as OrderValidationError,
    ALLOWED_VENDOR_STATUSES,
    complete_return as service_complete_return,
)
from app.services.wallet_ops import InsufficientFunds
from app.utils import has_required_fields

vendor_bp = Blueprint("vendor", __name__, url_prefix=f"{API_PREFIX}/vendor")

# Vendor Onboarding -----------------
@vendor_bp.route("/profile", methods=["POST"])
@auth_required
@role_required(["vendor"])
def vendor_profile_setup():
    user = request.user
    data = request.get_json()
    required = ["business_type", "business_name", "address"]
    if not has_required_fields(data, required):
        return error("Missing required vendor details", status=400)
    try:
        with transactional("Failed to create vendor profile"):
            vendor_service.create_vendor_profile(user, data)
        return jsonify({"status": "success", "message": "Vendor profile created"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()

# Vendor Onboarding Documents-----------------
@vendor_bp.route("/upload-document", methods=["POST"])
@auth_required
@role_required(["vendor"])
def upload_vendor_document():
    user = request.user
    data = request.get_json()

    doc_type = data.get("document_type")
    file_url = data.get("file_url")
    try:
        with transactional("Failed to upload vendor document"):
            vendor_service.add_document(user, doc_type, file_url)
        return jsonify({"status": "success", "message": "Document uploaded"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()

# Vendor Payout info ----------------
@vendor_bp.route("/payout/setup", methods=["POST"])
@auth_required
@role_required(["vendor"])
def setup_payout_bank():
    user = request.user
    data = request.get_json()
    try:
        with transactional("Failed to setup payout bank"):
            vendor_service.setup_payout(user, data)
        return jsonify({"status": "success", "message": "Payout bank info saved"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()


# ------------ Shop Management Endpoints -------------

@vendor_bp.route("/shop", methods=["POST"])
@auth_required
@role_required(["vendor"])
def create_shop():
    """Create a shop for the authenticated vendor."""
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
    """Edit the vendor's existing shop."""
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
    """Return the vendor's shop details."""
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
    """Replace the stored hours for the vendor's shop."""
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
    """Mark the shop open or closed."""
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


# ------------ Order Management Endpoints -------------

@vendor_bp.route("/orders", methods=["GET"])
@auth_required
@role_required("vendor")
def get_shop_orders():
    """List orders for the vendor's shop."""
    user = request.user
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return error("Shop not found", status=404)
    orders = Order.query.filter_by(shop_id=shop.id).order_by(Order.created_at.desc()).all()
    result = []
    for order in orders:
        item_list = [
            {
                "name": oi.name,
                "quantity": oi.quantity,
                "unit_price": float(oi.unit_price),
                "subtotal": float(oi.subtotal),
            }
            for oi in order.items
        ]
        result.append(
            {
                "order_id": order.id,
                "customer": order.user_phone,
                "payment_mode": order.payment_mode,
                "payment_status": order.payment_status,
                "status": order.status,
                "total_amount": float(order.total_amount),
                "final_amount": float(order.final_amount),
                "delivery_notes": order.delivery_notes,
                "created_at": order.created_at,
                "items": item_list,
            }
        )
    return jsonify({"status": "success", "orders": result}), 200


@vendor_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@auth_required
@role_required("vendor:deliver_order")
def update_order_status(order_id):
    user = request.user
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ALLOWED_VENDOR_STATUSES:
        return error("Invalid status", status=400)
    order = Order.query.get(order_id)
    if not order:
        return error("Order not found", status=404)
    shop = Shop.query.get(order.shop_id)
    if not shop or shop.phone != user.phone:
        return error("Unauthorized", status=403)
    try:
        with transactional("Failed to update order status"):
            update_status_by_vendor(user, order, new_status)
        return jsonify({"status": "success", "message": f"Order marked as {new_status}"}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except OrderValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return error("Failed to update order status", status=500)


@vendor_bp.route("/orders/<int:order_id>/modify", methods=["POST"])
@auth_required
@role_required("vendor:modify_order")
def modify_order_item(order_id):
    user = request.user
    data = request.get_json()
    modifications = data.get("modifications", [])
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return error("Unauthorized", status=403)
    if order.status in ["cancelled", "delivered"]:
        return error("Cannot modify a closed order", status=400)
    updated_total = Decimal(0)
    update_log = []
    for mod in modifications:
        item_id = mod.get("item_id")
        new_qty = mod.get("quantity")
        order_item = OrderItem.query.filter_by(order_id=order.id, item_id=item_id).first()
        if order_item:
            if new_qty == 0:
                db.session.delete(order_item)
                update_log.append(f"Removed item {item_id}")
            else:
                order_item.quantity = new_qty
                order_item.subtotal = Decimal(new_qty) * Decimal(order_item.unit_price)
                update_log.append(f"Updated item {item_id} to qty {new_qty}")
    db.session.flush()
    updated_items = OrderItem.query.filter_by(order_id=order.id).all()
    updated_total = sum(Decimal(oi.quantity) * Decimal(oi.unit_price) for oi in updated_items)
    order.final_amount = updated_total
    order.status = "awaiting_consumer_confirmation"
    db.session.add(OrderStatusLog(order_id=order.id, status="awaiting_consumer_confirmation", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="vendor_modified", actor_phone=user.phone, details="; ".join(update_log)))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order modified. Awaiting your confirmation."))
    try:
        with transactional("Failed to modify order"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Order modified", "new_total": float(updated_total)}), 200


@vendor_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@auth_required
@role_required("vendor:cancel_order_vendor")
def cancel_order_vendor(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order:
        return error("Order not found", status=404)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop or shop.id != order.shop_id:
        return error("Unauthorized", status=403)
    try:
        with transactional("Failed to cancel order"):
            refund = cancel_order_by_vendor(user, order)
        return jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except OrderValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return error("Failed to cancel order", status=500)


@vendor_bp.route("/orders/<int:order_id>/message", methods=["POST"])
@auth_required
@role_required("vendor")
def send_order_message_vendor(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return error("Message required", status=400)
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return error("Unauthorized", status=403)
    db.session.add(OrderMessage(order_id=order_id, sender_phone=user.phone, message=message))
    db.session.add(OrderActionLog(order_id=order_id, action_type="message_sent", actor_phone=user.phone, details=message))
    try:
        with transactional("Failed to send order message"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Message sent"}), 200


@vendor_bp.route("/orders/<int:order_id>/messages", methods=["GET"])
@auth_required
@role_required("vendor")
def get_order_messages_vendor(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return error("Unauthorized", status=403)
    messages = OrderMessage.query.filter_by(order_id=order_id).order_by(OrderMessage.timestamp.asc()).all()
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200


# -------- Return and Issue Endpoints ---------

@vendor_bp.route("/orders/issues", methods=["GET"])
@auth_required
@role_required("vendor")
def get_order_issues():
    """List issues for a given order if order_id provided."""
    user = request.user
    order_id = request.args.get("order_id", type=int)
    if order_id:
        order = Order.query.get(order_id)
    else:
        order = None
    shop = Shop.query.filter_by(phone=user.phone).first()
    if order_id and (not order or not shop or order.shop_id != shop.id):
        return error("Unauthorized", status=403)
    issues = (
        OrderIssue.query.filter_by(order_id=order.id)
        .order_by(OrderIssue.created_at.desc())
        .all()
        if order
        else []
    )
    result = [i.to_dict() for i in issues]
    return jsonify({"status": "success", "issues": result}), 200


@vendor_bp.route("/orders/<int:order_id>/return/accept", methods=["POST"])
@auth_required
@role_required("vendor")
def accept_return(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return error("Unauthorized", status=403)
    returns = OrderReturn.query.filter_by(order_id=order.id, status="requested").all()
    if not returns:
        return error("No pending return requests", status=400)
    for r in returns:
        r.status = "accepted"
    order.status = "return_accepted"
    db.session.add(
        OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone)
    )
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="return_accepted",
            actor_phone=user.phone,
            details="Vendor accepted the return request",
        )
    )
    try:
        with transactional("Failed to accept return"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return request accepted"}), 200


@vendor_bp.route("/orders/<int:order_id>/return/complete", methods=["POST"])
@auth_required
@role_required("vendor")
def complete_return(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return error("Unauthorized", status=403)
    try:
        with transactional("Failed to complete return"):
            service_complete_return(user, order)
        return (
            jsonify({"status": "success", "message": "Return marked as completed"}),
            200,
        )
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except OrderValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return error("Failed to complete return", status=500)


@vendor_bp.route("/orders/<int:order_id>/return/initiate", methods=["POST"])
@auth_required
@role_required("vendor")
def vendor_initiate_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return error("Unauthorized", status=403)
    if order.status != "delivered":
        return error("Only delivered orders can be returned", status=400)
    for item in items:
        db.session.add(
            OrderReturn(
                order_id=order.id,
                item_id=item.get("item_id"),
                quantity=item.get("quantity", 1),
                reason=reason,
                initiated_by="vendor",
                status="accepted",
            )
        )
    order.status = "return_accepted"
    db.session.add(
        OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone)
    )
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="vendor_forced_return",
            actor_phone=user.phone,
            details=f"{len(items)} item(s) returned. Reason: {reason}",
        )
    )
    try:
        with transactional("Failed to initiate return"):
            pass
    except Exception:
        return internal_error_response()
    return (
        jsonify({"status": "success", "message": "Return initiated and accepted"}),
        200,
    )

