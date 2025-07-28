import importlib
import pytest
from helpers.jwt_helpers import create_access_token
from models import db, UserProfile, Shop, Order


def _load_app(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    import wsgi as entry
    importlib.reload(entry)
    return entry.app


@pytest.fixture
def client(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(UserProfile(phone="admin", role="admin"))
        db.session.commit()
    return app.test_client()

def _token(client):
    with client.application.app_context():
        return create_access_token("admin", "admin")


def test_admin_users_endpoint(client):
    token = _token(client)
    r = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "users" in r.get_json()


def test_admin_shops_endpoint(client):
    token = _token(client)
    r = client.get("/api/v1/admin/shops", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "shops" in r.get_json()


def test_admin_orders_endpoint(client):
    token = _token(client)
    r = client.get("/api/v1/admin/orders", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "orders" in r.get_json()
