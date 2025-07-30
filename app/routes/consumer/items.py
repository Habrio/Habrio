from flask import request, jsonify
from app.utils import error
from models.item import Item
from models.shop import Shop
from . import consumer_bp

@consumer_bp.route('/shop/<int:shop_id>/items', methods=['GET'])
def view_items_by_shop(shop_id):
    shop = Shop.query.get(shop_id)
    if not shop:
        return error("Shop not found", status=404)
    if not shop.is_open:
        return error("Shop is currently closed", status=403)
    items = Item.query.filter_by(shop_id=shop_id, is_available=True).all()
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
            "expiry_date": item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else None,
            "image_url": item.image_url
        })
    return jsonify({
        "status": "success",
        "shop": {
            "id": shop.id,
            "shop_name": shop.shop_name,
            "shop_type": shop.shop_type
        },
        "items": item_list
    }), 200

