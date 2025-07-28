import importlib, pytest
from helpers.jwt_helpers import create_access_token


def _load(monkeypatch):
    monkeypatch.setenv("APP_ENV","testing")
    import wsgi as entry; importlib.reload(entry)
    return entry.app


def _token(app, phone, role):
    with app.app_context():
        return create_access_token(phone, role)


def test_scope_allowed(monkeypatch):
    app = _load(monkeypatch)
    client = app.test_client()
    hdr = {"Authorization": f"Bearer {_token(app,'vmod','vendor')}"}
    r = client.post("/api/v1/test_support/vendor_scope_ping", headers=hdr)
    assert r.status_code == 200
    assert r.get_json()["data"]["pong"] == "vendor_modify_ok"


def test_scope_denied(monkeypatch):
    app = _load(monkeypatch)
    client = app.test_client()
    hdr = {"Authorization": f"Bearer {_token(app,'vbad','vendor')}"}
    r = client.post("/api/v1/test_support/vendor/dummy_deliver", headers=hdr)
    assert r.status_code == 200
