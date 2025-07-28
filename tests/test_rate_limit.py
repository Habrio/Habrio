import importlib
from app.version import API_PREFIX

def _load_app(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    import wsgi as entry
    importlib.reload(entry)
    return entry.app

def test_otp_send_rate_limit(monkeypatch):
    app = _load_app(monkeypatch)
    client = app.test_client()
    for i in range(6):
        r = client.post(f"{API_PREFIX}/send-otp", json={"phone": "9111111111"})
    assert r.status_code == 429
    assert "limit" in r.get_json()["message"].lower()

def test_order_confirm_rate_limit(monkeypatch):
    app = _load_app(monkeypatch)
    client = app.test_client()
    for i in range(21):
        r = client.post(f"{API_PREFIX}/order/confirm", json={"dummy": "ok"})
    assert r.status_code == 429
