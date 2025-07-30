# === /agent/tools.py ===
from flask import request
from models.item import Item
from models.cart import CartItem


def get_available_items():
    items = Item.query.filter_by(is_available=True).limit(10).all()
    return ", ".join([f"{item.title} (₹{item.price})" for item in items]) or "No available items found."

def get_cart_summary():
    phone = getattr(request, "phone", None)
    if not phone:
        return "User not authenticated"
    items = CartItem.query.filter_by(user_phone=phone).all()
    if not items:
        return "Cart is empty."
    summary = [f"{item.item.name} (x{item.quantity})" for item in items]
    return ", ".join(summary)
