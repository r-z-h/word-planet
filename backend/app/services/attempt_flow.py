import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Attempt, KnowledgePoint, Question, User, WrongQuestion
from .attempts import (
    advance_if_complete,
    award_badges,
    get_or_create_daily_task,
    get_progress,
    had_correct_attempt_today,
    local_today,
    touch_streak,
)


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
    """一次作答的全部副作用：记录、错题本、每日任务、知识点推进、连续学习、徽章。"""
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
    get_or_create_daily_task(db, user.id, local_today(db))

    progress = get_progress(db, user.id)
    current = (
        db.get(KnowledgePoint, progress.current_knowledge_point_id)
        if progress.current_knowledge_point_id
        else None
    )

    advanced = False
    if current is not None and question.knowledge_point_id == current.id:
        advanced, current = advance_if_complete(db, user, current)

    touch_streak(db, user.id, had_correct_today, is_correct)
    new_badges = award_badges(db, user)

    return {
        "progress_advanced": advanced,
        "current_knowledge_point": current,
        "new_badges": new_badges,
    }
