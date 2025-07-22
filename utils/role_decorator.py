from functools import wraps
from flask import request, jsonify
from models.user import UserProfile

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = UserProfile.query.filter_by(phone=request.phone).first()
            if not user or user.role not in allowed_roles:
                return jsonify({"status": "error", "message": "Access denied"}), 403
            request.user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator
