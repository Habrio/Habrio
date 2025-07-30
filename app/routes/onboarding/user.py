from flask import Blueprint, request, jsonify
from app.version import API_PREFIX
from models import db
from app.utils import auth_required
from app.utils import role_required
from app.utils import error, transactional
from app.utils.validation import validate_schema
from app.schemas.onboarding import BasicOnboardingRequest
import logging
from app.utils import internal_error_response

user_bp = Blueprint("user", __name__, url_prefix=API_PREFIX)

# Basic onboarding -------------
@user_bp.route("/onboarding/basic", methods=["POST"])
@auth_required
@validate_schema(BasicOnboardingRequest)
def basic_onboarding():
    """Complete initial onboarding details for the authenticated user."""
    data: BasicOnboardingRequest = request.validated_data

    user = request.user

    if user.basic_onboarding_done:
        return jsonify({"status": "success", "message": "Basic onboarding already complete"}), 200

    user.name = data.name
    user.city = data.city
    user.society = data.society
    user.role = data.role
    user.basic_onboarding_done = True

    try:
        with transactional("Failed basic onboarding"):
            db.session.add(user)
    except Exception:
        return internal_error_response()

    return jsonify({"status": "success", "message": "Basic onboarding complete"}), 200

