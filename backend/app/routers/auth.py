import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Progress, User
from ..schemas import (
    CaptchaOut,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    OkResponse,
    RegisterRequest,
    TokenResponse,
)
from ..security import (
    create_access_token,
    hash_password,
    normalize_account,
    verify_password,
)
from ..services.security_extra import make_captcha, rate_limit, verify_captcha

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/captcha", response_model=CaptchaOut)
def captcha():
    return make_captcha()


@router.get("/security-config")
def security_config():
    return {"require_captcha": settings.require_captcha}


def _check_password_bytes(raw: str) -> None:
    if len(raw.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="密码过长（bcrypt 上限 72 字节）")


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "register")
    verify_captcha(payload.captcha_token, payload.captcha_code)
    if not payload.agreed_terms:
        raise HTTPException(
            status_code=422,
            detail={"detail": "请先阅读并同意用户协议与隐私政策", "code": "TERMS_REQUIRED"},
        )
    _check_password_bytes(payload.password)
    account = normalize_account(payload.account)

    exists = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(
            status_code=409, detail={"detail": "账号已存在", "code": "ACCOUNT_EXISTS"}
        )

    user = User(
        account=account,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname.strip(),
        has_tested=False,
    )
    db.add(user)
    db.flush()

    db.add(
        Progress(
            user_id=user.id,
            current_knowledge_point_id=None,
            completed_knowledge_points=[],
        )
    )
    db.commit()
    db.refresh(user)

    return TokenResponse(
        user_id=str(user.id),
        access_token=create_access_token(str(user.id)),
        has_tested=False,
        level=None,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "login")
    verify_captcha(payload.captcha_token, payload.captcha_code)
    account = normalize_account(payload.account)
    user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401, detail={"detail": "账号或密码错误", "code": "BAD_CREDENTIALS"}
        )

    return LoginResponse(
        access_token=create_access_token(str(user.id)),
        has_tested=user.has_tested,
        level=user.level,
    )


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        user_id=str(user.id),
        nickname=user.nickname,
        level=user.level,
        has_tested=user.has_tested,
    )


@router.post("/change-password", response_model=OkResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(
            status_code=401, detail={"detail": "原密码不正确", "code": "WRONG_PASSWORD"}
        )
    _check_password_bytes(payload.new_password)
    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=422, detail={"detail": "新密码不能和原密码相同", "code": "SAME_PASSWORD"}
        )
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return OkResponse()
