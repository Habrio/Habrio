import pytest
from app.utils import create_access_token
from models import db, UserProfile
from app.version import API_PREFIX

@pytest.fixture
def tokens(app):
    with app.app_context():
        users = {
            'consumer': UserProfile(phone='contract_c', role='consumer'),
            'vendor': UserProfile(phone='contract_v', role='vendor'),
            'admin': UserProfile(phone='contract_a', role='admin'),
        }
        db.session.add_all(users.values())
        db.session.commit()
        return {role: create_access_token(user.phone, role) for role, user in users.items()}

def _hdr(token):
    return {'Authorization': f'Bearer {token}'}

def test_role_contracts(client, tokens):
    c = _hdr(tokens['consumer'])
    v = _hdr(tokens['vendor'])
    a = _hdr(tokens['admin'])

    # consumer allowed
    assert client.get(f"{API_PREFIX}/consumer/wallet", headers=c).status_code == 200
    # consumer forbidden on vendor and admin routes
    assert client.get(f"{API_PREFIX}/vendor/wallet", headers=c).status_code == 403
    assert client.get(f"{API_PREFIX}/admin/users", headers=c).status_code == 403

    # vendor allowed
    assert client.get(f"{API_PREFIX}/vendor/wallet", headers=v).status_code == 200
    # vendor forbidden on consumer and admin routes
    assert client.get(f"{API_PREFIX}/consumer/wallet", headers=v).status_code == 403
    assert client.get(f"{API_PREFIX}/admin/users", headers=v).status_code == 403

    # admin allowed
    assert client.get(f"{API_PREFIX}/admin/users", headers=a).status_code == 200
    # admin forbidden on consumer and vendor routes
    assert client.get(f"{API_PREFIX}/consumer/wallet", headers=a).status_code == 403
    assert client.get(f"{API_PREFIX}/vendor/wallet", headers=a).status_code == 403
