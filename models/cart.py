from models import db
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
