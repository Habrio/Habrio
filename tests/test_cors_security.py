import importlib
import sys


def load_app(monkeypatch, cors_value):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", cors_value)
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'dummy')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'dummy')
    monkeypatch.setenv('TWILIO_WHATSAPP_FROM', 'dummy')
    for module in ["main", "app.config"]:
        if module in sys.modules:
            del sys.modules[module]
    main = importlib.import_module("main")
    return main.app


def test_cors_preflight_allows_whitelisted_origin(monkeypatch):
    app = load_app(monkeypatch, "http://localhost:3000,https://app.example.com")
    app.config.update(TESTING=True)
    client = app.test_client()
    resp = client.open(
        "/__ok",
        method="OPTIONS",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    vary = resp.headers.get("Vary")
    if vary:
        assert "Origin" in vary


def test_cors_preflight_blocks_disallowed_origin(monkeypatch):
    app = load_app(monkeypatch, "https://app.example.com")
    app.config.update(TESTING=True)
    client = app.test_client()
    resp = client.open(
        "/__ok",
        method="OPTIONS",
        headers={
            "Origin": "http://evil.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code in (200, 204)
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_security_headers_and_expose_request_id(monkeypatch):
    app = load_app(monkeypatch, "*")
    app.config.update(TESTING=True)
    client = app.test_client()
    resp = client.get(
        "/__ok",
        headers={"Origin": "http://any.test", "X-Request-ID": "abc-123"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert resp.headers.get("X-Request-ID") == "abc-123"
    expose = resp.headers.get("Access-Control-Expose-Headers", "")
    assert "X-Request-ID" in expose

