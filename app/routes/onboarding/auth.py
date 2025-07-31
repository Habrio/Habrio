from flask import Blueprint, request, jsonify, current_app
from app.version import API_PREFIX
from flask_limiter.util import get_remote_address
from extensions import limiter
from models.user import OTP, UserProfile
from models import db
import random
from datetime import datetime, timedelta
from twilio.rest import Client
import logging
from app.utils import internal_error_response
from app.utils import error, transactional
from app.utils.validation import validate_schema
from app.tasks.notifications import send_whatsapp_message_task
from app.schemas.auth import SendOTPRequest, VerifyOTPRequest
from app.utils import (
    create_access_token,
    create_refresh_token,
    decode_token,
    TokenError,
)


auth_bp = Blueprint("auth", __name__, url_prefix=API_PREFIX)

# --- Logout handler ---
@auth_bp.route("/logout", methods=["POST"])
def logout_handler():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return error("Token missing", status=401)
    token = auth.split(" ", 1)[1]
    try:
        decode_token(token)
    except TokenError as e:
        return error(str(e), status=401)
    return jsonify({"status": "success", "message": "Logged out"}), 200


@auth_bp.route("/auth/refresh", methods=["POST"])
def refresh_tokens():
    j = request.get_json() or {}
    token = j.get("refresh_token", "")
    try:
        payload = decode_token(token, expected_type="refresh")
    except TokenError as e:
        return error(str(e), status=401)

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

def init_twilio(app):
    sid = app.config.get("TWILIO_ACCOUNT_SID")
    token = app.config.get("TWILIO_AUTH_TOKEN")
    whatsapp_from = app.config.get("TWILIO_WHATSAPP_FROM")
    if not all([sid, token, whatsapp_from]):
        logging.warning("Twilio credentials missing; using dummy values for testing")
        sid = sid or "dummy"
        token = token or "dummy"
        whatsapp_from = whatsapp_from or "dummy"
    app.twilio_client = Client(sid, token)
    app.config["TWILIO_WHATSAPP_FROM"] = whatsapp_from


# --- OTP Utility ---

def generate_otp():
    return str(random.randint(100000, 999999))


def send_whatsapp_message(to, body):
    try:
        client = current_app.twilio_client
        whatsapp_from = current_app.config.get("TWILIO_WHATSAPP_FROM")
        message = client.messages.create(
            from_=whatsapp_from,
            to=f"whatsapp:{to}",
            body=body
        )
        logging.info("[WhatsApp] ✅ Message sent. SID: %s", message.sid)
    except Exception as e:
        logging.error("Failed to send message: %s", e, exc_info=True)


# --- Send OTP ---

@auth_bp.route("/send-otp", methods=["POST"])
@limiter.limit(
    lambda: current_app.config["OTP_SEND_LIMIT_PER_IP"],
    key_func=get_remote_address,
    error_message="Too many OTP requests from this IP",
)
@limiter.limit(
    lambda: current_app.config["OTP_SEND_LIMIT_PER_PHONE"],
    key_func=lambda: (request.get_json() or {}).get("phone", ""),
    error_message="Too many OTP requests for this phone number",
)
@validate_schema(SendOTPRequest)
def send_otp_handler():
    data: SendOTPRequest = request.validated_data
    phone = data.phone

    otp_code = str(random.randint(100000, 999999))

    new_otp = OTP(
        phone=phone,
        otp=otp_code,
        is_used=False,
        created_at=datetime.utcnow()
    )

    try:
        with transactional("Failed to create OTP"):
            db.session.add(new_otp)
    except Exception as e:
        logging.error("Failed to create OTP: %s", e, exc_info=True)
        return internal_error_response()

    logging.info("[DEBUG] OTP for %s is %s", phone, otp_code)
    if current_app.config.get("TESTING"):
        send_whatsapp_message_task(phone, f"Your OTP is {otp_code}")
    else:
        send_whatsapp_message_task.delay(phone, f"Your OTP is {otp_code}")

    return jsonify({"status": "success", "message": "OTP sent"}), 200

# --- Verify OTP ---

@auth_bp.route("/verify-otp", methods=["POST"])
@limiter.limit(
    lambda: current_app.config["LOGIN_LIMIT_PER_IP"],
    key_func=get_remote_address,
    error_message="Too many logins from this IP",
)
@validate_schema(VerifyOTPRequest)
def verify_otp_handler():
    data: VerifyOTPRequest = request.validated_data
    phone = data.phone.strip()
    otp = data.otp.strip()

    otp_record = OTP.query.filter_by(phone=phone, otp=otp, is_used=False).first()

    if not otp_record:
        recent_otp = OTP.query.filter_by(phone=phone).order_by(OTP.created_at.desc()).first()
        if recent_otp:
            logging.warning("OTP mismatch: submitted=%s, expected=%s", otp, recent_otp.otp)
            logging.warning("is_used=%s, created_at=%s", recent_otp.is_used, recent_otp.created_at)
        else:
            logging.warning("No OTP record found for phone: %s", phone)
        return error("Invalid or expired OTP", status=401)

    otp_expiry_minutes = 10
    if datetime.utcnow() - otp_record.created_at > timedelta(minutes=otp_expiry_minutes):
        return error("OTP expired", status=401)

    otp_record.is_used = True

    user_agent = request.headers.get("User-Agent", "")[:200]

    user = UserProfile.query.filter_by(phone=phone).first()
    if not user:
        user = UserProfile(phone=phone)
    user.device_info = user_agent

    access_token = create_access_token(phone, user.role or "")
    refresh_token = create_refresh_token(phone)
    otp_record.token = "issued"

    try:
        with transactional("Failed to verify OTP"):
            db.session.add(otp_record)
            db.session.add(user)
    except Exception as e:
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
