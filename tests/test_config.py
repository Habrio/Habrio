"""Tests for configuration loading via main.py entrypoint."""
import importlib
import os
import sys


def load_app(monkeypatch, env):
    # set required env vars for services
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'dummy')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'dummy')
    monkeypatch.setenv('TWILIO_WHATSAPP_FROM', 'dummy')
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    # Reload modules with updated environment
    for module in ['main', 'app.config']:
        if module in sys.modules:
            del sys.modules[module]
    main = importlib.import_module('main')
    return main.app


def test_testing_config_uses_memory_db(monkeypatch):
    app = load_app(monkeypatch, {'APP_ENV': 'testing'})
    assert app.config['TESTING'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite://')


def test_development_defaults(monkeypatch):
    app = load_app(monkeypatch, {
        'APP_ENV': 'development',
        'DATABASE_URL': None,
    })
    assert app.config['DEBUG'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///dev.db'
