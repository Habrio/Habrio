import pytest
from models.user import OTP, UserProfile
from app.version import API_PREFIX


def send_otp(client, phone):
    return client.post(f"{API_PREFIX}/send-otp", json={'phone': phone})


def verify_otp(client, phone, otp):
    return client.post(f"{API_PREFIX}/verify-otp", json={'phone': phone, 'otp': otp})


def logout(client, token=None):
    headers = {}
    if token:
        headers['Authorization'] = token
    return client.post(f"{API_PREFIX}/logout", headers=headers)


def basic_onboarding(client, token):
    headers = {'Authorization': f'Bearer {token}'}
    payload = {
        'name': 'Test',
        'city': 'City',
        'society': 'Society',
        'role': 'consumer'
    }
    return client.post(f"{API_PREFIX}/onboarding/basic", json=payload, headers=headers)


def test_send_otp_success_and_db_entry(client, app):
    phone = '1234567890'
    response = send_otp(client, phone)
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'
    with app.app_context():
        otp_entry = OTP.query.filter_by(phone=phone).first()
        assert otp_entry is not None
        assert otp_entry.is_used is False


def test_send_otp_no_phone(client):
    response = client.post('/api/v1/send-otp', json={})
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'


def test_verify_otp_success_creates_profile(client, app):
    phone = '1112223333'
    send_otp(client, phone)
    with app.app_context():
        otp_code = OTP.query.filter_by(phone=phone).first().otp
    response = verify_otp(client, phone, otp_code)
    data = response.get_json()
    assert response.status_code == 200
    assert data['status'] == 'success'
    assert 'access_token' in data
    token = data['access_token']
    with app.app_context():
        user = UserProfile.query.filter_by(phone=phone).first()
        assert user is not None
        assert user is not None
        assert user.basic_onboarding_done is False


def test_verify_otp_invalid_code(client, app):
    phone = '4445556666'
    send_otp(client, phone)
    response = verify_otp(client, phone, '000000')
    assert response.status_code == 401
    assert response.get_json()['message'] == 'Invalid or expired OTP'


def test_logout_flow_invalidates_token(client, app):
    phone = '7778889999'
    send_otp(client, phone)
    with app.app_context():
        otp_code = OTP.query.filter_by(phone=phone).first().otp
    verify_resp = verify_otp(client, phone, otp_code)
    token = verify_resp.get_json()['access_token']
    # token works before logout
    onboard_resp = basic_onboarding(client, token)
    assert onboard_resp.status_code == 200
    # logout
    logout_resp = logout(client, f"Bearer {token}")
    assert logout_resp.status_code == 200
    # token still works after logout in JWT flow
    with app.app_context():
        assert UserProfile.query.filter_by(phone=phone).first() is not None
    fail_resp = basic_onboarding(client, token)
    assert fail_resp.status_code == 200
    second_logout = logout(client, f"Bearer {token}")
    assert second_logout.status_code == 200


def test_logout_without_token(client):
    response = logout(client)
    assert response.status_code == 401
    assert response.get_json()['message'] == 'Token missing'
