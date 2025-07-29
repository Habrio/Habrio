import os
import sys
import importlib
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models import db

@pytest.fixture(scope='session')
def app_instance():
    os.environ.setdefault('APP_ENV','testing')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
    os.environ.setdefault('TWILIO_ACCOUNT_SID', 'dummy')
    os.environ.setdefault('TWILIO_AUTH_TOKEN', 'dummy')
    os.environ.setdefault('TWILIO_WHATSAPP_FROM', 'dummy')
    from app import create_app
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )
    return app

@pytest.fixture(scope='function')
def app(app_instance):
    with app_instance.app_context():
        db.drop_all()
        db.create_all()
        yield app_instance
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    return app.test_client()
