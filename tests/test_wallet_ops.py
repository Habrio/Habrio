import os, importlib, sys
from decimal import Decimal
import pytest
from models import db
from models.wallet import ConsumerWallet, WalletTransaction, VendorWallet, VendorWalletTransaction


def _reload_entrypoint(monkeypatch):
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "dummy")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "dummy")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "dummy")
    import wsgi as entry
    importlib.reload(entry)
    return entry.app, entry


def test_consumer_credit_and_debit_via_helper(monkeypatch):
    app, entry = _reload_entrypoint(monkeypatch)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        r = client.post("/__wallet/consumer/adjust", json={"phone": "999", "delta": 100, "type": "recharge", "reference": "t1"})
        assert r.status_code == 200
        assert r.get_json()["data"]["balance"] == 100.0

        r = client.post("/__wallet/consumer/adjust", json={"phone": "999", "delta": -30, "type": "debit", "reference": "t2"})
        assert r.status_code == 200
        assert r.get_json()["data"]["balance"] == 70.0

        r = client.post("/__wallet/consumer/adjust", json={"phone": "999", "delta": -100, "type": "debit", "reference": "t3"})
        assert r.status_code == 400

        w = ConsumerWallet.query.filter_by(user_phone="999").first()
        assert float(w.balance) == 70.0
        txns = WalletTransaction.query.filter_by(user_phone="999").all()
        assert len(txns) == 2


def test_vendor_credit_and_withdraw(monkeypatch):
    app, entry = _reload_entrypoint(monkeypatch)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        r = client.post("/__wallet/vendor/adjust", json={"phone": "888", "delta": 250, "type": "credit", "reference": "v1"})
        assert r.status_code == 200
        assert r.get_json()["data"]["balance"] == 250.0

        r = client.post("/__wallet/vendor/adjust", json={"phone": "888", "delta": -100, "type": "withdrawal", "reference": "v2"})
        assert r.status_code == 200
        assert r.get_json()["data"]["balance"] == 150.0

        w = VendorWallet.query.filter_by(user_phone="888").first()
        assert float(w.balance) == 150.0
        txns = VendorWalletTransaction.query.filter_by(user_phone="888").all()
        assert len(txns) == 2


def test_wallet_service_endpoints_use_helpers(monkeypatch):
    app, entry = _reload_entrypoint(monkeypatch)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        client.post("/__wallet/consumer/adjust", json={"phone": "777", "delta": 50, "type": "recharge", "reference": "s1"})
        r = client.post("/__wallet/consumer/adjust", json={"phone": "777", "delta": -60, "type": "debit", "reference": "s2"})
        assert r.status_code == 400

