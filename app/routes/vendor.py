from flask import Blueprint, request, jsonify
from app.version import API_PREFIX
from models import db
from app.utils import auth_required
from app.utils import role_required
import logging
from app.utils import internal_error_response
from app.utils import error, transactional
from app.services import vendor_service
from app.services.vendor_service import ValidationError
from app.utils import has_required_fields

vendor_bp = Blueprint("vendor", __name__, url_prefix=f"{API_PREFIX}/vendor")

# Vendor Onboarding -----------------
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
            vendor_service.create_vendor_profile(user, data)
        return jsonify({"status": "success", "message": "Vendor profile created"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
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
        with transactional("Failed to upload vendor document"):
            vendor_service.add_document(user, doc_type, file_url)
        return jsonify({"status": "success", "message": "Document uploaded"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()

# Vendor Payout info ----------------
@vendor_bp.route("/payout/setup", methods=["POST"])
@auth_required
@role_required(["vendor"])
def setup_payout_bank():
    user = request.user
    data = request.get_json()
    try:
        with transactional("Failed to setup payout bank"):
            vendor_service.setup_payout(user, data)
        return jsonify({"status": "success", "message": "Payout bank info saved"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()
