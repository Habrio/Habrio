import importlib
import pytest
import jwt
import datetime as dt
from app.utils import decode_token, create_access_token, create_refresh_token


def _load(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    import wsgi as entry
    importlib.reload(entry)
    return entry.app


def _get_tokens(c, phone="auth1"):
    r = c.post("/__auth/login_stub", json={"phone": phone, "role": "consumer"})
    return r.get_json()["data"]


def test_access_token_allows_request(monkeypatch):
    app = _load(monkeypatch)
    with app.app_context():
        c = app.test_client()
        toks = _get_tokens(c)
        r = c.get("/api/v1/test_support/__ok", headers={"Authorization": f"Bearer {toks['access']}"})
        assert r.status_code == 200


def test_expired_access_token_blocked(monkeypatch):
    app = _load(monkeypatch)
    with app.app_context():
        past = dt.datetime.utcnow() - dt.timedelta(seconds=1)
        expired = jwt.encode({"sub": "x", "role": "consumer", "type": "access", "exp": past}, app.config["JWT_SECRET"], algorithm="HS256")
        c = app.test_client()
        r = c.get("/api/v1/test_support/__ok", headers={"Authorization": f"Bearer {expired}"})
        assert r.status_code == 401


def test_refresh_returns_new_access(monkeypatch):
    app = _load(monkeypatch)
    with app.app_context():
        c = app.test_client()
        toks = _get_tokens(c, "auth2")
        r = c.post("/api/v1/auth/refresh", json={"refresh_token": toks["refresh"]})
        assert r.status_code == 200
        new_access = r.get_json()["access_token"]
        r2 = c.get("/api/v1/test_support/__ok", headers={"Authorization": f"Bearer {new_access}"})
        assert r2.status_code == 200
