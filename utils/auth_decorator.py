from functools import wraps
from flask import request, jsonify, g
from utils.role_decorator import role_required  # keep role decorator unchanged
from helpers.jwt_helpers import decode_token, TokenError
from models.user import UserProfile


def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"status": "error", "message": "Auth header missing"}), 401
        token = auth.split(" ", 1)[1]
        try:
            payload = decode_token(token, expected_type="access")
        except TokenError as e:
            return jsonify({"status": "error", "message": str(e)}), 401

        # Expose user info to downstream handlers
        g.phone = payload["sub"]
        g.role = payload.get("role")
        request.phone = g.phone  # maintain backward compat
        user = UserProfile.query.filter_by(phone=g.phone).first()
        if user:
            request.user = user
        else:
            request.user = type("User", (), {"phone": g.phone, "role": g.role})
        return func(*args, **kwargs)

    return wrapper
