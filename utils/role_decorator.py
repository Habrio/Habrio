from functools import wraps
from flask import request, g, jsonify
from app.auth.permissions import role_has_scope


def _to_set(obj):
    return set(obj) if isinstance(obj, (list, tuple, set)) else {obj}


def role_required(required):
    """
    Accepts:
      - "vendor"
      - ["vendor", "admin"]
      - "vendor:modify_order"
      - ["admin", "vendor:deliver_order"]
    Authorizes if ANY entry matches:
      • plain role: g.role == entry
      • role:action: g.role == role AND role_has_scope(role, action)
    """
    required_set = _to_set(required)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = getattr(g, "role", None)
            db_role = getattr(getattr(request, "user", None), "role", None)
            if db_role:
                role = db_role
            if not role:
                return jsonify({"status":"error","message":"Role missing"}), 403
            for entry in required_set:
                if ":" in entry:
                    r, action = entry.split(":",1)
                    if role == r and role_has_scope(role, action):
                        break
                else:
                    if role == entry:
                        break
            else:
                return jsonify({"status":"error","message":"Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper

    return decorator
