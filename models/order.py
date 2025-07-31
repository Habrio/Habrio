from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from models import BIGINT
from sqlalchemy.sql import func
from models import db
from datetime import datetime


class Order(db.Model):
    __tablename__ = "order"
    __table_args__ = (
        db.Index("ix_order_shop_status", "shop_id", "status"),
    )
    id = Column(BIGINT, primary_key=True)
    user_phone = Column(String(15), ForeignKey("user_profile.phone"), nullable=False)
    shop_id = Column(BIGINT, ForeignKey("shop.id"), nullable=False)
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
    id = db.Column(BIGINT, primary_key=True)
    order_id = db.Column(BIGINT, db.ForeignKey("order.id"), nullable=False)
    item_id = db.Column(BIGINT, nullable=False)

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
    id = Column(BIGINT, primary_key=True)
    order_id = Column(BIGINT, ForeignKey("order.id"), nullable=False)
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
    id = Column(BIGINT, primary_key=True)
    order_id = Column(BIGINT, ForeignKey("order.id"), nullable=False)
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
    id = Column(BIGINT, primary_key=True)
    order_id = Column(BIGINT, ForeignKey("order.id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    actor_phone = Column(String(15), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=func.now())


class OrderRating(db.Model):
    __tablename__ = "order_rating"
    id = db.Column(BIGINT, primary_key=True)
    order_id = db.Column(BIGINT, db.ForeignKey("order.id"), nullable=False)
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
    id = db.Column(BIGINT, primary_key=True)
    order_id = db.Column(BIGINT, db.ForeignKey("order.id"), nullable=False)
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
    id = db.Column(BIGINT, primary_key=True)
    order_id = db.Column(BIGINT, db.ForeignKey("order.id"), nullable=False)
    item_id = db.Column(BIGINT, db.ForeignKey("item.id"), nullable=True)  # Null for full return
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
