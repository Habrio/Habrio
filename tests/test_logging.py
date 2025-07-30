import importlib
import sys
import logging

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


def test_request_id_header_and_propagation(test_client):
    resp = test_client.get("/__ok", headers={"X-Request-ID": "my-fixed-id-123"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "my-fixed-id-123"


def test_logs_include_request_id_attribute(monkeypatch, caplog):
    app = load_app(monkeypatch)
    app.config.update(TESTING=True)
    caplog.set_level("INFO")
    client = app.test_client()
    resp = client.get("/__log", headers={"X-Request-ID": "rid-abc"})
    assert resp.status_code == 200
    assert any(getattr(r, "request_id", "") == "rid-abc" for r in caplog.records)


def test_sensitive_fields_masked_in_info(monkeypatch, caplog):
    from app.logging import MaskingFilter
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    app = load_app(monkeypatch)
    app.config.update(TESTING=True)
    caplog.set_level("INFO")
    caplog.handler.addFilter(MaskingFilter())
    logger = logging.getLogger("mask_test")
    with app.app_context():
        logger.info({"email": "user@example.com", "otp": "123456"})
    record = next(r for r in caplog.records if r.name == "mask_test")
    assert isinstance(record.msg, dict)
    assert record.msg["email"] == "[REDACTED]"
    assert record.msg["otp"] == "[REDACTED]"


def test_sensitive_fields_visible_in_debug(monkeypatch, caplog):
    from app.logging import MaskingFilter
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("APP_ENV", "development")
    app = load_app(monkeypatch)
    app.config.update(TESTING=True)
    caplog.set_level("DEBUG")
    caplog.handler.addFilter(MaskingFilter())
    logger = logging.getLogger("mask_test_debug")
    with app.app_context():
        logger.debug({"password": "secret"})
    record = next(r for r in caplog.records if r.name == "mask_test_debug")
    assert isinstance(record.msg, dict)
    assert record.msg["password"] == "secret"

