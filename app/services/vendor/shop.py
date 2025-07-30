from datetime import datetime
from models import db
from models.shop import Shop
from models.vendor import VendorProfile


class ShopValidationError(Exception):
    pass


def create_shop_for_vendor(user, data) -> Shop:
    vendor_profile = VendorProfile.query.filter_by(user_phone=user.phone).first()
    if not vendor_profile:
        raise ShopValidationError("Vendor profile not found. Please complete vendor onboarding first.")
    if Shop.query.filter_by(phone=user.phone).first():
        raise ShopValidationError("Shop already exists for this vendor")
    required_fields = ["shop_name", "shop_type"]
    if not all(field in data for field in required_fields):
        raise ShopValidationError("Missing required fields")
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
    db.session.flush()
    vendor_profile.shop_id = new_shop.id
    user.role_onboarding_done = True
    return new_shop
