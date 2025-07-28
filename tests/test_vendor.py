import pytest
from models.user import OTP, UserProfile
from models.vendor import VendorProfile, VendorDocument, VendorPayoutBank
from models import db
from app.version import API_PREFIX


def send_otp(client, phone):
    return client.post(f"{API_PREFIX}/send-otp", json={'phone': phone})


def verify_otp(client, phone, otp):
    return client.post(f"{API_PREFIX}/verify-otp", json={'phone': phone, 'otp': otp})


def obtain_token(client, app, phone):
    send_otp(client, phone)
    with app.app_context():
        otp_code = OTP.query.filter_by(phone=phone).first().otp
    resp = verify_otp(client, phone, otp_code)
    return resp.get_json()['auth_token']


def do_basic_onboarding(client, token, role='vendor'):
    payload = {
        'name': 'VendorUser',
        'city': 'Town',
        'society': 'Society',
        'role': role
    }
    return client.post(f"{API_PREFIX}/onboarding/basic", json=payload, headers={'Authorization': token})


def test_vendor_profile_setup_success(client, app):
    phone = '8000000001'
    token = obtain_token(client, app, phone)
    do_basic_onboarding(client, token, role='vendor')

    payload = {
        'business_type': 'retail',
        'business_name': 'My Store',
        'gst_number': 'GST123',
        'address': '123 Market'
    }
    resp = client.post('/api/v1/vendor/profile', json=payload, headers={'Authorization': token})
    assert resp.status_code == 200
    with app.app_context():
        profile = VendorProfile.query.filter_by(user_phone=phone).first()
        user = UserProfile.query.filter_by(phone=phone).first()
        assert profile is not None
        assert profile.business_name == 'My Store'
        assert user.role_onboarding_done is False


def test_vendor_profile_requires_basic_onboarding(client, app):
    phone = '8000000002'
    token = obtain_token(client, app, phone)
    with app.app_context():
        user = UserProfile.query.filter_by(phone=phone).first()
        user.role = 'vendor'
        db.session.commit()

    resp = client.post('/api/v1/vendor/profile', json={'business_type': 'retail', 'business_name': 'Test', 'address': 'Addr'}, headers={'Authorization': token})
    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Basic onboarding incomplete'


def test_vendor_profile_missing_fields_and_duplicate(client, app):
    phone = '8000000003'
    token = obtain_token(client, app, phone)
    do_basic_onboarding(client, token, role='vendor')
    # Missing fields
    resp = client.post('/api/v1/vendor/profile', json={'business_name': 'A'}, headers={'Authorization': token})
    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Missing required vendor details'

    # Successful creation
    payload = {
        'business_type': 'retail',
        'business_name': 'Shop',
        'address': 'Addr'
    }
    assert client.post('/api/v1/vendor/profile', json=payload, headers={'Authorization': token}).status_code == 200
    # Second attempt should fail
    resp_again = client.post('/api/v1/vendor/profile', json=payload, headers={'Authorization': token})
    assert resp_again.status_code == 400
    assert resp_again.get_json()['message'] == 'Vendor profile already exists'


def test_upload_vendor_document(client, app):
    phone = '8000000004'
    token = obtain_token(client, app, phone)
    do_basic_onboarding(client, token, role='vendor')
    client.post('/api/v1/vendor/profile', json={'business_type': 'retail', 'business_name': 'Shop', 'address': 'Addr'}, headers={'Authorization': token})

    resp = client.post('/api/v1/vendor/upload-document', json={'document_type': 'aadhaar', 'file_url': 'http://file'}, headers={'Authorization': token})
    assert resp.status_code == 200
    with app.app_context():
        doc = VendorDocument.query.filter_by(vendor_phone=phone, document_type='aadhaar').first()
        assert doc is not None

    resp_fail = client.post('/api/v1/vendor/upload-document', json={'document_type': 'aadhaar'}, headers={'Authorization': token})
    assert resp_fail.status_code == 400


def test_setup_payout_bank_create_and_update(client, app):
    phone = '8000000005'
    token = obtain_token(client, app, phone)
    do_basic_onboarding(client, token, role='vendor')
    client.post('/api/v1/vendor/profile', json={'business_type': 'retail', 'business_name': 'Shop', 'address': 'Addr'}, headers={'Authorization': token})

    data1 = {'bank_name': 'BankA', 'account_number': '111', 'ifsc_code': 'IFSC1'}
    resp1 = client.post('/api/v1/vendor/payout/setup', json=data1, headers={'Authorization': token})
    assert resp1.status_code == 200
    with app.app_context():
        bank = VendorPayoutBank.query.filter_by(user_phone=phone).first()
        assert bank is not None
        assert bank.bank_name == 'BankA'

    data2 = {'bank_name': 'BankB', 'account_number': '222', 'ifsc_code': 'IFSC2'}
    resp2 = client.post('/api/v1/vendor/payout/setup', json=data2, headers={'Authorization': token})
    assert resp2.status_code == 200
    with app.app_context():
        banks = VendorPayoutBank.query.filter_by(user_phone=phone).all()
        assert len(banks) == 1
        assert banks[0].bank_name == 'BankB'
        assert banks[0].account_number == '222'

    resp_fail = client.post('/api/v1/vendor/payout/setup', json={'bank_name': 'BankX'}, headers={'Authorization': token})
    assert resp_fail.status_code == 400
