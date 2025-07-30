from flask import request, jsonify
from decimal import Decimal
from models import db
from models.shop import Shop
from models.order import (
    Order,
    OrderItem,
    OrderStatusLog,
    OrderActionLog,
    OrderMessage,
    OrderIssue,
    OrderReturn,
)
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds
from app.utils import auth_required, role_required, transactional, error, internal_error_response
from . import vendor_bp

class OrderValidationError(Exception):
    pass

ALLOWED_VENDOR_STATUSES = ["accepted", "rejected", "delivered"]

def update_status_by_vendor(user, order: Order, new_status: str):
    if new_status not in ALLOWED_VENDOR_STATUSES:
        raise OrderValidationError("Invalid status")
    if new_status == "delivered" and order.payment_mode == "wallet" and order.payment_status == "paid":
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

def cancel_order_by_vendor(user, order: Order) -> Decimal:
    if order.status in ["cancelled", "delivered"]:
        raise OrderValidationError("Order already closed")
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
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by shop."))
    return refund_amount

def service_complete_return(user, order: Order) -> Decimal:
    if order.status != "return_accepted":
        raise OrderValidationError("Return not accepted yet")
    returns = OrderReturn.query.filter_by(order_id=order.id, status="accepted").all()
    if not returns:
        raise OrderValidationError("No accepted returns found")
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
    return refund_total


@vendor_bp.route("/orders", methods=["GET"])
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


@vendor_bp.route("/orders/issues", methods=["GET"])
@auth_required
@role_required("vendor")
def get_order_issues():
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
