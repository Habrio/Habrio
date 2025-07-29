from flask import Blueprint
# --- services/item.py ---
from flask import request, jsonify
from app.version import API_PREFIX
from models.item import Item
from models.shop import Shop
from models import db
from app.utils import auth_required
from app.utils import role_required
from datetime import datetime
import pandas as pd
from werkzeug.utils import secure_filename
import os
import logging
item_bp = Blueprint("item", __name__, url_prefix=API_PREFIX)

from app.utils import internal_error_response

@item_bp.route("/item/add", methods=["POST"])
@auth_required
@role_required(["vendor"])
def add_item():
    user = request.user
    data = request.get_json()

    required_fields = ["title", "price"]
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    item = Item(
        shop_id=shop.id,
        title=data["title"],
        brand=data.get("brand"),
        description=data.get("description", ""),
        mrp=data.get("mrp"),
        price=data["price"],
        discount=data.get("discount"),
        quantity_in_stock=data.get("quantity_in_stock", 0),
        unit=data.get("unit", "pcs"),
        pack_size=data.get("pack_size"),
        is_available=True,
        is_active=True,
        category=data.get("category"),
        tags=data.get("tags"),
        sku=data.get("sku"),
        expiry_date=data.get("expiry_date"),
        image_url=data.get("image_url")
    )

    db.session.add(item)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to add item: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Item added"}), 200

@item_bp.route("/item/<int:item_id>/toggle", methods=["POST"])
@auth_required
@role_required(["vendor"])
def toggle_item_availability(item_id):
    user = request.user
    item = Item.query.get(item_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not item or item.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Item not found or unauthorized"}), 404

    item.is_available = not item.is_available
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to toggle item availability: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Item availability updated"}), 200

@item_bp.route("/item/update/<int:item_id>", methods=["POST"])
@auth_required
@role_required(["vendor"])
def update_item(item_id):
    user = request.user
    data = request.get_json()
    item = Item.query.get(item_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not item or item.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Item not found or unauthorized"}), 404

    item.title = data.get("title", item.title)
    item.brand = data.get("brand", item.brand)
    item.description = data.get("description", item.description)
    item.mrp = data.get("mrp", item.mrp)
    item.price = data.get("price", item.price)
    item.discount = data.get("discount", item.discount)
    item.quantity_in_stock = data.get("quantity_in_stock", item.quantity_in_stock)
    item.unit = data.get("unit", item.unit)
    item.pack_size = data.get("pack_size", item.pack_size)
    item.category = data.get("category", item.category)
    item.tags = data.get("tags", item.tags)
    item.sku = data.get("sku", item.sku)
    item.expiry_date = data.get("expiry_date", item.expiry_date)
    item.image_url = data.get("image_url", item.image_url)
    item.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to update item: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Item updated"}), 200

@item_bp.route("/item/my", methods=["GET"])
@auth_required
@role_required(["vendor"])
def get_items():
    user = request.user
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    items = Item.query.filter_by(shop_id=shop.id).all()
    result = [
        {
            "id": item.id,
            "title": item.title,
            "brand": item.brand,
            "price": item.price,
            "mrp": item.mrp,
            "discount": item.discount,
            "description": item.description,
            "quantity_in_stock": item.quantity_in_stock,
            "unit": item.unit,
            "pack_size": item.pack_size,
            "category": item.category,
            "tags": item.tags,
            "sku": item.sku,
            "expiry_date": str(item.expiry_date) if item.expiry_date else None,
            "image_url": item.image_url,
            "is_available": item.is_available,
            "is_active": item.is_active
        } for item in items
    ]
    return jsonify({"status": "success", "data": result}), 200

@item_bp.route("/item/bulk-upload", methods=["POST"])
@auth_required
@role_required(["vendor"])
def bulk_upload_items():
    user = request.user
    file = request.files.get("file")

    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    ext = filename.split('.')[-1].lower()

    try:
        if ext == "csv":
            df = pd.read_csv(file)
        elif ext in ["xls", "xlsx"]:
            df = pd.read_excel(file)
        else:
            return jsonify({"status": "error", "message": "Unsupported file type"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"File read error: {str(e)}"}), 400

    required_columns = {"title", "price"}
    if not required_columns.issubset(set(df.columns)):
        return jsonify({"status": "error", "message": f"Missing columns: {required_columns}"}), 400

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    created = 0
    for _, row in df.iterrows():
        try:
            item = Item(
                shop_id=shop.id,
                title=row["title"],
                brand=row.get("brand"),
                price=row["price"],
                mrp=row.get("mrp"),
                discount=row.get("discount"),
                quantity_in_stock=row.get("quantity_in_stock", 0),
                unit=row.get("unit"),
                pack_size=row.get("pack_size"),
                category=row.get("category"),
                tags=row.get("tags"),
                sku=row.get("sku"),
                expiry_date=row.get("expiry_date"),
                image_url=row.get("image_url"),
                description=row.get("description", ""),
                is_available=True,
                is_active=True
            )
            db.session.add(item)
            created += 1
        except Exception:
            continue

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to bulk upload items: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": f"{created} items uploaded"}), 200


# View items available in a given shop
@item_bp.route("/shop/<int:shop_id>/items", methods=["GET"])
@auth_required
@role_required(["consumer"])
def view_items_by_shop(shop_id):
    # 1. Verify shop exists and is currently open
    shop = Shop.query.get(shop_id)
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404
    if not shop.is_open:
        return jsonify({"status": "error", "message": "Shop is currently closed"}), 403

    # 2. Fetch only available items
    items = Item.query.filter_by(shop_id=shop_id, is_available=True).all()

    # 3. Build response list
    item_list = []
    for item in items:
        item_list.append({
            "id": item.id,
            "title": item.title,
            "brand": item.brand,
            "price": item.price,
            "mrp": item.mrp,
            "discount": item.discount,
            "description": item.description,
            "unit": item.unit,
            "pack_size": item.pack_size,
            "category": item.category,
            "tags": item.tags,
            "sku": item.sku,
            "expiry_date": item.expiry_date.strftime("%Y-%m-%d") if item.expiry_date else None,
            "image_url": item.image_url
        })

    return jsonify({"status": "success", "shop": {
                        "id": shop.id,
                        "shop_name": shop.shop_name,
                        "shop_type": shop.shop_type
                    }, "items": item_list}), 200
