from flask import Blueprint, request, jsonify
from app.version import API_PREFIX
from models import db
from app.utils import auth_required
from app.utils import role_required
import logging
from app.utils import internal_error_response
from app.services import vendor_service
from app.services.vendor_service import ValidationError

vendor_bp = Blueprint("vendor", __name__, url_prefix=f"{API_PREFIX}/vendor")

# Vendor Onboarding -----------------
@vendor_bp.route("/profile", methods=["POST"])
@auth_required
@role_required(["vendor"])
def vendor_profile_setup():
    user = request.user
    data = request.get_json()
    try:
        vendor_service.create_vendor_profile(user, data)
        db.session.commit()
        return jsonify({"status": "success", "message": "Vendor profile created"}), 200
    except ValidationError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to create vendor profile: %s", e, exc_info=True)
        return internal_error_response()

# Vendor Onboarding Documents-----------------
@vendor_bp.route("/upload-document", methods=["POST"])
@auth_required
@role_required(["vendor"])
def upload_vendor_document():
    user = request.user
    data = request.get_json()

    doc_type = data.get("document_type")
    file_url = data.get("file_url")
    try:
        vendor_service.add_document(user, doc_type, file_url)
        db.session.commit()
        return jsonify({"status": "success", "message": "Document uploaded"}), 200
    except ValidationError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to upload vendor document: %s", e, exc_info=True)
        return internal_error_response()

# Vendor Payout info ----------------
@vendor_bp.route("/payout/setup", methods=["POST"])
@auth_required
@role_required(["vendor"])
def setup_payout_bank():
    user = request.user
    data = request.get_json()
    try:
        vendor_service.setup_payout(user, data)
        db.session.commit()
        return jsonify({"status": "success", "message": "Payout bank info saved"}), 200
    except ValidationError as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to setup payout bank: %s", e, exc_info=True)
        return internal_error_response()
