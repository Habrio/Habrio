from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime
from sqlalchemy.sql import func
from models import db


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

