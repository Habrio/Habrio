import sys
import importlib
import pytest
from werkzeug.routing import Rule


def _load_app(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    for m in ["main", "app.config", "app.test_support"]:
        if m in sys.modules:
            del sys.modules[m]
    import main as entry
    importlib.reload(entry)
    return entry.app


def test_test_support_unversioned_still_works(monkeypatch):
    app = _load_app(monkeypatch)
    c = app.test_client()
    r = c.get("/__ok")
    assert r.status_code == 200
    js = r.get_json()
    assert js["status"] == "success"
    assert js["data"]["ping"] == "pong"


def test_test_support_also_available_under_api_v1(monkeypatch):
    app = _load_app(monkeypatch)
    c = app.test_client()
    r = c.get("/api/v1/test_support/__ok")
    assert r.status_code == 200
    js = r.get_json()
    assert js["status"] == "success"
    assert js["data"]["ping"] == "pong"


def test_url_map_contains_api_v1_rules(monkeypatch):
    app = _load_app(monkeypatch)
    prefixes = {str(r.rule) for r in app.url_map.iter_rules()}
    assert any(p.startswith("/api/v1/") for p in prefixes)
