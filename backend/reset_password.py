"""管理员运维脚本：重置密码 / 设为管理员。

用法：
    python reset_password.py <账号> <新密码>
    python reset_password.py --list            # 列出账号
"""

import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password, normalize_account


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--list':
        with SessionLocal() as db:
            rows = db.execute(select(User.account, User.nickname, User.level)).all()
        for a, n, lv in rows:
            print(f'{a}\t{n}\t{lv}')
        return

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    account = normalize_account(sys.argv[1])
    new_password = sys.argv[2]
    if len(new_password) < 6:
        print('密码至少 6 位')
        sys.exit(1)

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
        if user is None:
            print('账号不存在:', account)
            sys.exit(1)
        user.password_hash = hash_password(new_password)
        db.commit()
        print('已重置密码:', account)


if __name__ == '__main__':
    main()
