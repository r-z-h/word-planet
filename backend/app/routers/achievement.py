from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_tested
from ..models import Achievement, Badge, KnowledgePoint, PlanetMedal, User
from ..schemas import AchievementItem, AchievementResponse, BadgeDef, MedalItem
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

    earned_codes = {badge.code for _, badge in rows}
    all_badges = db.execute(select(Badge).order_by(Badge.code)).scalars().all()

    def cond_text(badge: Badge) -> str:
        t, v = badge.condition_type, badge.condition_value
        if t == "streak":
            return f"连续学习 ≥{v} 天"
        if t == "answer_correct":
            return f"累计答对 ≥{v} 题"
        if t == "complete_kp":
            return "完成第 1 个知识点"
        if t == "complete_level":
            return "完成当前等级全部知识点"
        if t == "perfect_set":
            return "有一套 15 题全对"
        if t == "level_test_pass":
            return "通过 1 次能力测试"
        if t == "active_days":
            return f"累计学习 ≥{v} 天"
        if t == "daily_correct":
            return f"单日答对 ≥{v} 题"
        if t == "planet_medals":
            return f"单个星球集齐 {v} 枚徽记"
        if t == "perfect_sets":
            return f"累计 {v} 套全对"
        if t == "wrong_cleared":
            return f"错题本待练清零（历史错题 ≥{v}）"
        if t == "refill":
            return f"错题本补花 ≥{v} 次"
        if t == "consecutive_correct":
            return f"连续答对 ≥{v} 题"
        if t == "ultimate":
            return "所有星球都拿到过花 + 字母表已完成"
        return ""

    return AchievementResponse(
        items=[
            AchievementItem(
                badge_id=str(badge.id),
                code=badge.code,
                name=badge.name,
                icon=badge.icon or "",
                condition=cond_text(badge),
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
                medal_icon=kp.medal_icon,
            )
            for pm, kp in medals
        ],
        badges=[
            BadgeDef(
                code=b.code,
                name=b.name,
                icon=b.icon or "",
                earned=b.code in earned_codes,
                condition=cond_text(b),
            )
            for b in all_badges
        ],
    )
