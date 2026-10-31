"""公网安全：验证码 / 限流开关 / 注销账号。"""

import base64
import json

import pytest


def _decode_captcha(token):
    raw = token.split('.')[0]
    return json.loads(base64.urlsafe_b64decode(raw.encode()))


def test_captcha_and_security_config(client):
    r = client.get('/api/captcha')
    assert r.status_code == 200
    d = r.json()
    assert 'question' in d and 'token' in d
    cfg = client.get('/api/security-config')
    assert cfg.status_code == 200 and cfg.json()['require_captcha'] in (True, False)


def test_register_requires_captcha_when_enabled(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'require_captcha', True)
    r = client.post(
        '/api/register',
        json={'account': 'cap_user1', 'password': 'abc123456', 'nickname': 'n'},
    )
    assert r.status_code == 422
    assert r.json()['detail']['code'] == 'CAPTCHA_REQUIRED'

    cap = client.get('/api/captcha').json()
    ans = _decode_captcha(cap['token'])['ans']
    r2 = client.post(
        '/api/register',
        json={
            'account': 'cap_user1',
            'password': 'abc123456',
            'nickname': 'n',
            'captcha_token': cap['token'],
            'captcha_code': str(ans),
        },
    )
    assert r2.status_code == 201, r2.text


def test_register_requires_terms(user_client):
    r = user_client.post(
        '/api/register',
        json={
            'account': 'terms_user_x',
            'password': 'abc123456',
            'nickname': 'n',
            'agreed_terms': False,
        },
    )
    assert r.status_code == 422
    assert r.json()['detail']['code'] == 'TERMS_REQUIRED'


def test_delete_account(user_client):
    r = user_client.post('/api/account/delete', json={'password': 'wrong'})
    assert r.status_code == 401

    r2 = user_client.post('/api/account/delete', json={'password': 'abc123456'})
    assert r2.status_code == 200, r2.text

    r3 = user_client.post(
        '/api/login', json={'account': user_client.account, 'password': 'abc123456'}
    )
    assert r3.status_code == 401
