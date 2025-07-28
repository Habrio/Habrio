from flask import Blueprint, request
from app.utils.responses import ok, error
import logging
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds
from helpers.jwt_helpers import create_access_token, create_refresh_token
from services.consumerorder import _confirm_order_core, _confirm_modified_order_core, _cancel_order_consumer_core
from services.vendororder import (
    _vendor_update_order_status_core,
    _vendor_cancel_order_core,
    _vendor_complete_return_core,
)
from models import db
from models.user import UserProfile
from models.shop import Shop
from models.item import Item
from models.cart import CartItem
from models.order import Order, OrderItem, OrderReturn
from decimal import Decimal as D


test_support_bp = Blueprint("test_support_bp", __name__)


@test_support_bp.route("/__ok", methods=["GET"])
def __ok():
    return ok({"ping": "pong"})


@test_support_bp.route("/__boom", methods=["GET"])
def __boom():
    raise RuntimeError("boom")


@test_support_bp.route("/__log", methods=["GET"])
def __log():
    logging.getLogger(__name__).info("test log line")
    from app.utils.responses import ok
    return ok({"logged": True})


@test_support_bp.route("/__auth/login_stub", methods=["POST"])
def __login_stub():
    j = request.get_json() or {}
    phone = j.get("phone", "test")
    role = j.get("role", "consumer")
    from app.utils.responses import ok
    if not UserProfile.query.filter_by(phone=phone).first():
        db.session.add(UserProfile(phone=phone, role=role))
        db.session.commit()
    return ok({
        "access": create_access_token(phone, role),
        "refresh": create_refresh_token(phone),
    })


@test_support_bp.route("/__wallet/consumer/adjust", methods=["POST"])
def __wallet_consumer_adjust():
    """Adjust consumer wallet for testing."""
    payload = request.get_json() or {}
    try:
        bal = adjust_consumer_balance(
            payload.get("phone"),
            payload.get("delta", 0),
            reference=payload.get("reference", "test"),
            type=payload.get("type", "recharge"),
            source="test",
        )
        db.session.commit()
        return ok({"balance": float(bal)})
    except InsufficientFunds as e:
        db.session.rollback()
        return error(str(e), status=400)
    except Exception:
        db.session.rollback()
        return error("wallet op failed", status=500)


@test_support_bp.route("/__wallet/vendor/adjust", methods=["POST"])
def __wallet_vendor_adjust():
    payload = request.get_json() or {}
    try:
        bal = adjust_vendor_balance(
            payload.get("phone"),
            payload.get("delta", 0),
            reference=payload.get("reference", "test"),
            type=payload.get("type", "credit"),
        )
        db.session.commit()
        return ok({"balance": float(bal)})
    except InsufficientFunds as e:
        db.session.rollback()
        return error(str(e), status=400)
    except Exception:
        db.session.rollback()
        return error("wallet op failed", status=500)


@test_support_bp.route("/__seed/basic", methods=["POST"])
def __seed_basic():
    """
    Body:
    {
      "consumer_phone": "c1",
      "vendor_phone": "v1",
      "shop_name": "S",
      "item": {"title": "Milk", "price": 50.0},
      "cart_qty": 2
    }
    Creates minimal user/vendor/shop/item and adds cart record for consumer.
    Returns: {"shop_id":..., "item_id":..., "cart_qty":...}
    """
    p = request.get_json() or {}
    cphone = p.get("consumer_phone", "c1")
    vphone = p.get("vendor_phone", "v1")
    if not UserProfile.query.filter_by(phone=cphone).first():
        db.session.add(UserProfile(phone=cphone, role="consumer", basic_onboarding_done=True))
    if not UserProfile.query.filter_by(phone=vphone).first():
        db.session.add(UserProfile(phone=vphone, role="vendor", basic_onboarding_done=True))
    db.session.flush()
    shop = Shop.query.filter_by(phone=vphone).first()
    if not shop:
        shop = Shop(shop_name=p.get("shop_name", "S"), shop_type="grocery", society="soc", city="city", phone=vphone, is_open=True)
        db.session.add(shop)
        db.session.flush()
    itm = Item(shop_id=shop.id, title=p.get("item", {}).get("title", "Milk"), price=float(p.get("item", {}).get("price", 50.0)), is_available=True, is_active=True)
    db.session.add(itm)
    db.session.flush()
    qty = int(p.get("cart_qty", 1))
    db.session.add(CartItem(user_phone=cphone, shop_id=shop.id, item_id=itm.id, quantity=qty))
    db.session.commit()
    return ok({"shop_id": shop.id, "item_id": itm.id, "cart_qty": qty})


@test_support_bp.route("/__wallet/seed", methods=["POST"])
def __wallet_seed():
    """Seed consumer wallet using adjust_consumer_balance."""
    j = request.get_json() or {}
    try:
        bal = adjust_consumer_balance(j.get("phone"), j.get("amount", 0), reference="seed", type="recharge", source="test")
        db.session.commit()
        return ok({"balance": float(bal)})
    except Exception:
        db.session.rollback()
        return error("seed failed", 500)


@test_support_bp.route("/__orders/confirm", methods=["POST"])
def __orders_confirm():
    """Call _confirm_order_core with a lightweight user object."""
    j = request.get_json() or {}
    class _U:
        pass
    u = _U()
    u.phone = j.get("phone")
    return _confirm_order_core(u, j.get("payment_mode", "cash"), j.get("delivery_notes", ""))


@test_support_bp.route("/__orders/confirm_modified/<int:order_id>", methods=["POST"])
def __orders_confirm_modified(order_id):
    """Set order state then call _confirm_modified_order_core."""
    j = request.get_json() or {}
    order = Order.query.get(order_id)
    if not order:
        return error("not found", 404)
    order.final_amount = j.get("new_final_amount", order.total_amount)
    order.status = "awaiting_consumer_confirmation"
    db.session.commit()
    class _U:
        pass
    u = _U()
    u.phone = j.get("phone")
    return _confirm_modified_order_core(u, order)


@test_support_bp.route("/__orders/cancel/<int:order_id>", methods=["POST"])
def __orders_cancel(order_id):
    j = request.get_json() or {}
    class _U:
        pass
    u = _U()
    u.phone = j.get("phone")
    order = Order.query.get(order_id)
    if not order:
        return error("not found", 404)
    return _cancel_order_consumer_core(u, order)


@test_support_bp.route("/__seed/order_paid", methods=["POST"])
def __seed_order_paid():
    """
    Body:
    {
      "consumer_phone":"c",
      "vendor_phone":"v",
      "shop_name":"S",
      "items":[{"title":"A","price":50,"qty":2},{"title":"B","price":25,"qty":1}],
      "status":"pending",  # initial status
      "wallet_paid": true  # if true, set payment_mode=wallet, payment_status=paid
    }
    Creates consumer, vendor, shop, items and an order with OrderItems.
    Does NOT auto credit or debit wallets; that will be done by test steps or route cores.
    Returns: {"order_id":..., "total":...,"final":...}
    """
    j = request.get_json() or {}
    cph = j.get("consumer_phone", "c")
    vph = j.get("vendor_phone", "v")
    if not UserProfile.query.filter_by(phone=cph).first():
        db.session.add(UserProfile(phone=cph, role="consumer", basic_onboarding_done=True))
    if not UserProfile.query.filter_by(phone=vph).first():
        db.session.add(UserProfile(phone=vph, role="vendor", basic_onboarding_done=True))
    db.session.flush()
    shop = Shop.query.filter_by(phone=vph).first()
    if not shop:
        shop = Shop(shop_name=j.get("shop_name", "S"), shop_type="grocery", society="soc", city="city", phone=vph, is_open=True)
        db.session.add(shop)
        db.session.flush()

    items = j.get("items", [{"title": "A", "price": 50, "qty": 2}])
    order = Order(
        user_phone=cph,
        shop_id=shop.id,
        status=j.get("status", "pending"),
        payment_mode="wallet" if j.get("wallet_paid", True) else "cash",
        payment_status="paid" if j.get("wallet_paid", True) else "unpaid",
        total_amount=0,
        final_amount=0,
    )
    db.session.add(order)
    db.session.flush()

    tot = D("0.00")
    for idx, it in enumerate(items, start=1):
        p = D(str(it.get("price", 0)))
        q = D(str(it.get("qty", 1)))
        subt = p * q
        tot += subt
        db.session.add(
            OrderItem(
                order_id=order.id,
                item_id=idx,
                name=it.get("title", "A"),
                unit="pcs",
                unit_price=p,
                quantity=int(q),
                subtotal=subt,
            )
        )

    order.total_amount = tot
    order.final_amount = tot
    db.session.commit()
    return ok({"order_id": order.id, "total": float(tot), "final": float(tot)})


@test_support_bp.route("/__vendor/update_status/<int:order_id>", methods=["POST"])
def __vendor_update_status(order_id):
    j = request.get_json() or {}
    class _U:
        pass
    u = _U()
    u.phone = j.get("vendor_phone")
    order = Order.query.get(order_id)
    if not order:
        return error("not found", 404)
    return _vendor_update_order_status_core(u, order, j.get("status", "delivered"))


@test_support_bp.route("/__vendor/cancel/<int:order_id>", methods=["POST"])
def __vendor_cancel(order_id):
    j = request.get_json() or {}
    class _U:
        pass
    u = _U()
    u.phone = j.get("vendor_phone")
    order = Order.query.get(order_id)
    if not order:
        return error("not found", 404)
    return _vendor_cancel_order_core(u, order)


@test_support_bp.route("/__vendor/return/prepare/<int:order_id>", methods=["POST"])
def __vendor_return_prepare(order_id):
    """
    Body: {"returns":[{"item_name":"A","quantity":1}]}
    Creates accepted OrderReturn rows for the named order items.
    """
    j = request.get_json() or {}
    order = Order.query.get(order_id)
    if not order:
        return error("not found", 404)
    order.status = "delivered"
    db.session.commit()
    for r in j.get("returns", []):
        name = r.get("item_name")
        qty = int(r.get("quantity", 1))
        oi = OrderItem.query.filter_by(order_id=order.id, name=name).first()
        if not oi:
            continue
        db.session.add(
            OrderReturn(
                order_id=order.id,
                item_id=oi.item_id,
                quantity=qty,
                reason="test",
                initiated_by="vendor",
                status="accepted",
            )
        )
    order.status = "return_accepted"
    db.session.commit()
    return ok({"prepared": True})


@test_support_bp.route("/__vendor/return/complete/<int:order_id>", methods=["POST"])
def __vendor_return_complete(order_id):
    j = request.get_json() or {}
    class _U:
        pass
    u = _U()
    u.phone = j.get("vendor_phone")
    order = Order.query.get(order_id)
    if not order:
        return error("not found", 404)
    return _vendor_complete_return_core(u, order)
