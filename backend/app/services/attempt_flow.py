import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Attempt, KnowledgePoint, Progress, Question, User, WrongQuestion
from .attempts import (
    award_badges,
    get_or_create_daily_task,
    get_progress,
    had_correct_attempt_today,
    local_today,
    touch_streak,
)
from .lesson import SETS_REQUIRED, is_set_complete, mark_set_complete
from . import rewards


def update_wrong_book(
    db: Session, user_id: uuid.UUID, question_id: uuid.UUID, is_correct: bool
) -> None:
    record = db.query(WrongQuestion).filter(
        WrongQuestion.user_id == user_id, WrongQuestion.question_id == question_id
    ).one_or_none()

    if not is_correct:
        if record is None:
            db.add(
                WrongQuestion(
                    user_id=user_id,
                    question_id=question_id,
                    error_count=1,
                    consecutive_correct=0,
                )
            )
        else:
            record.error_count += 1
            record.consecutive_correct = 0
            record.last_wrong_at = datetime.now(timezone.utc)
    elif record is not None:
        record.consecutive_correct += 1

    db.flush()


def apply_attempt(
    db: Session,
    user: User,
    question: Question,
    *,
    is_correct: bool,
    question_type: str = "question",
    idempotency_key: str | None = None,
) -> dict:
    """一次作答的副作用：记录、错题本、套完成、每日任务、连续学习、徽章。"""
    had_correct_today = had_correct_attempt_today(db, user.id) if is_correct else False

    db.add(
        Attempt(
            user_id=user.id,
            question_id=question.id,
            question_type=question_type,
            idempotency_key=idempotency_key,
            is_correct=is_correct,
        )
    )
    db.flush()

    update_wrong_book(db, user.id, question.id, is_correct)

    # 三层奖励：答对一题记一朵花（错题本补花走 practice）。幂等，重复作答不重复记。
    if is_correct:
        rewards.award_flower(
            db,
            user.id,
            question,
            source="practice" if question_type == "practice" else "main",
        )

    day = local_today(db)
    task = get_or_create_daily_task(db, user.id, day)

    kp = db.get(KnowledgePoint, question.knowledge_point_id)
    progress_row = get_progress(db, user.id)
    set_completed = False
    if kp is not None and is_set_complete(db, user.id, kp.id, question.set_no):
        mark_set_complete(db, user, kp, question.set_no)
        set_completed = True
        task.is_completed = True
        # 套完成行刚建立，回填花数/完成标记
        rewards.recompute_set_progress(db, user.id, kp.id, question.set_no)

        # 该知识点累计完成满 3 套 -> 记入「已完成知识点」（用于徽章与报告）
        from .lesson import completed_set_numbers

        done = completed_set_numbers(db, user.id, kp.id)
        if len(done) >= SETS_REQUIRED:
            completed = list(progress_row.completed_knowledge_points or [])
            if str(kp.id) not in completed:
                completed.append(str(kp.id))
                progress_row.completed_knowledge_points = completed

    touch_streak(db, user.id, had_correct_today, is_correct)
    new_badges = award_badges(db, user)

    current = (
        db.get(KnowledgePoint, progress_row.current_knowledge_point_id)
        if progress_row.current_knowledge_point_id
        else None
    )

    return {
        "progress_advanced": set_completed,
        "current_knowledge_point": current,
        "new_badges": new_badges,
    }
