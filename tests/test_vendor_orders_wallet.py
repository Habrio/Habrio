import importlib
import pytest
from models import db
from models.wallet import ConsumerWallet, VendorWallet, WalletTransaction, VendorWalletTransaction


def _load_app(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    import wsgi as entry
    importlib.reload(entry)
    return entry.app


def test_delivered_credits_vendor_wallet(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        r = c.post("/__seed/order_paid", json={
            "consumer_phone": "c10",
            "vendor_phone": "v10",
            "items": [{"title": "A", "price": 50, "qty": 3}],
            "wallet_paid": True
        })
        oid = r.get_json()["data"]["order_id"]
        r = c.post(f"/__vendor/update_status/{oid}", json={"vendor_phone": "v10", "status": "delivered"})
        assert r.status_code == 200
        vw = VendorWallet.query.filter_by(user_phone="v10").first()
        assert float(vw.balance) == 150.0
        tx = VendorWalletTransaction.query.filter_by(user_phone="v10").all()
        assert any(t.type == "credit" for t in tx)


def test_vendor_cancel_refunds_consumer(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        r = c.post("/__seed/order_paid", json={
            "consumer_phone": "c11",
            "vendor_phone": "v11",
            "items": [{"title": "A", "price": 40, "qty": 2}],
            "wallet_paid": True
        })
        oid = r.get_json()["data"]["order_id"]
        r = c.post(f"/__vendor/cancel/{oid}", json={"vendor_phone": "v11"})
        assert r.status_code == 200
        cw = ConsumerWallet.query.filter_by(user_phone="c11").first()
        assert float(cw.balance) == 80.0
        tx = WalletTransaction.query.filter_by(user_phone="c11").all()
        assert any(t.type == "refund" for t in tx)


def test_complete_return_refunds_consumer_and_debits_vendor(monkeypatch):
    app = _load_app(monkeypatch)
    with app.app_context():
        db.create_all()
        c = app.test_client()
        r = c.post("/__seed/order_paid", json={
            "consumer_phone": "c12",
            "vendor_phone": "v12",
            "items": [
                {"title": "A", "price": 50, "qty": 2},
                {"title": "B", "price": 30, "qty": 1}
            ],
            "wallet_paid": True
        })
        oid = r.get_json()["data"]["order_id"]
        c.post(f"/__vendor/update_status/{oid}", json={"vendor_phone": "v12", "status": "delivered"})
        c.post(f"/__vendor/return/prepare/{oid}", json={"returns": [{"item_name": "A", "quantity": 1}]})
        r = c.post(f"/__vendor/return/complete/{oid}", json={"vendor_phone": "v12"})
        assert r.status_code == 200
        cw = ConsumerWallet.query.filter_by(user_phone="c12").first()
        vw = VendorWallet.query.filter_by(user_phone="v12").first()
        assert float(cw.balance) == 50.0
        assert float(vw.balance) == 130.0 - 50.0

