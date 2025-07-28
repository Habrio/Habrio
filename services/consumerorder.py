from flask import request, jsonify
from models import db
from models.cart import CartItem
from decimal import Decimal
from models.wallet import ConsumerWallet, WalletTransaction
from models.order import Order, OrderItem, OrderStatusLog, OrderActionLog, OrderMessage, OrderRating, OrderIssue, OrderReturn
from datetime import datetime
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
import logging
from utils.responses import internal_error_response

# ------------------- Confirm Order -------------------
@auth_required
@role_required("consumer")
def confirm_order():
    user = request.user
    data = request.get_json()
    payment_mode = data.get("payment_mode", "cash")
    delivery_notes = data.get("delivery_notes", "")

    cart_items = CartItem.query.filter_by(user_phone=user.phone).all()
    if not cart_items:
        return jsonify({"status": "error", "message": "Cart is empty"}), 400

    shop_id = cart_items[0].shop_id
    total_amount = sum(Decimal(ci.quantity) * Decimal(ci.item.price) for ci in cart_items)

    # Wallet balance check
    if payment_mode == "wallet":
        wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
        if not wallet or wallet.balance < total_amount:
            return jsonify({"status": "error", "message": "Insufficient wallet balance"}), 400
        wallet.balance -= total_amount

    # Create Order
    new_order = Order(
        user_phone=user.phone,
        shop_id=shop_id,
        payment_mode=payment_mode,
        payment_status="paid" if payment_mode == "wallet" else "unpaid",
        delivery_notes=delivery_notes,
        total_amount=total_amount,
        final_amount=total_amount,
        status="pending"
    )
    db.session.add(new_order)
    db.session.flush()

    # Add WalletTransaction if applicable
    if payment_mode == "wallet":
        db.session.add(WalletTransaction(
            user_phone=user.phone,
            type="debit",
            amount=total_amount,
            reference=f"Order #{new_order.id}",
            status="success"
        ))

    # Add Order Items
    for ci in cart_items:
        db.session.add(OrderItem(
            order_id=new_order.id,
            item_id=ci.item.id,
            name=ci.item.title,
            unit=ci.item.unit,
            unit_price=ci.item.price,
            quantity=ci.quantity,
            subtotal=Decimal(ci.quantity) * Decimal(ci.item.price)
        ))

    # Clear cart
    CartItem.query.filter_by(user_phone=user.phone).delete()

    # Log status and action
    db.session.add(OrderStatusLog(order_id=new_order.id, status="pending", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=new_order.id, action_type="order_created", actor_phone=user.phone, details="Order placed"))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to confirm order: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Order placed successfully", "order_id": new_order.id}), 200


# ------------------- Confirm Modified Order -------------------
@auth_required
@role_required("consumer")
def confirm_modified_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "awaiting_consumer_confirmation":
        return jsonify({"status": "error", "message": "Order not in modifiable state"}), 400

    old_amount = Decimal(order.total_amount)
    new_amount = Decimal(order.final_amount) if order.final_amount else old_amount

    refund_amount = Decimal(0)
    if order.payment_mode == "wallet" and new_amount < old_amount:
        refund_amount = old_amount - new_amount
        wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
        wallet.balance += refund_amount
        db.session.add(WalletTransaction(
            user_phone=user.phone,
            amount=refund_amount,
            type="refund",
            reference=f"Order #{order.id}",
            status="success"
        ))

    order.status = "confirmed"
    order.total_amount = new_amount
    db.session.add(OrderStatusLog(order_id=order.id, status="confirmed", updated_by=user.phone))
    db.session.add(OrderActionLog(
        order_id=order.id,
        action_type="modification_confirmed",
        actor_phone=user.phone,
        details=f"Confirmed modified order. Refund: ₹{float(refund_amount)}"
    ))
    db.session.add(OrderMessage(
        order_id=order.id,
        sender_phone=user.phone,
        message="I’ve confirmed the changes. Please proceed."
    ))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to confirm modified order: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Modified order confirmed", "refund": float(refund_amount)}), 200


# ------------------- Cancel Order -------------------
@auth_required
@role_required("consumer")
def cancel_order_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status in ["cancelled", "delivered"]:
        return jsonify({"status": "error", "message": "Order already closed"}), 400

    refund_amount = Decimal(0)
    if order.payment_mode == "wallet":
        refund_amount = Decimal(order.total_amount)
        wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
        wallet.balance += refund_amount
        db.session.add(WalletTransaction(
            user_phone=user.phone,
            amount=refund_amount,
            type="refund",
            reference=f"Order #{order.id}",
            status="success"
        ))

    order.status = "cancelled"
    db.session.add(OrderStatusLog(order_id=order.id, status="cancelled", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="order_cancelled", actor_phone=user.phone, details="Cancelled by consumer"))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by you."))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to cancel order: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund_amount)}), 200


# ------------------- Send Order Message -------------------
@auth_required
@role_required("consumer")
def send_order_message_consumer(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return jsonify({"status": "error", "message": "Message required"}), 400

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    db.session.add(OrderMessage(order_id=order_id, sender_phone=user.phone, message=message))
    db.session.add(OrderActionLog(order_id=order_id, action_type="message_sent", actor_phone=user.phone, details=message))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to send order message: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Message sent"}), 200


# ------------------- Get Order Messages -------------------
@auth_required
@role_required("consumer")
def get_order_messages_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    messages = OrderMessage.query.filter_by(order_id=order_id).order_by(OrderMessage.timestamp.asc()).all()
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200


# ------------------- Get Order History -------------------
@auth_required
@role_required("consumer")
def get_order_history():
    user = request.user
    orders = Order.query.filter_by(user_phone=user.phone).order_by(Order.created_at.desc()).all()
    result = []

    for order in orders:
        items = OrderItem.query.filter_by(order_id=order.id).all()
        item_list = [{
            "name": oi.name,
            "quantity": oi.quantity,
            "unit_price": float(oi.unit_price),
            "subtotal": float(oi.subtotal)
        } for oi in items]

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
            "items": item_list
        })

    return jsonify({"status": "success", "orders": result}), 200

# ------------------- Rate Order -------------------

@auth_required
@role_required("consumer")
def rate_order(order_id):
    user = request.user
    data = request.get_json()
    rating = data.get("rating")
    review = data.get("review", "").strip()

    if not rating or not (1 <= int(rating) <= 5):
        return jsonify({"status": "error", "message": "Rating must be between 1 and 5"}), 400

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized or order not found"}), 403

    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Order not yet delivered"}), 400

    existing = OrderRating.query.filter_by(order_id=order_id).first()
    if existing:
        return jsonify({"status": "error", "message": "Rating already submitted"}), 400

    # Save Rating
    rating_entry = OrderRating(
        order_id=order.id,
        user_phone=user.phone,
        rating=int(rating),
        review=review
    )
    db.session.add(rating_entry)

    # Log Action
    db.session.add(OrderActionLog(
        order_id=order.id,
        action_type="order_rated",
        actor_phone=user.phone,
        details=f"Rated {rating}/5. {review}" if review else f"Rated {rating}/5"
    ))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to rate order: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({
        "status": "success",
        "message": "Thank you for rating!",
        "rating": rating_entry.to_dict()
    }), 200

# ------------------- Raise Order Issue-------------------

@auth_required
@role_required("consumer")
def raise_order_issue(order_id):
    user = request.user
    data = request.get_json()
    issue_type = data.get("issue_type")
    description = data.get("description", "")

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Issue can only be raised for delivered orders"}), 400

    issue = OrderIssue(
        order_id=order.id,
        user_phone=user.phone,
        issue_type=issue_type,
        description=description,
    )
    db.session.add(issue)

    # Log action & send message to vendor
    db.session.add(OrderActionLog(
        order_id=order.id,
        action_type="issue_raised",
        actor_phone=user.phone,
        details=f"Issue: {issue_type} | {description}"
    ))
    db.session.add(OrderMessage(
        order_id=order.id,
        sender_phone=user.phone,
        message=f"Issue raised: {issue_type}\n{description}"
    ))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to raise order issue: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Issue raised"}), 200

# ------------------- Request return -------------------

@auth_required
@role_required("consumer")
def request_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])  # [{"item_id": 1, "quantity": 1}, ...]

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Only delivered orders can be returned"}), 400

    for item in items:
        db.session.add(OrderReturn(
            order_id=order.id,
            item_id=item.get("item_id"),
            quantity=item.get("quantity", 1),
            reason=reason,
            initiated_by="consumer",
            status="requested"
        ))

    db.session.add(OrderActionLog(
        order_id=order.id,
        actor_phone=user.phone,
        action_type="return_requested",
        details=f"{len(items)} item(s) requested for return. Reason: {reason}"
    ))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to request return: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Return request sent"}), 200
