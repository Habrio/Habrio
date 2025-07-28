from flask import request, jsonify, current_app, Blueprint
from flask_limiter.util import get_remote_address
from main import limiter, app
from models.user import OTP, UserProfile
from models import db
import random
from datetime import datetime, timedelta
from twilio.rest import Client
import os
import logging
from utils.responses import internal_error_response
from helpers.jwt_helpers import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenError,
)


auth_bp = Blueprint("auth_bp", __name__)

# --- Logout handler ---

def logout_handler():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"status": "error", "message": "Token missing"}), 401
    token = auth.split(" ", 1)[1]
    try:
        decode_token(token)
    except TokenError as e:
        return jsonify({"status": "error", "message": str(e)}), 401
    return jsonify({"status": "success", "message": "Logged out"}), 200


@auth_bp.route("/refresh", methods=["POST"])
def refresh_tokens():
    j = request.get_json() or {}
    token = j.get("refresh_token", "")
    try:
        payload = decode_token(token, expected_type="refresh")
    except TokenError as e:
        return jsonify({"status": "error", "message": str(e)}), 401

    phone = payload.get("sub")
    user = UserProfile.query.filter_by(phone=phone).first()
    role = user.role if user else ""
    access_token = create_access_token(phone, role or "")
    refresh_token = create_refresh_token(phone)
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": current_app.config["ACCESS_TOKEN_LIFETIME_MIN"] * 60,
    }), 200

# --- Twilio Configuration ---

twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")

if not all([twilio_sid, twilio_token, whatsapp_from]):
    raise EnvironmentError("❌ Twilio credentials are missing from environment variables.")

client = Client(twilio_sid, twilio_token)


# --- OTP Utility ---

def generate_otp():
    return str(random.randint(100000, 999999))


def send_whatsapp_message(to, body):
    try:
        message = client.messages.create(
            from_=whatsapp_from,
            to=f"whatsapp:{to}",
            body=body
        )
        logging.info("[WhatsApp] ✅ Message sent. SID: %s", message.sid)
    except Exception as e:
        logging.error("Failed to send message: %s", e, exc_info=True)


# --- Send OTP ---

@limiter.limit(
    app.config["OTP_SEND_LIMIT_PER_IP"],
    key_func=get_remote_address,
    error_message="Too many OTP requests from this IP",
)
@limiter.limit(
    app.config["OTP_SEND_LIMIT_PER_PHONE"],
    key_func=lambda: (request.get_json() or {}).get("phone", ""),
    error_message="Too many OTP requests for this phone number",
)
def send_otp_handler():
    data = request.get_json()
    phone = data.get("phone")

    if not phone:
        return jsonify({"status": "error", "message": "Phone number is required"}), 400

    # Generate OTP (you may already have this logic)
    otp_code = str(random.randint(100000, 999999))

    # ✅ Create new OTP record with fresh timestamp
    new_otp = OTP(
        phone=phone,
        otp=otp_code,
        is_used=False,
        created_at=datetime.utcnow()
    )

    db.session.add(new_otp)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to create OTP: %s", e, exc_info=True)
        return internal_error_response()

    # ✅ Send via Twilio or mock
    logging.info("[DEBUG] OTP for %s is %s", phone, otp_code)

    return jsonify({"status": "success", "message": "OTP sent"}), 200

# --- Verify OTP ---

@limiter.limit(
    app.config["LOGIN_LIMIT_PER_IP"],
    key_func=get_remote_address,
    error_message="Too many logins from this IP",
)
def verify_otp_handler():
    data = request.get_json()
    phone = data.get("phone", "").strip()
    otp = data.get("otp", "").strip()

    if not phone or not otp:
        return jsonify({"status": "error", "message": "Phone and OTP are required"}), 400

    # ✅ Look for matching OTP record
    otp_record = OTP.query.filter_by(phone=phone, otp=otp, is_used=False).first()

    if not otp_record:
        # 🔍 Debug info if OTP failed
        recent_otp = OTP.query.filter_by(phone=phone).order_by(OTP.created_at.desc()).first()
        if recent_otp:
            logging.warning("OTP mismatch: submitted=%s, expected=%s", otp, recent_otp.otp)
            logging.warning("is_used=%s, created_at=%s", recent_otp.is_used, recent_otp.created_at)
        else:
            logging.warning("No OTP record found for phone: %s", phone)
        return jsonify({"status": "error", "message": "Invalid or expired OTP"}), 401

    # ✅ Check OTP expiry
    otp_expiry_minutes = 10
    if datetime.utcnow() - otp_record.created_at > timedelta(minutes=otp_expiry_minutes):
        return jsonify({"status": "error", "message": "OTP expired"}), 401

    # ✅ Mark OTP as used
    otp_record.is_used = True

    # ✅ Get device/user-agent info safely
    user_agent = request.headers.get("User-Agent", "")[:200]

    # ✅ Create or update UserProfile
    user = UserProfile.query.filter_by(phone=phone).first()
    if not user:
        user = UserProfile(phone=phone)
    user.device_info = user_agent

    # ✅ Generate tokens
    access_token = create_access_token(phone, user.role or "")
    refresh_token = create_refresh_token(phone)
    otp_record.token = "issued"

    # ✅ Commit to DB
    db.session.add(otp_record)
    db.session.add(user)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error("Failed to verify OTP: %s", e, exc_info=True)
        return internal_error_response()

    logging.info("[DEBUG] ✅ OTP verified. Tokens issued for %s", phone)

    return jsonify({
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": current_app.config["ACCESS_TOKEN_LIFETIME_MIN"] * 60,
        "basic_onboarding_done": user.basic_onboarding_done if user else False
    }), 200
