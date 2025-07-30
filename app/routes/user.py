from flask import Blueprint, request, jsonify
from app.version import API_PREFIX
from models.user import ConsumerProfile
from models import db
from app.utils import auth_required
from app.utils import role_required
from app.utils import error, has_required_fields, transactional
import logging
from app.utils import internal_error_response

user_bp = Blueprint("user", __name__, url_prefix=API_PREFIX)

# Basic onboarding -------------
@user_bp.route("/onboarding/basic", methods=["POST"])
@auth_required
def basic_onboarding():
    """Complete initial onboarding details for the authenticated user."""
    data = request.get_json()
    required_fields = ["name", "city", "society", "role"]
    if not has_required_fields(data, required_fields):
        return error("Missing fields", status=400)

    user = request.user

    if user.basic_onboarding_done:
        return jsonify({"status": "success", "message": "Basic onboarding already complete"}), 200

    user.name = data["name"]
    user.city = data["city"]
    user.society = data["society"]
    user.role = data["role"]
    user.basic_onboarding_done = True

    try:
        with transactional("Failed basic onboarding"):
            db.session.add(user)
    except Exception:
        return internal_error_response()

    return jsonify({"status": "success", "message": "Basic onboarding complete"}), 200

# Consumer onboarding -------------
@user_bp.route("/onboarding/consumer", methods=["POST"])
@auth_required
@role_required(["consumer"])
def consumer_onboarding():
    user = request.user
    if not user or not user.basic_onboarding_done:
        return error("Basic onboarding incomplete", status=400)
    if user.role_onboarding_done:
        return error("Role onboarding already done", status=400)

    data = request.get_json()

    existing = ConsumerProfile.query.filter_by(user_phone=request.phone).first()
    if existing:
        return error("Profile already exists", status=400)

    consumer_profile = ConsumerProfile(
        user_phone=request.phone,
        name=user.name,
        city=user.city,
        society=user.society,
        flat_number=data.get("flat_number"),
        profile_image_url=data.get("profile_image_url"),
        gender=data.get("gender"),
        date_of_birth=data.get("date_of_birth"),
        preferred_language=data.get("preferred_language")
    )

    try:
        with transactional("Failed consumer onboarding"):
            db.session.add(consumer_profile)
            user.role_onboarding_done = True
    except Exception:
        return internal_error_response()

    return jsonify({"status": "success", "message": "Consumer onboarding done"}), 200

# Get Consumer Profile -------------
@user_bp.route("/profile/me", methods=["GET"])
@auth_required
@role_required(["consumer"])
def get_consumer_profile():
    user = request.user
    if not user:
        return error("User not found", status=404)

    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()
    if not profile:
        return error("Consumer profile not found", status=404)

    data = profile.to_dict()
    return jsonify({"status": "success", "data": data}), 200

# Edit Consumer Profile -------------
@user_bp.route("/profile/edit", methods=["POST"])
@auth_required
@role_required(["consumer"])
def edit_consumer_profile():
    user = request.user
    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()

    if not profile:
        return error("Consumer profile not found", status=404)

    data = request.get_json()

    profile.flat_number = data.get("flat_number", profile.flat_number)
    profile.profile_image_url = data.get("profile_image_url", profile.profile_image_url)
    profile.gender = data.get("gender", profile.gender)
    profile.date_of_birth = data.get("date_of_birth", profile.date_of_birth)
    profile.preferred_language = data.get("preferred_language", profile.preferred_language)

    try:
        with transactional("Failed to edit consumer profile"):
            pass  # changes already on profile object
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Profile updated"}), 200
