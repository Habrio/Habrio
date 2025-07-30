from flask import request, jsonify
from . import vendor_bp
from app.utils import auth_required, role_required, transactional, error, internal_error_response, has_required_fields
from models.vendor import VendorProfile, VendorDocument, VendorPayoutBank
from datetime import datetime
from models import db

class ValidationError(Exception):
    pass

def create_vendor_profile(user, data):
    if not user or not user.basic_onboarding_done:
        raise ValidationError("Basic onboarding incomplete")
    business_type = data.get("business_type")
    business_name = data.get("business_name")
    gst_number = data.get("gst_number")
    address = data.get("address")
    if not business_type or not business_name or not address:
        raise ValidationError("Missing required vendor details")
    existing_profile = VendorProfile.query.filter_by(user_phone=user.phone).first()
    if existing_profile:
        raise ValidationError("Vendor profile already exists")
    profile = VendorProfile(
        user_phone=user.phone,
        business_name=business_name,
        gst_number=gst_number,
        address=address,
        business_type=business_type,
        kyc_status="pending",
    )
    db.session.add(profile)
    return profile

def add_document(user, doc_type: str, file_url: str) -> VendorDocument:
    if not doc_type or not file_url:
        raise ValidationError("Missing document type or file URL")
    new_doc = VendorDocument(
        vendor_phone=user.phone,
        document_type=doc_type,
        file_url=file_url,
    )
    db.session.add(new_doc)
    return new_doc

def setup_payout(user, data) -> VendorPayoutBank:
    required_fields = ["bank_name", "account_number", "ifsc_code"]
    if not all(field in data for field in required_fields):
        raise ValidationError("Missing bank details")
    existing = VendorPayoutBank.query.filter_by(user_phone=user.phone).first()
    if not existing:
        existing = VendorPayoutBank(user_phone=user.phone)
        db.session.add(existing)
    existing.bank_name = data["bank_name"]
    existing.account_number = data["account_number"]
    existing.ifsc_code = data["ifsc_code"]
    existing.updated_at = datetime.utcnow()
    return existing


@vendor_bp.route("/profile", methods=["POST"])
@auth_required
@role_required(["vendor"])
def vendor_profile_setup():
    user = request.user
    data = request.get_json()
    required = ["business_type", "business_name", "address"]
    if not has_required_fields(data, required):
        return error("Missing required vendor details", status=400)
    try:
        with transactional("Failed to create vendor profile"):
            create_vendor_profile(user, data)
        return jsonify({"status": "success", "message": "Vendor profile created"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()


@vendor_bp.route("/upload-document", methods=["POST"])
@auth_required
@role_required(["vendor"])
def upload_vendor_document():
    user = request.user
    data = request.get_json()
    doc_type = data.get("document_type")
    file_url = data.get("file_url")
    try:
        with transactional("Failed to upload vendor document"):
            add_document(user, doc_type, file_url)
        return jsonify({"status": "success", "message": "Document uploaded"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()


@vendor_bp.route("/payout/setup", methods=["POST"])
@auth_required
@role_required(["vendor"])
def setup_payout_bank():
    user = request.user
    data = request.get_json()
    try:
        with transactional("Failed to setup payout bank"):
            setup_payout(user, data)
        return jsonify({"status": "success", "message": "Payout bank info saved"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()
