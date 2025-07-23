from flask import request, jsonify
from models.user import OTP, UserProfile
from models import db
import random, uuid
from datetime import datetime, timedelta
from twilio.rest import Client
import os

# --- Logout handler ---

def logout_handler():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"status": "error", "message": "Token missing"}), 401

    user = UserProfile.query.filter_by(auth_token=token).first()
    if not user:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    user.auth_token = None
    user.token_created_at = None
    db.session.commit()

    return jsonify({"status": "success", "message": "Logged out"}), 200

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
        print(f"[WhatsApp] ✅ Message sent. SID: {message.sid}")
    except Exception as e:
        print(f"[WhatsApp] ❌ Failed to send message: {e}")


# --- Send OTP ---

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
    db.session.commit()

    # ✅ Send via Twilio or mock
    print(f"[DEBUG] OTP for {phone} is {otp_code}")  # Or use your actual Twilio send logic

    return jsonify({"status": "success", "message": "OTP sent"}), 200

# --- Verify OTP ---

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
            print(f"[DEBUG] OTP mismatch: submitted={otp}, expected={recent_otp.otp}")
            print(f"[DEBUG] is_used={recent_otp.is_used}, created_at={recent_otp.created_at}")
        else:
            print(f"[DEBUG] No OTP record found for phone: {phone}")
        return jsonify({"status": "error", "message": "Invalid or expired OTP"}), 401

    # ✅ Check OTP expiry
    otp_expiry_minutes = 10
    if datetime.utcnow() - otp_record.created_at > timedelta(minutes=otp_expiry_minutes):
        return jsonify({"status": "error", "message": "OTP expired"}), 401

    # ✅ Mark OTP as used
    otp_record.is_used = True

    # ✅ Generate secure token
    token = str(uuid.uuid4())
    otp_record.token = token

    # ✅ Get device/user-agent info safely
    user_agent = request.headers.get("User-Agent", "")[:200]

    # ✅ Create or update UserProfile
    user = UserProfile.query.filter_by(phone=phone).first()
    if not user:
        user = UserProfile(phone=phone)

    user.auth_token = token
    user.token_created_at = datetime.utcnow()
    user.device_info = user_agent

    # ✅ Commit to DB
    db.session.add(otp_record)
    db.session.add(user)
    db.session.commit()

    print(f"[DEBUG] ✅ OTP verified. Auth token issued for {phone}")

    return jsonify({
        "status": "success",
        "auth_token": token,
        "basic_onboarding_done": user.basic_onboarding_done if user else False
    }), 200