from models import db
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