from flask import request, jsonify
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
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from decimal import Decimal
import logging
from utils.responses import internal_error_response
from app.services.wallet_ops import (
    adjust_consumer_balance,
    adjust_vendor_balance,
    InsufficientFunds,
)


def _vendor_update_order_status_core(user, order, new_status):
    """Core logic for vendor updating order status without auth."""
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
        db.session.add(
            OrderStatusLog(order_id=order.id, status=new_status, updated_by=user.phone)
        )
        db.session.add(
            OrderActionLog(
                order_id=order.id,
                action_type="status_updated",
                actor_phone=user.phone,
                details=f"Order status updated to {new_status}",
            )
        )
        db.session.commit()
        return (
            jsonify({"status": "success", "message": f"Order marked as {new_status}"}),
            200,
        )
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to update order status"}), 500


def _vendor_cancel_order_core(user, order):
    """Core logic for vendor cancelling an order."""
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
        db.session.add(
            OrderStatusLog(order_id=order.id, status="cancelled", updated_by=user.phone)
        )
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
    """Mark return completed and handle wallet adjustments."""
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
        db.session.add(
            OrderStatusLog(order_id=order.id, status="return_completed", updated_by=user.phone)
        )
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
                source="return_completed",
            )

        db.session.commit()
        return jsonify({"status": "success", "message": "Return marked as completed"}), 200
    except InsufficientFunds as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error", "message": "Failed to complete return"}), 500

# ------------------- Vendor: View Orders -------------------
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
        item_list = [{
            "name": oi.name,
            "quantity": oi.quantity,
            "unit_price": float(oi.unit_price),
            "subtotal": float(oi.subtotal)
        } for oi in order.items]

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
            "items": item_list
        })

    return jsonify({"status": "success", "orders": result}), 200


# ------------------- Vendor: Update Order Status -------------------

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

# ------------------- Vendor: Cancel Order -------------------
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


# ------------------- Vendor: Modify Order -------------------
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
        logging.error("Failed to modify order items: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Order modified", "new_total": float(updated_total)}), 200


# ------------------- Vendor: Send Message -------------------
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

    db.session.add(OrderMessage(
        order_id=order_id,
        sender_phone=user.phone,
        message=message
    ))
    db.session.add(OrderActionLog(
        order_id=order_id,
        action_type="message_sent",
        actor_phone=user.phone,
        details=message
    ))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to send vendor order message: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Message sent"}), 200


# ------------------- Vendor: Get Messages -------------------
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

# ------------------- Vendor: Get order issues -------------------

@auth_required
@role_required("vendor")
def get_issues_for_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    issues = OrderIssue.query.filter_by(order_id=order.id).order_by(OrderIssue.created_at.desc()).all()
    result = [i.to_dict() for i in issues]

    return jsonify({"status": "success", "issues": result}), 200

# ------------------- Vendor: Create return-------------------
@auth_required
@role_required("vendor")
def vendor_initiate_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])  # [{"item_id": 1, "quantity": 1}, ...]

    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Only delivered orders can be returned"}), 400

    for item in items:
        db.session.add(OrderReturn(
            order_id=order.id,
            item_id=item.get("item_id"),
            quantity=item.get("quantity", 1),
            reason=reason,
            initiated_by="vendor",
            status="accepted"  # ✅ No need for consumer to approve
        ))

    order.status = "return_accepted"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="vendor_forced_return", actor_phone=user.phone, details=f"{len(items)} item(s) returned. Reason: {reason}"))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to initiate return: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Return initiated and accepted"}), 200


# ------------------- Vendor: Accept return-------------------

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
        logging.error("Failed to accept return: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Return request accepted"}), 200


# ------------------- Vendor: Complete Retrun-------------------

@auth_required
@role_required("vendor")
def complete_return(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    return _vendor_complete_return_core(user, order)
