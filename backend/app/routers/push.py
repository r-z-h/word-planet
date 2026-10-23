from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_tested
from ..models import PushSubscription, User
from ..schemas import OkResponse, PushSubscribeRequest

router = APIRouter(prefix="/api/push", tags=["push"])


@router.get("/public-key")
def public_key() -> dict:
    """前端订阅时需要的 VAPID 公钥（base64url，未压缩点）。"""
    return {"key": settings.vapid_public_key}


@router.post("/subscribe", response_model=OkResponse)
def subscribe(
    payload: PushSubscribeRequest,
    user: User = Depends(require_tested),
    db: Session = Depends(get_db),
):
    subscription = payload.subscription or {}
    endpoint = subscription.get("endpoint") or ""
    if not endpoint:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="subscription.endpoint 缺失")

    record = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).scalar_one_or_none()

    if record is None:
        db.add(
            PushSubscription(user_id=user.id, endpoint=endpoint, subscription=subscription)
        )
    else:
        record.user_id = user.id
        record.subscription = subscription

    db.commit()
    return OkResponse()


@router.delete("/unsubscribe", response_model=OkResponse)
def unsubscribe(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    db.execute(delete(PushSubscription).where(PushSubscription.user_id == user.id))
    db.commit()
    return OkResponse()
