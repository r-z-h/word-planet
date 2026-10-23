import uuid
from datetime import date, timedelta

from fastapi import Depends, HTTPException
from jose import ExpiredSignatureError, JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail={"detail": "未登录", "code": "NOT_LOGGED_IN"})
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail={"detail": "登录已过期", "code": "TOKEN_EXPIRED"}
        )
    except JWTError:
        raise HTTPException(status_code=401, detail={"detail": "未登录", "code": "NOT_LOGGED_IN"})

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail={"detail": "未登录", "code": "NOT_LOGGED_IN"})

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail={"detail": "未登录", "code": "NOT_LOGGED_IN"})

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"detail": "未登录", "code": "NOT_LOGGED_IN"})
    return user


def require_tested(user: User = Depends(get_current_user)) -> User:
    if not user.has_tested:
        raise HTTPException(
            status_code=409, detail={"detail": "尚未完成水平测试", "code": "NOT_TESTED"}
        )
    return user
