import pytest
from models.user import UserProfile, ConsumerProfile
from models import db
from app.version import API_PREFIX


def send_otp(client, phone):
    return client.post(f"{API_PREFIX}/send-otp", json={'phone': phone})


def verify_otp(client, phone, otp):
    return client.post(f"{API_PREFIX}/verify-otp", json={'phone': phone, 'otp': otp})


def do_basic_onboarding(client, token, name='User', city='Town', society='Society', role='consumer'):
    payload = {
        'name': name,
        'city': city,
        'society': society,
        'role': role
    }
    return client.post(f"{API_PREFIX}/onboarding/basic", json=payload, headers={'Authorization': f'Bearer {token}'})


def do_consumer_onboarding(client, token, **extra):
    return client.post(f"{API_PREFIX}/onboarding/consumer", json=extra, headers={'Authorization': f'Bearer {token}'})


def get_profile(client, token):
    return client.get(f"{API_PREFIX}/profile/me", headers={'Authorization': f'Bearer {token}'})


def edit_profile(client, token, data):
    return client.post(f"{API_PREFIX}/profile/edit", json=data, headers={'Authorization': f'Bearer {token}'})



def obtain_token(client, phone):
    resp = client.post("/__auth/login_stub", json={"phone": phone, "role": "consumer"})
    return resp.get_json()["data"]["access"]


def test_basic_onboarding_success(client, app):
    phone = '9900011111'
    token = obtain_token(client, phone)
    resp = do_basic_onboarding(client, token, name='Alice', city='Delhi', society='Blue', role='consumer')
    assert resp.status_code == 200
    with app.app_context():
        user = UserProfile.query.filter_by(phone=phone).first()
        assert user.name == 'Alice'
        assert user.city == 'Delhi'
        assert user.society == 'Blue'
        assert user.role == 'consumer'
        assert user.basic_onboarding_done is True


def test_basic_onboarding_missing_fields(client, app):
    phone = '9900022222'
    token = obtain_token(client, phone)
    resp = client.post('/api/v1/onboarding/basic', json={'name': 'Bob'}, headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Missing fields'


def test_basic_onboarding_already_onboarded(client, app):
    phone = '9900033333'
    token = obtain_token(client, phone)
    assert do_basic_onboarding(client, token).status_code == 200
    resp_again = do_basic_onboarding(client, token)
    assert resp_again.status_code == 400
    assert resp_again.get_json()['message'] == 'User already onboarded'


def test_consumer_onboarding_success(client, app):
    phone = '9900044444'
    token = obtain_token(client, phone)
    do_basic_onboarding(client, token, role='consumer')
    resp = do_consumer_onboarding(client, token, flat_number='A1', preferred_language='en')
    assert resp.status_code == 200
    with app.app_context():
        profile = ConsumerProfile.query.filter_by(user_phone=phone).first()
        user = UserProfile.query.filter_by(phone=phone).first()
        assert profile is not None
        assert profile.flat_number == 'A1'
        assert profile.preferred_language == 'en'
        assert user.role_onboarding_done is True


def test_consumer_onboarding_without_basic(client, app):
    phone = '9900055555'
    token = obtain_token(client, phone)
    # Assign a role so role_required passes but basic onboarding flag remains False
    with app.app_context():
        user = UserProfile.query.filter_by(phone=phone).first()
        user.role = 'consumer'
        db.session.commit()

    resp = do_consumer_onboarding(client, token)
    assert resp.status_code == 400
    assert resp.get_json()['message'] == 'Basic onboarding incomplete'
    with app.app_context():
        assert ConsumerProfile.query.filter_by(user_phone=phone).first() is None


def test_consumer_onboarding_already_done(client, app):
    phone = '9900066666'
    token = obtain_token(client, phone)
    do_basic_onboarding(client, token)
    assert do_consumer_onboarding(client, token).status_code == 200
    resp_again = do_consumer_onboarding(client, token)
    assert resp_again.status_code == 400
    assert resp_again.get_json()['message'] == 'Role onboarding already done'


def test_get_and_edit_consumer_profile(client, app):
    phone = '9900077777'
    token = obtain_token(client, phone)
    do_basic_onboarding(client, token)
    do_consumer_onboarding(client, token, flat_number='101', preferred_language='en')

    get_resp = get_profile(client, token)
    assert get_resp.status_code == 200
    data = get_resp.get_json()['data']
    assert data['phone'] == phone
    assert data['flat_number'] == '101'

    edit_resp = edit_profile(client, token, {'flat_number': '202', 'preferred_language': 'hi'})
    assert edit_resp.status_code == 200
    with app.app_context():
        profile = ConsumerProfile.query.filter_by(user_phone=phone).first()
        assert profile.flat_number == '202'
        assert profile.preferred_language == 'hi'

    get_resp2 = get_profile(client, token)
    assert get_resp2.get_json()['data']['flat_number'] == '202'

