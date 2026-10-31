"""失败锁定（5次/分钟 → 10分钟）与管理员解锁。"""

import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User


def _set_admin(user_id):
    with SessionLocal() as db:
        u = db.get(User, uuid.UUID(user_id))
        u.is_admin = True
        db.commit()


def test_lock_after_five_failures(client):
    acc = 'lock_' + uuid.uuid4().hex[:6]
    client.post('/api/register', json={'account': acc, 'password': 'abc123456', 'nickname': 'x'})
    for _ in range(5):
        r = client.post('/api/login', json={'account': acc, 'password': 'wrongpass'})
        assert r.status_code == 401
    r = client.post('/api/login', json={'account': acc, 'password': 'abc123456'})
    assert r.status_code == 429, r.text
    d = r.json()['detail']
    assert d['code'] == 'LOCKED'
    assert 0 < d['retry_after'] <= 600
    assert '秒' in d['detail'] or '分' in d['detail']


def test_admin_clear_lock(user_client):
    acc = 'lk2_' + uuid.uuid4().hex[:6]
    user_client.post('/api/register', json={'account': acc, 'password': 'abc123456', 'nickname': 'x'})
    for _ in range(5):
        user_client.post('/api/login', json={'account': acc, 'password': 'bad'})
    r = user_client.post('/api/login', json={'account': acc, 'password': 'abc123456'})
    assert r.status_code == 429

    _set_admin(user_client.user_id)
    r2 = user_client.post('/api/admin/clear-lock', json={'account': acc})
    assert r2.status_code == 200, r2.text

    r3 = user_client.post('/api/login', json={'account': acc, 'password': 'abc123456'})
    assert r3.status_code == 200, r3.text


def test_admin_unlock_level(user_client):
    acc = 'ul_' + uuid.uuid4().hex[:6]
    user_client.post('/api/register', json={'account': acc, 'password': 'abc123456', 'nickname': 'x'})
    _set_admin(user_client.user_id)

    r = user_client.post('/api/admin/unlock-level', json={'account': acc})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.account == acc)).scalar_one()
        assert u.max_level == 'L3'
        assert u.has_tested is True
