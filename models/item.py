# --- models/item.py ---
from models import db, BIGINT
from datetime import datetime

class Item(db.Model):
    __tablename__ = "item"

    id = db.Column(BIGINT, primary_key=True)
    shop_id = db.Column(BIGINT, db.ForeignKey("shop.id"), nullable=False)

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
