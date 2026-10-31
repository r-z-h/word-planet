"""创建/提升管理员账号。

用法：
    python create_admin.py <账号> <密码> [昵称]

若账号已存在：只把它设为管理员（不改密码，除非同时给了 --reset-password）。
"""

import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Progress, User
from app.security import hash_password, normalize_account


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    account = normalize_account(sys.argv[1])
    password = sys.argv[2]
    nickname = sys.argv[3] if len(sys.argv) > 3 else '管理员'
    reset = '--reset-password' in sys.argv

    if len(password) < 6:
        print('密码至少 6 位')
        sys.exit(1)

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
        if user is None:
            user = User(
                account=account,
                password_hash=hash_password(password),
                nickname=nickname,
                has_tested=True,
                level='L1',
                max_level='L3',
                is_admin=True,
            )
            db.add(user)
            db.flush()
            db.add(Progress(user_id=user.id, current_knowledge_point_id=None, completed_knowledge_points=[]))
            print('已创建管理员:', account)
        else:
            user.is_admin = True
            if reset:
                user.password_hash = hash_password(password)
                print('已提升为管理员并重置密码:', account)
            else:
                print('账号已存在，已设为管理员（密码未改）:', account)
        db.commit()


if __name__ == '__main__':
    main()
