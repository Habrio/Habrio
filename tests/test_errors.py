import importlib
import sys
import pytest


def load_app(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'testing')
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'dummy')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'dummy')
    monkeypatch.setenv('TWILIO_WHATSAPP_FROM', 'dummy')
    for module in ['main', 'app.config']:
        if module in sys.modules:
            del sys.modules[module]
    main = importlib.import_module('main')
    return main.app


@pytest.fixture()
def test_client(monkeypatch):
    app = load_app(monkeypatch)
    app.config.update(TESTING=True)
    return app.test_client()


def test_404_json_envelope(test_client):
    resp = test_client.get('/no/such/route')
    assert resp.status_code == 404
    data = resp.get_json()
    assert data['status'] == 'error'
    assert data['code'] == 404
    assert isinstance(data.get('message'), str)


def test_unexpected_500_json_envelope(test_client):
    resp = test_client.get('/__boom')
    assert resp.status_code == 500
    data = resp.get_json()
    assert data['status'] == 'error'
    assert data['code'] == 500
    assert 'RuntimeError' not in data['message']


def test_ok_helper_endpoint(test_client):
    resp = test_client.get('/__ok')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {
        'status': 'success',
        'message': 'success',
        'data': {'ping': 'pong'}
    }
