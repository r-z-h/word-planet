from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Achievement, Badge, User
from ..schemas import AchievementItem, AchievementResponse

router = APIRouter(prefix="/api", tags=["achievements"])


@router.get("/achievements", response_model=AchievementResponse)
def list_achievements(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Achievement, Badge)
        .join(Badge, Badge.id == Achievement.badge_id)
        .where(Achievement.user_id == user.id)
        .order_by(Achievement.earned_at)
    ).all()

    return AchievementResponse(
        items=[
            AchievementItem(
                badge_id=str(badge.id),
                code=badge.code,
                name=badge.name,
                earned_at=achievement.earned_at,
            )
            for achievement, badge in rows
        ]
    )
