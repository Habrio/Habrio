from flask import request, jsonify
from models import db
from models.user import ConsumerProfile
from app.utils import auth_required, role_required, transactional, error, internal_error_response
from . import consumer_bp


@consumer_bp.route("/onboarding", methods=["POST"])
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
        preferred_language=data.get("preferred_language"),
    )
    try:
        with transactional("Failed consumer onboarding"):
            db.session.add(consumer_profile)
            user.role_onboarding_done = True
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Consumer onboarding done"}), 200


@consumer_bp.route("/profile/me", methods=["GET"])
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


@consumer_bp.route("/profile/edit", methods=["POST"])
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
            pass
    except Exception:
        return internal_error_response()
    return jsonify({"status": "success", "message": "Profile updated"}), 200
