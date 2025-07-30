from flask import request, jsonify, current_app
from flask_limiter.util import get_remote_address
from extensions import limiter
from decimal import Decimal
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
from models.cart import CartItem
from models.item import Item
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds
from app.utils import auth_required, role_required, transactional, error, internal_error_response
from . import consumer_bp

class ValidationError(Exception):
    pass

ALLOWED_VENDOR_STATUSES = ["accepted", "rejected", "delivered"]

def confirm_order_service(user, payment_mode: str = "cash", delivery_notes: str = ""):
    cart_items = CartItem.query.filter_by(user_phone=user.phone).all()
    if not cart_items:
        raise ValidationError("Cart is empty")
    shop_id = cart_items[0].shop_id
    total_amount = sum(Decimal(ci.quantity) * Decimal(ci.item.price) for ci in cart_items)

    for ci in cart_items:
        item = Item.query.filter_by(id=ci.item_id).with_for_update().one()
        if item.quantity_in_stock is not None:
            if item.quantity_in_stock < ci.quantity:
                raise ValidationError(f"Not enough stock for item {item.title}")
            item.quantity_in_stock -= ci.quantity

    if payment_mode == "wallet":
        adjust_consumer_balance(
            user.phone,
            -total_amount,
            reference="Order debit (pre-create)",
            type="debit",
            source="order_confirm",
        )

    new_order = Order(
        user_phone=user.phone,
        shop_id=shop_id,
        payment_mode=payment_mode,
        payment_status="paid" if payment_mode == "wallet" else "unpaid",
        delivery_notes=delivery_notes,
        total_amount=total_amount,
        final_amount=total_amount,
        status="pending",
    )
    db.session.add(new_order)
    db.session.flush()

    for ci in cart_items:
        db.session.add(
            OrderItem(
                order_id=new_order.id,
                item_id=ci.item.id,
                name=ci.item.title,
                unit=ci.item.unit,
                unit_price=ci.item.price,
                quantity=ci.quantity,
                subtotal=Decimal(ci.quantity) * Decimal(ci.item.price),
            )
        )

    CartItem.query.filter_by(user_phone=user.phone).delete()

    db.session.add(OrderStatusLog(order_id=new_order.id, status="pending", updated_by=user.phone))
    db.session.add(
        OrderActionLog(
            order_id=new_order.id,
            action_type="order_created",
            actor_phone=user.phone,
            details="Order placed",
        )
    )
    return new_order

def confirm_modified_order_service(user, order: Order) -> Decimal:
    if not order or order.user_phone != user.phone:
        raise ValidationError("Unauthorized")
    if order.status != "awaiting_consumer_confirmation":
        raise ValidationError("Order not in modifiable state")
    old_amount = Decimal(order.total_amount)
    new_amount = Decimal(order.final_amount) if order.final_amount else old_amount
    refund_amount = Decimal(0)
    if order.payment_mode == "wallet" and new_amount < old_amount:
        delta = old_amount - new_amount
        refund_amount = delta
        adjust_consumer_balance(
            user.phone,
            delta,
            reference=f"Order #{order.id} modification refund",
            type="refund",
            source="order_modify",
        )
    order.status = "confirmed"
    order.total_amount = new_amount
    db.session.add(OrderStatusLog(order_id=order.id, status="confirmed", updated_by=user.phone))
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="modification_confirmed",
            actor_phone=user.phone,
            details=f"Confirmed modified order. Refund: ₹{float(refund_amount)}",
        )
    )
    db.session.add(
        OrderMessage(
            order_id=order.id,
            sender_phone=user.phone,
            message="I’ve confirmed the changes. Please proceed.",
        )
    )
    return refund_amount

def cancel_order_by_consumer(user, order: Order) -> Decimal:
    if not order or order.user_phone != user.phone:
        raise ValidationError("Unauthorized")
    if order.status in ["cancelled", "delivered"]:
        raise ValidationError("Order already closed")
    refund_amount = Decimal(0)
    if order.payment_mode == "wallet":
        refund_amount = Decimal(order.total_amount)
        adjust_consumer_balance(
            user.phone,
            refund_amount,
            reference=f"Order #{order.id} cancel refund",
            type="refund",
            source="order_cancel",
        )
    order.status = "cancelled"
    db.session.add(OrderStatusLog(order_id=order.id, status="cancelled", updated_by=user.phone))
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="order_cancelled",
            actor_phone=user.phone,
            details="Cancelled by consumer",
        )
    )
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by you."))
    return refund_amount


@consumer_bp.route("/order/confirm", methods=["POST"])
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


@consumer_bp.route("/order/history", methods=["GET"])
@auth_required
@role_required("consumer")
def get_order_history():
    user = request.user
    orders = Order.query.filter_by(user_phone=user.phone).order_by(Order.created_at.desc()).all()
    result = []
    for order in orders:
        items = OrderItem.query.filter_by(order_id=order.id).all()
        item_list = [
            {"name": oi.name, "quantity": oi.quantity, "unit_price": float(oi.unit_price), "subtotal": float(oi.subtotal)}
            for oi in items
        ]
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


@consumer_bp.route("/order/confirm-modified/<int:order_id>", methods=["POST"])
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


@consumer_bp.route("/order/cancel/<int:order_id>", methods=["POST"])
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


@consumer_bp.route("/order/message/send/<int:order_id>", methods=["POST"])
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


@consumer_bp.route("/order/messages/<int:order_id>", methods=["GET"])
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


@consumer_bp.route("/order/rate/<int:order_id>", methods=["POST"])
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
    return jsonify({"status": "success", "message": "Thank you for rating!", "rating": rating_entry.to_dict()}), 200


@consumer_bp.route("/order/issue/<int:order_id>", methods=["POST"])
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
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="issue_raised",
            actor_phone=user.phone,
            details=f"Issue: {issue_type} | {description}",
        )
    )
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message=f"Issue raised: {issue_type}\n{description}"))
    try:
        with transactional("Failed to raise issue"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Issue raised"}), 200


@consumer_bp.route("/order/return/raise/<int:order_id>", methods=["POST"])
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
