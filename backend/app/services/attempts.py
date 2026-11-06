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
    LevelTest,
    PlanetMedal,
    Progress,
    Question,
    QuestionFlower,
    SetProgress,
    Streak,
    User,
    WrongQuestion,
)

MASTERY_STREAK = 3  # 错题本连续答对 3 次视为掌握，并补发该题 1 朵花


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
    # 「初学有成」= 完成 L1 第一个"攒徽记"的知识点（字母表只判完成、不算这个徽章的达成）
    l1_first = db.execute(
        select(KnowledgePoint)
        .where(
            KnowledgePoint.level == "L1",
            KnowledgePoint.counts_for_gate.is_(True),
            KnowledgePoint.gate_mode == "medals",
        )
        .order_by(KnowledgePoint.sort_order)
        .limit(1)
    ).scalar_one_or_none()

    earned: set[str] = {
        str(b.badge_id) for b in db.execute(
            select(Achievement).where(Achievement.user_id == user.id)
        ).scalars()
    }

    def all_level_completed() -> bool:
        from .lesson import kp_completed

        kps = db.execute(
            select(KnowledgePoint).where(KnowledgePoint.level == user.level)
        ).scalars().all()
        if not kps:
            return False
        for kp in kps:
            if kp.gate_mode == "completion":
                if not kp_completed(db, user.id, kp):
                    return False
            elif str(kp.id) not in completed:
                return False
        return True

    def perfect_set_done() -> bool:
        return (
            db.execute(
                select(SetProgress.id)
                .where(SetProgress.user_id == user.id, SetProgress.is_complete.is_(True))
                .limit(1)
            ).first()
            is not None
        )

    def level_test_passed() -> bool:
        return (
            db.execute(
                select(LevelTest.id)
                .where(LevelTest.user_id == user.id, LevelTest.passed.is_(True))
                .limit(1)
            ).first()
            is not None
        )

    def active_days_count() -> int:
        return db.execute(
            select(func.count(func.distinct(local_date_of(Attempt.created_at)))).where(
                Attempt.user_id == user.id
            )
        ).scalar_one()

    def today_correct_count() -> int:
        return db.execute(
            select(func.count())
            .select_from(Attempt)
            .where(
                Attempt.user_id == user.id,
                Attempt.is_correct.is_(True),
                local_date_of(Attempt.created_at) == local_today(db),
            )
        ).scalar_one()

    def max_planet_medals() -> int:
        return (
            db.execute(
                select(func.max(PlanetMedal.medals)).where(PlanetMedal.user_id == user.id)
            ).scalar_one()
            or 0
        )

    def perfect_sets_count() -> int:
        return db.execute(
            select(func.count())
            .select_from(SetProgress)
            .where(SetProgress.user_id == user.id, SetProgress.is_complete.is_(True))
        ).scalar_one()

    def wrong_cleared_ok(threshold: int) -> bool:
        pending = db.execute(
            select(func.count()).select_from(WrongQuestion).where(WrongQuestion.user_id == user.id)
        ).scalar_one()
        wrong_hist = db.execute(
            select(func.count())
            .select_from(Attempt)
            .where(Attempt.user_id == user.id, Attempt.is_correct.is_(False))
        ).scalar_one()
        return pending == 0 and wrong_hist >= threshold

    def refill_count() -> int:
        return db.execute(
            select(func.count())
            .select_from(QuestionFlower)
            .where(QuestionFlower.user_id == user.id, QuestionFlower.source == "practice")
        ).scalar_one()

    def max_consecutive_correct() -> int:
        rows = db.execute(
            select(Attempt.is_correct)
            .where(Attempt.user_id == user.id)
            .order_by(Attempt.created_at)
        ).scalars().all()
        best = cur = 0
        for ok in rows:
            if ok:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        return best

    def ultimate_done() -> bool:
        from .lesson import kp_completed

        total = db.execute(
            select(func.count())
            .select_from(Question)
            .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
            .where(KnowledgePoint.produces_flowers.is_(True))
        ).scalar_one()
        if not total:
            return False
        got = db.execute(
            select(func.count(func.distinct(QuestionFlower.question_id)))
            .select_from(QuestionFlower)
            .join(Question, Question.id == QuestionFlower.question_id)
            .join(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
            .where(
                QuestionFlower.user_id == user.id,
                KnowledgePoint.produces_flowers.is_(True),
            )
        ).scalar_one()
        if got < total:
            return False
        letter = db.execute(
            select(KnowledgePoint)
            .where(KnowledgePoint.level == "L1", KnowledgePoint.gate_mode == "completion")
            .limit(1)
        ).scalar_one_or_none()
        return (letter is None) or kp_completed(db, user.id, letter)

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
        elif badge.condition_type == "complete_level":
            ok = all_level_completed()
        elif badge.condition_type == "perfect_set":
            ok = perfect_set_done()
        elif badge.condition_type == "level_test_pass":
            ok = level_test_passed()
        elif badge.condition_type == "active_days":
            ok = active_days_count() >= badge.condition_value
        elif badge.condition_type == "daily_correct":
            ok = today_correct_count() >= badge.condition_value
        elif badge.condition_type == "planet_medals":
            ok = max_planet_medals() >= badge.condition_value
        elif badge.condition_type == "perfect_sets":
            ok = perfect_sets_count() >= badge.condition_value
        elif badge.condition_type == "wrong_cleared":
            ok = wrong_cleared_ok(badge.condition_value)
        elif badge.condition_type == "refill":
            ok = refill_count() >= badge.condition_value
        elif badge.condition_type == "consecutive_correct":
            ok = max_consecutive_correct() >= badge.condition_value
        elif badge.condition_type == "ultimate":
            ok = ultimate_done()
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
