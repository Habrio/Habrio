import pytest
from app.utils import create_access_token
from models import db, UserProfile
from app.version import API_PREFIX

@pytest.fixture
def tokens(app):
    with app.app_context():
        users = {
            'consumer': UserProfile(phone='c_role', role='consumer'),
            'vendor': UserProfile(phone='v_role', role='vendor'),
            'admin': UserProfile(phone='a_role', role='admin'),
        }
        db.session.add_all(users.values())
        db.session.commit()
        return {
            role: create_access_token(user.phone, role)
            for role, user in users.items()
        }

def test_blueprint_access(client, tokens):
    c_hdr = {'Authorization': f'Bearer {tokens["consumer"]}'}
    v_hdr = {'Authorization': f'Bearer {tokens["vendor"]}'}
    a_hdr = {'Authorization': f'Bearer {tokens["admin"]}'}

    # consumer routes
    assert client.get(f"{API_PREFIX}/consumer/cart/view", headers=c_hdr).status_code == 200
    assert client.get(f"{API_PREFIX}/consumer/cart/view", headers=v_hdr).status_code == 403

    # vendor routes
    assert client.get(f"{API_PREFIX}/vendor/wallet", headers=v_hdr).status_code == 200
    assert client.get(f"{API_PREFIX}/vendor/wallet", headers=c_hdr).status_code == 403

    # admin routes
    assert client.get(f"{API_PREFIX}/admin/users", headers=a_hdr).status_code == 200
    assert client.get(f"{API_PREFIX}/admin/users", headers=v_hdr).status_code == 403
