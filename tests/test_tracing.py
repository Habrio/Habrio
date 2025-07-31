import importlib
import sys
import pytest


def load_app(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'dummy')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'dummy')
    monkeypatch.setenv('TWILIO_WHATSAPP_FROM', 'dummy')
    for module in ["wsgi", "app.config"]:
        if module in sys.modules:
            del sys.modules[module]
    entry = importlib.import_module("wsgi")
    return entry.app


@pytest.fixture()
def test_client(monkeypatch):
    app = load_app(monkeypatch)
    app.config.update(TESTING=True)
    return app.test_client()


def test_traceparent_header(test_client):
    resp = test_client.get("/__ok")
    assert resp.status_code == 200
    assert "traceparent" in resp.headers
