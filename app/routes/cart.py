from flask import Blueprint
from flask import request, jsonify
from models.cart import CartItem
from models.shop import Shop
from models.item import Item
from models.user import UserProfile
from models import db
from app.utils import auth_required
from app.utils import role_required
import logging
from app.utils import internal_error_response
cart_bp = Blueprint("cart", __name__, url_prefix="/api/v1/cart")


MAX_QUANTITY_PER_ITEM = 10  # Set your max quantity per item limit here

# Add item to cart
@cart_bp.route("/add", methods=["POST"])
@auth_required
@role_required("consumer")
def add_to_cart():
    data = request.get_json()
    phone = request.phone
    item_id = data.get("item_id")
    quantity = data.get("quantity", 1)

    item = Item.query.get(item_id)
    if not item or not item.is_available:
        return jsonify({"status": "error", "message": "Item not available"}), 404

    if quantity < 1:
        return jsonify({"status": "error", "message": "Quantity must be at least 1"}), 400

    if quantity > MAX_QUANTITY_PER_ITEM:
        return jsonify({"status": "error", "message": f"Cannot add more than {MAX_QUANTITY_PER_ITEM} units per item"}), 400

    existing_items = CartItem.query.filter_by(user_phone=phone).all()
    if existing_items:
        if any(ci.shop_id != item.shop_id for ci in existing_items):
            return jsonify({"status": "error", "message": "Cart contains items from a different shop"}), 400

    cart_item = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
    if cart_item:
        new_quantity = cart_item.quantity + quantity
        if new_quantity > MAX_QUANTITY_PER_ITEM:
            return jsonify({"status": "error", "message": f"Max limit is {MAX_QUANTITY_PER_ITEM} units"}), 400
        cart_item.quantity = new_quantity
    else:
        cart_item = CartItem(user_phone=phone, item_id=item_id, shop_id=item.shop_id, quantity=quantity)
        db.session.add(cart_item)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to add to cart: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Item added to cart"}), 200


# Update quantity of an item
@cart_bp.route("/update", methods=["POST"])
@auth_required
@role_required("consumer")
def update_cart_quantity():
    data = request.get_json()
    phone = request.phone
    item_id = data.get("item_id")
    quantity = data.get("quantity")

    if not item_id or quantity is None:
        return jsonify({"status": "error", "message": "Item ID and quantity required"}), 400

    if quantity < 1 or quantity > MAX_QUANTITY_PER_ITEM:
        return jsonify({"status": "error", "message": f"Quantity must be between 1 and {MAX_QUANTITY_PER_ITEM}"}), 400

    cart_item = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
    if not cart_item:
        return jsonify({"status": "error", "message": "Item not found in cart"}), 404

    cart_item.quantity = quantity
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to update cart quantity: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Cart quantity updated"}), 200


# View cart with availability and price refresh
@cart_bp.route("/view", methods=["GET"])
@auth_required
@role_required("consumer")
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
            "item_name": item.title,                   # ✅ corrected from item.name
            "available": available,
            "price": price,
            "mrp": mrp,
            "savings": round(item_savings, 2),
            "quantity": quantity,
            "unit": item.unit,
            "pack_size": item.pack_size,
            "subtotal": round(subtotal, 2),
            "shop_id": shop.id,
            "shop_name": shop.shop_name               # ✅ corrected from shop.name
        })

    return jsonify({
        "status": "success",
        "cart": cart_data,
        "total_price": round(total_price, 2),
        "total_savings": round(savings, 2)
    }), 200



@cart_bp.route("/remove", methods=["POST"])
# Remove single item
@auth_required
@role_required("consumer")
def remove_item():
    data = request.get_json()
    phone = request.phone
    item_id = data.get("item_id")

    cart_item = CartItem.query.filter_by(user_phone=phone, item_id=item_id).first()
    if cart_item:
        db.session.delete(cart_item)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error("Failed to remove cart item: %s", e, exc_info=True)
            return internal_error_response()
        return jsonify({"status": "success", "message": "Item removed"}), 200

    return jsonify({"status": "error", "message": "Item not found"}), 404


# Clear cart
@cart_bp.route("/clear", methods=["POST"])
@auth_required
@role_required("consumer")
def clear_cart():
    phone = request.phone
    CartItem.query.filter_by(user_phone=phone).delete()
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to clear cart: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Cart cleared"}), 200
