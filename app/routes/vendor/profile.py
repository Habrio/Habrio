from flask import request, jsonify
from . import vendor_bp
from app.utils import auth_required, role_required, transactional, error, internal_error_response
from app.utils.validation import validate_schema
from app.schemas.vendor import VendorProfileRequest, VendorDocumentRequest, PayoutSetupRequest
from app.services.vendor.profile import (
    create_vendor_profile,
    add_document,
    setup_payout,
    ValidationError,
)


@vendor_bp.route("/profile", methods=["POST"])
@auth_required
@role_required(["vendor"])
@validate_schema(VendorProfileRequest)
def vendor_profile_setup():
    user = request.user
    data: VendorProfileRequest = request.validated_data
    try:
        with transactional("Failed to create vendor profile"):
            create_vendor_profile(user, data.dict())
        return jsonify({"status": "success", "message": "Vendor profile created"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()


@vendor_bp.route("/upload-document", methods=["POST"])
@auth_required
@role_required(["vendor"])
@validate_schema(VendorDocumentRequest)
def upload_vendor_document():
    user = request.user
    data: VendorDocumentRequest = request.validated_data
    doc_type = data.document_type
    file_url = data.file_url
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
@validate_schema(PayoutSetupRequest)
def setup_payout_bank():
    user = request.user
    data: PayoutSetupRequest = request.validated_data
    try:
        with transactional("Failed to setup payout bank"):
            setup_payout(user, data.dict())
        return jsonify({"status": "success", "message": "Payout bank info saved"}), 200
    except ValidationError as e:
        return error(str(e), status=400)
    except Exception:
        return internal_error_response()
