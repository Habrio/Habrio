from models import db
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

