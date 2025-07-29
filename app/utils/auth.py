from functools import wraps
from flask import request, g
from .responses import error
from app.auth.permissions import role_has_scope
from .jwt import decode_token, TokenError
from models.user import UserProfile


def auth_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth:
            return error("Auth header missing", status=401)
        token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else auth
        try:
            payload = decode_token(token, expected_type="access")
        except TokenError as e:
            return error(str(e), status=401)

        g.phone = payload["sub"]
        g.role = payload.get("role")
        request.phone = g.phone
        user = UserProfile.query.filter_by(phone=g.phone).first()
        if user:
            request.user = user
        else:
            request.user = type("User", (), {"phone": g.phone, "role": g.role})
        return func(*args, **kwargs)

    return wrapper


def _to_set(obj):
    return set(obj) if isinstance(obj, (list, tuple, set)) else {obj}


def role_required(required):
    """Authorize based on user role or scoped action."""
    required_set = _to_set(required)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = getattr(g, "role", None)
            db_role = getattr(getattr(request, "user", None), "role", None)
            if db_role:
                role = db_role
            if not role:
                return error("Role missing", status=403)
            for entry in required_set:
                if ":" in entry:
                    r, action = entry.split(":", 1)
                    if role == r and role_has_scope(role, action):
                        break
                else:
                    if role == entry:
                        break
            else:
                return error("Forbidden", status=403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
