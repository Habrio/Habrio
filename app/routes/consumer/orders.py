from flask import request, jsonify, current_app
from flask_limiter.util import get_remote_address
from extensions import limiter
from models import db
from models.order import (
    Order,
    OrderItem,
    OrderActionLog,
    OrderMessage,
    OrderRating,
    OrderIssue,
    OrderReturn,
)
from app.services.consumer.wallet import InsufficientFunds
from app.utils import transactional, error, internal_error_response
from . import consumer_bp
from app.services.consumer.orders import (
    ValidationError,
    confirm_order_service,
    confirm_modified_order_service,
    cancel_order_by_consumer,
)


@consumer_bp.route("/order/confirm", methods=["POST"])
@limiter.limit(
    lambda: current_app.config["ORDER_LIMIT_PER_IP"],
    key_func=get_remote_address,
    error_message="Too many orders from this IP",
)
def confirm_order():
    user = request.user
    data = request.get_json()
    payment_mode = data.get("payment_mode", "cash")
    delivery_notes = data.get("delivery_notes", "")
    try:
        with transactional("Order confirmation failed"):
            new_order = confirm_order_service(user, payment_mode, delivery_notes)
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Order placed successfully",
                    "order_id": new_order.id,
                }
            ),
            200,
        )
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@consumer_bp.route("/order/history", methods=["GET"])
def get_order_history():
    user = request.user
    orders = (
        Order.query.filter_by(user_phone=user.phone)
        .order_by(Order.created_at.desc())
        .all()
    )
    result = []
    for order in orders:
        items = OrderItem.query.filter_by(order_id=order.id).all()
        item_list = [
            {
                "name": oi.name,
                "quantity": oi.quantity,
                "unit_price": float(oi.unit_price),
                "subtotal": float(oi.subtotal),
            }
            for oi in items
        ]
        result.append(
            {
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
            }
        )
    return jsonify({"status": "success", "orders": result}), 200


@consumer_bp.route("/orders/<int:order_id>/confirm-modified", methods=["POST"])
def confirm_modified_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    try:
        with transactional("Failed to confirm modified order"):
            refund = confirm_modified_order_service(user, order)
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Modified order confirmed",
                    "refund": float(refund),
                }
            ),
            200,
        )
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@consumer_bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    try:
        with transactional("Failed to cancel order"):
            refund = cancel_order_by_consumer(user, order)
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Order cancelled",
                    "refund": float(refund),
                }
            ),
            200,
        )
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@consumer_bp.route("/orders/<int:order_id>/message", methods=["POST"])
def send_order_message_consumer(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return error("Message required", status=400)
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    db.session.add(
        OrderMessage(order_id=order_id, sender_phone=user.phone, message=message)
    )
    db.session.add(
        OrderActionLog(
            order_id=order_id,
            action_type="message_sent",
            actor_phone=user.phone,
            details=message,
        )
    )
    try:
        with transactional("Failed to send order message"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Message sent"}), 200


@consumer_bp.route("/orders/<int:order_id>/messages", methods=["GET"])
def get_order_messages_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    messages = (
        OrderMessage.query.filter_by(order_id=order_id)
        .order_by(OrderMessage.timestamp.asc())
        .all()
    )
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200


@consumer_bp.route("/orders/<int:order_id>/rate", methods=["POST"])
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
    rating_entry = OrderRating(
        order_id=order.id, user_phone=user.phone, rating=int(rating), review=review
    )
    db.session.add(rating_entry)
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="order_rated",
            actor_phone=user.phone,
            details=f"Rated {rating}/5. {review}" if review else f"Rated {rating}/5",
        )
    )
    try:
        with transactional("Failed to rate order"):
            pass
    except Exception:
        return internal_error_response()
    return (
        jsonify(
            {
                "status": "success",
                "message": "Thank you for rating!",
                "rating": rating_entry.to_dict(),
            }
        ),
        200,
    )


@consumer_bp.route("/orders/<int:order_id>/issue", methods=["POST"])
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
    issue = OrderIssue(
        order_id=order.id,
        user_phone=user.phone,
        issue_type=issue_type,
        description=description,
    )
    db.session.add(issue)
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="issue_raised",
            actor_phone=user.phone,
            details=f"Issue: {issue_type} | {description}",
        )
    )
    db.session.add(
        OrderMessage(
            order_id=order.id,
            sender_phone=user.phone,
            message=f"Issue raised: {issue_type}\n{description}",
        )
    )
    try:
        with transactional("Failed to raise issue"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Issue raised"}), 200


@consumer_bp.route("/orders/<int:order_id>/return/raise", methods=["POST"])
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
        db.session.add(
            OrderReturn(
                order_id=order.id,
                item_id=item.get("item_id"),
                quantity=item.get("quantity", 1),
                reason=reason,
                initiated_by="consumer",
                status="requested",
            )
        )
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            actor_phone=user.phone,
            action_type="return_requested",
            details=f"{len(items)} item(s) requested for return. Reason: {reason}",
        )
    )
    try:
        with transactional("Failed to request return"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return request sent"}), 200
