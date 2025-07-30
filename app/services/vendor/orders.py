from decimal import Decimal
from models import db
from models.order import (
    Order,
    OrderItem,
    OrderStatusLog,
    OrderActionLog,
    OrderMessage,
    OrderReturn,
)
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance


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


__all__ = [
    "ALLOWED_VENDOR_STATUSES",
    "OrderValidationError",
    "update_status_by_vendor",
    "cancel_order_by_vendor",
    "service_complete_return",
]
