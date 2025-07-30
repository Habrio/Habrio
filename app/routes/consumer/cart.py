from flask import request, jsonify
from models import db
from models.cart import CartItem
from models.item import Item
from decimal import Decimal
from app.utils import transactional, error, internal_error_response
from . import consumer_bp


@consumer_bp.route("/cart/add", methods=["POST"])
def add_to_cart():
    data = request.get_json()
    phone = request.phone
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)
    item = Item.query.get(item_id)
    if not item or not item.is_available:
        return error("Item not available", status=404)
    if quantity < 1:
        return error("Quantity must be at least 1", status=400)
    MAX_QUANTITY_PER_ITEM = 10
    if quantity > MAX_QUANTITY_PER_ITEM:
        return error(f"Cannot add more than {MAX_QUANTITY_PER_ITEM} units per item", status=400)
    existing_items = CartItem.query.filter_by(user_phone=phone).all()
    if existing_items:
        if any(ci.shop_id != item.shop_id for ci in existing_items):
            return error("Cart contains items from a different shop", status=400)
    cart_item = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
    if cart_item:
        new_quantity = cart_item.quantity + quantity
        if new_quantity > MAX_QUANTITY_PER_ITEM:
            return error(f"Max limit is {MAX_QUANTITY_PER_ITEM} units", status=400)
        cart_item.quantity = new_quantity
    else:
        cart_item = CartItem(user_phone=phone, item_id=item_id, shop_id=item.shop_id, quantity=quantity)
        db.session.add(cart_item)
    try:
        with transactional("Failed to add to cart"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Item added to cart"}), 200


@consumer_bp.route("/cart/update", methods=["POST"])
def update_cart_quantity():
    data = request.get_json()
    phone = request.phone
    item_id = data.get("item_id")
    quantity = data.get("quantity")
    MAX_QUANTITY_PER_ITEM = 10
    if not item_id or quantity is None:
        return error("Item ID and quantity required", status=400)
    if quantity < 1 or quantity > MAX_QUANTITY_PER_ITEM:
        return error(f"Quantity must be between 1 and {MAX_QUANTITY_PER_ITEM}", status=400)
    cart_item = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
    if not cart_item:
        return error("Item not found in cart", status=404)
    cart_item.quantity = quantity
    try:
        with transactional("Failed to update cart quantity"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Cart quantity updated"}), 200


@consumer_bp.route("/cart/view", methods=["GET"])
def view_cart():
    phone = request.phone
    items = CartItem.query.filter_by(user_phone=phone).all()
    cart_data = []
    total_price = 0.0
    savings = 0.0
    for cart_item in items:
        item = cart_item.item
        shop = cart_item.shop
        available = item.is_available
        price = item.price
        mrp = item.mrp
        quantity = cart_item.quantity
        subtotal = price * quantity
        item_savings = (mrp - price) * quantity if mrp and price < mrp else 0
        total_price += subtotal
        savings += item_savings
        cart_data.append({
            "id": cart_item.id,
            "item_id": item.id,
            "item_name": item.title,
            "available": available,
            "price": price,
            "mrp": mrp,
            "savings": round(item_savings, 2),
            "quantity": quantity,
            "unit": item.unit,
            "pack_size": item.pack_size,
            "subtotal": round(subtotal, 2),
            "shop_id": shop.id,
            "shop_name": shop.shop_name,
        })
    return jsonify({
        "status": "success",
        "cart": cart_data,
        "total_price": round(total_price, 2),
        "total_savings": round(savings, 2),
    }), 200


@consumer_bp.route("/cart/remove", methods=["POST"])
def remove_item():
    data = request.get_json()
    phone = request.phone
    item_id = data.get("item_id")
    cart_item = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
    if cart_item:
        db.session.delete(cart_item)
        try:
            with transactional("Failed to remove cart item"):
                pass
        except Exception:
            return internal_error_response()
        return jsonify({"status": "success", "message": "Item removed"}), 200
    return error("Item not found", status=404)


@consumer_bp.route("/cart/clear", methods=["POST"])
def clear_cart():
    phone = request.phone
    CartItem.query.filter_by(user_phone=phone).delete()
    try:
        with transactional("Failed to clear cart"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Cart cleared"}), 200
