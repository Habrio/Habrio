import pytest
from models.wallet import ConsumerWallet, WalletTransaction, VendorWallet, VendorWalletTransaction
from models.vendor import VendorPayoutBank
from models import db
from app.version import API_PREFIX


def obtain_token(client, phone, role="consumer"):
    resp = client.post("/__auth/login_stub", json={"phone": phone, "role": role})
    return resp.get_json()["data"]["access"]


def onboard_consumer(client, token):
    basic = {'name': 'C', 'city': 'Town', 'society': 'Soc', 'role': 'consumer'}
    client.post(f"{API_PREFIX}/onboarding/basic", json=basic, headers={'Authorization': f'Bearer {token}'})
    client.post(f"{API_PREFIX}/onboarding/consumer", json={'flat_number': '1A'}, headers={'Authorization': f'Bearer {token}'})


def onboard_vendor(client, token):
    basic = {'name': 'V', 'city': 'Town', 'society': 'Soc', 'role': 'vendor'}
    client.post(f"{API_PREFIX}/onboarding/basic", json=basic, headers={'Authorization': f'Bearer {token}'})



def setup_payout_bank(client, token):
    data = {'bank_name': 'BankA', 'account_number': '123456', 'ifsc_code': 'IFSC0'}
    return client.post(f"{API_PREFIX}/vendor/payout/setup", json=data, headers={'Authorization': f'Bearer {token}'})


# ---------------------- Consumer Wallet ----------------------

def test_get_or_create_wallet(client, app):
    phone = '7000000001'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)

    resp = client.get('/api/v1/wallet', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 0.0
    with app.app_context():
        wallet = ConsumerWallet.query.filter_by(user_phone=phone).first()
        assert wallet is not None
        assert float(wallet.balance) == 0.0

    resp2 = client.get('/api/v1/wallet', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    assert resp2.get_json()['balance'] == 0.0
    with app.app_context():
        assert ConsumerWallet.query.filter_by(user_phone=phone).count() == 1


def test_load_wallet_success_and_invalid_amount(client, app):
    phone = '7000000002'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)

    resp = client.post('/api/v1/wallet/load', json={'amount': 500}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 500.0
    with app.app_context():
        wallet = ConsumerWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 500.0
        txn = WalletTransaction.query.filter_by(user_phone=phone, type='recharge').first()
        assert txn and float(txn.amount) == 500.0

    resp_bad = client.post('/api/v1/wallet/load', json={'amount': 0}, headers={'Authorization': f'Bearer {token}'})
    assert resp_bad.status_code == 400
    assert resp_bad.get_json()['message'] == 'Invalid amount'
    with app.app_context():
        assert float(ConsumerWallet.query.filter_by(user_phone=phone).first().balance) == 500.0
        assert WalletTransaction.query.filter_by(user_phone=phone, type='recharge').count() == 1


def test_debit_wallet_success_and_insufficient(client, app):
    phone = '7000000003'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)
    client.post('/api/v1/wallet/load', json={'amount': 300}, headers={'Authorization': f'Bearer {token}'})

    resp = client.post('/api/v1/wallet/debit', json={'amount': 100}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 200.0
    with app.app_context():
        wallet = ConsumerWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 200.0
        assert WalletTransaction.query.filter_by(user_phone=phone, type='debit').count() == 1

    resp_bad = client.post('/api/v1/wallet/debit', json={'amount': 400}, headers={'Authorization': f'Bearer {token}'})
    assert resp_bad.status_code == 400
    assert resp_bad.get_json()['message'] == 'Insufficient balance'
    with app.app_context():
        assert float(ConsumerWallet.query.filter_by(user_phone=phone).first().balance) == 200.0
        assert WalletTransaction.query.filter_by(user_phone=phone, type='debit').count() == 1

    # when wallet doesn't exist
    phone2 = '7000000004'
    token2 = obtain_token(client, phone2)
    onboard_consumer(client, token2)
    resp_none = client.post('/api/v1/wallet/debit', json={'amount': 50}, headers={'Authorization': f'Bearer {token2}'})
    assert resp_none.status_code == 400
    assert resp_none.get_json()['message'] == 'Insufficient balance'


def test_refund_wallet_creates_wallet(client, app):
    phone = '7000000005'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)

    resp = client.post('/api/v1/wallet/refund', json={'amount': 120}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 120.0
    with app.app_context():
        wallet = ConsumerWallet.query.filter_by(user_phone=phone).first()
        assert wallet and float(wallet.balance) == 120.0
        txn = WalletTransaction.query.filter_by(user_phone=phone, type='refund').first()
        assert txn and float(txn.amount) == 120.0


def test_wallet_transaction_history(client, app):
    phone = '7000000006'
    token = obtain_token(client, phone)
    onboard_consumer(client, token)

    client.post('/api/v1/wallet/load', json={'amount': 50}, headers={'Authorization': f'Bearer {token}'})
    client.post('/api/v1/wallet/debit', json={'amount': 20}, headers={'Authorization': f'Bearer {token}'})
    client.post('/api/v1/wallet/refund', json={'amount': 10}, headers={'Authorization': f'Bearer {token}'})

    resp = client.get('/api/v1/wallet/history', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()['transactions']
    assert len(data) == 3
    types = {t['type'] for t in data}
    assert types == {'recharge', 'debit', 'refund'}


# ---------------------- Vendor Wallet ----------------------

def test_get_vendor_wallet_and_creation(client, app):
    phone = '7100000001'
    token = obtain_token(client, phone)
    onboard_vendor(client, token)

    resp = client.get('/api/v1/vendor/wallet', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 0.0
    with app.app_context():
        wallet = VendorWallet.query.filter_by(user_phone=phone).first()
        assert wallet and float(wallet.balance) == 0.0

    resp2 = client.get('/api/v1/vendor/wallet', headers={'Authorization': f'Bearer {token}'})
    assert resp2.status_code == 200
    with app.app_context():
        assert VendorWallet.query.filter_by(user_phone=phone).count() == 1


def test_credit_vendor_wallet_and_invalid_amount(client, app):
    phone = '7100000002'
    token = obtain_token(client, phone)
    onboard_vendor(client, token)

    resp = client.post('/api/v1/vendor/wallet/credit', json={'amount': 100}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 100.0
    with app.app_context():
        wallet = VendorWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 100.0
        txn = VendorWalletTransaction.query.filter_by(user_phone=phone, type='credit').first()
        assert txn and float(txn.amount) == 100.0

    bad = client.post('/api/v1/vendor/wallet/credit', json={'amount': 0}, headers={'Authorization': f'Bearer {token}'})
    assert bad.status_code == 400
    assert bad.get_json()['message'] == 'Invalid credit amount'
    with app.app_context():
        assert float(VendorWallet.query.filter_by(user_phone=phone).first().balance) == 100.0
        assert VendorWalletTransaction.query.filter_by(user_phone=phone, type='credit').count() == 1


def test_debit_vendor_wallet_success_and_insufficient(client, app):
    phone = '7100000003'
    token = obtain_token(client, phone)
    onboard_vendor(client, token)
    client.post('/api/v1/vendor/wallet/credit', json={'amount': 100}, headers={'Authorization': f'Bearer {token}'})

    resp = client.post('/api/v1/vendor/wallet/debit', json={'amount': 30}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json()['balance'] == 70.0
    with app.app_context():
        wallet = VendorWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 70.0
        assert VendorWalletTransaction.query.filter_by(user_phone=phone, type='debit').count() == 1

    resp_bad = client.post('/api/v1/vendor/wallet/debit', json={'amount': 200}, headers={'Authorization': f'Bearer {token}'})
    assert resp_bad.status_code == 400
    assert resp_bad.get_json()['message'] == 'Insufficient balance'


def test_withdraw_vendor_wallet(client, app):
    phone = '7100000004'
    token = obtain_token(client, app, phone)
    onboard_vendor(client, token)
    setup_payout_bank(client, token)
    client.post('/api/v1/vendor/wallet/credit', json={'amount': 100}, headers={'Authorization': f'Bearer {token}'})

    resp = client.post('/api/v1/vendor/wallet/withdraw', json={'amount': 60}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['balance'] == 40.0
    assert data['bank_account'] == '123456'
    with app.app_context():
        wallet = VendorWallet.query.filter_by(user_phone=phone).first()
        assert float(wallet.balance) == 40.0
        txn = VendorWalletTransaction.query.filter_by(user_phone=phone, type='withdrawal').first()
        assert txn and float(txn.amount) == 60.0

    resp_bad = client.post('/api/v1/vendor/wallet/withdraw', json={'amount': 100}, headers={'Authorization': f'Bearer {token}'})
    assert resp_bad.status_code == 400
    assert resp_bad.get_json()['message'] == 'Insufficient balance'

    # No bank info scenario
    phone2 = '7100000005'
    token2 = obtain_token(client, phone2)
    onboard_vendor(client, token2)
    client.post('/api/v1/vendor/wallet/credit', json={'amount': 20}, headers={'Authorization': f'Bearer {token2}'})
    fail_no_bank = client.post('/api/v1/vendor/wallet/withdraw', json={'amount': 10}, headers={'Authorization': f'Bearer {token2}'})
    assert fail_no_bank.status_code == 400
    assert fail_no_bank.get_json()['message'] == 'No payout bank setup found'


def test_vendor_wallet_history(client, app):
    phone = '7100000006'
    token = obtain_token(client, phone)
    onboard_vendor(client, token)

    client.post('/api/v1/vendor/wallet/credit', json={'amount': 40}, headers={'Authorization': f'Bearer {token}'})
    client.post('/api/v1/vendor/wallet/debit', json={'amount': 10}, headers={'Authorization': f'Bearer {token}'})

    resp = client.get('/api/v1/vendor/wallet/history', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    data = resp.get_json()['transactions']
    assert len(data) == 2
    types = {t['type'] for t in data}
    assert types == {'credit', 'debit'}
