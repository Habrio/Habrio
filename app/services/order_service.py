from decimal import Decimal
from typing import List
from models import db
from models.cart import CartItem
from models.order import (
    Order, OrderItem, OrderStatusLog, OrderActionLog, OrderMessage, OrderReturn
)
from models.item import Item
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds

class ValidationError(Exception):
    pass


def confirm_order(user, payment_mode: str = "cash", delivery_notes: str = "") -> Order:
    cart_items: List[CartItem] = CartItem.query.filter_by(user_phone=user.phone).all()
    if not cart_items:
        raise ValidationError("Cart is empty")
    shop_id = cart_items[0].shop_id
    total_amount = sum(Decimal(ci.quantity) * Decimal(ci.item.price) for ci in cart_items)

    # lock items and update stock
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


def confirm_modified_order(user, order: Order) -> Decimal:
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


def update_status_by_vendor(user, order: Order, new_status: str):
    if new_status not in ["accepted", "rejected", "delivered"]:
        raise ValidationError("Invalid status")
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
        raise ValidationError("Order already closed")
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


def complete_return(user, order: Order) -> Decimal:
    if order.status != "return_accepted":
        raise ValidationError("Return not accepted yet")
    returns = OrderReturn.query.filter_by(order_id=order.id, status="accepted").all()
    if not returns:
        raise ValidationError("No accepted returns found")
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
