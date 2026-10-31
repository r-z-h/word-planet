from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Achievement, Badge, KnowledgePoint, PlanetMedal, User
from ..schemas import AchievementItem, AchievementResponse, MedalItem
from ..services.lesson import kp_set_numbers

router = APIRouter(prefix="/api", tags=["achievements"])


@router.get("/achievements", response_model=AchievementResponse)
def list_achievements(user: User = Depends(require_tested), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Achievement, Badge)
        .join(Badge, Badge.id == Achievement.badge_id)
        .where(Achievement.user_id == user.id)
        .order_by(Achievement.earned_at)
    ).all()

    medals = db.execute(
        select(PlanetMedal, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == PlanetMedal.knowledge_point_id)
        .where(PlanetMedal.user_id == user.id)
        .order_by(KnowledgePoint.level, KnowledgePoint.sort_order)
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
        ],
        medals=[
            MedalItem(
                knowledge_point_id=str(kp.id),
                name=kp.name,
                level=kp.level,
                medals=pm.medals,
                max_medals=len(kp_set_numbers(db, kp.id)),
            )
            for pm, kp in medals
        ],
    )
