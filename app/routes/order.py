from flask import Blueprint, request, jsonify, current_app
from app.version import API_PREFIX
from flask_limiter.util import get_remote_address
from extensions import limiter
from models import db
from models.cart import CartItem
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
    confirm_order as confirm_order_service,
    confirm_modified_order as confirm_modified_order_service,
    cancel_order_by_consumer,
    update_status_by_vendor,
    cancel_order_by_vendor,
    complete_return as service_complete_return,
    ValidationError,
    ALLOWED_VENDOR_STATUSES,
)
from app.services.wallet_ops import InsufficientFunds
from models.shop import Shop

order_bp = Blueprint("order", __name__, url_prefix=f"{API_PREFIX}/order")

# ------------------- Consumer Endpoints -------------------

@order_bp.route("/confirm", methods=["POST"])
@limiter.limit(lambda: current_app.config["ORDER_LIMIT_PER_IP"], key_func=get_remote_address, error_message="Too many orders from this IP")
@auth_required
@role_required("consumer")
def confirm_order():
    user = request.user
    data = request.get_json()
    payment_mode = data.get("payment_mode", "cash")
    delivery_notes = data.get("delivery_notes", "")
    try:
        with transactional("Order confirmation failed"):
            new_order = confirm_order_service(user, payment_mode, delivery_notes)
        return jsonify({"status": "success", "message": "Order placed successfully", "order_id": new_order.id}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@order_bp.route("/history", methods=["GET"])
@auth_required
@role_required("consumer")
def get_order_history():
    user = request.user
    orders = Order.query.filter_by(user_phone=user.phone).order_by(Order.created_at.desc()).all()
    result = []
    for order in orders:
        items = OrderItem.query.filter_by(order_id=order.id).all()
        item_list = [{"name": oi.name, "quantity": oi.quantity, "unit_price": float(oi.unit_price), "subtotal": float(oi.subtotal)} for oi in items]
        result.append({
            "order_id": order.id,
            "shop_id": order.shop_id,
            "payment_mode": order.payment_mode,
            "payment_status": order.payment_status,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "final_amount": float(order.final_amount),
            "delivery_notes": order.delivery_notes,
            "created_at": order.created_at,
            "items": item_list,
        })
    return jsonify({"status": "success", "orders": result}), 200


@order_bp.route("/consumer/confirm-modified/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def confirm_modified_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    try:
        with transactional("Failed to confirm modified order"):
            refund = confirm_modified_order_service(user, order)
        return jsonify({"status": "success", "message": "Modified order confirmed", "refund": float(refund)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@order_bp.route("/consumer/cancel/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def cancel_order_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    try:
        with transactional("Failed to cancel order"):
            refund = cancel_order_by_consumer(user, order)
        return jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@order_bp.route("/consumer/message/send/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def send_order_message_consumer(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return error("Message required", status=400)
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    db.session.add(OrderMessage(order_id=order_id, sender_phone=user.phone, message=message))
    db.session.add(OrderActionLog(order_id=order_id, action_type="message_sent", actor_phone=user.phone, details=message))
    try:
        with transactional("Failed to send order message"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Message sent"}), 200


@order_bp.route("/consumer/messages/<int:order_id>", methods=["GET"])
@auth_required
@role_required("consumer")
def get_order_messages_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    messages = OrderMessage.query.filter_by(order_id=order_id).order_by(OrderMessage.timestamp.asc()).all()
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200


@order_bp.route("/rate/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def rate_order(order_id):
    user = request.user
    data = request.get_json()
    rating = data.get("rating")
    review = data.get("review", "").strip()
    if not rating or not (1 <= int(rating) <= 5):
        return error("Rating must be between 1 and 5", status=400)
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized or order not found", status=403)
    if order.status != "delivered":
        return error("Order not yet delivered", status=400)
    existing = OrderRating.query.filter_by(order_id=order_id).first()
    if existing:
        return error("Rating already submitted", status=400)
    rating_entry = OrderRating(order_id=order.id, user_phone=user.phone, rating=int(rating), review=review)
    db.session.add(rating_entry)
    db.session.add(OrderActionLog(order_id=order.id, action_type="order_rated", actor_phone=user.phone, details=f"Rated {rating}/5. {review}" if review else f"Rated {rating}/5"))
    try:
        with transactional("Failed to rate order"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Thank you for rating!", "rating": rating_entry.to_dict()}), 200


@order_bp.route("/issue/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def raise_order_issue(order_id):
    user = request.user
    data = request.get_json()
    issue_type = data.get("issue_type")
    description = data.get("description", "")
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    if order.status != "delivered":
        return error("Issue can only be raised for delivered orders", status=400)
    issue = OrderIssue(order_id=order.id, user_phone=user.phone, issue_type=issue_type, description=description)
    db.session.add(issue)
    db.session.add(OrderActionLog(order_id=order.id, action_type="issue_raised", actor_phone=user.phone, details=f"Issue: {issue_type} | {description}"))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message=f"Issue raised: {issue_type}\n{description}"))
    try:
        with transactional("Failed to raise issue"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Issue raised"}), 200


@order_bp.route("/return/raise/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def request_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    if order.status != "delivered":
        return error("Only delivered orders can be returned", status=400)
    for item in items:
        db.session.add(OrderReturn(order_id=order.id, item_id=item.get("item_id"), quantity=item.get("quantity", 1), reason=reason, initiated_by="consumer", status="requested"))
    db.session.add(OrderActionLog(order_id=order.id, actor_phone=user.phone, action_type="return_requested", details=f"{len(items)} item(s) requested for return. Reason: {reason}"))
    try:
        with transactional("Failed to request return"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return request sent"}), 200

# ------------------- Vendor Endpoints -------------------

@order_bp.route("/vendor", methods=["GET"])
@auth_required
@role_required("vendor")
def get_shop_orders():
    user = request.user
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return error("Shop not found", status=404)
    orders = Order.query.filter_by(shop_id=shop.id).order_by(Order.created_at.desc()).all()
    result = []
    for order in orders:
        item_list = [{"name": oi.name, "quantity": oi.quantity, "unit_price": float(oi.unit_price), "subtotal": float(oi.subtotal)} for oi in order.items]
        result.append({
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
        })
    return jsonify({"status": "success", "orders": result}), 200


@order_bp.route("/vendor/status/<int:order_id>", methods=["POST"])
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
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return error("Failed to update order status", status=500)


@order_bp.route("/vendor/modify/<int:order_id>", methods=["POST"])
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


@order_bp.route("/vendor/cancel/<int:order_id>", methods=["POST"])
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
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return error("Failed to cancel order", status=500)


@order_bp.route("/vendor/message/send/<int:order_id>", methods=["POST"])
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


@order_bp.route("/vendor/messages/<int:order_id>", methods=["GET"])
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


@order_bp.route("/vendor/issues", methods=["GET"])
@auth_required
@role_required("vendor")
def get_issues_for_order(order_id=None):
    user = request.user
    if order_id:
        order = Order.query.get(order_id)
    else:
        order = None
    shop = Shop.query.filter_by(phone=user.phone).first()
    if order_id and (not order or not shop or order.shop_id != shop.id):
        return error("Unauthorized", status=403)
    issues = OrderIssue.query.filter_by(order_id=order.id).order_by(OrderIssue.created_at.desc()).all() if order else []
    result = [i.to_dict() for i in issues]
    return jsonify({"status": "success", "issues": result}), 200


@order_bp.route("/return/vendor/accept/<int:order_id>", methods=["POST"])
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
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="return_accepted", actor_phone=user.phone, details="Vendor accepted the return request"))
    try:
        with transactional("Failed to accept return"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return request accepted"}), 200


@order_bp.route("/return/complete/<int:order_id>", methods=["POST"])
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
        return jsonify({"status": "success", "message": "Return marked as completed"}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return error("Failed to complete return", status=500)


@order_bp.route("/return/vendor/initiate/<int:order_id>", methods=["POST"])
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
        db.session.add(OrderReturn(order_id=order.id, item_id=item.get("item_id"), quantity=item.get("quantity", 1), reason=reason, initiated_by="vendor", status="accepted"))
    order.status = "return_accepted"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="vendor_forced_return", actor_phone=user.phone, details=f"{len(items)} item(s) returned. Reason: {reason}"))
    try:
        with transactional("Failed to initiate return"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return initiated and accepted"}), 200
