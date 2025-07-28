# --- services/user.py ---
from flask import request, jsonify
from models.user import ConsumerProfile
from models import db
from utils.auth_decorator import auth_required
from utils.role_decorator import role_required
from datetime import datetime
import logging
from utils.responses import internal_error_response

# Basic onboarding -------------
@auth_required
def basic_onboarding():
    """Complete initial onboarding details for the authenticated user."""
    data = request.get_json()
    required_fields = ["name", "city", "society", "role"]
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing fields"}), 400

    phone = request.phone
    role = data["role"]

    user = request.user

    if user.basic_onboarding_done:
        return jsonify({"status": "error", "message": "User already onboarded"}), 400
    if user.role and user.role != role:
        return jsonify({"status": "error", "message": "Role mismatch"}), 400

    user.name = data["name"]
    user.city = data["city"]
    user.society = data["society"]
    user.role = role
    user.basic_onboarding_done = True

    db.session.add(user)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed basic onboarding: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Basic onboarding complete"}), 200


# Consumer onboarding -------------
@auth_required
@role_required(["consumer"])
def consumer_onboarding():
    user = request.user
    if not user or not user.basic_onboarding_done:
        return jsonify({"status": "error", "message": "Basic onboarding incomplete"}), 400
    if user.role_onboarding_done:
        return jsonify({"status": "error", "message": "Role onboarding already done"}), 400

    data = request.get_json()

    existing = ConsumerProfile.query.filter_by(user_phone=request.phone).first()
    if existing:
        return jsonify({"status": "error", "message": "Profile already exists"}), 400

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

    db.session.add(consumer_profile)
    user.role_onboarding_done = True
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed consumer onboarding: %s", e, exc_info=True)
        return internal_error_response()

    return jsonify({"status": "success", "message": "Consumer onboarding done"}), 200

# Get Consumer Profile -------------

@auth_required
@role_required(["consumer"])
def get_consumer_profile():
    user = request.user
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()
    if not profile:
        return jsonify({"status": "error", "message": "Consumer profile not found"}), 404

    data = profile.to_dict()
    return jsonify({"status": "success", "data": data}), 200

# Edit Consumer Profile -------------
@auth_required
@role_required(["consumer"])
def edit_consumer_profile():
    user = request.user
    profile = ConsumerProfile.query.filter_by(user_phone=user.phone).first()

    if not profile:
        return jsonify({"status": "error", "message": "Consumer profile not found"}), 404

    data = request.get_json()

    profile.flat_number = data.get("flat_number", profile.flat_number)
    profile.profile_image_url = data.get("profile_image_url", profile.profile_image_url)
    profile.gender = data.get("gender", profile.gender)
    profile.date_of_birth = data.get("date_of_birth", profile.date_of_birth)
    profile.preferred_language = data.get("preferred_language", profile.preferred_language)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to edit consumer profile: %s", e, exc_info=True)
        return internal_error_response()
    return jsonify({"status": "success", "message": "Profile updated"}), 200