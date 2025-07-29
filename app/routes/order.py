from flask import Blueprint, request, jsonify, current_app
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
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds
from models.shop import Shop

order_bp = Blueprint("order", __name__, url_prefix="/api/v1/order")

# ------------------- Helper functions -------------------

def _confirm_order_core(user, payment_mode, delivery_notes):
    cart_items = CartItem.query.filter_by(user_phone=user.phone).all()
    if not cart_items:
        return jsonify({"status": "error", "message": "Cart is empty"}), 400

    shop_id = cart_items[0].shop_id
    total_amount = sum(Decimal(ci.quantity) * Decimal(ci.item.price) for ci in cart_items)

    try:
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

        db.session.add(
            OrderStatusLog(order_id=new_order.id, status="pending", updated_by=user.phone)
        )
        db.session.add(
            OrderActionLog(
                order_id=new_order.id,
                action_type="order_created",
                actor_phone=user.phone,
                details="Order placed",
            )
        )

        db.session.commit()
        return (
            jsonify({"status": "success", "message": "Order placed successfully", "order_id": new_order.id}),
            200,
        )
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return internal_error_response()


def _confirm_modified_order_core(user, order):
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "awaiting_consumer_confirmation":
        return jsonify({"status": "error", "message": "Order not in modifiable state"}), 400

    old_amount = Decimal(order.total_amount)
    new_amount = Decimal(order.final_amount) if order.final_amount else old_amount

    refund_amount = Decimal(0)

    try:
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

        db.session.commit()
        return (
            jsonify({"status": "success", "message": "Modified order confirmed", "refund": float(refund_amount)}),
            200,
        )
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return internal_error_response()


def _cancel_order_consumer_core(user, order):
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status in ["cancelled", "delivered"]:
        return jsonify({"status": "error", "message": "Order already closed"}), 400

    refund_amount = Decimal(0)

    try:
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
        db.session.add(
            OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by you.")
        )

        db.session.commit()
        return (
            jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund_amount)}),
            200,
        )
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return internal_error_response()


def _vendor_update_order_status_core(user, order, new_status):
    try:
        if new_status not in ["accepted", "rejected", "delivered"]:
            return jsonify({"status": "error", "message": "Invalid status"}), 400

        if (
            new_status == "delivered"
            and order.payment_mode == "wallet"
            and order.payment_status == "paid"
        ):
            amt = Decimal(order.final_amount or order.total_amount)
            adjust_vendor_balance(
                user.phone,
                +amt,
                reference=f"Order #{order.id} delivered",
                type="credit",
                source="order_delivered",
            )

        order.status = new_status
        db.session.add(OrderStatusLog(order_id=order.id, status=new_status, updated_by=user.phone))
        db.session.add(
            OrderActionLog(
                order_id=order.id,
                action_type="status_updated",
                actor_phone=user.phone,
                details=f"Order status updated to {new_status}",
            )
        )
        db.session.commit()
        return (jsonify({"status": "success", "message": f"Order marked as {new_status}"}), 200)
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to update order status"}), 500


def _vendor_cancel_order_core(user, order):
    try:
        if order.status in ["cancelled", "delivered"]:
            return jsonify({"status": "error", "message": "Order already closed"}), 400

        refund_amount = Decimal(0)
        if order.payment_mode == "wallet":
            refund_amount = Decimal(order.total_amount)
            adjust_consumer_balance(
                order.user_phone,
                +refund_amount,
                reference=f"Order #{order.id} vendor cancel",
                type="refund",
                source="vendor_cancel",
            )

        order.status = "cancelled"
        db.session.add(OrderStatusLog(order_id=order.id, status="cancelled", updated_by=user.phone))
        db.session.add(
            OrderActionLog(
                order_id=order.id,
                action_type="order_cancelled",
                actor_phone=user.phone,
                details="Cancelled by vendor",
            )
        )
        db.session.add(
            OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by shop.")
        )
        db.session.commit()
        return (
            jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund_amount)}),
            200,
        )
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to cancel order"}), 500


def _vendor_complete_return_core(user, order):
    try:
        if order.status != "return_accepted":
            return jsonify({"status": "error", "message": "Return not accepted yet"}), 400

        returns = OrderReturn.query.filter_by(order_id=order.id, status="accepted").all()
        if not returns:
            return jsonify({"status": "error", "message": "No accepted returns found"}), 400

        from decimal import Decimal as D

        refund_total = D("0.00")
        for r in returns:
            for oi in OrderItem.query.filter_by(order_id=order.id, item_id=r.item_id).all():
                refund_total += D(str(oi.unit_price)) * D(str(r.quantity))

        for r in returns:
            r.status = "completed"

        order.status = "return_completed"
        db.session.add(OrderStatusLog(order_id=order.id, status="return_completed", updated_by=user.phone))
        db.session.add(
            OrderActionLog(
                order_id=order.id,
                action_type="return_completed",
                actor_phone=user.phone,
                details="Vendor marked return as picked up",
            )
        )

        if order.payment_mode == "wallet" and refund_total > 0:
            adjust_consumer_balance(
                order.user_phone,
                +refund_total,
                reference=f"Return refund for order #{order.id}",
                type="refund",
                source="return_completed",
            )
            adjust_vendor_balance(
                user.phone,
                -refund_total,
                reference=f"Return refund for order #{order.id}",
                type="debit",
            )

        db.session.commit()
        return jsonify({"status": "success", "message": "Return marked as completed"}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to complete return"}), 500

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
    return _confirm_order_core(user, payment_mode, delivery_notes)


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
    return _confirm_modified_order_core(user, order)


@order_bp.route("/consumer/cancel/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def cancel_order_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    return _cancel_order_consumer_core(user, order)


@order_bp.route("/consumer/message/send/<int:order_id>", methods=["POST"])
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
        return internal_error_response()
    return jsonify({"status": "success", "message": "Message sent"}), 200


@order_bp.route("/consumer/messages/<int:order_id>", methods=["GET"])
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


@order_bp.route("/rate/<int:order_id>", methods=["POST"])
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
    rating_entry = OrderRating(order_id=order.id, user_phone=user.phone, rating=int(rating), review=review)
    db.session.add(rating_entry)
    db.session.add(OrderActionLog(order_id=order.id, action_type="order_rated", actor_phone=user.phone, details=f"Rated {rating}/5. {review}" if review else f"Rated {rating}/5"))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Issue can only be raised for delivered orders"}), 400
    issue = OrderIssue(order_id=order.id, user_phone=user.phone, issue_type=issue_type, description=description)
    db.session.add(issue)
    db.session.add(OrderActionLog(order_id=order.id, action_type="issue_raised", actor_phone=user.phone, details=f"Issue: {issue_type} | {description}"))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message=f"Issue raised: {issue_type}\n{description}"))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Only delivered orders can be returned"}), 400
    for item in items:
        db.session.add(OrderReturn(order_id=order.id, item_id=item.get("item_id"), quantity=item.get("quantity", 1), reason=reason, initiated_by="consumer", status="requested"))
    db.session.add(OrderActionLog(order_id=order.id, actor_phone=user.phone, action_type="return_requested", details=f"{len(items)} item(s) requested for return. Reason: {reason}"))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
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
        return jsonify({"status": "error", "message": "Shop not found"}), 404
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
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"status": "error", "message": "Order not found"}), 404
    shop = Shop.query.get(order.shop_id)
    if not shop or shop.phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    return _vendor_update_order_status_core(user, order, new_status)


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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status in ["cancelled", "delivered"]:
        return jsonify({"status": "error", "message": "Cannot modify a closed order"}), 400
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
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return internal_error_response()
    return jsonify({"status": "success", "message": "Order modified", "new_total": float(updated_total)}), 200


@order_bp.route("/vendor/cancel/<int:order_id>", methods=["POST"])
@auth_required
@role_required("vendor:cancel_order_vendor")
def cancel_order_vendor(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"status": "error", "message": "Order not found"}), 404
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop or shop.id != order.shop_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    return _vendor_cancel_order_core(user, order)


@order_bp.route("/vendor/message/send/<int:order_id>", methods=["POST"])
@auth_required
@role_required("vendor")
def send_order_message_vendor(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return jsonify({"status": "error", "message": "Message required"}), 400
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    db.session.add(OrderMessage(order_id=order_id, sender_phone=user.phone, message=message))
    db.session.add(OrderActionLog(order_id=order_id, action_type="message_sent", actor_phone=user.phone, details=message))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    returns = OrderReturn.query.filter_by(order_id=order.id, status="requested").all()
    if not returns:
        return jsonify({"status": "error", "message": "No pending return requests"}), 400
    for r in returns:
        r.status = "accepted"
    order.status = "return_accepted"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="return_accepted", actor_phone=user.phone, details="Vendor accepted the return request"))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    return _vendor_complete_return_core(user, order)


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
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Only delivered orders can be returned"}), 400
    for item in items:
        db.session.add(OrderReturn(order_id=order.id, item_id=item.get("item_id"), quantity=item.get("quantity", 1), reason=reason, initiated_by="vendor", status="accepted"))
    order.status = "return_accepted"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="vendor_forced_return", actor_phone=user.phone, details=f"{len(items)} item(s) returned. Reason: {reason}"))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return initiated and accepted"}), 200
