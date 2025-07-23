# === models/cart.py ===
from datetime import datetime

class CartItem(db.Model):
    __tablename__ = "cart_item"

    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String(15), db.ForeignKey("user_profile.phone"), nullable=False)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    price_at_addition = db.Column(db.Float, nullable=True)  # Optional snapshot (can be NULL)

    item = db.relationship("Item")
    shop = db.relationship("Shop")


# === models/item.py ===
# --- models/item.py ---
from datetime import datetime

class Item(db.Model):
    __tablename__ = "item"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)

    # Core details
    title = db.Column(db.String(100), nullable=False)             # Replaces 'name'
    brand = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)

    # Pricing
    mrp = db.Column(db.Float, nullable=True)                      # MRP
    price = db.Column(db.Float, nullable=False)                   # Selling price
    discount = db.Column(db.Float, nullable=True)                 # Optional %

    # Inventory & Unit Info
    quantity_in_stock = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(20), nullable=True)                # kg, ml, packet, pcs
    pack_size = db.Column(db.String(50), nullable=True)           # 500ml, 1kg, etc.

    # Availability & status
    is_available = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)               # For soft delete

    # Tags / Metadata
    category = db.Column(db.String(50), nullable=True)            # snacks, dairy, etc.
    tags = db.Column(db.String(100), nullable=True)               # e.g. "organic,vegan"
    sku = db.Column(db.String(50), nullable=True)                 # item code
    expiry_date = db.Column(db.Date, nullable=True)

    # Media
    image_url = db.Column(db.String(255), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    shop = db.relationship("Shop", backref="items")


# === models/order.py ===
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime


class Order(db.Model):
    __tablename__ = "order"
    id = Column(Integer, primary_key=True)
    user_phone = Column(String(15), ForeignKey("user_profile.phone"), nullable=False)
    shop_id = Column(Integer, ForeignKey("shop.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, accepted, modified, confirmed, cancelled, delivered
    payment_mode = Column(String(10), nullable=False)  # wallet or cash
    payment_status = Column(String(20), default="unpaid")  # unpaid, paid, refunded, partially_refunded
    delivery_notes = Column(Text, nullable=True)
    total_amount = Column(Float, nullable=False)
    final_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    ratings = db.relationship("OrderRating", backref="order", lazy=True)

    # Relationships (optional if you want to use them in queries)
    shop = db.relationship("Shop", backref="orders", lazy=True)
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)

class OrderItem(db.Model):
    __tablename__ = "order_item"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    item_id = db.Column(db.Integer, nullable=False)

    # Add these missing fields:
    name = db.Column(db.String(255))
    unit = db.Column(db.String(50))
    unit_price = db.Column(db.Numeric(10, 2))
    quantity = db.Column(db.Integer)
    subtotal = db.Column(db.Numeric(10, 2))

    def to_dict(self):
        return {
            "item_id": self.item_id,
            "name": self.name,
            "unit": self.unit,
            "unit_price": float(self.unit_price),
            "quantity": self.quantity,
            "subtotal": float(self.subtotal)
        }



class OrderMessage(db.Model):
    __tablename__ = "order_messages"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("order.id"), nullable=False)
    sender_phone = Column(String(15), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "sender_phone": self.sender_phone,
            "message": self.message,
            "timestamp": self.timestamp
        }


class OrderStatusLog(db.Model):
    __tablename__ = "order_status_log"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("order.id"), nullable=False)
    status = Column(String(30), nullable=False)
    updated_by = Column(String(15), nullable=False)
    timestamp = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "status": self.status,
            "updated_by": self.updated_by,
            "timestamp": self.timestamp
        }


class OrderActionLog(db.Model):
    __tablename__ = "order_action_log"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("order.id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    actor_phone = Column(String(15), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=func.now())


class OrderRating(db.Model):
    __tablename__ = "order_rating"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    user_phone = db.Column(db.String(15), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(250))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "rating": self.rating,
            "review": self.review,
            "created_at": self.created_at
        }

class OrderIssue(db.Model):
    __tablename__ = "order_issue"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    user_phone = db.Column(db.String, nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)  # e.g., "damaged_item", "missing_item"
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default="raised")  # raised, resolved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "user_phone": self.user_phone,
            "issue_type": self.issue_type,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

class OrderReturn(db.Model):
    __tablename__ = "order_return"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=True)  # Null for full return
    quantity = db.Column(db.Integer, nullable=False, default=1)
    reason = db.Column(db.String(255))
    initiated_by = db.Column(db.String(20))  # 'consumer' or 'vendor'
    status = db.Column(db.String(30), default="requested")  # requested, accepted, completed, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "item_id": self.item_id,
            "quantity": self.quantity,
            "reason": self.reason,
            "initiated_by": self.initiated_by,
            "status": self.status,
            "created_at": self.created_at
        }


# === models/shop.py ===
from datetime import datetime

class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_name = db.Column(db.String(100), nullable=False)         # renamed from name
    shop_type = db.Column(db.String(50), nullable=False)          # renamed from type
    society = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    description = db.Column(db.String(200))
    delivers = db.Column(db.Boolean, default=False)
    appointment_only = db.Column(db.Boolean, default=False)
    is_open = db.Column(db.Boolean, default=False)
    last_opened_at = db.Column(db.DateTime)
    last_closed_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # New optional/future-ready fields
    category_tags = db.Column(db.Text, nullable=True)
    logo_url = db.Column(db.String(255), nullable=True)
    rating = db.Column(db.Float, nullable=True)
    total_orders = db.Column(db.Integer, nullable=True)
    verified = db.Column(db.Boolean, default=False)
    featured = db.Column(db.Boolean, default=False)
    last_active_at = db.Column(db.DateTime, nullable=True)


class ShopHours(db.Model):
    __tablename__ = "shop_hours"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    open_time = db.Column(db.Time, nullable=True)
    close_time = db.Column(db.Time, nullable=True)

    shop = db.relationship("Shop", backref=db.backref("hours", lazy=True))

    def as_dict(self):
        return {
            "day_of_week": self.day_of_week,
            "open_time": self.open_time.strftime("%H:%M") if self.open_time else None,
            "close_time": self.close_time.strftime("%H:%M") if self.close_time else None
        }

class ShopActionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), nullable=False)
    action = db.Column(db.String(50))  # 'opened' or 'closed'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)



# === models/__init__.py ===
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# === models/user.py ===
# --- models/user.py ---
from datetime import datetime

# --- OTP Model ---
class OTP(db.Model):
    __tablename__ = "otp"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_used = db.Column(db.Boolean, default=False)

    
    def __repr__(self):
        return f"<OTP phone={self.phone} otp={self.otp}>"

# --- User Profile Model ---

class UserProfile(db.Model):
    __tablename__ = "user_profile"

    phone = db.Column(db.String(15), primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    society = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=True)
    basic_onboarding_done = db.Column(db.Boolean, default=False)
    role_onboarding_done = db.Column(db.Boolean, default=False)
    auth_token = db.Column(db.String(64), unique=True)
    device_info = db.Column(db.String(300), nullable=True) 
    token_created_at = db.Column(db.DateTime, default=datetime.utcnow)
    kyc_status = db.Column(db.String, default="pending")

    def __repr__(self):
        return f"<User phone={self.phone} role={self.role}>"

 # Consumer Profile------------

class ConsumerProfile(db.Model):
    __tablename__ = "consumer_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String(15), db.ForeignKey("user_profile.phone"), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50), nullable=False)
    society = db.Column(db.String(100), nullable=False)
    flat_number = db.Column(db.String(50), nullable=True)
    profile_image_url = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    preferred_language = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "name": self.name,
            "phone": self.user_phone,
            "city": self.city,
            "society": self.society,
            "flat_number": self.flat_number,
            "profile_image_url": self.profile_image_url,
            "gender": self.gender,
            "date_of_birth": str(self.date_of_birth) if self.date_of_birth else None,
            "preferred_language": self.preferred_language
        }


# === models/vendor.py ===
from datetime import datetime


class VendorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String, db.ForeignKey("user_profile.phone"), unique=True)
    shop_id = db.Column(db.Integer, db.ForeignKey("shop.id"), unique=True)
    business_name = db.Column(db.String)
    gst_number = db.Column(db.String)
    address = db.Column(db.String)
    kyc_status = db.Column(db.String, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    business_type = db.Column(db.String(100), nullable=True)


class VendorDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_phone = db.Column(db.String, db.ForeignKey("user_profile.phone"))
    document_type = db.Column(db.String)  # e.g., 'aadhaar', 'pan', 'shop_license'
    file_url = db.Column(db.String)
    status = db.Column(db.String, default='pending')  # pending, approved, rejected
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class VendorPayoutBank(db.Model):
    __tablename__ = "vendor_payout_bank"

    id = db.Column(db.Integer, primary_key=True)
    user_phone = db.Column(db.String(15), db.ForeignKey("user_profile.phone"), unique=True, nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(50), nullable=False)
    ifsc_code = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# === models/wallet.py ===
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime
from sqlalchemy.sql import func


class ConsumerWallet(db.Model):
    __tablename__ = "consumer_wallet"
    id = Column(Integer, primary_key=True)
    user_phone = Column(String(15), nullable=False)
    balance = Column(Numeric(10, 2), default=0.00)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class WalletTransaction(db.Model):
    __tablename__ = "wallet_transaction"
    id = Column(Integer, primary_key=True)
    user_phone = Column(String(15), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String(20), nullable=False)  # e.g. debit, credit, refund
    reference = Column(Text, nullable=True)    # order id or message
    status = Column(String(20), nullable=True)  # e.g. success, failed
    source = Column(String(50), nullable=True)  # e.g. order, refund
    created_at = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "user_phone": self.user_phone,
            "amount": float(self.amount),
            "type": self.type,
            "reference": self.reference,
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

class VendorWallet(db.Model):
    __tablename__ = "vendor_wallet"
    id = Column(Integer, primary_key=True)
    user_phone = Column(String(15), nullable=False)
    balance = Column(Numeric(10, 2), default=0.00)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class VendorWalletTransaction(db.Model):
    __tablename__ = "vendor_wallet_transaction"
    id = Column(Integer, primary_key=True)
    user_phone = Column(String(15), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(String(20), nullable=False)  # credit, debit
    reference = Column(Text, nullable=True)
    status = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "user_phone": self.user_phone,
            "amount": float(self.amount),
            "type": self.type,
            "reference": self.reference,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }



# === services/__init__.py ===


# === services/cart.py ===
from flask import request, jsonify
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required

MAX_QUANTITY_PER_ITEM = 10  # Set your max quantity per item limit here

# Add item to cart
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

    db.session.commit()
    return jsonify({"status": "success", "message": "Item added to cart"}), 200


# Update quantity of an item
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
    db.session.commit()
    return jsonify({"status": "success", "message": "Cart quantity updated"}), 200


# View cart with availability and price refresh
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
        db.session.commit()
        return jsonify({"status": "success", "message": "Item removed"}), 200

    return jsonify({"status": "error", "message": "Item not found"}), 404


# Clear cart
@auth_required
@role_required("consumer")
def clear_cart():
    phone = request.phone
    CartItem.query.filter_by(user_phone=phone).delete()
    db.session.commit()
    return jsonify({"status": "success", "message": "Cart cleared"}), 200


# === services/vendororder.py ===
from flask import request, jsonify
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from decimal import Decimal

# ------------------- Vendor: View Orders -------------------
@auth_required
@role_required("vendor")
def get_shop_orders():
    user = request.user
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    orders = Order.query.filter_by(shop_id=shop.id).order_by(Order.created_at.desc()).all()
    result = []
    for order in orders:
        item_list = [{
            "name": oi.name,
            "quantity": oi.quantity,
            "unit_price": float(oi.unit_price),
            "subtotal": float(oi.subtotal)
        } for oi in order.items]

        result.append({
            "order_id": order.id,
            "customer": order.user_phone,
            "payment_mode": order.payment_mode,
            "payment_status": order.payment_status,
            "status": order.status,
            "total_amount": float(order.total_amount),
            "final_amount": float(order.final_amount),
            "delivery_notes": order.delivery_notes,
            "created_at": order.created_at,
            "items": item_list
        })

    return jsonify({"status": "success", "orders": result}), 200


# ------------------- Vendor: Update Order Status -------------------

@auth_required
@role_required("vendor")
def update_order_status(order_id):
    user = request.user
    data = request.get_json()
    new_status = data.get("status")

    if new_status not in ["accepted", "rejected", "delivered"]:
        return jsonify({"status": "error", "message": "Invalid status"}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"status": "error", "message": "Order not found"}), 404

    # ✅ Fetch shop from order first
    shop = Shop.query.get(order.shop_id)
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    # ✅ Now verify vendor owns the shop
    if shop.phone != user.phone:  # OR shop.user_phone or shop.vendor_phone depending on your DB schema
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    # ✅ Credit vendor wallet if delivered & prepaid
    if new_status == "delivered" and order.payment_mode == "wallet" and order.payment_status == "paid":
        wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
        if not wallet:
            wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
            db.session.add(wallet)

        wallet.balance += Decimal(order.final_amount)
        db.session.add(VendorWalletTransaction(
            user_phone=user.phone,
            amount=Decimal(order.final_amount),
            type="credit",
            reference=f"Order #{order.id}",
            status="success"
        ))

    order.status = new_status
    db.session.add(OrderStatusLog(order_id=order.id, status=new_status, updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="status_updated", actor_phone=user.phone, details=f"Order status updated to {new_status}"))

    db.session.commit()
    return jsonify({"status": "success", "message": f"Order marked as {new_status}"}), 200

# ------------------- Vendor: Cancel Order -------------------
@auth_required
@role_required("vendor")
def cancel_order_vendor(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"status": "error", "message": "Order not found"}), 404

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop or shop.id != order.shop_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if order.status in ["cancelled", "delivered"]:
        return jsonify({"status": "error", "message": "Order already closed"}), 400

    refund_amount = Decimal(0)
    if order.payment_mode == "wallet":
        wallet = ConsumerWallet.query.filter_by(user_phone=order.user_phone).first()
        refund_amount = Decimal(order.total_amount)
        wallet.balance += refund_amount
        db.session.add(WalletTransaction(
            user_phone=order.user_phone,
            amount=refund_amount,
            type="refund",
            reference=f"Order #{order.id}",
            status="success"
        ))

    order.status = "cancelled"
    db.session.add(OrderStatusLog(order_id=order.id, status="cancelled", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="order_cancelled", actor_phone=user.phone, details="Cancelled by vendor"))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by shop."))

    db.session.commit()
    return jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund_amount)}), 200


# ------------------- Vendor: Modify Order -------------------
@auth_required
@role_required("vendor")
def modify_order_item(order_id):
    user = request.user
    data = request.get_json()
    modifications = data.get("modifications", [])

    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if order.status in ["cancelled", "delivered"]:
        return jsonify({"status": "error", "message": "Cannot modify a closed order"}), 400

    updated_total = Decimal(0)
    update_log = []

    for mod in modifications:
        item_id = mod.get("item_id")
        new_qty = mod.get("quantity")
        order_item = OrderItem.query.filter_by(order_id=order.id, item_id=item_id).first()

        if order_item:
            if new_qty == 0:
                db.session.delete(order_item)
                update_log.append(f"Removed item {item_id}")
            else:
                order_item.quantity = new_qty
                order_item.subtotal = Decimal(new_qty) * Decimal(order_item.unit_price)
                update_log.append(f"Updated item {item_id} to qty {new_qty}")

    db.session.flush()
    updated_items = OrderItem.query.filter_by(order_id=order.id).all()
    updated_total = sum(Decimal(oi.quantity) * Decimal(oi.unit_price) for oi in updated_items)

    order.final_amount = updated_total
    order.status = "awaiting_consumer_confirmation"

    db.session.add(OrderStatusLog(order_id=order.id, status="awaiting_consumer_confirmation", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="vendor_modified", actor_phone=user.phone, details="; ".join(update_log)))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order modified. Awaiting your confirmation."))

    db.session.commit()
    return jsonify({"status": "success", "message": "Order modified", "new_total": float(updated_total)}), 200


# ------------------- Vendor: Send Message -------------------
@auth_required
@role_required("vendor")
def send_order_message_vendor(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")

    if not message:
        return jsonify({"status": "error", "message": "Message required"}), 400

    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    db.session.add(OrderMessage(
        order_id=order_id,
        sender_phone=user.phone,
        message=message
    ))
    db.session.add(OrderActionLog(
        order_id=order_id,
        action_type="message_sent",
        actor_phone=user.phone,
        details=message
    ))
    db.session.commit()

    return jsonify({"status": "success", "message": "Message sent"}), 200


# ------------------- Vendor: Get Messages -------------------
@auth_required
@role_required("vendor")
def get_order_messages_vendor(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    messages = OrderMessage.query.filter_by(order_id=order_id).order_by(OrderMessage.timestamp.asc()).all()
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200

# ------------------- Vendor: Get order issues -------------------

@auth_required
@role_required("vendor")
def get_issues_for_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    issues = OrderIssue.query.filter_by(order_id=order.id).order_by(OrderIssue.created_at.desc()).all()
    result = [i.to_dict() for i in issues]

    return jsonify({"status": "success", "issues": result}), 200

# ------------------- Vendor: Create return-------------------
@auth_required
@role_required("vendor")
def vendor_initiate_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])  # [{"item_id": 1, "quantity": 1}, ...]

    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()
    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Only delivered orders can be returned"}), 400

    for item in items:
        db.session.add(OrderReturn(
            order_id=order.id,
            item_id=item.get("item_id"),
            quantity=item.get("quantity", 1),
            reason=reason,
            initiated_by="vendor",
            status="accepted"  # ✅ No need for consumer to approve
        ))

    order.status = "return_accepted"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="vendor_forced_return", actor_phone=user.phone, details=f"{len(items)} item(s) returned. Reason: {reason}"))
    db.session.commit()

    return jsonify({"status": "success", "message": "Return initiated and accepted"}), 200


# ------------------- Vendor: Accept return-------------------

@auth_required
@role_required("vendor")
def accept_return(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    returns = OrderReturn.query.filter_by(order_id=order.id, status="requested").all()
    if not returns:
        return jsonify({"status": "error", "message": "No pending return requests"}), 400

    for r in returns:
        r.status = "accepted"

    order.status = "return_accepted"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_accepted", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="return_accepted", actor_phone=user.phone, details="Vendor accepted the return request"))
    db.session.commit()

    return jsonify({"status": "success", "message": "Return request accepted"}), 200


# ------------------- Vendor: Complete Retrun-------------------

@auth_required
@role_required("vendor")
def complete_return(order_id):
    user = request.user
    order = Order.query.get(order_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not order or not shop or order.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "return_accepted":
        return jsonify({"status": "error", "message": "Return not accepted yet"}), 400

    returns = OrderReturn.query.filter_by(order_id=order.id, status="accepted").all()
    if not returns:
        return jsonify({"status": "error", "message": "No accepted returns found"}), 400

    for r in returns:
        r.status = "completed"

    order.status = "return_completed"
    db.session.add(OrderStatusLog(order_id=order.id, status="return_completed", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="return_completed", actor_phone=user.phone, details="Vendor marked return as picked up"))

    if order.payment_mode == "wallet":
        refund_total = sum([
            Decimal(oi.unit_price) * r.quantity
            for r in returns
            for oi in OrderItem.query.filter_by(order_id=order.id, item_id=r.item_id).all()
        ])
        wallet = ConsumerWallet.query.filter_by(user_phone=order.user_phone).first()
        vendor_wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()

        wallet.balance += refund_total
        vendor_wallet.balance -= refund_total

        db.session.add(WalletTransaction(
            user_phone=order.user_phone,
            amount=refund_total,
            type="refund",
            reference=f"Return refund for order #{order.id}",
            status="success"
        ))
        db.session.add(VendorWalletTransaction(
            user_phone=user.phone,
            amount=refund_total,
            type="debit",
            reference=f"Return refund for order #{order.id}",
            status="success"
        ))

    db.session.commit()
    return jsonify({"status": "success", "message": "Return marked as completed"}), 200


# === services/consumerorder.py ===
from flask import request, jsonify
from decimal import Decimal
from datetime import datetime
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required

# ------------------- Confirm Order -------------------
@auth_required
@role_required("consumer")
def confirm_order():
    user = request.user
    data = request.get_json()
    payment_mode = data.get("payment_mode", "cash")
    delivery_notes = data.get("delivery_notes", "")

    cart_items = CartItem.query.filter_by(user_phone=user.phone).all()
    if not cart_items:
        return jsonify({"status": "error", "message": "Cart is empty"}), 400

    shop_id = cart_items[0].shop_id
    total_amount = sum(Decimal(ci.quantity) * Decimal(ci.item.price) for ci in cart_items)

    # Wallet balance check
    if payment_mode == "wallet":
        wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
        if not wallet or wallet.balance < total_amount:
            return jsonify({"status": "error", "message": "Insufficient wallet balance"}), 400
        wallet.balance -= total_amount

    # Create Order
    new_order = Order(
        user_phone=user.phone,
        shop_id=shop_id,
        payment_mode=payment_mode,
        payment_status="paid" if payment_mode == "wallet" else "unpaid",
        delivery_notes=delivery_notes,
        total_amount=total_amount,
        final_amount=total_amount,
        status="pending"
    )
    db.session.add(new_order)
    db.session.flush()

    # Add WalletTransaction if applicable
    if payment_mode == "wallet":
        db.session.add(WalletTransaction(
            user_phone=user.phone,
            type="debit",
            amount=total_amount,
            reference=f"Order #{new_order.id}",
            status="success"
        ))

    # Add Order Items
    for ci in cart_items:
        db.session.add(OrderItem(
            order_id=new_order.id,
            item_id=ci.item.id,
            name=ci.item.title,
            unit=ci.item.unit,
            unit_price=ci.item.price,
            quantity=ci.quantity,
            subtotal=Decimal(ci.quantity) * Decimal(ci.item.price)
        ))

    # Clear cart
    CartItem.query.filter_by(user_phone=user.phone).delete()

    # Log status and action
    db.session.add(OrderStatusLog(order_id=new_order.id, status="pending", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=new_order.id, action_type="order_created", actor_phone=user.phone, details="Order placed"))

    db.session.commit()
    return jsonify({"status": "success", "message": "Order placed successfully", "order_id": new_order.id}), 200


# ------------------- Confirm Modified Order -------------------
@auth_required
@role_required("consumer")
def confirm_modified_order(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "awaiting_consumer_confirmation":
        return jsonify({"status": "error", "message": "Order not in modifiable state"}), 400

    old_amount = Decimal(order.total_amount)
    new_amount = Decimal(order.final_amount) if order.final_amount else old_amount

    refund_amount = Decimal(0)
    if order.payment_mode == "wallet" and new_amount < old_amount:
        refund_amount = old_amount - new_amount
        wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
        wallet.balance += refund_amount
        db.session.add(WalletTransaction(
            user_phone=user.phone,
            amount=refund_amount,
            type="refund",
            reference=f"Order #{order.id}",
            status="success"
        ))

    order.status = "confirmed"
    order.total_amount = new_amount
    db.session.add(OrderStatusLog(order_id=order.id, status="confirmed", updated_by=user.phone))
    db.session.add(OrderActionLog(
        order_id=order.id,
        action_type="modification_confirmed",
        actor_phone=user.phone,
        details=f"Confirmed modified order. Refund: ₹{float(refund_amount)}"
    ))
    db.session.add(OrderMessage(
        order_id=order.id,
        sender_phone=user.phone,
        message="I’ve confirmed the changes. Please proceed."
    ))

    db.session.commit()
    return jsonify({"status": "success", "message": "Modified order confirmed", "refund": float(refund_amount)}), 200


# ------------------- Cancel Order -------------------
@auth_required
@role_required("consumer")
def cancel_order_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status in ["cancelled", "delivered"]:
        return jsonify({"status": "error", "message": "Order already closed"}), 400

    refund_amount = Decimal(0)
    if order.payment_mode == "wallet":
        refund_amount = Decimal(order.total_amount)
        wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
        wallet.balance += refund_amount
        db.session.add(WalletTransaction(
            user_phone=user.phone,
            amount=refund_amount,
            type="refund",
            reference=f"Order #{order.id}",
            status="success"
        ))

    order.status = "cancelled"
    db.session.add(OrderStatusLog(order_id=order.id, status="cancelled", updated_by=user.phone))
    db.session.add(OrderActionLog(order_id=order.id, action_type="order_cancelled", actor_phone=user.phone, details="Cancelled by consumer"))
    db.session.add(OrderMessage(order_id=order.id, sender_phone=user.phone, message="Order cancelled by you."))

    db.session.commit()
    return jsonify({"status": "success", "message": "Order cancelled", "refund": float(refund_amount)}), 200


# ------------------- Send Order Message -------------------
@auth_required
@role_required("consumer")
def send_order_message_consumer(order_id):
    user = request.user
    data = request.get_json()
    message = data.get("message")
    if not message:
        return jsonify({"status": "error", "message": "Message required"}), 400

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    db.session.add(OrderMessage(order_id=order_id, sender_phone=user.phone, message=message))
    db.session.add(OrderActionLog(order_id=order_id, action_type="message_sent", actor_phone=user.phone, details=message))
    db.session.commit()

    return jsonify({"status": "success", "message": "Message sent"}), 200


# ------------------- Get Order Messages -------------------
@auth_required
@role_required("consumer")
def get_order_messages_consumer(order_id):
    user = request.user
    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    messages = OrderMessage.query.filter_by(order_id=order_id).order_by(OrderMessage.timestamp.asc()).all()
    result = [msg.to_dict() for msg in messages]
    return jsonify({"status": "success", "messages": result}), 200


# ------------------- Get Order History -------------------
@auth_required
@role_required("consumer")
def get_order_history():
    user = request.user
    orders = Order.query.filter_by(user_phone=user.phone).order_by(Order.created_at.desc()).all()
    result = []

    for order in orders:
        items = OrderItem.query.filter_by(order_id=order.id).all()
        item_list = [{
            "name": oi.name,
            "quantity": oi.quantity,
            "unit_price": float(oi.unit_price),
            "subtotal": float(oi.subtotal)
        } for oi in items]

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
            "items": item_list
        })

    return jsonify({"status": "success", "orders": result}), 200

# ------------------- Rate Order -------------------

@auth_required
@role_required("consumer")
def rate_order(order_id):
    user = request.user
    data = request.get_json()
    rating = data.get("rating")
    review = data.get("review", "").strip()

    if not rating or not (1 <= int(rating) <= 5):
        return jsonify({"status": "error", "message": "Rating must be between 1 and 5"}), 400

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized or order not found"}), 403

    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Order not yet delivered"}), 400

    existing = OrderRating.query.filter_by(order_id=order_id).first()
    if existing:
        return jsonify({"status": "error", "message": "Rating already submitted"}), 400

    # Save Rating
    rating_entry = OrderRating(
        order_id=order.id,
        user_phone=user.phone,
        rating=int(rating),
        review=review
    )
    db.session.add(rating_entry)

    # Log Action
    db.session.add(OrderActionLog(
        order_id=order.id,
        action_type="order_rated",
        actor_phone=user.phone,
        details=f"Rated {rating}/5. {review}" if review else f"Rated {rating}/5"
    ))

    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Thank you for rating!",
        "rating": rating_entry.to_dict()
    }), 200

# ------------------- Raise Order Issue-------------------

@auth_required
@role_required("consumer")
def raise_order_issue(order_id):
    user = request.user
    data = request.get_json()
    issue_type = data.get("issue_type")
    description = data.get("description", "")

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Issue can only be raised for delivered orders"}), 400

    issue = OrderIssue(
        order_id=order.id,
        user_phone=user.phone,
        issue_type=issue_type,
        description=description,
    )
    db.session.add(issue)

    # Log action & send message to vendor
    db.session.add(OrderActionLog(
        order_id=order.id,
        action_type="issue_raised",
        actor_phone=user.phone,
        details=f"Issue: {issue_type} | {description}"
    ))
    db.session.add(OrderMessage(
        order_id=order.id,
        sender_phone=user.phone,
        message=f"Issue raised: {issue_type}\n{description}"
    ))

    db.session.commit()
    return jsonify({"status": "success", "message": "Issue raised"}), 200

# ------------------- Request return -------------------

@auth_required
@role_required("consumer")
def request_return(order_id):
    user = request.user
    data = request.get_json()
    reason = data.get("reason", "")
    items = data.get("items", [])  # [{"item_id": 1, "quantity": 1}, ...]

    order = Order.query.get(order_id)
    if not order or order.user_phone != user.phone:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403
    if order.status != "delivered":
        return jsonify({"status": "error", "message": "Only delivered orders can be returned"}), 400

    for item in items:
        db.session.add(OrderReturn(
            order_id=order.id,
            item_id=item.get("item_id"),
            quantity=item.get("quantity", 1),
            reason=reason,
            initiated_by="consumer",
            status="requested"
        ))

    db.session.add(OrderActionLog(
        order_id=order.id,
        actor_phone=user.phone,
        action_type="return_requested",
        details=f"{len(items)} item(s) requested for return. Reason: {reason}"
    ))
    db.session.commit()

    return jsonify({"status": "success", "message": "Return request sent"}), 200


# === services/vendor.py ===
from flask import request, jsonify
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from datetime import datetime


# Vendor Onboarding -----------------

@auth_required
@role_required(["vendor"])
def vendor_profile_setup():
    user = UserProfile.query.filter_by(phone=request.phone).first()

    if not user or not user.basic_onboarding_done:
        return jsonify({"status": "error", "message": "Basic onboarding incomplete"}), 400

    data = request.get_json()
    business_type = data.get("business_type")
    business_name = data.get("business_name")
    gst_number = data.get("gst_number")
    address = data.get("address")

    if not business_type or not business_name or not address:
        return jsonify({"status": "error", "message": "Missing required vendor details"}), 400

    existing_profile = VendorProfile.query.filter_by(user_phone=user.phone).first()
    if existing_profile:
        return jsonify({"status": "error", "message": "Vendor profile already exists"}), 400

    profile = VendorProfile(
        user_phone=user.phone,
        business_name=business_name,
        gst_number=gst_number,
        address=address,
        business_type=business_type,
        kyc_status="pending"
    )
    db.session.add(profile)
    db.session.commit()

    return jsonify({"status": "success", "message": "Vendor profile created"}), 200

# Vendor Onboarding Documents-----------------

@auth_required
@role_required(["vendor"])
def upload_vendor_document():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()

    doc_type = data.get("document_type")
    file_url = data.get("file_url")

    if not doc_type or not file_url:
        return jsonify({"status": "error", "message": "Missing document type or file URL"}), 400

    new_doc = VendorDocument(
        vendor_phone=user.phone,
        document_type=doc_type,
        file_url=file_url
    )
    db.session.add(new_doc)
    db.session.commit()

    return jsonify({"status": "success", "message": "Document uploaded"}), 200

# Vendor Payout info ----------------

@auth_required
@role_required(["vendor"])
def setup_payout_bank():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()

    required_fields = ["bank_name", "account_number", "ifsc_code"]
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing bank details"}), 400

    existing = VendorPayoutBank.query.filter_by(user_phone=user.phone).first()
    if not existing:
        existing = VendorPayoutBank(user_phone=user.phone)
        db.session.add(existing)

    existing.bank_name = data["bank_name"]
    existing.account_number = data["account_number"]
    existing.ifsc_code = data["ifsc_code"]
    existing.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({"status": "success", "message": "Payout bank info saved"}), 200


# === services/item.py ===
# --- services/item.py ---
from flask import request, jsonify
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from datetime import datetime
import pandas as pd
from werkzeug.utils import secure_filename
import os

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
    db.session.commit()

    return jsonify({"status": "success", "message": "Item added"}), 200

@auth_required
@role_required(["vendor"])
def toggle_item_availability(item_id):
    user = request.user
    item = Item.query.get(item_id)
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not item or item.shop_id != shop.id:
        return jsonify({"status": "error", "message": "Item not found or unauthorized"}), 404

    item.is_available = not item.is_available
    db.session.commit()

    return jsonify({"status": "success", "message": "Item availability updated"}), 200

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

    db.session.commit()
    return jsonify({"status": "success", "message": "Item updated"}), 200

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

    db.session.commit()
    return jsonify({"status": "success", "message": f"{created} items uploaded"}), 200


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

# === services/wallet.py ===
# services/wallet.py

from flask import request, jsonify
    ConsumerWallet,
    WalletTransaction,
    VendorWallet,
    VendorWalletTransaction,
)
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from decimal import Decimal


# ------------------- Get or Create Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def get_or_create_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Consumer Wallet Transactions -------------------
@auth_required
@role_required(["consumer"])
def wallet_transaction_history():
    txns = WalletTransaction.query.filter_by(user_phone=request.phone)\
        .order_by(WalletTransaction.created_at.desc()).limit(50).all()
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


# ------------------- Load Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def load_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-load")

    if amount <= 0:
        return jsonify({"status": "error", "message": "Invalid amount"}), 400

    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.flush()

    wallet.balance += amount
    db.session.add(WalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="recharge",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Debit Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def debit_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-debit")

    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"}), 400

    wallet.balance -= amount
    db.session.add(WalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="debit",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Refund to Consumer Wallet -------------------
@auth_required
@role_required(["consumer"])
def refund_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-refund")

    wallet = ConsumerWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = ConsumerWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.flush()

    wallet.balance += amount
    db.session.add(WalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="refund",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Get or Create Vendor Wallet -------------------
@auth_required
@role_required(["vendor"])
def get_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Vendor Wallet Transactions -------------------
@auth_required
@role_required(["vendor"])
def get_vendor_wallet_history():
    txns = VendorWalletTransaction.query.filter_by(user_phone=request.phone)\
        .order_by(VendorWalletTransaction.created_at.desc()).limit(50).all()
    result = [txn.to_dict() for txn in txns]
    return jsonify({"status": "success", "transactions": result}), 200


# ------------------- Credit Vendor Wallet -------------------
@auth_required
@role_required(["vendor"])
def credit_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-credit")

    if amount <= 0:
        return jsonify({"status": "error", "message": "Invalid credit amount"}), 400

    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet:
        wallet = VendorWallet(user_phone=user.phone, balance=Decimal("0.00"))
        db.session.add(wallet)
        db.session.flush()

    wallet.balance += amount
    db.session.add(VendorWalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="credit",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Debit Vendor Wallet -------------------
@auth_required
@role_required(["vendor"])
def debit_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))
    reference = data.get("reference", "manual-debit")

    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"}), 400

    wallet.balance -= amount
    db.session.add(VendorWalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="debit",
        reference=reference,
        status="success"
    ))
    db.session.commit()
    return jsonify({"status": "success", "balance": float(wallet.balance)}), 200


# ------------------- Withdraw Vendor Wallet to Bank -------------------
@auth_required
@role_required(["vendor"])
def withdraw_vendor_wallet():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    data = request.get_json()
    amount = Decimal(str(data.get("amount", "0")))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Invalid withdrawal amount"}), 400

    wallet = VendorWallet.query.filter_by(user_phone=user.phone).first()
    if not wallet or wallet.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"}), 400

    bank = VendorPayoutBank.query.filter_by(user_phone=user.phone).first()
    if not bank:
        return jsonify({"status": "error", "message": "No payout bank setup found"}), 400

    wallet.balance -= amount
    db.session.add(VendorWalletTransaction(
        user_phone=user.phone,
        amount=amount,
        type="withdrawal",
        reference=f"Withdraw to {bank.account_number}",
        status="success"
    ))
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Withdrawal initiated",
        "bank_account": bank.account_number,
        "balance": float(wallet.balance)
    }), 200


# === services/shop.py ===
from flask import request, jsonify
from datetime import datetime
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required

# --- Create shop by vendor ---
@auth_required
@role_required(["vendor"])
def create_shop():
    user = request.user
    data = request.get_json()
    vendor_profile = VendorProfile.query.filter_by(user_phone=user.phone).first()
    if not vendor_profile:
        return jsonify({"status": "error", "message": "Vendor profile not found. Please complete vendor onboarding first."}), 400

    if Shop.query.filter_by(phone=user.phone).first():
        return jsonify({"status": "error", "message": "Shop already exists for this vendor"}), 400

    required_fields = ["shop_name", "shop_type"]
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    new_shop = Shop(
        shop_name=data["shop_name"],
        shop_type=data["shop_type"],
        society=user.society,
        city=user.city,
        phone=user.phone,
        description=data.get("description", ""),
        delivers=data.get("delivers", False),
        appointment_only=data.get("appointment_only", False),
        is_open=data.get("is_open", True),
        category_tags=data.get("category_tags"),
        logo_url=data.get("logo_url"),
        featured=data.get("featured", False),
        verified=data.get("verified", False),
        last_active_at=datetime.utcnow()
    )

    db.session.add(new_shop)
    db.session.flush()  # Get shop.id

    # Link shop to vendor
    vendor_profile.shop_id = new_shop.id

    # Mark onboarding done after shop creation
    user.role_onboarding_done = True

    db.session.commit()

    return jsonify({"status": "success", "message": "Shop created"}), 200

# --- Edit shop by vendor ---
@auth_required
@role_required(["vendor"])
def edit_shop():
    user = request.user
    data = request.get_json()

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    shop.shop_name = data.get("shop_name", shop.shop_name)
    shop.shop_type = data.get("shop_type", shop.shop_type)
    shop.society = data.get("society", shop.society)
    shop.description = data.get("description", shop.description)
    shop.delivers = data.get("delivers", shop.delivers)
    shop.appointment_only = data.get("appointment_only", shop.appointment_only)
    shop.is_open = data.get("is_open", shop.is_open)
    shop.category_tags = data.get("category_tags", shop.category_tags)
    shop.logo_url = data.get("logo_url", shop.logo_url)
    shop.featured = data.get("featured", shop.featured)
    shop.verified = data.get("verified", shop.verified)

    db.session.commit()
    return jsonify({"status": "success", "message": "Shop updated"}), 200

# --- Get shop by vendor ---
@auth_required
@role_required(["vendor", "admin"])
def get_my_shop():
    user = request.user

    if user.role == "vendor":
        shop = Shop.query.filter_by(phone=user.phone).first()
        if not shop:
            return jsonify({"status": "error", "message": "Shop not found"}), 404

        result = {
            "id": shop.id,
            "shop_name": shop.shop_name,
            "shop_type": shop.shop_type,
            "society": shop.society,
            "phone": shop.phone,
            "description": shop.description,
            "delivers": shop.delivers,
            "appointment_only": shop.appointment_only,
            "is_open": shop.is_open,
            "logo_url": shop.logo_url,
            "category_tags": shop.category_tags,
            "verified": shop.verified,
            "featured": shop.featured
        }
        return jsonify({"status": "success", "data": result}), 200

    else:  # admin sees all shops
        shops = Shop.query.all()
        result = [{
            "id": s.id,
            "shop_name": s.shop_name,
            "shop_type": s.shop_type,
            "society": s.society,
            "phone": s.phone,
            "description": s.description,
            "delivers": s.delivers,
            "appointment_only": s.appointment_only,
            "is_open": s.is_open,
            "logo_url": s.logo_url,
            "category_tags": s.category_tags,
            "verified": s.verified,
            "featured": s.featured
        } for s in shops]
        return jsonify({"status": "success", "data": result}), 200

# --- Update shop hours ---
@auth_required
@role_required(["vendor"])
def update_shop_hours():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    shop = Shop.query.filter_by(phone=user.phone).first()

    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    data = request.get_json()
    weekly_hours = data.get("weekly_hours")

    if not weekly_hours:
        return jsonify({"status": "error", "message": "No hours data provided"}), 400

    # Clear previous hours
    ShopHours.query.filter_by(shop_id=shop.id).delete()

    for entry in weekly_hours:
        day = entry.get("day_of_week")
        open_time = entry.get("open_time")
        close_time = entry.get("close_time")

        # Skip if closed or incomplete
        if day is None or open_time in [None, "", "Closed"] or close_time in [None, "", "Closed"]:
            continue

        try:
            open_dt = datetime.strptime(open_time, "%H:%M").time()
            close_dt = datetime.strptime(close_time, "%H:%M").time()
        except ValueError:
            continue  # Skip invalid time format

        new_hour = ShopHours(
            shop_id=shop.id,
            day_of_week=day,
            open_time=open_dt,
            close_time=close_dt
        )
        db.session.add(new_hour)

    db.session.commit()
    return jsonify({"status": "success", "message": "Shop hours updated"}), 200

# Toggle shop status --------------------

@auth_required
@role_required(["vendor"])
def toggle_shop_status():
    user = request.user
    data = request.get_json()
    new_status = data.get("is_open")

    if new_status not in [True, False]:
        return jsonify({"status": "error", "message": "Invalid is_open value"}), 400

    shop = Shop.query.filter_by(phone=user.phone).first()
    if not shop:
        return jsonify({"status": "error", "message": "Shop not found"}), 404

    shop.is_open = new_status
    timestamp = datetime.utcnow()

    if new_status:
        shop.last_opened_at = timestamp
        action = "opened"
    else:
        shop.last_closed_at = timestamp
        action = "closed"

    log = ShopActionLog(shop_id=shop.id, action=action, timestamp=timestamp)
    db.session.add(log)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Shop marked as {action}"}), 200


# --- Shop searching by customer ---

# List all shops in the user's society and city
@auth_required
@role_required(["consumer"])
def list_shops():
    user = request.user
    city, society = user.city, user.society

    # Optional query filters
    status = request.args.get("status")       # e.g. "open" or "closed"
    shop_type = request.args.get("type")      # e.g. "grocery"
    tags = request.args.getlist("tag")        # e.g. ?tag=organic&tag=dairy

    query = Shop.query.filter_by(city=city, society=society)

    if status == "open":
        query = query.filter_by(is_open=True)
    elif status == "closed":
        query = query.filter_by(is_open=False)

    if shop_type:
        query = query.filter(Shop.shop_type.ilike(f"%{shop_type}%"))

    if tags:
        # assume category_tags stored as comma‐separated or JSON array
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
            "logo_url": s.logo_url
        })

    return jsonify({"status": "success", "shops": result}), 200

# Search shops by name or type
@auth_required
@role_required(["consumer"])
def search_shops():
    user = request.user
    city = user.city
    society = user.society

    query_param = request.args.get("q", "").lower().strip()

    if not query_param:
        return jsonify({"status": "error", "message": "Missing search query 'q'"}), 400

    results = Shop.query.filter(
        Shop.city == city,
        Shop.society == society,
        Shop.is_open == True,
        db.or_(
            Shop.shop_name.ilike(f"%{query_param}%"),
            Shop.shop_type.ilike(f"%{query_param}%")
        )
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
            "logo_url": shop.logo_url
        })

    return jsonify({"status": "success", "shops": shop_list}), 200

# === services/auth.py ===
from flask import request, jsonify
import random, uuid
from datetime import datetime, timedelta
from twilio.rest import Client
import os

# --- Logout handler ---

def logout_handler():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"status": "error", "message": "Token missing"}), 401

    user = UserProfile.query.filter_by(auth_token=token).first()
    if not user:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    user.auth_token = None
    user.token_created_at = None
    db.session.commit()

    return jsonify({"status": "success", "message": "Logged out"}), 200

# --- Twilio Configuration ---

twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")

if not all([twilio_sid, twilio_token, whatsapp_from]):
    raise EnvironmentError("❌ Twilio credentials are missing from environment variables.")

client = Client(twilio_sid, twilio_token)


# --- OTP Utility ---

def generate_otp():
    return str(random.randint(100000, 999999))


def send_whatsapp_message(to, body):
    try:
        message = client.messages.create(
            from_=whatsapp_from,
            to=f"whatsapp:{to}",
            body=body
        )
        print(f"[WhatsApp] ✅ Message sent. SID: {message.sid}")
    except Exception as e:
        print(f"[WhatsApp] ❌ Failed to send message: {e}")


# --- Send OTP ---

def send_otp_handler():
    data = request.get_json()
    phone = data.get("phone")

    if not phone:
        return jsonify({"status": "error", "message": "Phone number is required"}), 400

    # Generate OTP (you may already have this logic)
    otp_code = str(random.randint(100000, 999999))

    # ✅ Create new OTP record with fresh timestamp
    new_otp = OTP(
        phone=phone,
        otp=otp_code,
        is_used=False,
        created_at=datetime.utcnow()
    )

    db.session.add(new_otp)
    db.session.commit()

    # ✅ Send via Twilio or mock
    print(f"[DEBUG] OTP for {phone} is {otp_code}")  # Or use your actual Twilio send logic

    return jsonify({"status": "success", "message": "OTP sent"}), 200

# --- Verify OTP ---

def verify_otp_handler():
    data = request.get_json()
    phone = data.get("phone", "").strip()
    otp = data.get("otp", "").strip()

    if not phone or not otp:
        return jsonify({"status": "error", "message": "Phone and OTP are required"}), 400

    # ✅ Look for matching OTP record
    otp_record = OTP.query.filter_by(phone=phone, otp=otp, is_used=False).first()

    if not otp_record:
        # 🔍 Debug info if OTP failed
        recent_otp = OTP.query.filter_by(phone=phone).order_by(OTP.created_at.desc()).first()
        if recent_otp:
            print(f"[DEBUG] OTP mismatch: submitted={otp}, expected={recent_otp.otp}")
            print(f"[DEBUG] is_used={recent_otp.is_used}, created_at={recent_otp.created_at}")
        else:
            print(f"[DEBUG] No OTP record found for phone: {phone}")
        return jsonify({"status": "error", "message": "Invalid or expired OTP"}), 401

    # ✅ Check OTP expiry
    otp_expiry_minutes = 10
    if datetime.utcnow() - otp_record.created_at > timedelta(minutes=otp_expiry_minutes):
        return jsonify({"status": "error", "message": "OTP expired"}), 401

    # ✅ Mark OTP as used
    otp_record.is_used = True

    # ✅ Generate secure token
    token = str(uuid.uuid4())
    otp_record.token = token

    # ✅ Get device/user-agent info safely
    user_agent = request.headers.get("User-Agent", "")[:200]

    # ✅ Create or update UserProfile
    user = UserProfile.query.filter_by(phone=phone).first()
    if not user:
        user = UserProfile(phone=phone)

    user.auth_token = token
    user.token_created_at = datetime.utcnow()
    user.device_info = user_agent

    # ✅ Commit to DB
    db.session.add(otp_record)
    db.session.add(user)
    db.session.commit()

    print(f"[DEBUG] ✅ OTP verified. Auth token issued for {phone}")

    return jsonify({
        "status": "success",
        "auth_token": token,
        "basic_onboarding_done": user.basic_onboarding_done if user else False
    }), 200

# === services/user.py ===
# --- services/user.py ---
from flask import request, jsonify
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from datetime import datetime

# Basic onboarding -------------
@auth_required
def basic_onboarding():
    data = request.get_json()
    required_fields = ["name", "city", "society", "role"]
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    phone = request.phone
    role = data["role"]

    user = UserProfile.query.filter_by(phone=phone).first()

    if user:
        if user.basic_onboarding_done:
            return jsonify({"status": "error", "message": "User already onboarded"}), 400
        if user.role and user.role != role:
            return jsonify({"status": "error", "message": "Role mismatch"}), 400
    else:
        user = UserProfile(phone=phone)

    user.name = data["name"]
    user.city = data["city"]
    user.society = data["society"]
    user.role = role
    user.basic_onboarding_done = True

    db.session.add(user)
    db.session.commit()

    return jsonify({"status": "success", "message": "Basic onboarding complete"}), 200


# Consumer onboarding -------------
@auth_required
@role_required(["consumer"])
def consumer_onboarding():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    if not user or not user.basic_onboarding_done:
        return jsonify({"status": "error", "message": "Basic onboarding incomplete"}), 400
    if user.role_onboarding_done:
        return jsonify({"status": "error", "message": "Role onboarding already done"}), 400

    data = request.get_json()

    existing = ConsumerProfile.query.filter_by(user_phone=request.phone).first()
    if existing:
        return jsonify({"status": "error", "message": "Profile already exists"}), 400

    consumer_profile = ConsumerProfile(
        user_phone=request.phone,
        name=user.name,
        city=user.city,
        society=user.society,
        flat_number=data.get("flat_number"),
        profile_image_url=data.get("profile_image_url"),
        gender=data.get("gender"),
        date_of_birth=data.get("date_of_birth"),
        preferred_language=data.get("preferred_language")
    )

    db.session.add(consumer_profile)
    user.role_onboarding_done = True
    db.session.commit()

    return jsonify({"status": "success", "message": "Consumer onboarding done"}), 200

# Get Consumer Profile -------------

@auth_required
@role_required(["consumer"])
def get_consumer_profile():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()
    if not profile:
        return jsonify({"status": "error", "message": "Consumer profile not found"}), 404

    data = profile.to_dict()
    return jsonify({"status": "success", "data": data}), 200

# Edit Consumer Profile -------------
@auth_required
@role_required(["consumer"])
def edit_consumer_profile():
    user = UserProfile.query.filter_by(phone=request.phone).first()
    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()

    if not profile:
        return jsonify({"status": "error", "message": "Consumer profile not found"}), 404

    data = request.get_json()

    profile.flat_number = data.get("flat_number", profile.flat_number)
    profile.profile_image_url = data.get("profile_image_url", profile.profile_image_url)
    profile.gender = data.get("gender", profile.gender)
    profile.date_of_birth = data.get("date_of_birth", profile.date_of_birth)
    profile.preferred_language = data.get("preferred_language", profile.preferred_language)

    db.session.commit()
    return jsonify({"status": "success", "message": "Profile updated"}), 200

# === utils/__init__.py ===


# === utils/auth_decorator.py ===
from flask import request, jsonify
from datetime import datetime, timedelta
from functools import wraps

def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"status": "error", "message": "Token missing"}), 401

        user = UserProfile.query.filter_by(auth_token=token).first()
        if not user:
            return jsonify({"status": "error", "message": "Invalid token"}), 401

        if user.token_created_at and datetime.utcnow() - user.token_created_at > timedelta(days=30):
            return jsonify({"status": "error", "message": "Token expired"}), 401

        request.phone = user.phone
        request.user = user
        request.user_role = user.role
        return f(*args, **kwargs)

    return decorated_function


# === utils/role_decorator.py ===
from functools import wraps
from flask import request, jsonify

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = UserProfile.query.filter_by(phone=request.phone).first()
            if not user or user.role not in allowed_roles:
                return jsonify({"status": "error", "message": "Access denied"}), 403
            request.user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# === agent/__init__.py ===


# === agent/prompt_templates.py ===
# === /agent/prompt_templates.py ===
def get_agent_prompt(user_info):
    return f"""
You are an assistant for a hyperlocal society commerce app. The user is a consumer.
They may ask questions about available items, suggestions, or cart.
Give helpful responses and use tools when needed.
User Phone: {user_info.get('phone')}
Role: {user_info.get('user_role')}
    """.strip()

# === agent/query_handler.py ===
# === /agent/query_handler.py ===
from flask import request, jsonify
from agent.agent_core import run_agent

def ask_agent_handler():
    user_query = request.json.get("query")
    if not user_query:
        return jsonify({"status": "error", "message": "Query is required"}), 400

    user_info = {
        "phone": getattr(request, "phone", None),
        "user_role": getattr(request, "user_role", None),
    }

    try:
        answer, suggestions = run_agent(user_query, user_info)
        return jsonify({"status": "success", "answer": answer, "suggestions": suggestions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# === agent/tools.py ===
# === /agent/tools.py ===
from flask import request


def get_available_items():
    items = Item.query.filter_by(is_available=True).limit(10).all()
    return ", ".join([f"{item.name} (₹{item.price})" for item in items]) or "No available items found."

def get_cart_summary():
    phone = getattr(request, "phone", None)
    if not phone:
        return "User not authenticated"
    items = CartItem.query.filter_by(user_phone=phone).all()
    if not items:
        return "Cart is empty."
    summary = [f"{item.item.name} (x{item.quantity})" for item in items]
    return ", ".join(summary)


# === agent/agent_core.py ===
# === /agent/agent_core.py ===
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from agent.tools import get_available_items, get_cart_summary
from agent.prompt_templates import get_agent_prompt

try:
    import openai
    print("✅ openai module imported:", openai.__file__)
    print("✅ openai version:", openai.__version__)
except Exception as e:
    print("❌ Failed to import openai:", str(e))

llm = ChatOpenAI(temperature=0, model="gpt-4")  # or "gpt-3.5-turbo"

tools = [
    Tool(
        name="GetAvailableItems",
        func=get_available_items,
        description="Get available items for the user's society."
    ),
    Tool(
        name="GetCartSummary",
        func=get_cart_summary,
        description="Get a summary of items in the user's cart."
    )
]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)

def run_agent(query, user_info):
    try:
        prompt = get_agent_prompt(user_info)
        final_input = f"{prompt}\nUser: {query}"
        print("🔍 Final Agent Input:", final_input)
        response = agent.run(final_input)
        print("✅ Agent Response:", response)
        return response, ["Would you like to add to cart?", "Do you want checkout link?"]
    except Exception as e:
        print("❌ Agent Error:", str(e))
        raise e  # Let the API return it as part of 500 handler

# === main.py ===
from flask import Flask
    auth as auth_services,
    user as user_services,
    vendor as vendor_services,
    shop as shop_services,
    item as item_services,
    cart as cart_services,
    wallet as wallet_services,
    consumerorder as consumer_order_services,
    vendororder as vendor_order_services
)
# from agent.query_handler import ask_agent_handler
from dotenv import load_dotenv
import os
import logging
from flask_cors import CORS

# This will allow all origins by default
app = Flask(__name__)
CORS(app)

# --- Load Environment Variables ---
load_dotenv()

# --- App Setup ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
with app.app_context():
    db.create_all()
    print("✅ Tables created")

# ========================== Health Check ==========================
@app.route("/health")
def health():
    return {"status": "ok", "base_url": "https://2e6bee57-c137-4144-90f2-64265943227d-00-c6d7jiueybzk.pike.replit.dev"}, 200

# ===================== Auth Routes and basic onboarding ====================
app.add_url_rule("/send-otp", view_func=auth_services.send_otp_handler, methods=["POST"])
app.add_url_rule("/verify-otp", view_func=auth_services.verify_otp_handler, methods=["POST"])
app.add_url_rule("/logout", view_func=auth_services.logout_handler, methods=["POST"])
app.add_url_rule("/onboarding/basic", view_func=user_services.basic_onboarding, methods=["POST"])

# ========================== Consumer Routes ==========================
# Onboarding
app.add_url_rule("/onboarding/consumer", view_func=user_services.consumer_onboarding, methods=["POST"])

# Profile
app.add_url_rule("/profile/me", view_func=user_services.get_consumer_profile, methods=["GET"])
app.add_url_rule("/profile/edit", view_func=user_services.edit_consumer_profile, methods=["POST"])

# Wallet
app.add_url_rule("/wallet", view_func=wallet_services.get_or_create_wallet, methods=["GET"])
app.add_url_rule("/wallet/history", view_func=wallet_services.wallet_transaction_history, methods=["GET"])
app.add_url_rule("/wallet/load", view_func=wallet_services.load_wallet, methods=["POST"])
app.add_url_rule("/wallet/debit", view_func=wallet_services.debit_wallet, methods=["POST"])
app.add_url_rule("/wallet/refund", view_func=wallet_services.refund_wallet, methods=["POST"])

# Shops & Items
app.add_url_rule("/shops", view_func=shop_services.list_shops, methods=["GET"])
app.add_url_rule("/shops/search", view_func=shop_services.search_shops, methods=["GET"])
app.add_url_rule("/items/shop/<int:shop_id>", view_func=item_services.view_items_by_shop, methods=["GET"])

# Cart
app.add_url_rule("/cart/add", view_func=cart_services.add_to_cart, methods=["POST"])
app.add_url_rule("/cart/view", view_func=cart_services.view_cart, methods=["GET"])
app.add_url_rule("/cart/update", view_func=cart_services.update_cart_quantity, methods=["POST"])
app.add_url_rule("/cart/remove", view_func=cart_services.remove_item, methods=["POST"])
app.add_url_rule("/cart/clear", view_func=cart_services.clear_cart, methods=["POST"])

# Consumer Orders
app.add_url_rule("/order/confirm", view_func=consumer_order_services.confirm_order, methods=["POST"])
app.add_url_rule("/order/history", view_func=consumer_order_services.get_order_history, methods=["GET"])
app.add_url_rule("/order/consumer/confirm-modified/<int:order_id>", view_func=consumer_order_services.confirm_modified_order, methods=["POST"])
app.add_url_rule("/order/consumer/cancel/<int:order_id>", view_func=consumer_order_services.cancel_order_consumer, methods=["POST"])
app.add_url_rule("/order/consumer/message/send/<int:order_id>", view_func=consumer_order_services.send_order_message_consumer, methods=["POST"])
app.add_url_rule("/order/consumer/messages/<int:order_id>", view_func=consumer_order_services.get_order_messages_consumer, methods=["GET"])
app.add_url_rule("/order/rate/<int:order_id>", view_func=consumer_order_services.rate_order, methods=["POST"])
app.add_url_rule("/order/issue/<int:order_id>", view_func=consumer_order_services.raise_order_issue, methods=["POST"])
app.add_url_rule("/order/return/raise/<int:order_id>", view_func=consumer_order_services.request_return, methods=["POST"])

# ========================== Vendor Routes ==========================
# Onboarding & Shop Setup
app.add_url_rule("/vendor/profile", view_func=vendor_services.vendor_profile_setup, methods=["POST"])
app.add_url_rule("/vendor/upload-document", view_func=vendor_services.upload_vendor_document, methods=["POST"])
app.add_url_rule("/vendor/create-shop", view_func=shop_services.create_shop, methods=["POST"])
app.add_url_rule("/vendor/payout/setup", view_func=vendor_services.setup_payout_bank, methods=["POST"])

# Shop Management
app.add_url_rule("/shop/update-hours", view_func=shop_services.update_shop_hours, methods=["POST"])
app.add_url_rule("/shop/edit", view_func=shop_services.edit_shop, methods=["POST"])
app.add_url_rule("/shop/my", view_func=shop_services.get_my_shop, methods=["GET"])
app.add_url_rule("/vendor/shop/toggle_status", view_func=shop_services.toggle_shop_status, methods=["POST"])

# Items
app.add_url_rule("/item/add", view_func=item_services.add_item, methods=["POST"])
app.add_url_rule("/item/bulk-upload", view_func=item_services.bulk_upload_items, methods=["POST"])
app.add_url_rule("/item/<int:item_id>/toggle", view_func=item_services.toggle_item_availability, methods=["POST"])
app.add_url_rule("/item/update/<int:item_id>", view_func=item_services.update_item, methods=["POST"])
app.add_url_rule("/item/my", view_func=item_services.get_items, methods=["GET"])

# Vendor Wallet
app.add_url_rule("/vendor/wallet", view_func=wallet_services.get_vendor_wallet, methods=["GET"])
app.add_url_rule("/vendor/wallet/history", view_func=wallet_services.get_vendor_wallet_history, methods=["GET"])
app.add_url_rule("/vendor/wallet/credit", view_func=wallet_services.credit_vendor_wallet, methods=["POST"])
app.add_url_rule("/vendor/wallet/debit", view_func=wallet_services.debit_vendor_wallet, methods=["POST"])
app.add_url_rule("/vendor/wallet/withdraw", view_func=wallet_services.withdraw_vendor_wallet, methods=["POST"])

# Vendor Orders
app.add_url_rule("/order/vendor", view_func=vendor_order_services.get_shop_orders, methods=["GET"])
app.add_url_rule("/order/vendor/status/<int:order_id>", view_func=vendor_order_services.update_order_status, methods=["POST"])
app.add_url_rule("/order/vendor/modify/<int:order_id>", view_func=vendor_order_services.modify_order_item, methods=["POST"])
app.add_url_rule("/order/vendor/cancel/<int:order_id>", view_func=vendor_order_services.cancel_order_vendor, methods=["POST"])
app.add_url_rule("/order/vendor/message/send/<int:order_id>", view_func=vendor_order_services.send_order_message_vendor, methods=["POST"])
app.add_url_rule("/order/vendor/messages/<int:order_id>", view_func=vendor_order_services.get_order_messages_vendor, methods=["GET"])
app.add_url_rule("/order/vendor/issues", view_func=vendor_order_services.get_issues_for_order, methods=["GET"])
app.add_url_rule("/order/return/vendor/accept/<int:order_id>", view_func=vendor_order_services.accept_return, methods=["POST"])
app.add_url_rule("/order/return/complete/<int:order_id>", view_func=vendor_order_services.complete_return, methods=["POST"])
app.add_url_rule("/order/return/vendor/initiate/<int:order_id>", view_func=vendor_order_services.vendor_initiate_return, methods=["POST"])

# ========================== Logging ==========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ========================== Run ==========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)
