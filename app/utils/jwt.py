import datetime as dt
from typing import Dict
import jwt
from flask import current_app


def _secret() -> str:
    return current_app.config["JWT_SECRET"]


def _utcnow():
    return dt.datetime.utcnow()


def _exp(minutes: int = None, days: int = None):
    now = _utcnow()
    if minutes:
        return now + dt.timedelta(minutes=minutes)
    if days:
        return now + dt.timedelta(days=days)
    raise ValueError("must supply minutes or days")


def create_access_token(phone: str, role: str) -> str:
    cfg = current_app.config
    payload: Dict = {
        "sub": phone,
        "role": role,
        "type": "access",
        "exp": _exp(minutes=cfg["ACCESS_TOKEN_LIFETIME_MIN"]),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def create_refresh_token(phone: str) -> str:
    cfg = current_app.config
    payload = {
        "sub": phone,
        "type": "refresh",
        "exp": _exp(days=cfg["REFRESH_TOKEN_LIFETIME_DAYS"]),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


class TokenError(Exception):
    pass


def decode_token(token: str, expected_type: str = "access") -> Dict:
    try:
        data = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise TokenError("token expired")
    except jwt.InvalidTokenError:
        raise TokenError("invalid token")

    if data.get("type") != expected_type:
        raise TokenError(f"expected {expected_type} token")
    return data
