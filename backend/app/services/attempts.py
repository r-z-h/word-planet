import uuid
from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    Achievement,
    Attempt,
    Badge,
    DailyTask,
    KnowledgePoint,
    Progress,
    Question,
    Streak,
    User,
    WrongQuestion,
)

MASTERY_STREAK = 2


def local_today(db: Session) -> date:
    """当前时区下的“今天”，不依赖 DB session 时区。"""
    stmt = select(cast(func.timezone(settings.app_timezone, func.now()), Date))
    return db.execute(stmt).scalar_one()


def local_date_of(column):
    return cast(func.timezone(settings.app_timezone, column), Date)


def get_or_create_daily_task(db: Session, user_id: uuid.UUID, day: date) -> DailyTask:
    task = db.execute(
        select(DailyTask).where(DailyTask.user_id == user_id, DailyTask.task_date == day)
    ).scalar_one_or_none()
    if task is None:
        task = DailyTask(user_id=user_id, task_date=day, is_completed=False)
        db.add(task)
        db.flush()
    return task


def get_progress(db: Session, user_id: uuid.UUID) -> Progress:
    progress = db.get(Progress, user_id)
    if progress is None:
        raise RuntimeError(f"progress row missing for user {user_id}")
    return progress


def question_ids_of_kp(db: Session, kp_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.execute(select(Question.id).where(Question.knowledge_point_id == kp_id)).scalars()
    )


def is_kp_complete(db: Session, user_id: uuid.UUID, kp_id: uuid.UUID) -> bool:
    """知识点完成 = 该知识点下每道题都做过一遍（对错不论）。

    答错的题只进错题本，不再回到主流程；掌握度由错题本单独练。
    """
    qids = question_ids_of_kp(db, kp_id)
    if not qids:
        return False

    attempted = db.execute(
        select(func.count(func.distinct(Attempt.question_id))).where(
            Attempt.user_id == user_id,
            Attempt.question_id.in_(qids),
            Attempt.question_type != "practice",  # 错题本练习不算进学习进度
        )
    ).scalar_one()
    return attempted >= len(qids)


def next_kp_of_level(db: Session, kp: KnowledgePoint) -> KnowledgePoint | None:
    return db.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.level == kp.level, KnowledgePoint.sort_order > kp.sort_order)
        .order_by(KnowledgePoint.sort_order)
        .limit(1)
    ).scalar_one_or_none()


def first_kp_of_level(db: Session, level: str) -> KnowledgePoint | None:
    return db.execute(
        select(KnowledgePoint)
        .where(KnowledgePoint.level == level)
        .order_by(KnowledgePoint.sort_order)
        .limit(1)
    ).scalar_one_or_none()


def advance_if_complete(db: Session, user: User, kp: KnowledgePoint) -> tuple[bool, KnowledgePoint]:
    """完成则戴入 completed、推进到下一个知识点，并把当天任务置为已完成。"""
    progress = get_progress(db, user.id)
    if not is_kp_complete(db, user.id, kp.id):
        return False, kp

    completed = list(progress.completed_knowledge_points or [])
    kp_str = str(kp.id)
    if kp_str not in completed:
        completed.append(kp_str)
        progress.completed_knowledge_points = completed

    nxt = next_kp_of_level(db, kp)
    if nxt is not None:
        progress.current_knowledge_point_id = nxt.id

    day = local_today(db)
    task = get_or_create_daily_task(db, user.id, day)
    task.is_completed = True

    db.flush()
    return True, (nxt or kp)


def touch_streak(db: Session, user_id: uuid.UUID, had_correct_today: bool, is_correct: bool) -> None:
    """当天首次答对时更新连续学习。"""
    if not is_correct or had_correct_today:
        return

    today = local_today(db)
    streak = db.get(Streak, user_id)
    if streak is None:
        streak = Streak(user_id=user_id, current_streak=0, longest_streak=0)
        db.add(streak)

    last = streak.last_study_date
    if last == today:
        pass
    elif last == today - timedelta(days=1):
        streak.current_streak += 1
    elif last is None:
        streak.current_streak = 1
    else:
        streak.current_streak = 1

    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    streak.last_study_date = today
    db.flush()


def award_badges(db: Session, user: User) -> list[str]:
    badges = db.execute(select(Badge)).scalars().all()
    if not badges:
        return []

    streak = db.get(Streak, user.id)
    correct_total = db.execute(
        select(func.count()).select_from(Attempt).where(
            Attempt.user_id == user.id, Attempt.is_correct.is_(True)
        )
    ).scalar_one()

    progress = db.get(Progress, user.id)
    completed = set(progress.completed_knowledge_points or []) if progress else set()
    l1_first = first_kp_of_level(db, "L1")

    earned: set[str] = {
        str(b.badge_id) for b in db.execute(
            select(Achievement).where(Achievement.user_id == user.id)
        ).scalars()
    }

    new_codes: list[str] = []
    for badge in badges:
        if str(badge.id) in earned:
            continue
        ok = False
        if badge.condition_type == "streak":
            ok = (streak.current_streak if streak else 0) >= badge.condition_value
        elif badge.condition_type == "answer_correct":
            ok = correct_total >= badge.condition_value
        elif badge.condition_type == "complete_kp":
            ok = bool(l1_first) and str(l1_first.id) in completed
        if ok:
            db.add(Achievement(user_id=user.id, badge_id=badge.id))
            new_codes.append(badge.code)

    if new_codes:
        db.flush()
    return new_codes


def had_correct_attempt_today(db: Session, user_id: uuid.UUID) -> bool:
    today = local_today(db)
    stmt = (
        select(func.count())
        .select_from(Attempt)
        .where(
            Attempt.user_id == user_id,
            Attempt.is_correct.is_(True),
            local_date_of(Attempt.created_at) == today,
        )
    )
    return db.execute(stmt).scalar_one() > 0
