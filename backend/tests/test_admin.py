"""管理员权限：非管理员 403、管理员可列用户/重置密码/授权。"""

import uuid

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User


def _set_admin(user_id, flag=True):
    with SessionLocal() as db:
        u = db.get(User, uuid.UUID(user_id))
        u.is_admin = flag
        db.commit()


def test_non_admin_forbidden(user_client):
    r = user_client.get('/api/admin/users')
    assert r.status_code == 403
    assert r.json()['detail']['code'] == 'NOT_ADMIN'


def test_admin_list_and_reset_and_grant(user_client):
    _set_admin(user_client.user_id, True)

    r = user_client.get('/api/admin/users')
    assert r.status_code == 200, r.text
    accounts = [i['account'] for i in r.json()['items']]
    assert user_client.account in accounts

    # 新建一个普通账号，用管理员重置它的密码
    client2 = user_client
    acc = 'adm_target_' + uuid.uuid4().hex[:6]
    resp = client2.post(
        '/api/register',
        json={'account': acc, 'password': 'abc123456', 'nickname': '目标'},
    )
    assert resp.status_code == 201, resp.text

    r2 = client2.post(
        '/api/admin/reset-password', json={'account': acc, 'new_password': 'newpass999'}
    )
    assert r2.status_code == 200, r2.text

    r3 = client2.post('/api/login', json={'account': acc, 'password': 'newpass999'})
    assert r3.status_code == 200, r3.text

    r4 = client2.post('/api/admin/set-admin', json={'account': acc, 'is_admin': True})
    assert r4.status_code == 200, r4.text
    with SessionLocal() as db:
        u = db.execute(select(User).where(User.account == acc)).scalar_one()
        assert u.is_admin is True


def test_admin_delete_account(user_client):
    _set_admin(user_client.user_id, True)
    acc = 'del_' + uuid.uuid4().hex[:6]
    r = user_client.post(
        '/api/register', json={'account': acc, 'password': 'abc123456', 'nickname': '待删'}
    )
    assert r.status_code == 201

    r_self = user_client.post('/api/admin/delete-account', json={'account': user_client.account})
    assert r_self.status_code == 422

    r2 = user_client.post('/api/admin/delete-account', json={'account': acc})
    assert r2.status_code == 200, r2.text
    r3 = user_client.post('/api/login', json={'account': acc, 'password': 'abc123456'})
    assert r3.status_code == 401
