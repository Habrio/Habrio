from flask import request, jsonify
from models.user import UserProfile
from datetime import datetime, timedelta
from functools import wraps

def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"status": "error", "message": "Token missing"}), 401

        user = UserProfile.query.filter_by(auth_token=token).first()
        if not user:
            return jsonify({"status": "error", "message": "Invalid token"}), 401

        if user.token_created_at and datetime.utcnow() - user.token_created_at > timedelta(days=30):
            return jsonify({"status": "error", "message": "Token expired"}), 401

        request.phone = user.phone
        request.user = user
        request.user_role = user.role
        return f(*args, **kwargs)

    return decorated_function
