from decimal import Decimal
from models import db
from models.order import (
    Order,
    OrderItem,
    OrderStatusLog,
    OrderActionLog,
    OrderMessage,
)
from models.cart import CartItem
from models.item import Item
from app.services.wallet_ops import adjust_consumer_balance


class ValidationError(Exception):
    pass


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


__all__ = [
    "ValidationError",
    "confirm_order_service",
    "confirm_modified_order_service",
    "cancel_order_by_consumer",
]
