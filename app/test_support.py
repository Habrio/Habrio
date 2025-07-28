from flask import Blueprint, request
from app.utils.responses import ok, error
import logging
from app.services.wallet_ops import adjust_consumer_balance, adjust_vendor_balance, InsufficientFunds
from services.consumerorder import _confirm_order_core, _confirm_modified_order_core, _cancel_order_consumer_core
from models import db
from models.user import UserProfile
from models.shop import Shop
from models.item import Item
from models.cart import CartItem
from models.order import Order


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
