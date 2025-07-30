from flask import Blueprint, request, jsonify, current_app
from flask_limiter.util import get_remote_address
from extensions import limiter
from app.version import API_PREFIX
from models import db
from models.user import ConsumerProfile
from models.cart import CartItem
from models.item import Item
from models.order import (
    Order,
    OrderItem,
    OrderStatusLog,
    OrderActionLog,
    OrderMessage,
    OrderRating,
    OrderIssue,
    OrderReturn,
)
from models.shop import Shop
from models.wallet import ConsumerWallet, WalletTransaction
from models.vendor import VendorPayoutBank
from decimal import Decimal
from app.utils import (
    auth_required,
    role_required,
    error,
    has_required_fields,
    transactional,
    internal_error_response,
)
from app.services.order_service import (
    confirm_order as confirm_order_service,
    confirm_modified_order as confirm_modified_order_service,
    cancel_order_by_consumer,
    ValidationError,
)
from app.services.wallet_ops import (
    adjust_consumer_balance,
    InsufficientFunds,
)

consumer_bp = Blueprint("consumer", __name__, url_prefix=f"{API_PREFIX}/consumer")

# --- Onboarding ---
@consumer_bp.route("/onboarding", methods=["POST"])
@auth_required
@role_required(["consumer"])
def consumer_onboarding():
    user = request.user
    if not user or not user.basic_onboarding_done:
        return error("Basic onboarding incomplete", status=400)
    if user.role_onboarding_done:
        return error("Role onboarding already done", status=400)

    data = request.get_json()

    existing = ConsumerProfile.query.filter_by(user_phone=request.phone).first()
    if existing:
        return error("Profile already exists", status=400)

    consumer_profile = ConsumerProfile(
        user_phone=request.phone,
        name=user.name,
        city=user.city,
        society=user.society,
        flat_number=data.get("flat_number"),
        profile_image_url=data.get("profile_image_url"),
        gender=data.get("gender"),
        date_of_birth=data.get("date_of_birth"),
        preferred_language=data.get("preferred_language"),
    )

    try:
        with transactional("Failed consumer onboarding"):
            db.session.add(consumer_profile)
            user.role_onboarding_done = True
    except Exception:
        return internal_error_response()

    return jsonify({"status": "success", "message": "Consumer onboarding done"}), 200


@consumer_bp.route("/profile/me", methods=["GET"])
@auth_required
@role_required(["consumer"])
def get_consumer_profile():
    user = request.user
    if not user:
        return error("User not found", status=404)

    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()
    if not profile:
        return error("Consumer profile not found", status=404)

    data = profile.to_dict()
    return jsonify({"status": "success", "data": data}), 200


@consumer_bp.route("/profile/edit", methods=["POST"])
@auth_required
@role_required(["consumer"])
def edit_consumer_profile():
    user = request.user
    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()

    if not profile:
        return error("Consumer profile not found", status=404)

    data = request.get_json()

    profile.flat_number = data.get("flat_number", profile.flat_number)
    profile.profile_image_url = data.get("profile_image_url", profile.profile_image_url)
    profile.gender = data.get("gender", profile.gender)
    profile.date_of_birth = data.get("date_of_birth", profile.date_of_birth)
    profile.preferred_language = data.get("preferred_language", profile.preferred_language)

    try:
        with transactional("Failed to edit consumer profile"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Profile updated"}), 200


# --- Cart Endpoints ---
@consumer_bp.route("/cart/add", methods=["POST"])
@auth_required
@role_required("consumer")
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
@auth_required
@role_required("consumer")
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
            with transactional("Failed to remove cart item"):
                pass
        except Exception:
            return internal_error_response()
        return jsonify({"status": "success", "message": "Item removed"}), 200

    return error("Item not found", status=404)


@consumer_bp.route("/cart/clear", methods=["POST"])
@auth_required
@role_required("consumer")
def clear_cart():
    phone = request.phone
    CartItem.query.filter_by(user_phone=phone).delete()
    try:
        with transactional("Failed to clear cart"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Cart cleared"}), 200


# --- Wallet Endpoints ---
@consumer_bp.route("/wallet", methods=["GET"])
@auth_required
@role_required(["consumer"])
def get_or_create_wallet():
    user = request.user
    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        try:
            with transactional("Failed to create wallet"):
                db.session.add(wallet)
        except Exception:
            return internal_error_response()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


@consumer_bp.route("/wallet/history", methods=["GET"])
@auth_required
@role_required(["consumer"])
def wallet_transaction_history():
    txns = (
        WalletTransaction.query.filter_by(user_phone=request.phone)
        .order_by(WalletTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


@consumer_bp.route("/wallet/load", methods=["POST"])
@auth_required
@role_required(["consumer"])
def load_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        if amount <= 0:
            return error("Invalid amount", status=400)

        with transactional("Failed to load wallet"):
            new_bal = adjust_consumer_balance(
                user.phone,
                amount,
                reference=data.get("reference", "manual-load"),
                type="recharge",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        current_app.logger.error("Failed to load wallet: %s", e, exc_info=True)
        return internal_error_response()


@consumer_bp.route("/wallet/debit", methods=["POST"])
@auth_required
@role_required(["consumer"])
def debit_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-debit")

        with transactional("Failed to debit wallet"):
            new_bal = adjust_consumer_balance(
                user.phone,
                -amount,
                reference=reference,
                type="debit",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        current_app.logger.error("Failed to debit wallet: %s", e, exc_info=True)
        return internal_error_response()


@consumer_bp.route("/wallet/refund", methods=["POST"])
@auth_required
@role_required(["consumer"])
def refund_wallet():
    user = request.user
    data = request.get_json()
    try:
        amount = Decimal(str(data.get("amount", "0")))
        reference = data.get("reference", "manual-refund")

        with transactional("Failed to refund wallet"):
            new_bal = adjust_consumer_balance(
                user.phone,
                amount,
                reference=reference,
                type="refund",
                source="api",
            )
        return jsonify({"status": "success", "balance": float(new_bal)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except Exception as e:
        current_app.logger.error("Failed to refund wallet: %s", e, exc_info=True)
        return internal_error_response()


# --- Order Endpoints ---

@consumer_bp.route("/order/confirm", methods=["POST"])
@limiter.limit(lambda: current_app.config["ORDER_LIMIT_PER_IP"], key_func=get_remote_address, error_message="Too many orders from this IP")
@auth_required
@role_required("consumer")
def confirm_order():
    user = request.user
    data = request.get_json()
    payment_mode = data.get("payment_mode", "cash")
    delivery_notes = data.get("delivery_notes", "")
    try:
        with transactional("Order confirmation failed"):
            new_order = confirm_order_service(user, payment_mode, delivery_notes)
        return jsonify({"status": "success", "message": "Order placed successfully", "order_id": new_order.id}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@consumer_bp.route("/order/history", methods=["GET"])
@auth_required
@role_required("consumer")
def get_order_history():
    user = request.user
    orders = Order.query.filter_by(user_phone=user.phone).order_by(Order.created_at.desc()).all()
    result = []
    for order in orders:
        items = OrderItem.query.filter_by(order_id=order.id).all()
        item_list = [
            {"name": oi.name, "quantity": oi.quantity, "unit_price": float(oi.unit_price), "subtotal": float(oi.subtotal)}
            for oi in items
        ]
        result.append({
            "order_id": order.id,
            "shop_id": order.shop_id,
            "payment_mode": order.payment_mode,
            "payment_status": order.payment_status,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "final_amount": float(order.final_amount),
            "delivery_notes": order.delivery_notes,
            "created_at": order.created_at,
            "items": item_list,
        })
    return jsonify({"status": "success", "orders": result}), 200


@consumer_bp.route("/order/confirm-modified/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def confirm_modified_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    try:
        with transactional("Failed to confirm modified order"):
            refund = confirm_modified_order_service(user, order)
        return jsonify({"status": "success", "message": "Modified order confirmed", "refund": float(refund)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@consumer_bp.route("/order/cancel/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def cancel_order_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    try:
        with transactional("Failed to cancel order"):
            refund = cancel_order_by_consumer(user, order)
        return jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund)}), 200
    except InsufficientFunds as e:
        return error(str(e), status=400)
    except ValidationError as e:
        status = 403 if "Unauthorized" in str(e) else 400
        return error(str(e), status=status)
    except Exception:
        return internal_error_response()


@consumer_bp.route("/order/message/send/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def send_order_message_consumer(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return error("Message required", status=400)
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    db.session.add(OrderMessage(order_id=order_id, sender_phone=user.phone, message=message))
    db.session.add(OrderActionLog(order_id=order_id, action_type="message_sent", actor_phone=user.phone, details=message))
    try:
        with transactional("Failed to send order message"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Message sent"}), 200


@consumer_bp.route("/order/messages/<int:order_id>", methods=["GET"])
@auth_required
@role_required("consumer")
def get_order_messages_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    messages = OrderMessage.query.filter_by(order_id=order_id).order_by(OrderMessage.timestamp.asc()).all()
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200


@consumer_bp.route("/order/rate/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def rate_order(order_id):
    user = request.user
    data = request.get_json()
    rating = data.get("rating")
    review = data.get("review", "").strip()
    if not rating or not (1 <= int(rating) <= 5):
        return error("Rating must be between 1 and 5", status=400)
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized or order not found", status=403)
    if order.status != "delivered":
        return error("Order not yet delivered", status=400)
    existing = OrderRating.query.filter_by(order_id=order_id).first()
    if existing:
        return error("Rating already submitted", status=400)
    rating_entry = OrderRating(order_id=order.id, user_phone=user.phone, rating=int(rating), review=review)
    db.session.add(rating_entry)
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="order_rated",
            actor_phone=user.phone,
            details=f"Rated {rating}/5. {review}" if review else f"Rated {rating}/5",
        )
    )
    try:
        with transactional("Failed to rate order"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Thank you for rating!", "rating": rating_entry.to_dict()}), 200


@consumer_bp.route("/order/issue/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def raise_order_issue(order_id):
    user = request.user
    data = request.get_json()
    issue_type = data.get("issue_type")
    description = data.get("description", "")
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    if order.status != "delivered":
        return error("Issue can only be raised for delivered orders", status=400)
    issue = OrderIssue(order_id=order.id, user_phone=user.phone, issue_type=issue_type, description=description)
    db.session.add(issue)
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            action_type="issue_raised",
            actor_phone=user.phone,
            details=f"Issue: {issue_type} | {description}",
        )
    )
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message=f"Issue raised: {issue_type}\n{description}"))
    try:
        with transactional("Failed to raise issue"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Issue raised"}), 200


@consumer_bp.route("/order/return/raise/<int:order_id>", methods=["POST"])
@auth_required
@role_required("consumer")
def request_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return error("Unauthorized", status=403)
    if order.status != "delivered":
        return error("Only delivered orders can be returned", status=400)
    for item in items:
        db.session.add(
            OrderReturn(
                order_id=order.id,
                item_id=item.get("item_id"),
                quantity=item.get("quantity", 1),
                reason=reason,
                initiated_by="consumer",
                status="requested",
            )
        )
    db.session.add(
        OrderActionLog(
            order_id=order.id,
            actor_phone=user.phone,
            action_type="return_requested",
            details=f"{len(items)} item(s) requested for return. Reason: {reason}",
        )
    )
    try:
        with transactional("Failed to request return"):
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Return request sent"}), 200


# --- Shop Browsing ---
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
