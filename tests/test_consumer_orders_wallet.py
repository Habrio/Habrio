import importlib
import pytest
from models import db
from models.wallet import ConsumerWallet, WalletTransaction


def _load_app(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    import wsgi as entry
    importlib.reload(entry)
    return entry.app


def test_confirm_order_wallet_debits(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        c.post("/__seed/basic", json={"consumer_phone": "c1", "vendor_phone": "v1", "item": {"title": "Milk", "price": 50.0}, "cart_qty": 2})
        r = c.post("/__wallet/seed", json={"phone": "c1", "amount": 200})
        assert r.status_code == 200
        r = c.post("/__orders/confirm", json={"phone": "c1", "payment_mode": "wallet"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "success"
        order_id = data["order_id"]
        w = ConsumerWallet.query.filter_by(user_phone="c1").first()
        assert float(w.balance) == 100.0


def test_confirm_modified_order_refund(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        c.post("/__seed/basic", json={"consumer_phone": "c2", "vendor_phone": "v2", "item": {"title": "Tea", "price": 40.0}, "cart_qty": 3})
        c.post("/__wallet/seed", json={"phone": "c2", "amount": 200})
        r = c.post("/__orders/confirm", json={"phone": "c2", "payment_mode": "wallet"})
        oid = r.get_json()["order_id"]
        r = c.post(f"/__orders/confirm_modified/{oid}", json={"phone": "c2", "new_final_amount": 90})
        assert r.status_code == 200
        w = ConsumerWallet.query.filter_by(user_phone="c2").first()
        assert float(w.balance) == 200 - 120 + 30


def test_cancel_order_refund(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        c.post("/__seed/basic", json={"consumer_phone": "c3", "vendor_phone": "v3", "item": {"title": "Bread", "price": 30.0}, "cart_qty": 2})
        c.post("/__wallet/seed", json={"phone": "c3", "amount": 100})
        r = c.post("/__orders/confirm", json={"phone": "c3", "payment_mode": "wallet"})
        oid = r.get_json()["order_id"]
        r = c.post(f"/__orders/cancel/{oid}", json={"phone": "c3"})
        assert r.status_code == 200
        w = ConsumerWallet.query.filter_by(user_phone="c3").first()
        assert float(w.balance) == 100.0
