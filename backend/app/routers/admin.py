"""管理员接口：用户列表 / 重置密码 / 授予或取消管理员。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import (
    Achievement,
    Attempt,
    DailyTask,
    FlowerExchange,
    LevelTest,
    PlanetMedal,
    Progress,
    PushSubscription,
    QuestionFlower,
    SetProgress,
    Streak,
    User,
    WrongQuestion,
)
from ..schemas import (
    AdminAccountActionRequest,
    AdminResetPasswordRequest,
    AdminSetAdminRequest,
    AdminUserItem,
    AdminUsersResponse,
    OkResponse,
)
from ..security import hash_password, normalize_account
from ..services.security_extra import clear_lock_for_account, lock_remaining_for_account

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=AdminUsersResponse)
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(User).order_by(User.created_at.desc()).limit(500)).scalars()
    return AdminUsersResponse(
        items=[
            AdminUserItem(
                id=str(u.id),
                account=u.account,
                nickname=u.nickname,
                level=u.level,
                max_level=u.max_level,
                has_tested=u.has_tested,
                is_admin=u.is_admin,
                created_at=u.created_at,
                locked_remaining=lock_remaining_for_account(u.account),
            )
            for u in rows
        ]
    )


@router.post("/reset-password", response_model=OkResponse)
def admin_reset_password(
    payload: AdminResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = normalize_account(payload.account)
    user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"detail": "账号不存在", "code": "USER_NOT_FOUND"})
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return OkResponse()


@router.post("/set-admin", response_model=OkResponse)
def admin_set_admin(
    payload: AdminSetAdminRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = normalize_account(payload.account)
    user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"detail": "账号不存在", "code": "USER_NOT_FOUND"})
    if not payload.is_admin and user.id == admin.id:
        raise HTTPException(status_code=422, detail={"detail": "不能取消自己的管理员权限", "code": "CANNOT_DEMOTE_SELF"})
    user.is_admin = payload.is_admin
    db.commit()
    return OkResponse()


@router.post("/unlock-level", response_model=OkResponse)
def admin_unlock_level(
    payload: AdminAccountActionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """解锁该账号的全部等级（max_level=L3，并标记为已测）。"""
    account = normalize_account(payload.account)
    user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"detail": "账号不存在", "code": "USER_NOT_FOUND"})
    user.max_level = 'L3'
    user.has_tested = True
    db.commit()
    return OkResponse()


@router.post("/clear-lock", response_model=OkResponse)
def admin_clear_lock(
    payload: AdminAccountActionRequest,
    admin: User = Depends(require_admin),
):
    """解除该账号的登录/注册失败锁定（清空频率计数）。"""
    clear_lock_for_account(normalize_account(payload.account))
    return OkResponse()


@router.post("/delete-account", response_model=OkResponse)
def admin_delete_account(
    payload: AdminAccountActionRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除指定账号及其全部数据（不能删除自己）。"""
    account = normalize_account(payload.account)
    user = db.execute(select(User).where(User.account == account)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"detail": "账号不存在", "code": "USER_NOT_FOUND"})
    if user.id == admin.id:
        raise HTTPException(status_code=422, detail={"detail": "不能删除自己的账号", "code": "CANNOT_DELETE_SELF"})

    for model in (
        Attempt,
        WrongQuestion,
        Achievement,
        SetProgress,
        QuestionFlower,
        PlanetMedal,
        FlowerExchange,
        LevelTest,
        DailyTask,
        PushSubscription,
        Streak,
    ):
        db.execute(delete(model).where(model.user_id == user.id))
    db.execute(delete(Progress).where(Progress.user_id == user.id))
    db.flush()
    db.delete(user)
    db.commit()
    clear_lock_for_account(account)
    return OkResponse()
