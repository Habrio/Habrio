from flask import request, jsonify
from models.vendor import VendorProfile, VendorDocument, VendorPayoutBank
from models import db
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from datetime import datetime
import logging
from utils.responses import internal_error_response


# Vendor Onboarding -----------------

@auth_required
@role_required(["vendor"])
def vendor_profile_setup():
    user = request.user

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
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to create vendor profile: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Vendor profile created"}), 200

# Vendor Onboarding Documents-----------------

@auth_required
@role_required(["vendor"])
def upload_vendor_document():
    user = request.user
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
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to upload vendor document: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Document uploaded"}), 200

# Vendor Payout info ----------------

@auth_required
@role_required(["vendor"])
def setup_payout_bank():
    user = request.user
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

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to setup payout bank: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Payout bank info saved"}), 200
