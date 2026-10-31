"""账号注销（PIPL 注销权）：校验密码后删除账号及其全部学习数据。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
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
from ..schemas import DeleteAccountRequest, OkResponse
from ..security import verify_password

router = APIRouter(prefix="/api/account", tags=["account"])


@router.post("/delete", response_model=OkResponse)
def delete_account(
    payload: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401, detail={"detail": "密码不正确", "code": "WRONG_PASSWORD"}
        )

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

    prog = db.get(Progress, user.id)
    if prog is not None:
        db.delete(prog)
    db.flush()
    db.delete(user)
    db.commit()
    return OkResponse()
