from flask import request, jsonify
from models import db
from models.shop import Shop
from app.utils import auth_required, role_required, error
from . import consumer_bp


@consumer_bp.route("/shops", methods=["GET"])
@auth_required
@role_required(["consumer"])
def list_shops():
    user = request.user
    city, society = user.city, user.society
    status = request.args.get("status")
    shop_type = request.args.get("type")
    tags = request.args.getlist("tag")
    query = Shop.query.filter_by(city=city, society=society)
    if status == "open":
        query = query.filter_by(is_open=True)
    elif status == "closed":
        query = query.filter_by(is_open=False)
    if shop_type:
        query = query.filter(Shop.shop_type.ilike(f"%{shop_type}%"))
    if tags:
        for t in tags:
            query = query.filter(Shop.category_tags.ilike(f"%{t}%"))
    shops = query.all()
    result = []
    for s in shops:
        result.append({
            "id": s.id,
            "shop_name": s.shop_name,
            "shop_type": s.shop_type,
            "description": s.description,
            "is_open": s.is_open,
            "delivers": s.delivers,
            "appointment_only": s.appointment_only,
            "category_tags": s.category_tags,
            "logo_url": s.logo_url,
        })
    return jsonify({"status": "success", "shops": result}), 200


@consumer_bp.route("/shops/search", methods=["GET"])
@auth_required
@role_required(["consumer"])
def search_shops():
    user = request.user
    city = user.city
    society = user.society
    query_param = request.args.get("q", "").lower().strip()
    if not query_param:
        return error("Missing search query 'q'", status=400)
    results = Shop.query.filter(
        Shop.city == city,
        Shop.society == society,
        Shop.is_open == True,
        db.or_(Shop.shop_name.ilike(f"%{query_param}%"), Shop.shop_type.ilike(f"%{query_param}%")),
    ).all()
    shop_list = []
    for shop in results:
        shop_list.append({
            "id": shop.id,
            "shop_name": shop.shop_name,
            "shop_type": shop.shop_type,
            "description": shop.description,
            "is_open": shop.is_open,
            "delivers": shop.delivers,
            "appointment_only": shop.appointment_only,
            "category_tags": shop.category_tags,
            "logo_url": shop.logo_url,
        })
    return jsonify({"status": "success", "shops": shop_list}), 200
